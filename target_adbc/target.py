"""ADBC target implementation."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, override

from singer_sdk import typing as th
from singer_sdk.target_base import Target

from target_adbc import connect
from target_adbc.sinks import ADBCSink

if TYPE_CHECKING:
    from collections.abc import Sequence

    from adbc_driver_manager import dbapi


class TargetADBC(Target):
    """Singer target for ADBC-compatible databases."""

    name = "target-adbc"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "uri",
            th.StringType,
            required=True,
            secret=True,
            description="ADBC URI. Examples: 'duckdb://...', 'postgresql://...'",
            examples=[
                "duckdb://",
                "postgresql://",
            ],
        ),
        th.Property(
            "duckdb",
            th.ObjectType(),
            description="DuckDB configuration.",
        ),
        th.Property(
            "sqlite",
            th.ObjectType(),
            description="SQLite configuration.",
        ),
        th.Property(
            "postgresql",
            th.ObjectType(),
            description="PostgreSQL configuration.",
        ),
        th.Property(
            "mssql",
            th.ObjectType(),
            description="Microsoft SQL Server configuration",
        ),
        th.Property(
            "default_target_schema",
            th.StringType,
            description=(
                "Default schema to use for tables if not specified in stream name. "
                "Some drivers require this (e.g., PostgreSQL)."
            ),
        ),
        th.Property(
            "table_prefix",
            th.StringType,
            default="",
            description="Prefix to add to all table names.",
        ),
        th.Property(
            "table_suffix",
            th.StringType,
            default="",
            description="Suffix to add to all table names.",
        ),
        th.Property(
            "overwrite_behavior",
            th.StringType,
            default="append",
            allowed_values=["append", "replace"],
            description=(
                "Behavior when the target table already exists:\n"
                "- 'append': Add new data to the existing table (default)\n"
                "- 'replace': Drop and recreate the table before loading"
            ),
        ),
        th.Property(
            "batch_size_rows",
            th.IntegerType,
            default=25_000,
            description="Maximum number of rows to process in a single batch.",
        ),
        th.Property(
            "add_record_metadata",
            th.BooleanType,
            default=True,
            description=(
                "Add metadata columns (_sdc_extracted_at, _sdc_received_at, "
                "_sdc_batched_at, _sdc_sequence, _sdc_table_version) to output tables."
            ),
        ),
        th.Property(
            "varchar_length",
            th.IntegerType,
            default=255,
            description="Default length for VARCHAR columns when not specified.",
        ),
    ).to_dict()

    default_sink_class = ADBCSink

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        parse_env_config: bool = False,
        validate_config: bool = True,
    ) -> None:
        """Initialize the target.

        Args:
            config: Target configuration dictionary.
            parse_env_config: Whether to parse environment variables for config.
            validate_config: Whether to validate the configuration.
        """
        super().__init__(
            config=config,
            parse_env_config=parse_env_config,
            validate_config=validate_config,
        )

        self._connection: dbapi.Connection | None = None
        self._uri: str = self.config["uri"]

        if self._uri.startswith(("duckdb://", "sqlite://")):
            self.logger.info("Setting max_parallelism to 1 to avoid database locks.")
            self._max_parallelism = 1

    @override
    def create_sink(
        self,
        *,
        stream_name: str,
        schema: dict[str, Any],
        key_properties: Sequence[str] | None = None,
    ) -> ADBCSink:
        return ADBCSink(
            target=self,
            stream_name=stream_name,
            schema=schema,
            key_properties=key_properties,
            connection=self.connection,
        )

    @property
    def connection(self) -> dbapi.Connection:
        """Get or create the shared ADBC connection."""
        self.logger.info("Connecting to database using URI: %s", self._uri)
        if self._connection is None:
            self._connection = connect.get_connection(self.config)
        return self._connection

    def _close_connection(self) -> None:
        if self._connection is not None:
            self.logger.info("Closing ADBC connection")
            self._connection.close()
            self._connection = None

    @override
    def process_endofpipe(self) -> None:
        """Close the shared ADBC connection after all sinks finish."""
        super().process_endofpipe()
        self._close_connection()

    def __del__(self) -> None:
        self._close_connection()


if __name__ == "__main__":
    TargetADBC.cli()
