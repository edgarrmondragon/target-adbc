import sqlite3
from pathlib import Path

from target_adbc.target import TargetADBC


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
