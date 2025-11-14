"""ADBC target implementation."""

from __future__ import annotations

from singer_sdk import typing as th
from singer_sdk.target_base import Target

from target_adbc.sinks import ADBCSink


class TargetADBC(Target):
    """Singer target for ADBC-compatible databases."""

    name = "target-adbc"

    # Disable parallel processing to avoid database lock contention
    # This is especially important for single-writer databases like DuckDB and SQLite
    max_parallelism = 1

    config_jsonschema = th.PropertiesList(
        th.Property(
            "driver",
            th.StringType,
            required=True,
            description="ADBC driver name. Examples: 'duckdb', 'sqlite', 'postgresql'",
        ),
        th.Property(
            "duckdb",
            th.ObjectType(
                th.Property(
                    "path",
                    th.StringType,
                    required=True,
                    description="Path to the DuckDB database file.",
                ),
            ),
            description="DuckDB configuration.",
        ),
        th.Property(
            "sqlite",
            th.ObjectType(
                th.Property(
                    "uri",
                    th.StringType,
                    required=True,
                    description="URI to the SQLite database file.",
                ),
            ),
            description="SQLite configuration.",
        ),
        th.Property(
            "postgresql",
            th.ObjectType(
                th.Property(
                    "uri",
                    th.StringType,
                    required=True,
                    description="URI to the PostgreSQL database.",
                ),
            ),
            description="PostgreSQL configuration.",
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
            allowed_values=["append", "replace", "fail"],
            description=(
                "Behavior when table already exists:\n"
                "- 'append': Add new data to existing table\n"
                "- 'replace': Drop and recreate table\n"
                "- 'fail': Raise an error if table exists"
            ),
        ),
        th.Property(
            "batch_size",
            th.IntegerType,
            default=10000,
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
        config: dict | None = None,
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

        # Set max batch size from config
        if self.config.get("batch_size"):
            self.default_sink_class.max_size = self.config["batch_size"]


if __name__ == "__main__":
    TargetADBC.cli()
