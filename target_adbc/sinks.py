"""ADBC sink implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from singer_sdk.sinks import BatchSink

from target_adbc.batch import BatchProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from adbc_driver_manager import dbapi
    from singer_sdk import Target
    from singer_sdk.helpers.types import Record


class ADBCSink(BatchSink):
    """ADBC sink class."""

    def __init__(
        self,
        target: Target,
        stream_name: str,
        schema: dict[str, Any],
        key_properties: Sequence[str] | None,
        *,
        connection: dbapi.Connection,
    ) -> None:
        """Initialize the ADBC sink."""
        super().__init__(target, stream_name, schema, key_properties)
        self.connection = connection
        self._processor: BatchProcessor | None = None

    def _get_table_name(self) -> str:
        """Get the target table name with prefix/suffix applied."""
        prefix = self.config.get("table_prefix", "")
        suffix = self.config.get("table_suffix", "")
        return f"{prefix}{self.stream_name}{suffix}"

    def _get_schema_name(self) -> str | None:
        """Get the target schema name."""
        if "." in self.stream_name:
            return self.stream_name.split(".")[0]
        return self.config.get("default_target_schema")

    @property
    def processor(self) -> BatchProcessor:
        """Return the BatchProcessor for this stream, creating it on first access."""
        if self._processor is None:
            self._processor = BatchProcessor(
                connection=self.connection,
                table_name=self._get_table_name(),
                schema_name=self._get_schema_name(),
                json_schema=self.schema,
                overwrite_behavior=self.config.get("overwrite_behavior", "append"),
                add_record_metadata=self.config.get("add_record_metadata", True),
                logger=self.logger,
            )
        return self._processor

    @override
    def process_batch(self, context: dict[str, Any]) -> None:
        """Process a batch of records.

        Args:
            context: Stream partition or context dictionary.
        """
        records: list[Record] = context["records"]
        try:
            self.processor.ingest(records)
        except Exception:
            self.clean_up()
            raise

    @override
    def clean_up(self) -> None:
        """Clean up resources."""
        self._processor = None
