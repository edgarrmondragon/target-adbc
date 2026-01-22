# Project Structure

```
target-adbc/
├── target_adbc/              # Main package
│   ├── __init__.py          # Package initialization and version
│   ├── target.py            # TargetADBC class (main entry point + config schema)
│   └── sinks.py             # ADBCSink class (data processing)
│
├── tests/                    # Test suite
│   ├── __init__.py
│   ├── conftest.py          # Pytest fixtures
│   ├── test_target.py       # Unit tests
│   └── e2e/                 # End-to-end tests
│       ├── test_duckdb.py   # DuckDB integration tests
│       └── test_sqlite.py   # SQLite integration tests
│
├── examples/                 # Example configurations and usage
│   ├── duckdb_config.json.example
│   ├── postgresql_config.json.example
│   ├── sqlite_config.json.example
│   ├── sample_input.jsonl
│   └── quickstart.sh        # Quick start demonstration script
│
├── .github/
│   └── workflows/
│       └── test.yml         # CI workflow
│
├── pyproject.toml           # Project metadata and dependencies
├── uv.lock                  # Dependency lock file
├── meltano.yml              # Meltano project configuration
├── .pre-commit-config.yaml  # Pre-commit hooks configuration
├── README.md                # Main documentation
├── CONTRIBUTING.md          # Contribution guidelines
├── CHANGELOG.md             # Version history
├── LICENSE                  # Apache 2.0 license
└── .gitignore               # Git ignore rules
```

## Core Components

### 1. Target (`target.py`)

The main entry point that:
- Defines the configuration schema using Singer SDK's typing system
- Initializes the Singer target
- Validates configuration
- Manages the lifecycle of sinks
- Provides CLI interface

**Key class**: `TargetADBC`

### 2. Sink (`sinks.py`)

Handles data processing:
- Receives batches of records
- Converts Singer schemas to PyArrow schemas
- Manages ADBC connections
- Performs bulk inserts using `adbc_ingest`
- Handles table creation and management

**Key class**: `ADBCSink`

## Data Flow

```
Singer Messages (stdin)
    ↓
TargetADBC.cli()
    ↓
Message Parser (SDK)
    ↓
ADBCSink.process_batch()
    ↓
PyArrow Table Conversion
    ↓
ADBC Connection
    ↓
Database (DuckDB, PostgreSQL, SQLite, etc.)
```

## Type Conversion Pipeline

```
Singer JSON Schema → PyArrow DataType → Database Type
---------------------------------------------------
integer            → int64()          → BIGINT
number             → float64()        → DOUBLE
string             → string()         → VARCHAR
boolean            → bool_()          → BOOLEAN
date-time          → timestamp()      → TIMESTAMP
date               → date32()         → DATE
time               → time64()         → TIME
object             → string()         → VARCHAR (JSON)
array              → list_()          → ARRAY
```

## Configuration Flow

```
config.json
    ↓
TargetADBC.config_jsonschema (validation)
    ↓
Target.__init__(config)
    ↓
Sink receives config
    ↓
ADBC connection created
```

## Extension Points

### Adding a New Data Type

1. Update `ADBCSink._json_type_to_arrow()` - add mapping
2. Update `ADBCSink._convert_value()` - add conversion logic
3. Add test case

### Adding a New Configuration Option

1. Add property to `TargetADBC.config_jsonschema` in `target.py`
2. Use in `ADBCSink` or `TargetADBC`
3. Document in README.md
4. Add test case

### Supporting a New Database

The target is designed to work with any ADBC driver without code changes!

Simply:
1. Install the ADBC driver: `pip install adbc-driver-{database}`
2. Configure the driver name in config.json
3. Provide appropriate connection parameters

## Testing Strategy

### Unit Tests (`tests/test_target.py`)
- Configuration handling
- Type conversion logic

### End-to-End Tests (`tests/e2e/`)
- DuckDB: Full data loading pipeline
- SQLite: Full data loading pipeline

### Test Fixtures (`tests/conftest.py`)
- Sample Singer messages
- Test database configurations

## Development Workflow

```bash
# Setup (using uv)
uv sync

# Development cycle
1. Make changes
2. Run tests: uv run pytest
3. Check types: uv run mypy target_adbc
4. Check style: uv run ruff check target_adbc
5. Format: uv run ruff format target_adbc

# Pre-commit hooks
pre-commit install
pre-commit run --all-files

# Testing
uv run pytest                        # All tests
uv run pytest tests/test_target.py   # Unit tests only
uv run pytest tests/e2e/             # E2E tests only
uv run pytest --cov=target_adbc      # With coverage

# Running
cat examples/sample_input.jsonl | uv run target-adbc --config examples/duckdb_config.json.example
```

## Dependencies

### Core Dependencies
- **singer-sdk**: Singer specification implementation and base classes
- **adbc-driver-manager**: ADBC connection management
- **pyarrow**: Arrow data format for efficient data transfer
- **duckdb**: DuckDB support (included by default)

### Dev Dependencies
- **pytest**: Testing framework
- **coverage**: Code coverage
- **mypy**: Static type checking
- **ruff**: Linting and formatting
- **pyarrow-stubs**: Type stubs for PyArrow

## Performance Characteristics

### Memory Usage
- Processes data in batches (default: 10,000 rows)
- Uses columnar format (PyArrow) - more memory efficient
- Connection pooling handled by ADBC driver

### Speed
- Bulk insert using ADBC's `adbc_ingest` (much faster than row-by-row)
- Direct Arrow format (no serialization overhead)
- Batch processing reduces network round-trips

### Scalability
- Configurable batch size for memory/speed tradeoff
- Supports streaming (doesn't load all data into memory)
- Driver-specific optimizations (e.g., DuckDB's parallel loading)

## Security Considerations

### Configuration
- Avoid storing passwords in config files (use environment variables)
- Use secure connection methods (SSL/TLS) when available
- Follow database-specific security best practices

### Data Handling
- No data is logged or persisted outside the target database
- Connection credentials are not exposed in logs
- Type conversion prevents SQL injection (parameterized inserts)
