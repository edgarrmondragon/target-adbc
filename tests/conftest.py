import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def duckdb_config(tmp_path: Path) -> dict[str, Any]:
    """Create a DuckDB configuration for testing."""
    db_path = tmp_path / "test.duckdb"
    return {
        "uri": f"duckdb://{db_path}",
        "batch_size_rows": 100,
        "add_record_metadata": False,
    }


@pytest.fixture
def singer_messages() -> list[str]:
    """Create sample Singer messages."""
    return [
        json.dumps({
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
        }),
        json.dumps({
            "type": "RECORD",
            "stream": "users",
            "record": {
                "id": 1,
                "name": "Alice",
                "email": "alice@example.com",
                "active": True,
            },
        }),
        json.dumps({
            "type": "RECORD",
            "stream": "users",
            "record": {
                "id": 2,
                "name": "Bob",
                "email": "bob@example.com",
                "active": False,
            },
        }),
    ]
