# Project Structure

```
target-adbc/
├── target_adbc/              # Main package
│   ├── __init__.py          # Package initialization
│   ├── target.py            # TargetADBC class (main entry point)
│   ├── sinks.py             # ADBCSink class (data processing)
│   └── settings.py          # Configuration schema
│
├── tests/                    # Test suite
│   ├── __init__.py
│   └── test_target.py       # Unit and integration tests
│
├── examples/                 # Example configurations and usage
│   ├── duckdb_config.json.example
│   ├── sample_input.jsonl
│   └── quickstart.sh        # Quick start demonstration script
│
├── pyproject.toml           # Project metadata and dependencies
├── README.md                # Main documentation
├── CONTRIBUTING.md          # Contribution guidelines
├── CHANGELOG.md             # Version history
├── LICENSE                  # Apache 2.0 license
└── .gitignore              # Git ignore rules
```

## Core Components

### 1. Target (`target.py`)

The main entry point that:
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

### 3. Settings (`settings.py`)

Configuration schema using Singer SDK's property types:
- Database driver configuration
- Connection parameters
- Behavioral settings (batch size, overwrite mode, etc.)
- Table naming options

**Key class**: `TargetADBCSettings`

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
Database (DuckDB, PostgreSQL, etc.)
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
object             → string()         → VARCHAR (JSON)
array              → list_()          → ARRAY
```

## Configuration Flow

```
config.json
    ↓
TargetADBCSettings.to_dict()
    ↓
JSON Schema Validation (SDK)
    ↓
Target.__init__(config)
    ↓
Sink receives config
    ↓
ADBC connection created
```

## Extension Points

### Adding a New Data Type

1. Update `ADBCSink._python_type_to_arrow()` - add mapping
2. Update `ADBCSink._convert_value()` - add conversion logic
3. Add test case

### Adding a New Configuration Option

1. Add property to `TargetADBCSettings`
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

### Unit Tests
- Settings validation
- Type conversion logic
- Configuration handling

### Integration Tests
- End-to-end data loading with DuckDB
- Schema creation and evolution
- Batch processing

### Test Fixtures
- Sample Singer messages
- Test database configurations
- Temporary database files

## Development Workflow

```bash
# Setup
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,duckdb]"

# Development cycle
1. Make changes
2. Run tests: pytest
3. Check types: mypy target_adbc
4. Check style: ruff check target_adbc
5. Format: ruff format target_adbc

# Testing
pytest                           # All tests
pytest tests/test_target.py     # Specific test
pytest --cov=target_adbc        # With coverage

# Running
cat examples/sample_input.jsonl | target-adbc --config examples/duckdb_config.json.example
```

## Dependencies

### Core Dependencies
- **singer-sdk**: Singer specification implementation and base classes
- **adbc-driver-manager**: ADBC connection management
- **pyarrow**: Arrow data format for efficient data transfer

### Optional Dependencies
- **adbc-driver-duckdb**: DuckDB support
- **adbc-driver-sqlite**: SQLite support
- **adbc-driver-postgresql**: PostgreSQL support

### Dev Dependencies
- **pytest**: Testing framework
- **mypy**: Static type checking
- **ruff**: Linting and formatting

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
