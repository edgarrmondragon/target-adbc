"""Batch processing for ADBC sinks."""

from __future__ import annotations

import datetime
import json
import logging
import uuid
from typing import TYPE_CHECKING, Any, Literal

import pyarrow as pa

if TYPE_CHECKING:
    from collections.abc import Sequence

    from adbc_driver_manager import dbapi
    from singer_sdk.helpers.types import Record

_BACKTICK_VENDORS = frozenset({"mysql", "mariadb", "bigquery"})


class BatchProcessor:
    """Handles batch ingestion of Singer records into an ADBC-compatible table.

    This class is intentionally decoupled from the Singer SDK so it can be
    instantiated directly in tests (e.g. against a testcontainers database)
    without going through the full target pipeline.
    """

    def __init__(  # ruff:ignore[too-many-arguments]
        self,
        connection: dbapi.Connection,
        table_name: str,
        schema_name: str | None,
        json_schema: dict[str, Any],
        *,
        key_properties: Sequence[str] | None = None,
        overwrite_behavior: Literal["append", "replace", "upsert"] = "append",
        add_record_metadata: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self.connection = connection
        self.table_name = table_name
        self.schema_name = schema_name
        self.json_schema = json_schema
        self.key_properties = list(key_properties or [])
        self.overwrite_behavior = overwrite_behavior
        if overwrite_behavior == "upsert" and not self.key_properties:
            raise ValueError("overwrite_behavior 'upsert' requires key_properties")
        self.add_record_metadata = add_record_metadata
        self.logger = logger or logging.getLogger(__name__)
        self._initialized = False

    @property
    def full_table_name(self) -> str:
        """Fully-qualified table name including schema prefix when present."""
        if self.schema_name:
            return f"{self.schema_name}.{self.table_name}"
        return self.table_name

    # ------------------------------------------------------------------
    # Type conversion helpers
    # ------------------------------------------------------------------

    def _json_type_to_arrow(self, python_type: dict[str, Any]) -> pa.DataType:
        """Convert a JSON Schema type definition to a PyArrow data type."""
        type_mapping: dict[str, pa.DataType] = {
            "string": pa.string(),
            "integer": pa.int64(),
            "number": pa.float64(),
            "boolean": pa.bool_(),
        }

        json_type: str | list[str] | None = python_type.get("type")
        json_format = python_type.get("format")

        if isinstance(json_type, list):
            non_null_types = [t for t in json_type if t != "null"]
            json_type_str = non_null_types[0] if non_null_types else "string"
        elif json_type is not None:
            json_type_str = str(json_type)
        else:
            json_type_str = "string"

        if json_format == "date-time":
            return pa.timestamp("us", tz="UTC")
        if json_format == "date":
            return pa.date32()
        if json_format == "time":
            return pa.time64("us")

        if json_type_str == "object":
            return pa.string()

        if json_type_str == "array":
            items_type = python_type.get("items", {})
            return pa.list_(self._json_type_to_arrow(items_type))

        return type_mapping.get(json_type_str, pa.string())

    def _create_arrow_schema(self) -> pa.Schema:
        """Build a PyArrow schema from the Singer JSON Schema."""
        fields = []
        for key, prop in self.json_schema.get("properties", {}).items():
            fields.append(pa.field(key, self._json_type_to_arrow(prop)))
        return pa.schema(fields)

    def _prepare_record(self, record: Record) -> Record:
        """Add Singer metadata columns to a record when configured."""
        prepared = record.copy()
        if self.add_record_metadata:
            now = datetime.datetime.now(datetime.UTC)
            prepared["_sdc_extracted_at"] = record.get("_sdc_extracted_at", now)
            prepared["_sdc_received_at"] = record.get("_sdc_received_at", now)
            prepared["_sdc_batched_at"] = now
            prepared["_sdc_sequence"] = record.get("_sdc_sequence", 0)
            prepared["_sdc_table_version"] = record.get("_sdc_table_version", 0)
        return prepared

    def _convert_value(self, value: Any, arrow_type: pa.DataType) -> Any:  # ruff:ignore[any-type, no-self-use, too-many-return-statements]
        """Coerce a Python value to the appropriate type for PyArrow."""
        if value is None:
            return None

        if pa.types.is_timestamp(arrow_type):
            if isinstance(value, str):
                value = datetime.datetime.fromisoformat(value)
            if isinstance(value, datetime.datetime) and value.tzinfo is None:
                return value.replace(tzinfo=datetime.UTC)
            return value

        if pa.types.is_date(arrow_type):
            if isinstance(value, str):
                return datetime.datetime.fromisoformat(value).date()
            if isinstance(value, datetime.datetime):
                return value.date()
            return value

        if pa.types.is_string(arrow_type) and isinstance(value, (dict, list)):
            return json.dumps(value)

        return value

    def _records_to_arrow_table(self, records: list[Record]) -> pa.Table:
        """Convert a list of Singer records to a PyArrow table."""
        if not records:
            raise ValueError("Cannot create table from empty records list")

        prepared_records = [self._prepare_record(r) for r in records]
        schema = self._create_arrow_schema()

        normalized_records = []
        for record in prepared_records:
            normalized = {
                field.name: self._convert_value(record.get(field.name), field.type)
                for field in schema
            }
            normalized_records.append(normalized)

        try:
            return pa.Table.from_pylist(normalized_records, schema=schema)
        except Exception:
            self.logger.error("Error creating Arrow table")
            raise

    # ------------------------------------------------------------------
    # Upsert helpers
    # ------------------------------------------------------------------

    def _quote(self, identifier: str) -> str:
        """Quote an identifier using the connected vendor's quote character."""
        vendor = str(self.connection.adbc_get_info().get("vendor_name", "")).lower()
        if vendor in _BACKTICK_VENDORS:
            return "`" + identifier.replace("`", "``") + "`"
        return '"' + identifier.replace('"', '""') + '"'

    def _qualify(self, table_name: str) -> str:
        parts = [self.schema_name, table_name] if self.schema_name else [table_name]
        return ".".join(self._quote(p) for p in parts)

    def _dedupe_by_key(self, records: list[Record]) -> list[Record]:
        """Keep only the last record for each primary key value."""
        latest: dict[tuple[Any, ...], Record] = {}
        for record in records:
            key = tuple(record.get(k) for k in self.key_properties)
            if None in key:
                raise ValueError(f"Record is missing a value for key properties: {record}")
            latest[key] = record
        return list(latest.values())

    def _upsert(self, arrow_table: pa.Table) -> int:
        """Merge *arrow_table* into the target table via a staging table.

        Uses only standard SQL (DELETE ... WHERE EXISTS + INSERT ... SELECT) in a
        single transaction so it works with any ADBC driver.
        """
        staging_name = f"_stg_{self.table_name}_{uuid.uuid4().hex[:8]}"
        staging = self._qualify(staging_name)

        try:
            row_count = self._merge(arrow_table, staging_name)
        except Exception:
            self.connection.rollback()
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {staging}")
            self.connection.commit()
            raise
        return row_count

    def _merge(self, arrow_table: pa.Table, staging_name: str) -> int:
        target = self._qualify(self.table_name)
        staging = self._qualify(staging_name)
        columns = ", ".join(self._quote(f) for f in arrow_table.schema.names)
        match = " AND ".join(
            f"s.{self._quote(k)} = {target}.{self._quote(k)}" for k in self.key_properties
        )
        with self.connection.cursor() as cursor:
            # Creates the target on first use; appends zero rows otherwise.
            cursor.adbc_ingest(
                self.table_name,
                arrow_table.slice(0, 0),
                mode="create_append",
                db_schema_name=self.schema_name,
            )
            row_count = cursor.adbc_ingest(
                staging_name,
                arrow_table,
                mode="replace",
                db_schema_name=self.schema_name,
            )
            delete_sql = (
                f"DELETE FROM {target} WHERE EXISTS (SELECT 1 FROM {staging} s WHERE {match})"  # ruff:ignore[hardcoded-sql-expression]
            )
            insert_sql = f"INSERT INTO {target} ({columns}) SELECT {columns} FROM {staging}"  # ruff:ignore[hardcoded-sql-expression]
            cursor.execute(delete_sql)
            cursor.execute(insert_sql)
            cursor.execute(f"DROP TABLE {staging}")
        self.connection.commit()
        return row_count

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def ingest(self, records: list[Record]) -> None:
        """Ingest a batch of records into the target table.

        On the first call the ADBC ingest mode is chosen based on
        *overwrite_behavior*; subsequent calls always use ``append``.
        """
        if not records:
            self.logger.info("No records to process in this batch")
            return

        self.logger.info("Processing batch of %d records", len(records))
        if self.overwrite_behavior == "upsert":
            records = self._dedupe_by_key(records)
        arrow_table = self._records_to_arrow_table(records)

        if self.overwrite_behavior == "upsert":
            self.logger.info("Upserting into %s on %s", self.full_table_name, self.key_properties)
            row_count = self._upsert(arrow_table)
            self._initialized = True
            self.logger.info(
                "Successfully upserted %d records into %s", row_count, self.full_table_name
            )
            return

        mode: Literal["replace", "create_append"] = (
            "replace"
            if self.overwrite_behavior == "replace" and not self._initialized
            else "create_append"
        )
        self.logger.info("Ingesting into %s (mode=%s)", self.full_table_name, mode)

        try:
            with self.connection.cursor() as cursor:
                row_count = cursor.adbc_ingest(
                    self.table_name,
                    arrow_table,
                    mode=mode,
                    db_schema_name=self.schema_name,
                )
            self.connection.commit()
            self._initialized = True
            self.logger.info(
                "Successfully ingested %d records into %s",
                row_count,
                self.full_table_name,
            )
        except Exception:
            self.logger.error("Error inserting records")
            raise
