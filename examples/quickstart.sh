#!/bin/bash
# Quick start script for testing target-adbc with DuckDB

set -e

echo "=== Target ADBC Quick Start ==="
echo ""

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo "⚠️  Warning: Not in a virtual environment"
    echo "   Consider running: python -m venv .venv && source .venv/bin/activate"
    echo ""
fi

echo "📦 Installing target-adbc with DuckDB driver..."
pip install -e ".[duckdb]" > /dev/null 2>&1

echo "✅ Installation complete"
echo ""

# Create config
CONFIG_FILE="examples/test_config.json"
echo "📝 Creating config file: $CONFIG_FILE"
cat > "$CONFIG_FILE" << EOF
{
  "uri": "duckdb://examples/test_database.duckdb",
  "batch_size_rows": 1000,
  "add_record_metadata": false
}
EOF

echo "✅ Config created"
echo ""

# Use the sample input
INPUT_FILE="examples/sample_input.jsonl"

echo "🎵 Loading sample data into DuckDB..."
cat "$INPUT_FILE" | target-adbc --config "$CONFIG_FILE"

echo ""
echo "✅ Data loaded successfully!"
echo ""

# Query the results
DB_PATH="examples/test_database.duckdb"
echo "📊 Querying results..."
python3 << EOF
from adbc_driver_manager import dbapi

with dbapi.connect(f"duckdb://{DB_PATH}") as conn, conn.cursor() as cursor:
    print("\n=== Users Table ===")
    cursor.execute("SELECT * FROM users ORDER BY id")
    rows = cursor.fetchall()

    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Email: {row[2]}")

    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    print(f"\nTotal records: {count}")
EOF

echo ""
echo "🎉 Quick start complete!"
echo ""
echo "Next steps:"
echo "  - Try modifying examples/sample_input.jsonl"
echo "  - Run: cat examples/sample_input.jsonl | target-adbc --config $CONFIG_FILE"
echo "  - Explore the database: duckdb $DB_PATH"
