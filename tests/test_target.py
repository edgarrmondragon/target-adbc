"""Tests for the ADBC target."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from target_adbc.target import TargetADBC


@pytest.fixture
def duckdb_config(tmp_path: Path) -> dict:
    """Create a DuckDB configuration for testing."""
    db_path = tmp_path / "test.duckdb"
    return {
        "driver": "duckdb",
        "duckdb": {
            "path": str(db_path),
        },
        "batch_size": 100,
        "add_record_metadata": False,
    }


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


@pytest.fixture
def singer_messages() -> list[str]:
    """Create sample Singer messages."""
    return [
        json.dumps(
            {
                "type": "SCHEMA",
                "stream": "users",
                "schema": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "active": {"type": "boolean"},
                    },
                },
                "key_properties": ["id"],
            }
        ),
        json.dumps(
            {
                "type": "RECORD",
                "stream": "users",
                "record": {
                    "id": 1,
                    "name": "Alice",
                    "email": "alice@example.com",
                    "active": True,
                },
            }
        ),
        json.dumps(
            {
                "type": "RECORD",
                "stream": "users",
                "record": {
                    "id": 2,
                    "name": "Bob",
                    "email": "bob@example.com",
                    "active": False,
                },
            }
        ),
    ]


def test_end_to_end_duckdb(
    duckdb_config: dict,
    singer_messages: list[str],
    tmp_path: Path,
):
    """Test end-to-end data loading with DuckDB."""
    duckdb = pytest.importorskip("duckdb")

    # Write messages to a file
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # Create target
    target = TargetADBC(config=duckdb_config)

    # Process messages
    with open(input_file) as f:
        target.listen(f)

    # Verify data was loaded
    db_path = duckdb_config["duckdb"]["path"]
    conn = duckdb.connect(db_path)

    # Check record count
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    assert count == 2

    # Check data
    rows = conn.execute("SELECT id, name, email, active FROM users ORDER BY id").fetchall()

    assert rows[0] == (1, "Alice", "alice@example.com", True)
    assert rows[1] == (2, "Bob", "bob@example.com", False)

    conn.close()


def test_end_to_end_sqlite(singer_messages: list[str], tmp_path: Path) -> None:
    """Test end-to-end data loading with SQLite."""
    db_path = tmp_path / "test.sqlite"

    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # Create target
    target = TargetADBC(config={"driver": "sqlite", "sqlite": {"uri": db_path.as_uri()}})

    # Process messages
    with open(input_file) as f:
        target.listen(f)

    # Verify data was loaded
    conn = sqlite3.connect(db_path.as_posix())
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    assert count == 2

    # Check data
    cursor.execute("SELECT id, name, email, active FROM users ORDER BY id")
    rows = cursor.fetchall()
    assert rows[0] == (1, "Alice", "alice@example.com", True)
    assert rows[1] == (2, "Bob", "bob@example.com", False)

    conn.close()


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
