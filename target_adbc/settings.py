"""Settings for the ADBC target."""

from __future__ import annotations

from singer_sdk import typing as th


class TargetADBCSettings(th.PropertiesList):
    """Settings for the ADBC target."""

    driver = th.Property(
        "driver",
        th.StringType,
        required=True,
        description=("ADBC driver name. Examples: 'duckdb', 'sqlite', 'postgresql'"),
    )

    uri = th.Property(
        "uri",
        th.StringType,
        description=(
            "Database path or connection string. Format depends on the driver. "
            "For DuckDB/SQLite, use a file path (e.g., 'my_db.duckdb'). "
            "For PostgreSQL, use a connection string or set connection_kwargs."
        ),
    )

    connection_kwargs = th.Property(
        "connection_kwargs",
        th.ObjectType(),
        description=(
            "Additional keyword arguments to pass to the ADBC connection. "
            "These are driver-specific and can include options like username, "
            "password, host, port, etc."
        ),
    )

    default_target_schema = th.Property(
        "default_target_schema",
        th.StringType,
        description=(
            "Default schema to use for tables if not specified in stream name. "
            "Some drivers require this (e.g., PostgreSQL)."
        ),
    )

    table_prefix = th.Property(
        "table_prefix",
        th.StringType,
        default="",
        description="Prefix to add to all table names.",
    )

    table_suffix = th.Property(
        "table_suffix",
        th.StringType,
        default="",
        description="Suffix to add to all table names.",
    )

    overwrite_behavior = th.Property(
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
    )

    batch_size = th.Property(
        "batch_size",
        th.IntegerType,
        default=10000,
        description="Maximum number of rows to process in a single batch.",
    )

    add_record_metadata = th.Property(
        "add_record_metadata",
        th.BooleanType,
        default=True,
        description=(
            "Add metadata columns (_sdc_extracted_at, _sdc_received_at, "
            "_sdc_batched_at, _sdc_sequence, _sdc_table_version) to output tables."
        ),
    )

    varchar_length = th.Property(
        "varchar_length",
        th.IntegerType,
        default=255,
        description="Default length for VARCHAR columns when not specified.",
    )
