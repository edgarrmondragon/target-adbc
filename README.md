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

# Basic installation
uv tool install --editable ./target-adbc

# With specific database drivers
uv tool install --editable "target-adbc[duckdb] @ ./target-adbc"
uv tool install --editable "target-adbc[sqlite] @ ./target-adbc"
uv tool install --editable "target-adbc[postgresql] @ ./target-adbc"

# For development
uv sync --all-extras
```

## Supported Databases

Any database with an ADBC driver is supported. Popular options include:

- **DuckDB** (`adbc-driver-duckdb`)
- **SQLite** (`adbc-driver-sqlite`)
- **PostgreSQL** (`adbc-driver-postgresql`)
- **Flight SQL** (`adbc-driver-flightsql`)

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
  "driver": "duckdb",
  "uri": "my_database.duckdb",
  "batch_size": 10000,
  "overwrite_behavior": "append"
}
```

#### SQLite Example

```json
{
  "driver": "sqlite",
  "uri": "my_database.sqlite",
  "batch_size": 5000
}
```

#### PostgreSQL Example

```json
{
  "driver": "postgresql",
  "connection_kwargs": {
    "username": "myuser",
    "password": "mypass",
    "host": "localhost",
    "port": 5432,
    "db_name": "mydb"
  },
  "default_target_schema": "public",
  "batch_size": 10000
}
```

### Configuration Options

| Setting | Required | Default | Description |
|---------|----------|---------|-------------|
| `driver` | Yes | - | ADBC driver name (e.g., `duckdb`, `sqlite`, `postgresql`) |
| `uri` | No | - | Database URI for connection |
| `connection_kwargs` | No | `{}` | Driver-specific connection parameters |
| `default_target_schema` | No | - | Default schema for tables |
| `table_prefix` | No | `""` | Prefix to add to all table names |
| `table_suffix` | No | `""` | Suffix to add to all table names |
| `overwrite_behavior` | No | `append` | How to handle existing tables: `append`, `replace`, or `fail` |
| `batch_size` | No | `10000` | Number of rows to process per batch |
| `add_record_metadata` | No | `true` | Add metadata columns (`_sdc_*`) to tables |
| `varchar_length` | No | `255` | Default VARCHAR length when not specified |

### Overwrite Behaviors

- **`append`** (default): Add new data to existing tables
- **`replace`**: Drop and recreate tables before loading
- **`fail`**: Raise an error if the table already exists

### Metadata Columns

When `add_record_metadata` is enabled (default), the following columns are added:

- `_sdc_extracted_at`: Timestamp when the record was extracted from the source
- `_sdc_received_at`: Timestamp when the record was received by the target
- `_sdc_batched_at`: Timestamp when the record was batched for loading
- `_sdc_sequence`: Sequence number for ordering
- `_sdc_table_version`: Table version number

## Using with Meltano

Add the target to your `meltano.yml`:

```yaml
plugins:
  loaders:
  - name: target-adbc
    namespace: target_adbc
    pip_url: -e /path/to/target-adbc
    executable: target-adbc
    settings:
    - name: driver
      kind: string
      description: ADBC driver name
    - name: uri
      kind: string
      description: Database URI
    - name: connection_kwargs
      kind: object
      description: Additional connection parameters
    - name: batch_size
      kind: integer
      value: 10000
    config:
      driver: duckdb
      uri: ${MELTANO_PROJECT_ROOT}/output/warehouse.duckdb
```

Then run:

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
  "driver": "duckdb",
  "uri": "users.duckdb"
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
  "driver": "postgresql",
  "connection_kwargs": {
    "username": "postgres",
    "password": "secret",
    "host": "localhost",
    "port": 5432,
    "db_name": "analytics"
  },
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

# Install in development mode
pip install -e ".[dev,duckdb]"
```

### Testing

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=target_adbc

# Type checking
mypy target_adbc

# Linting
ruff check target_adbc
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

1. **Batch Size**: Increase `batch_size` for larger datasets (e.g., 50000-100000 rows)
2. **Metadata**: Disable `add_record_metadata` if you don't need lineage tracking
3. **Schema**: Specify schema explicitly to avoid inference overhead
4. **Indexes**: Create indexes after loading large datasets, not before

## Troubleshooting

### Connection Issues

If you encounter connection errors:

1. Verify the driver is installed: `pip list | grep adbc-driver`
2. Check your connection parameters match the driver's requirements
3. Test the connection separately using the ADBC Python API

### Schema Errors

If you see schema-related errors:

1. Ensure your Singer schema is valid JSON Schema
2. Check for unsupported data types
3. Set `default_target_schema` for databases that require it (PostgreSQL)

### Performance Issues

If loading is slow:

1. Increase `batch_size` in your config
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
