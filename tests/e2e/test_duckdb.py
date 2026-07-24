from pathlib import Path
from typing import Any

from target_adbc.connect import get_connection
from target_adbc.target import TargetADBC


def test_end_to_end_duckdb(
    duckdb_config: dict[str, Any],
    singer_messages: list[str],
    tmp_path: Path,
) -> None:
    """Test end-to-end data loading with DuckDB."""
    # Write messages to a file
    input_file = tmp_path / "input.jsonl"
    input_file.write_text("\n".join(singer_messages))

    # Create target
    target = TargetADBC(config=duckdb_config)

    # Process messages
    with input_file.open() as f:
        target.listen(f)

    # Verify data was loaded
    with get_connection(duckdb_config) as conn, conn.cursor() as cur:
        # Check record count
        res = cur.execute("SELECT COUNT(*) FROM users").fetchone()
        assert res
        assert res[0] == 2

        # Check data
        rows = cur.execute("SELECT id, name, email, active FROM users ORDER BY id").fetchall()

        assert rows[0] == (1, "Alice", "alice@example.com", True)
        assert rows[1] == (2, "Bob", "bob@example.com", False)
