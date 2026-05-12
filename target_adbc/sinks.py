"""ADBC sink implementation."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any, Literal

import pyarrow as pa
from adbc_driver_manager import dbapi
from singer_sdk.sinks import BatchSink

if TYPE_CHECKING:
    from collections.abc import Sequence

    from singer_sdk import Target
    from singer_sdk.helpers.types import Record


class ADBCSink(BatchSink):
    """ADBC sink class."""

    max_size = 10000

    MODE_APPEND = "append"
    MODE_CREATE = "create"
    MODE_REPLACE = "replace"
    MODE_CREATE_APPEND = "create_append"

    def __init__(
        self,
        target: Target,
        stream_name: str,
        schema: dict[str, Any],
        key_properties: Sequence[str] | None,
    ) -> None:
        """Initialize the ADBC sink."""
        super().__init__(target, stream_name, schema, key_properties)
        self._connection: dbapi.Connection | None = None
        self._table_exists: dict[str, bool] = {}

    @property
    def connection(self) -> dbapi.Connection:
        """Get or create ADBC connection."""
        if self._connection is None:
            driver = self.config["driver"]
            self.logger.info("Connecting to database using driver: %s", driver)

            db_kwargs = self.config.get(driver, {})
            self._connection = dbapi.connect(driver=driver, db_kwargs=db_kwargs)

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

    def _json_type_to_arrow(self, python_type: dict[str, Any]) -> pa.DataType:
        """Convert JSON Schema type to PyArrow data type."""
        type_mapping: dict[str, pa.DataType] = {
            "string": pa.string(),
            "integer": pa.int64(),
            "number": pa.float64(),
            "boolean": pa.bool_(),
        }

        json_type: str | list[str] | None = python_type.get("type")
        json_format = python_type.get("format")

        # Handle array of types (nullable fields)
        if isinstance(json_type, list):
            # Filter out 'null' and get the actual type
            non_null_types = [t for t in json_type if t != "null"]
            json_type_str = non_null_types[0] if non_null_types else "string"
        elif json_type is not None:
            json_type_str = str(json_type)
        else:
            json_type_str = "string"

        # Handle datetime formats
        if json_format == "date-time":
            return pa.timestamp("us", tz="UTC")
        if json_format == "date":
            return pa.date32()
        if json_format == "time":
            return pa.time64("us")

        # Handle object type (JSON)
        if json_type_str == "object":
            return pa.string()  # Store as JSON string

        # Handle array type
        if json_type_str == "array":
            items_type = python_type.get("items", {})
            item_arrow_type = self._json_type_to_arrow(items_type)
            return pa.list_(item_arrow_type)

        return type_mapping.get(json_type_str, pa.string())

    def _create_arrow_schema(self, schema: dict[str, Any]) -> pa.Schema:
        """Create PyArrow schema from records and Singer schema."""
        fields = []

        for key in schema.get("properties", {}):
            prop = schema["properties"][key]
            arrow_type = self._json_type_to_arrow(prop)
            fields.append(pa.field(key, arrow_type))

        return pa.schema(fields)

    def _prepare_record(self, record: Record) -> Record:
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

    def _convert_value(self, value: Any, arrow_type: pa.DataType) -> Any:  # noqa: ANN401
        """Convert Python value to appropriate type for PyArrow."""
        if value is None:
            return None

        # Handle datetime conversions
        if pa.types.is_timestamp(arrow_type):
            if isinstance(value, str):
                value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
            if isinstance(value, datetime.datetime):
                # Ensure timezone aware
                if value.tzinfo is None:
                    return value.replace(tzinfo=datetime.timezone.utc)
                return value
            return value

        if pa.types.is_date(arrow_type):
            if isinstance(value, str):
                return datetime.datetime.fromisoformat(value).date()
            if isinstance(value, datetime.datetime):
                return value.date()
            return value

        # Handle JSON objects/arrays as strings
        if pa.types.is_string(arrow_type) and isinstance(value, (dict, list)):
            import json

            return json.dumps(value)

        return value

    def _records_to_arrow_table(self, records: list[Record]) -> pa.Table:
        """Convert records to PyArrow table."""
        if not records:
            raise ValueError("Cannot create table from empty records list")

        # Prepare records with metadata
        prepared_records = [self._prepare_record(r) for r in records]

        # Create schema
        schema = self._create_arrow_schema(self.schema)

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
        except Exception:
            self.logger.error("Error creating Arrow table")
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
                cursor.execute(f"SELECT 1 FROM {full_table_name} LIMIT 0")  # noqa: S608
                return True
        except Exception:
            return False

    def _drop_table(self, full_table_name: str) -> None:
        """Drop a table if it exists."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {full_table_name}")
            self.connection.commit()
            self.logger.info("Dropped table %s", full_table_name)
        except Exception:
            self.logger.warning("Error dropping table %s", full_table_name)

    def process_batch(self, context: dict[str, Any]) -> None:
        """Process a batch of records.

        Args:
            context: Stream partition or context dictionary.
        """
        records = context["records"]

        if not records:
            self.logger.info("No records to process in this batch")
            return

        self.logger.info("Processing batch of %s records", len(records))

        # Convert records to Arrow table
        arrow_table = self._records_to_arrow_table(records)

        # Get table name
        table_name = self._get_table_name()
        schema_name = self._get_schema_name()
        full_table_name = f"{schema_name}.{table_name}" if schema_name else table_name

        # Determine ingest mode and handle overwrite behavior
        cache_key = self._get_cache_key()
        is_first_batch = cache_key not in self._table_exists
        overwrite_behavior = self.config.get("overwrite_behavior", "append")

        # Check if table exists in database
        table_exists_in_db = self._check_table_exists(full_table_name)

        # Handle overwrite behavior on first batch
        if is_first_batch and table_exists_in_db:
            if overwrite_behavior == "replace":
                self.logger.info("Dropping existing table %s (replace mode)", full_table_name)
                self._drop_table(full_table_name)
                table_exists_in_db = False
            elif overwrite_behavior == "fail":
                raise RuntimeError(
                    "Table %s already exists and overwrite_behavior is 'fail'",
                    full_table_name,
                )
            # For 'append' mode, we'll just append to the existing table

        mode: Literal["append", "create"]

        # Determine ingest mode
        if table_exists_in_db:
            mode = "append"
            self.logger.info("Appending to existing table %s", full_table_name)
        else:
            mode = "create"
            self.logger.info("Creating table %s", full_table_name)

        # Insert data using ADBC
        try:
            with self.connection.cursor() as cursor:
                # Use adbc_ingest for efficient bulk insert
                cursor.adbc_ingest(
                    table_name,
                    arrow_table,
                    mode=mode,
                    db_schema_name=schema_name,
                )

            # Commit the transaction
            self.connection.commit()

            # Mark table as existing
            self._table_exists[cache_key] = True

            self.logger.info(
                "Successfully inserted %s records into %s",
                len(records),
                full_table_name,
            )

        except Exception:
            self.logger.error("Error inserting records")
            raise

    def clean_up(self) -> None:
        """Clean up resources."""
        if self._connection is not None:
            self.logger.info("Closing ADBC connection")
            self._connection.close()
            self._connection = None
