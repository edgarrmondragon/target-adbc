"""Tests for the ADBC target."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, TypeAlias

import adbc_driver_manager
import pytest
from singer_sdk.testing import SuiteConfig, TargetTestRunner, get_target_test_class

from target_adbc.target import TargetADBC

if TYPE_CHECKING:
    from pathlib import Path


# Standard Target Tests
StandardTargetTests = get_target_test_class(
    target_class=TargetADBC,
    config={
        "driver": "duckdb",
    },
)

Config: TypeAlias = dict[str, Any]


class TestTargetStandard(StandardTargetTests):  # type: ignore[misc,valid-type] # ty: ignore[unsupported-base]
    """Standard Target Tests."""

    @pytest.mark.xfail(
        reason="Schema evolution is not supported",
        raises=adbc_driver_manager.InternalError,
        strict=True,
    )
    def test_target_schema_updates(
        self,
        config: SuiteConfig,
        resource: Any,
        runner: TargetTestRunner,
    ) -> None:
        super().test_target_schema_updates(config, resource, runner)


def test_target_initialization(duckdb_config: Config) -> None:
    """Test that the target can be initialized."""
    target = TargetADBC(config=duckdb_config)
    assert target.name == "target-adbc"
    assert target.config["driver"] == "duckdb"


def test_parallelism_disabled() -> None:
    """Test that parallel processing is disabled by default."""
    target = TargetADBC(config={"driver": "duckdb"})
    assert target.max_parallelism == 1


def test_append_mode(
    duckdb_config: Config,
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test that append mode adds to existing tables."""
    duckdb = pytest.importorskip("duckdb")

    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # First load
    target = TargetADBC(config=duckdb_config)
    with open(input_file) as f:
        target.listen(f)

    # Check count after first load
    db_path = duckdb_config["duckdb"]["path"]
    conn = duckdb.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 2
    conn.close()

    # Second load (should append)
    target = TargetADBC(config=duckdb_config)
    with open(input_file) as f:
        target.listen(f)

    # Check count after second load
    conn = duckdb.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 4  # 2 original + 2 appended
    conn.close()


def test_replace_mode(
    duckdb_config: Config,
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test that replace mode drops and recreates tables."""
    duckdb = pytest.importorskip("duckdb")

    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # First load
    target = TargetADBC(config=duckdb_config)
    with open(input_file) as f:
        target.listen(f)

    # Check count after first load
    db_path = duckdb_config["duckdb"]["path"]
    conn = duckdb.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 2
    conn.close()

    # Second load with replace mode
    replace_config = duckdb_config.copy()
    replace_config["overwrite_behavior"] = "replace"
    target = TargetADBC(config=replace_config)
    with open(input_file) as f:
        target.listen(f)

    # Check count after second load (should be 2, not 4)
    conn = duckdb.connect(db_path)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 2  # Table was replaced
    conn.close()


def test_config_schema() -> None:
    """Test that config schema is properly defined."""
    schema = TargetADBC.config_jsonschema

    assert "driver" in schema["properties"]
    assert schema["properties"]["batch_size_rows"]["default"] == 25_000
    assert schema["properties"]["overwrite_behavior"]["default"] == "append"
    assert schema["properties"]["add_record_metadata"]["default"] is True

    allowed = schema["properties"]["overwrite_behavior"].get("enum")
    assert set(allowed) == {"append", "replace"}
