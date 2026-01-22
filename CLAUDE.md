# CLAUDE.md

This file provides guidance for Claude Code when working on this project.

## Project Overview

**target-adbc** is a Singer target that loads data into any ADBC-compatible database (DuckDB, PostgreSQL, SQLite, etc.). It uses the Singer SDK for message parsing and PyArrow for efficient columnar data transfer via the ADBC protocol.

## Common Commands

```bash
# Install dependencies
uv sync

# Run tests
uv run pytest                        # All tests
uv run pytest tests/test_target.py   # Unit tests
uv run pytest tests/e2e/             # End-to-end tests

# Type checking
uv run mypy target_adbc

# Linting and formatting
uv run ruff check target_adbc        # Check for issues
uv run ruff check --fix target_adbc  # Auto-fix issues
uv run ruff format target_adbc       # Format code

# Pre-commit hooks
pre-commit run --all-files

# Run the target
cat examples/sample_input.jsonl | uv run target-adbc --config examples/duckdb_config.json.example
```

## Architecture

The codebase has two main components:

1. **`target_adbc/target.py`** - `TargetADBC` class
   - Entry point and CLI
   - Configuration schema definition (no separate settings file)
   - Sets up sinks for each stream

2. **`target_adbc/sinks.py`** - `ADBCSink` class
   - Handles batch processing
   - Converts Singer JSON Schema to PyArrow types
   - Manages ADBC connections
   - Performs bulk inserts via `cursor.adbc_ingest()`

## Code Style

- Uses **Ruff** for linting and formatting (line length: 100)
- Type hints required; checked with **mypy**
- Tests use **pytest** with fixtures in `tests/conftest.py`
- Pre-commit hooks enforce style on commit

## Key Patterns

- Configuration is defined inline in `TargetADBC.config_jsonschema` using Singer SDK's `th.Property` types
- Type conversion: `_json_type_to_arrow()` maps JSON Schema types to PyArrow types
- Value conversion: `_convert_value()` handles Python-to-Arrow value transformations
- Connection management: lazy initialization via `connection` property

## Testing

- Unit tests: `tests/test_target.py`
- E2E tests: `tests/e2e/test_duckdb.py`, `tests/e2e/test_sqlite.py`
- Fixtures provide test configs and sample Singer messages
- Tests use temporary databases (cleaned up automatically)

## Adding New Features

- **New config option**: Add to `config_jsonschema` in `target.py`
- **New data type**: Update `_json_type_to_arrow()` and `_convert_value()` in `sinks.py`
- **New database**: Just configure the driver name - no code changes needed
