"""ADBC sink implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from adbc_driver_manager import dbapi
from singer_sdk.sinks import BatchSink

from target_adbc.batch import BatchProcessor

if TYPE_CHECKING:
    from collections.abc import Sequence

    from singer_sdk import Target
    from singer_sdk.helpers.types import Record


class ADBCSink(BatchSink):
    """ADBC sink class."""

    max_size = 10000

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
        self._processor: BatchProcessor | None = None

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

    def process_batch(self, context: dict[str, Any]) -> None:
        """Process a batch of records.

        Args:
            context: Stream partition or context dictionary.
        """
        records: list[Record] = context["records"]
        try:
            self.processor.ingest(records)
        except Exception:
            # The Singer SDK does not call clean_up() when process_batch raises,
            # so we close the connection here to avoid leaking resources.
            self.clean_up()
            raise

    def clean_up(self) -> None:
        """Clean up resources."""
        self._processor = None  # drop the extra Connection reference held by the processor
        if self._connection is not None:
            self.logger.info("Closing ADBC connection")
            self._connection.close()
            self._connection = None
