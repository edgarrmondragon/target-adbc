# target-adbc

A Singer target for loading data into ADBC-compatible databases.

[ADBC (Arrow Database Connectivity)](https://arrow.apache.org/adbc/) is a database access API that uses Apache Arrow for data interchange, providing efficient columnar data transfer between applications and databases.

## Features

- **Universal Database Support**: Works with any ADBC-compatible database driver (DuckDB, SQLite, PostgreSQL, etc.)
- **High Performance**: Uses Apache Arrow for efficient columnar data transfer
- **Flexible Configuration**: Supports various connection methods and driver-specific options
- **Singer Specification Compliant**: Fully compatible with the Singer ecosystem
- **Metadata Tracking**: Optional Stitch-style metadata columns for data lineage

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/target-adbc.git
cd target-adbc

# Install target-adbc with the drivers you need
uv tool install --editable "./target-adbc[duckdb,sqlite,postgres]"

# For development
uv sync --all-extras
```

## Supported Databases

Any database with an ADBC driver is supported. Popular options include:

| Database | Scheme in `uri` | Install with a PyPI extra | Install with `dbc` |
|----------|------------------|----------------------------|---------------------|
| **DuckDB** | `duckdb://` | `pip install target-adbc[duckdb]` | `dbc install duckdb` |
| **SQLite** | `sqlite://` | `pip install target-adbc[sqlite]` | `dbc install sqlite` |
| **PostgreSQL** | `postgresql://` | `pip install target-adbc[postgres]` | `dbc install postgresql` |
| **MSSQL** | `sqlserver://` | *(no PyPI driver)* | `dbc install mssql` |

### Installing ADBC Drivers

There are two ways to make an ADBC driver available to target-adbc:

1. **PyPI extras** (recommended for DuckDB, SQLite, and PostgreSQL). Installing the matching optional dependency pulls in a wheel that bundles the compiled driver — target-adbc detects and uses it automatically, so there's no separate driver-install step, and the driver version is pinned right alongside your other dependencies:

   ```bash
   uv sync --extra duckdb --extra sqlite --extra postgres
   # or: pip install "target-adbc[duckdb,sqlite,postgres]"
   ```

2. **[`dbc`](https://docs.columnar.tech/dbc/)**: required for drivers with no official PyPI package (e.g. MSSQL), and also works for DuckDB/SQLite/PostgreSQL if you'd rather manage drivers outside of your Python environment:

   ```bash
   # Install dbc (one-time setup)
   curl -LsSf https://dbc.columnar.tech/install.sh | sh

   # Install the drivers you need
   dbc install duckdb
   dbc install mssql
   ```

   If a PyPI extra is installed for a given database, target-adbc prefers it over a `dbc`-installed driver for that same database.

See the [ADBC documentation](https://arrow.apache.org/adbc/current/driver/installation.html) for a full list of available drivers.

## Usage

### Basic Example

The target accepts Singer messages on stdin and loads data into the configured database:

```bash
tap-something | target-adbc --config config.json
```

### Configuration

Create a `config.json` file with your database connection details:

#### DuckDB Example

```json
{
  "uri": "duckdb://my_database.duckdb",
  "batch_size_rows": 10000,
  "overwrite_behavior": "append"
}
```

#### SQLite Example

```json
{
  "uri": "sqlite://my_database.sqlite",
  "batch_size_rows": 5000
}
```

#### PostgreSQL Example

```json
{
  "uri": "postgresql://myuser:mypass@localhost:5432/mydb",
  "default_target_schema": "public",
  "batch_size_rows": 10000
}
```

### Configuration Options

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| `uri` | Yes | - | ADBC connection URI, e.g. `duckdb://my_database.duckdb`, `sqlite:///abs/path.db`, `postgresql://user:pass@host/db` |
| `duckdb` / `sqlite` / `postgresql` / `mssql` | No | `{}` | Extra driver-specific options passed through to the ADBC driver as-is (rarely needed — connection details normally belong in `uri`) |
| `default_target_schema` | No | - | Default schema for tables |
| `table_prefix` | No | `""` | Prefix to add to all table names |
| `table_suffix` | No | `""` | Suffix to add to all table names |
| `overwrite_behavior` | No | `append` | How to handle existing tables: `append` or `replace` |
| `batch_size_rows` | No | `25000` | Number of rows to process per batch |
| `add_record_metadata` | No | `true` | Add metadata columns (`_sdc_*`) to tables |
| `varchar_length` | No | `255` | Default VARCHAR length when not specified |

### Overwrite Behaviors

- **`append`** (default): Add new data to existing tables
- **`replace`**: Drop and recreate tables before loading

### Metadata Columns

When `add_record_metadata` is enabled (default), the following columns are added:

- `_sdc_extracted_at`: Timestamp when the record was extracted from the source
- `_sdc_received_at`: Timestamp when the record was received by the target
- `_sdc_batched_at`: Timestamp when the record was batched for loading
- `_sdc_sequence`: Sequence number for ordering
- `_sdc_table_version`: Table version number

## Using with Meltano

### Install ADBC Drivers First

Before using target-adbc with Meltano, install the required ADBC driver(s) — see [Installing ADBC Drivers](#installing-adbc-drivers) above. For DuckDB/SQLite/PostgreSQL, the simplest way is a PyPI extra:

```bash
pip_url: target-adbc[duckdb]
```

### Add to meltano.yml

Add the target to your `meltano.yml`:

```yaml
plugins:
  loaders:
  - name: target-adbc
    namespace: target_adbc
    pip_url: -e .
    executable: target-adbc
    settings:
    - name: uri
      kind: string
      sensitive: true
      description: "ADBC connection URI, e.g. duckdb://path/to.db, sqlite://path/to.db, postgresql://user:pass@host/db"

    # General settings
    - name: default_target_schema
      kind: string
      description: Default schema to use for tables if not specified in stream name
    - name: table_prefix
      kind: string
      description: Prefix to add to all table names
    - name: table_suffix
      kind: string
      description: Suffix to add to all table names
    - name: batch_size_rows
      kind: integer
      description: Maximum number of rows to process in a single batch
    - name: overwrite_behavior
      kind: options
      description: Behavior when table already exists
      options:
      - label: Append
        value: append
      - label: Replace
        value: replace
    - name: add_record_metadata
      kind: boolean
      description: Add metadata columns to the output tables
    - name: varchar_length
      kind: integer
      description: Default length for VARCHAR columns when not specified

  # Configured variant for DuckDB
  - name: target-adbc-duckdb
    pip_url: target-adbc[duckdb]
    inherit_from: target-adbc
    config:
      uri: duckdb://${MELTANO_PROJECT_ROOT}/output/warehouse.duckdb
      overwrite_behavior: replace

  # Configured variant for SQLite
  - name: target-adbc-sqlite
    pip_url: target-adbc[sqlite]
    inherit_from: target-adbc
    config:
      uri: sqlite://${MELTANO_PROJECT_ROOT}/output/warehouse.sqlite
      overwrite_behavior: replace
```

### Run with Meltano

```bash
meltano run tap-something target-adbc
```

## Examples

### Example 1: Load CSV to DuckDB

```bash
# Create a simple tap
cat << 'EOF' > sample_data.jsonl
{"type": "SCHEMA", "stream": "users", "schema": {"properties": {"id": {"type": "integer"}, "name": {"type": "string"}, "email": {"type": "string"}}, "type": "object"}, "key_properties": ["id"]}
{"type": "RECORD", "stream": "users", "record": {"id": 1, "name": "Alice", "email": "alice@example.com"}}
{"type": "RECORD", "stream": "users", "record": {"id": 2, "name": "Bob", "email": "bob@example.com"}}
EOF

# Create config
cat << 'EOF' > config.json
{
  "uri": "duckdb://users.duckdb"
}
EOF

# Load data
cat sample_data.jsonl | target-adbc --config config.json

# Query the result
duckdb users.duckdb -c "SELECT * FROM users"
```

### Example 2: Stream Data from API to PostgreSQL

```bash
# Configure PostgreSQL target
cat << 'EOF' > pg_config.json
{
  "uri": "postgresql://postgres:secret@localhost:5432/analytics",
  "default_target_schema": "raw_data",
  "overwrite_behavior": "append"
}
EOF

# Run with any Singer tap
tap-github --config tap_config.json | target-adbc --config pg_config.json
```

## Development

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/target-adbc
cd target-adbc

# Install in development mode, including the DuckDB/SQLite/PostgreSQL
# PyPI driver extras used by the test suite
uv sync --all-extras

# MSSQL has no PyPI driver, so it needs dbc for the mssql-related tests
curl -LsSf https://dbc.columnar.tech/install.sh | sh
dbc install mssql
```

### Testing

```bash
# Run tests
uv run pytest

# Run with coverage
uv run coverage run -m pytest

# Type checking
uv run mypy target_adbc tests

# Linting
uv run ruff check target_adbc tests
uv run ruff format target_adbc tests
```

## Architecture

The target follows the Singer specification and uses the Meltano SDK:

1. **Target** (`target.py`): Main entry point that orchestrates the data loading process
2. **Sink** (`sinks.py`): Handles batch processing and ADBC interactions
3. **Settings** (`settings.py`): Configuration schema and validation

### Data Flow

```
Singer Messages � Target � Sink � ADBC Connection � Database
                           �
                    PyArrow Tables
```

The sink:
1. Receives batches of records from the target
2. Converts records to PyArrow tables using the Singer schema
3. Uses ADBC's `adbc_ingest` for efficient bulk loading
4. Handles table creation, schema evolution, and error handling

## Singer Specification Compliance

This target implements the Singer specification:

- Accepts `SCHEMA`, `RECORD`, and `STATE` messages
- Outputs `STATE` messages for checkpoint management
- Handles schema evolution
- Supports batch processing for performance
- Validates configuration

## Performance Tips

1. **Batch Size**: Increase `batch_size_rows` for larger datasets (e.g., 50000-100000 rows)
2. **Metadata**: Disable `add_record_metadata` if you don't need lineage tracking
3. **Schema**: Specify schema explicitly to avoid inference overhead
4. **Indexes**: Create indexes after loading large datasets, not before

## Troubleshooting

### Connection Issues

If you encounter connection errors:

1. Ensure the driver is installed, either as a PyPI extra (`pip install target-adbc[duckdb]`) or with `dbc install <driver-name>`
2. Check your connection parameters match the driver's requirements
3. Test the connection separately using the ADBC Python API

### Schema Errors

If you see schema-related errors:

1. Ensure your Singer schema is valid JSON Schema
2. Check for unsupported data types
3. Set `default_target_schema` for databases that require it (PostgreSQL)

### Performance Issues

If loading is slow:

1. Increase `batch_size_rows` in your config
2. Disable metadata columns with `"add_record_metadata": false`
3. Use `overwrite_behavior: "replace"` instead of truncating manually

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the Apache License 2.0 - see the LICENSE file for details.

## Resources

- [Singer Specification](https://github.com/singer-io/getting-started/blob/master/docs/SPEC.md)
- [Meltano SDK Documentation](https://sdk.meltano.com/)
- [ADBC Documentation](https://arrow.apache.org/adbc/)
- [Apache Arrow Documentation](https://arrow.apache.org/)

## Acknowledgements

Built with:
- [Singer SDK](https://github.com/meltano/sdk) by Meltano
- [Apache Arrow ADBC](https://arrow.apache.org/adbc/) by the Apache Arrow community
