import json
from pathlib import Path

import pytest
from singer_sdk.testing import get_target_test_class


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


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Mark built-in tests that are expected to fail."""
    failing_tests = {
        "test_target_special_chars_in_attributes": pytest.mark.xfail(
            strict=True,
            reason="Table names with special characters are not supported. "
            "Parser error with characters like ':', '!', '?' in table names. "
            "GitHub issue: Create issue for special character support in table names",
        ),
    }

    for item in items:
        test_name = item.name
        if test_name in failing_tests:
            item.add_marker(failing_tests[test_name])
