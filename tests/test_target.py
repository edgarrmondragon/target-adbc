"""Tests for the ADBC target."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from target_adbc.target import TargetADBC

if TYPE_CHECKING:
    from pathlib import Path


def test_target_initialization(duckdb_config: dict):
    """Test that the target can be initialized."""
    target = TargetADBC(config=duckdb_config)
    assert target.name == "target-adbc"
    assert target.config["driver"] == "duckdb"


def test_sink_class_configured(duckdb_config: dict):
    """Test that the sink class is properly configured."""
    target = TargetADBC(config=duckdb_config)
    assert target.default_sink_class.max_size == 100


def test_parallelism_disabled():
    """Test that parallel processing is disabled by default."""
    target = TargetADBC(config={"driver": "duckdb"})
    assert target.max_parallelism == 1


def test_append_mode(duckdb_config: dict, singer_messages: list[str], tmp_path: Path):
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


def test_replace_mode(duckdb_config: dict, singer_messages: list[str], tmp_path: Path):
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


def test_fail_mode(duckdb_config: dict, singer_messages: list[str], tmp_path: Path):
    """Test that fail mode raises an error when table exists."""
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # First load
    target = TargetADBC(config=duckdb_config)
    with open(input_file) as f:
        target.listen(f)

    # Second load with fail mode should raise error
    fail_config = duckdb_config.copy()
    fail_config["overwrite_behavior"] = "fail"
    target = TargetADBC(config=fail_config)

    with pytest.raises(RuntimeError, match="already exists"):
        with open(input_file) as f:
            target.listen(f)


def test_config_schema():
    """Test that config schema is properly defined."""
    target = TargetADBC(config={"driver": "duckdb"}, validate_config=False)
    schema = target.config_jsonschema

    # Check required fields
    assert "driver" in schema["properties"]
    # Note: The schema structure differs from settings - driver is in properties

    # Check optional fields with defaults
    assert schema["properties"]["batch_size"]["default"] == 10000
    assert schema["properties"]["overwrite_behavior"]["default"] == "append"
    assert schema["properties"]["add_record_metadata"]["default"] is True

    # Check allowed values for overwrite_behavior
    allowed = schema["properties"]["overwrite_behavior"].get("enum")
    assert set(allowed) == {"append", "replace", "fail"}
