"""End-to-end tests for BatchProcessor across multiple ADBC backends.

The ``backend_connection`` fixture is parametrized in conftest.py to run
each test against DuckDB, SQLite, PostgreSQL, and MSSQL.  Backends whose
driver package is not installed are automatically skipped.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from target_adbc.batch import BatchProcessor

if TYPE_CHECKING:
    from tests.e2e.conftest import BackendConnection


SINGER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "id": {"type": "integer"},
        "name": {"type": "string"},
        "email": {"type": "string"},
        "active": {"type": "boolean"},
        "score": {"type": "number"},
    },
}

SAMPLE_RECORDS: list[dict[str, Any]] = [
    {"id": 1, "name": "Alice", "email": "alice@example.com", "active": True, "score": 9.5},
    {"id": 2, "name": "Bob", "email": "bob@example.com", "active": False, "score": 7.2},
]


def _make_proc(
    backend_connection: BackendConnection,
    table_name: str,
    **kwargs: Any,
) -> BatchProcessor:
    return BatchProcessor(
        connection=backend_connection.connection,
        table_name=table_name,
        schema_name=backend_connection.schema_name,
        json_schema=SINGER_SCHEMA,
        add_record_metadata=False,
        **kwargs,
    )


def test_creates_table(backend_connection: BackendConnection, table_name: str) -> None:
    """BatchProcessor creates the table and inserts records on first call."""
    proc = _make_proc(backend_connection, table_name)
    proc.ingest(SAMPLE_RECORDS)

    with backend_connection.connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {proc.full_table_name}")
        row = cur.fetchone()
        assert row is not None

    assert row == (2,)


def test_append_mode(backend_connection: BackendConnection, table_name: str) -> None:
    """Second ingest call appends rows to an existing table."""
    proc = _make_proc(backend_connection, table_name, overwrite_behavior="append")
    proc.ingest(SAMPLE_RECORDS)
    proc.ingest(SAMPLE_RECORDS)

    with backend_connection.connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {proc.full_table_name}")
        row = cur.fetchone()
        assert row is not None

    assert row == (4,)


def test_replace_mode(backend_connection: BackendConnection, table_name: str) -> None:
    """replace mode drops the existing table before the first ingest."""
    proc = _make_proc(backend_connection, table_name, overwrite_behavior="replace")
    proc.ingest(SAMPLE_RECORDS)

    proc2 = _make_proc(backend_connection, table_name, overwrite_behavior="replace")
    proc2.ingest(SAMPLE_RECORDS)

    with backend_connection.connection.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {proc2.full_table_name}")
        row = cur.fetchone()
        assert row is not None

    assert row == (2,)


def test_empty_batch_is_noop(backend_connection: BackendConnection, table_name: str) -> None:
    """ingest with an empty list does not create the table."""
    proc = _make_proc(backend_connection, table_name)
    proc.ingest([])

    with pytest.raises(Exception), backend_connection.connection.cursor() as cur:  # noqa: B017
        cur.execute(f"SELECT 1 FROM {proc.full_table_name}")
    backend_connection.connection.rollback()


def test_record_values_roundtrip(backend_connection: BackendConnection, table_name: str) -> None:
    """Data read back from the database matches what was written."""
    proc = _make_proc(backend_connection, table_name)
    proc.ingest(SAMPLE_RECORDS)

    with backend_connection.connection.cursor() as cur:
        cur.execute(
            f"SELECT id, name, email, active, score FROM {proc.full_table_name} ORDER BY id"
        )
        rows = cur.fetchall()

    assert rows[0] == (1, "Alice", "alice@example.com", True, 9.5)
    assert rows[1] == (2, "Bob", "bob@example.com", False, 7.2)
