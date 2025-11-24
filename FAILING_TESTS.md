# Failing Built-in Target Tests

This document lists the built-in target tests from the Meltano SDK that are currently failing. These tests are marked as `XFAIL(strict=True)` in the test suite.

## Summary

- **Total built-in tests**: 16
- **Passing**: 15
- **Failing**: 1

## Failing Tests

### 1. Special Characters in Table Names

**Test**: `test_target_special_chars_in_attributes`

**Status**: XFAIL (strict=True)

**Error**:
```
adbc_driver_manager.InternalError: INTERNAL: Parser Error: syntax error at or near ":"

LINE 1: CREATE TABLE test:SpecialChars!in?attributes (_id VARCHAR, d VARCHAR, _sdc_e...
                         ^
```

**Root Cause**:
Table names containing special characters like `:`, `!`, `?` are not properly handled. DuckDB (and likely other databases via ADBC) cannot parse table names with these characters without proper quoting or escaping.

**Impact**:
- Cannot create tables with special characters in stream names
- May affect users with tap sources that produce stream names with special characters

**Suggested Fix**:
- Implement table name sanitization or quoting logic
- Consider using identifier quoting for table/column names
- May need to handle differently across database drivers (DuckDB, SQLite, PostgreSQL, etc.)

**GitHub Issue**: To be created

## Notes

- All tests use the DuckDB driver with default configuration
- The `strict=True` parameter ensures that if any of these tests start passing unexpectedly, the test suite will fail, alerting us to remove the XFAIL marker
- This approach allows us to track known issues while still maintaining a passing test suite
