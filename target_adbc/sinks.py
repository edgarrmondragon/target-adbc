"""ADBC sink implementation."""

from __future__ import annotations

import datetime
from typing import Any

import adbc_driver_manager as adbc
import pyarrow as pa
from singer_sdk.sinks import BatchSink


class ADBCSink(BatchSink):
    """ADBC sink class."""

    max_size = 10000

    def __init__(self, *args, **kwargs):
        """Initialize the ADBC sink."""
        super().__init__(*args, **kwargs)
        self._connection: adbc.AdbcConnection | None = None
        self._table_exists: dict[str, bool] = {}

    @property
    def connection(self) -> adbc.AdbcConnection:
        """Get or create ADBC connection."""
        if self._connection is None:
            driver = self.config["driver"]
            uri = self.config.get("uri")
            connection_kwargs = self.config.get("connection_kwargs", {})

            self.logger.info(f"Connecting to database using driver: {driver}")

            # Use dbapi interface for specific drivers
            if driver == "adbc_driver_duckdb":
                import adbc_driver_duckdb.dbapi as dbapi

                # DuckDB can accept a path or use in-memory
                if uri:
                    # Extract path from URI
                    # "duckdb:///path/to/db" -> "/path/to/db" (absolute, 3 slashes)
                    # "duckdb://path/to/db" -> "path/to/db" (relative, 2 slashes)
                    # "duckdb://:memory:" -> ":memory:"
                    if uri.startswith("duckdb:///"):
                        path = uri[len("duckdb://"):]  # Keep the leading / from ///
                    elif uri.startswith("duckdb://"):
                        path = uri[len("duckdb://"):]
                    else:
                        path = uri
                    self._connection = dbapi.connect(path, **connection_kwargs)
                else:
                    # No URI means in-memory database
                    self._connection = dbapi.connect(":memory:", **connection_kwargs)

            elif driver == "adbc_driver_sqlite":
                import adbc_driver_sqlite.dbapi as dbapi

                if uri:
                    path = uri.replace("sqlite://", "")
                    self._connection = dbapi.connect(path, **connection_kwargs)
                else:
                    self._connection = dbapi.connect(**connection_kwargs)

            elif driver == "adbc_driver_postgresql":
                import adbc_driver_postgresql.dbapi as dbapi

                # PostgreSQL uses connection_kwargs for connection params
                params = connection_kwargs.copy()
                if uri:
                    params["uri"] = uri

                self._connection = dbapi.connect(**params)

            else:
                # Generic fallback - try to import the driver's dbapi module
                try:
                    import importlib
                    dbapi_module = importlib.import_module(f"{driver}.dbapi")
                    params = connection_kwargs.copy()
                    if uri:
                        params["uri"] = uri
                    self._connection = dbapi_module.connect(**params)
                except (ImportError, AttributeError) as e:
                    raise ValueError(
                        f"Unsupported or unavailable ADBC driver: {driver}. "
                        f"Make sure the driver package is installed. Error: {e}"
                    ) from e

        return self._connection

    def _get_table_name(self) -> str:
        """Get the target table name with prefix/suffix applied."""
        prefix = self.config.get("table_prefix", "")
        suffix = self.config.get("table_suffix", "")
        return f"{prefix}{self.stream_name}{suffix}"

    def _get_schema_name(self) -> str | None:
        """Get the target schema name."""
        # Check if stream name includes schema (e.g., "schema.table")
        if "." in self.stream_name:
            return self.stream_name.split(".")[0]
        return self.config.get("default_target_schema")

    def _python_type_to_arrow(self, python_type: dict[str, Any]) -> pa.DataType:
        """Convert JSON Schema type to PyArrow data type."""
        type_mapping = {
            "string": pa.string(),
            "integer": pa.int64(),
            "number": pa.float64(),
            "boolean": pa.bool_(),
        }

        json_type = python_type.get("type")
        json_format = python_type.get("format")

        # Handle array of types (nullable fields)
        if isinstance(json_type, list):
            # Filter out 'null' and get the actual type
            non_null_types = [t for t in json_type if t != "null"]
            if non_null_types:
                json_type = non_null_types[0]

        # Handle datetime formats
        if json_format == "date-time":
            return pa.timestamp("us", tz="UTC")
        if json_format == "date":
            return pa.date32()
        if json_format == "time":
            return pa.time64("us")

        # Handle object type (JSON)
        if json_type == "object":
            return pa.string()  # Store as JSON string

        # Handle array type
        if json_type == "array":
            items_type = python_type.get("items", {})
            item_arrow_type = self._python_type_to_arrow(items_type)
            return pa.list_(item_arrow_type)

        return type_mapping.get(json_type, pa.string())

    def _create_arrow_schema(self, records: list[dict]) -> pa.Schema:
        """Create PyArrow schema from records and Singer schema."""
        fields = []

        # Get Singer schema if available
        singer_schema = self.schema

        for key in singer_schema.get("properties", {}):
            prop = singer_schema["properties"][key]
            arrow_type = self._python_type_to_arrow(prop)
            fields.append(pa.field(key, arrow_type))

        # Add metadata columns if configured
        if self.config.get("add_record_metadata", True):
            fields.extend([
                pa.field("_sdc_extracted_at", pa.timestamp("us", tz="UTC")),
                pa.field("_sdc_received_at", pa.timestamp("us", tz="UTC")),
                pa.field("_sdc_batched_at", pa.timestamp("us", tz="UTC")),
                pa.field("_sdc_sequence", pa.int64()),
                pa.field("_sdc_table_version", pa.int64()),
            ])

        return pa.schema(fields)

    def _prepare_record(self, record: dict) -> dict:
        """Prepare a record for insertion, adding metadata if configured."""
        prepared = record.copy()

        if self.config.get("add_record_metadata", True):
            now = datetime.datetime.now(datetime.timezone.utc)
            prepared["_sdc_extracted_at"] = record.get("_sdc_extracted_at", now)
            prepared["_sdc_received_at"] = record.get("_sdc_received_at", now)
            prepared["_sdc_batched_at"] = now
            prepared["_sdc_sequence"] = record.get("_sdc_sequence", 0)
            prepared["_sdc_table_version"] = record.get("_sdc_table_version", 0)

        return prepared

    def _convert_value(self, value: Any, arrow_type: pa.DataType) -> Any:
        """Convert Python value to appropriate type for PyArrow."""
        if value is None:
            return None

        # Handle datetime conversions
        if pa.types.is_timestamp(arrow_type):
            if isinstance(value, str):
                # Parse ISO 8601 datetime strings
                dt = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
                # Ensure timezone aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=datetime.timezone.utc)
                return dt
            elif isinstance(value, datetime.datetime):
                # Ensure timezone aware
                if value.tzinfo is None:
                    return value.replace(tzinfo=datetime.timezone.utc)
                return value
            return value

        if pa.types.is_date(arrow_type):
            if isinstance(value, str):
                return datetime.datetime.fromisoformat(value).date()
            elif isinstance(value, datetime.datetime):
                return value.date()
            return value

        # Handle JSON objects/arrays as strings
        if pa.types.is_string(arrow_type) and isinstance(value, (dict, list)):
            import json
            return json.dumps(value)

        return value

    def _records_to_arrow_table(self, records: list[dict]) -> pa.Table:
        """Convert records to PyArrow table."""
        if not records:
            raise ValueError("Cannot create table from empty records list")

        # Prepare records with metadata
        prepared_records = [self._prepare_record(r) for r in records]

        # Create schema
        schema = self._create_arrow_schema(records)

        # Convert each record's values according to the schema
        normalized_records = []
        for record in prepared_records:
            normalized = {}
            for field in schema:
                value = record.get(field.name)
                normalized[field.name] = self._convert_value(value, field.type)
            normalized_records.append(normalized)

        # Use PyArrow's from_pylist for simpler conversion
        try:
            return pa.Table.from_pylist(normalized_records, schema=schema)
        except Exception as e:
            self.logger.error(f"Error creating Arrow table: {e}")
            self.logger.error(f"Schema: {schema}")
            self.logger.error(f"Sample record: {normalized_records[0] if normalized_records else 'none'}")
            raise

    def _get_cache_key(self) -> str:
        """Get the cache key for this table."""
        table_name = self._get_table_name()
        schema_name = self._get_schema_name()
        return f"{schema_name}.{table_name}" if schema_name else table_name

    def _check_table_exists(self, full_table_name: str) -> bool:
        """Check if a table exists in the database."""
        try:
            with self.connection.cursor() as cursor:
                # Try to query the table - if it fails, it doesn't exist
                cursor.execute(f"SELECT 1 FROM {full_table_name} LIMIT 0")
                return True
        except Exception:
            return False

    def _drop_table(self, full_table_name: str) -> None:
        """Drop a table if it exists."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
            self.connection.commit()
            self.logger.info(f"Dropped table {full_table_name}")
        except Exception as e:
            self.logger.warning(f"Error dropping table {full_table_name}: {e}")

    def process_batch(self, context: dict) -> None:
        """Process a batch of records.

        Args:
            context: Stream partition or context dictionary.
        """
        records = context["records"]

        if not records:
            self.logger.info("No records to process in this batch")
            return

        self.logger.info(f"Processing batch of {len(records)} records")

        # Convert records to Arrow table
        arrow_table = self._records_to_arrow_table(records)

        # Get table name
        table_name = self._get_table_name()
        schema_name = self._get_schema_name()

        if schema_name:
            full_table_name = f"{schema_name}.{table_name}"
        else:
            full_table_name = table_name

        # Determine ingest mode and handle overwrite behavior
        cache_key = self._get_cache_key()
        is_first_batch = cache_key not in self._table_exists
        overwrite_behavior = self.config.get("overwrite_behavior", "append")

        # Check if table exists in database
        table_exists_in_db = self._check_table_exists(full_table_name)

        # Handle overwrite behavior on first batch
        if is_first_batch and table_exists_in_db:
            if overwrite_behavior == "replace":
                self.logger.info(f"Dropping existing table {full_table_name} (replace mode)")
                self._drop_table(full_table_name)
                table_exists_in_db = False
            elif overwrite_behavior == "fail":
                raise RuntimeError(
                    f"Table {full_table_name} already exists and overwrite_behavior is 'fail'"
                )
            # For 'append' mode, we'll just append to the existing table

        # Determine ingest mode
        if table_exists_in_db:
            mode = "append"
            self.logger.info(f"Appending to existing table {full_table_name}")
        else:
            mode = "create"
            self.logger.info(f"Creating table {full_table_name}")

        # Insert data using ADBC
        try:
            with self.connection.cursor() as cursor:
                # Use adbc_ingest for efficient bulk insert
                cursor.adbc_ingest(
                    full_table_name,
                    arrow_table,
                    mode=mode,
                )

            # Commit the transaction
            self.connection.commit()

            # Mark table as existing
            self._table_exists[cache_key] = True

            self.logger.info(
                f"Successfully inserted {len(records)} records into {full_table_name}"
            )

        except Exception as e:
            self.logger.error(f"Error inserting records: {e}")
            self.logger.error(f"Table: {full_table_name}, Mode: {mode}")
            self.logger.error(f"Arrow schema: {arrow_table.schema}")
            raise

    def clean_up(self) -> None:
        """Clean up resources."""
        if self._connection is not None:
            self.logger.info("Closing ADBC connection")
            self._connection.close()
            self._connection = None
