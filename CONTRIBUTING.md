# Contributing to target-adbc

Thank you for your interest in contributing to target-adbc! This document provides guidelines and instructions for contributing.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- Git
- A virtual environment tool (venv, virtualenv, or conda)

### Development Setup

1. **Fork and clone the repository**

```bash
git clone https://github.com/yourusername/target-adbc.git
cd target-adbc
```

2. **Create a virtual environment**

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. **Install in development mode**

```bash
# Install with dev dependencies and DuckDB for testing
pip install -e ".[dev,duckdb]"
```

4. **Verify installation**

```bash
target-adbc --help
pytest tests/
```

## Development Workflow

### Making Changes

1. **Create a feature branch**

```bash
git checkout -b feature/your-feature-name
```

2. **Make your changes**

Follow the code style guidelines below and add tests for new functionality.

3. **Run tests**

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=target_adbc --cov-report=html

# Run specific test file
pytest tests/test_target.py
```

4. **Run linting and type checking**

```bash
# Format code
ruff format target_adbc tests

# Check for issues
ruff check target_adbc tests

# Type checking
mypy target_adbc
```

5. **Commit your changes**

```bash
git add .
git commit -m "Add feature: description of changes"
```

6. **Push and create a pull request**

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Style Guidelines

### Python Style

- Follow PEP 8 guidelines
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use meaningful variable and function names
- Add docstrings for all public functions and classes

### Docstring Format

Use Google-style docstrings:

```python
def example_function(param1: str, param2: int) -> bool:
    """Short description of function.

    Longer description if needed.

    Args:
        param1: Description of param1.
        param2: Description of param2.

    Returns:
        Description of return value.

    Raises:
        ValueError: When invalid input is provided.
    """
    pass
```

### Import Order

1. Standard library imports
2. Third-party imports
3. Local application imports

Use `from __future__ import annotations` at the top of each file.

## Testing Guidelines

### Writing Tests

- Write tests for all new features
- Ensure tests are isolated and can run independently
- Use fixtures for common test setup
- Test both success and failure cases
- Aim for >80% code coverage

### Test Structure

```python
def test_feature_name():
    """Test description."""
    # Arrange - set up test data
    data = {"key": "value"}

    # Act - perform the action
    result = function_to_test(data)

    # Assert - verify the result
    assert result == expected_value
```

### Running Tests with Different Drivers

To test with optional drivers:

```bash
# Install optional driver
pip install adbc-driver-postgresql

# Run tests that require it
pytest tests/test_postgresql.py
```

## Adding Support for New Features

### Adding a New Configuration Option

1. Add the property to `target_adbc/settings.py`:

```python
new_option = th.Property(
    "new_option",
    th.StringType,
    default="default_value",
    description="Description of what this does.",
)
```

2. Use it in the sink or target:

```python
value = self.config.get("new_option")
```

3. Add tests in `tests/test_settings.py`
4. Document it in `README.md`

### Adding Support for a New Data Type

1. Update `_python_type_to_arrow()` in `target_adbc/sinks.py`
2. Update `_convert_value()` if special conversion is needed
3. Add test cases in `tests/test_sinks.py`

## Documentation

### Updating Documentation

When adding features:

1. Update README.md with examples
2. Add docstrings to new code
3. Update CHANGELOG.md
4. Add examples to the `examples/` directory if applicable

### Documentation Style

- Use clear, concise language
- Provide code examples for complex features
- Include both simple and advanced usage examples
- Link to relevant external documentation

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] New code has tests
- [ ] Documentation is updated
- [ ] Commit messages are clear and descriptive

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Description of testing performed

## Checklist
- [ ] Tests pass
- [ ] Documentation updated
- [ ] Follows code style guidelines
```

## Release Process

(For maintainers)

1. Update version in `pyproject.toml` and `__init__.py`
2. Update CHANGELOG.md
3. Create a git tag: `git tag v0.x.0`
4. Push tag: `git push origin v0.x.0`
5. Build and publish: `python -m build && twine upload dist/*`

## Getting Help

- **Issues**: Open an issue on GitHub for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions
- **Documentation**: Check the README and docstrings

## Code of Conduct

### Our Standards

- Be respectful and inclusive
- Welcome newcomers
- Focus on constructive feedback
- Prioritize the community

### Reporting Issues

If you experience unacceptable behavior, please report it to the project maintainers.

## License

By contributing, you agree that your contributions will be licensed under the Apache License 2.0.

---

Thank you for contributing to target-adbc! 🎉
