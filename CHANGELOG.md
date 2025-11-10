# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial implementation of Singer target for ADBC-compatible databases
- Support for DuckDB, SQLite, PostgreSQL, and other ADBC drivers
- Configurable batch processing with customizable batch sizes
- Three overwrite behaviors: append, replace, and fail
- Optional metadata columns for data lineage tracking
- Type conversion between Singer JSON Schema and PyArrow types
- Support for datetime, date, time, and complex types
- Comprehensive test suite with pytest
- Example configurations and sample data
- Full documentation in README.md
- Contributing guidelines

### Features
- Generic ADBC driver support - works with any ADBC-compatible database
- Efficient bulk loading using PyArrow and ADBC's `adbc_ingest`
- Schema inference from Singer SCHEMA messages
- Configurable table naming with prefix/suffix support
- Default schema configuration for databases that require it
- Connection parameter flexibility through `connection_kwargs`

## [0.1.0] - 2024-01-09

### Added
- Initial release
