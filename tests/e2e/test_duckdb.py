from pathlib import Path
from typing import Any

import pytest

from target_adbc.target import TargetADBC


def test_end_to_end_duckdb(
    duckdb_config: dict[str, Any],
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
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
