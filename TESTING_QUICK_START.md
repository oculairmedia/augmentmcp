# Testing Quick Start Guide

## Installation

### Install Test Dependencies

```bash
# Install pytest and plugins
pip install pytest pytest-asyncio pytest-cov pytest-mock inline-snapshot pytest-xdist

# Or use requirements-dev.txt
pip install -r requirements-dev.txt
```

### Create requirements-dev.txt

```txt
# Testing framework
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
pytest-mock>=3.12.0
pytest-xdist>=3.5.0

# Snapshot testing
inline-snapshot>=0.10.0

# Code quality
black>=24.0.0
ruff>=0.1.0
mypy>=1.8.0

# Development
ipython>=8.20.0
```

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_resources.py

# Run specific test class
pytest tests/unit/test_resources.py::TestCapabilitiesResource

# Run specific test function
pytest tests/unit/test_resources.py::TestCapabilitiesResource::test_returns_all_required_fields

# Run tests matching pattern
pytest -k "security"
```

### Coverage Commands

```bash
# Run with coverage
pytest --cov=augment_mcp --cov-report=html

# Run with coverage and show missing lines
pytest --cov=augment_mcp --cov-report=term-missing

# Generate coverage report
pytest --cov=augment_mcp --cov-report=html
# Open htmlcov/index.html in browser

# Fail if coverage below threshold
pytest --cov=augment_mcp --cov-fail-under=90
```

### Parallel Execution

```bash
# Run tests in parallel (auto-detect CPU cores)
pytest -n auto

# Run tests in parallel (specific number of workers)
pytest -n 4

# Parallel with coverage
pytest -n auto --cov=augment_mcp
```

### Snapshot Testing

```bash
# Create snapshots (first run)
pytest --inline-snapshot=create

# Update snapshots after changes
pytest --inline-snapshot=fix

# Review snapshot changes
pytest --inline-snapshot=review
```

### Watch Mode (Development)

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw

# Run with coverage
ptw -- --cov=augment_mcp
```

---

## Test Organization

### Directory Structure

```
tests/
├── __init__.py
├── conftest.py                 # Shared fixtures
├── unit/
│   ├── __init__.py
│   ├── test_resources.py       # Resource tests
│   ├── test_prompts.py         # Prompt tests
│   ├── test_tools.py           # Tool tests
│   ├── test_helpers.py         # Helper function tests
│   └── test_advanced_resources.py  # Advanced resource tests
├── integration/
│   ├── __init__.py
│   ├── test_workflows.py       # End-to-end workflows
│   └── test_error_handling.py  # Error scenarios
└── fixtures/
    ├── __init__.py
    ├── workspaces.py           # Workspace fixtures
    ├── commands.py             # Command file fixtures
    └── settings.py             # Settings file fixtures
```

### Running by Category

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run only resource tests
pytest tests/unit/test_resources.py

# Run only prompt tests
pytest tests/unit/test_prompts.py
```

---

## CI/CD Configuration

### GitHub Actions Workflow

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]

    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests with coverage
      run: |
        pytest --cov=augment_mcp --cov-report=xml --cov-report=term-missing
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v4
      with:
        file: ./coverage.xml
        fail_ci_if_error: true
    
    - name: Check coverage threshold
      run: |
        pytest --cov=augment_mcp --cov-fail-under=90

  lint:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: "3.11"
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install black ruff mypy
    
    - name: Run black
      run: black --check augment_mcp/ tests/
    
    - name: Run ruff
      run: ruff check augment_mcp/ tests/
    
    - name: Run mypy
      run: mypy augment_mcp/
```

### Pre-commit Hooks

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 24.1.1
    hooks:
      - id: black
        language_version: python3.11

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.15
    hooks:
      - id: ruff
        args: [--fix, --exit-non-zero-on-fix]

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
        args: [--cov=augment_mcp, --cov-fail-under=90]
```

Install pre-commit:
```bash
pip install pre-commit
pre-commit install
```

---

## Debugging Tests

### Run with Debug Output

```bash
# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Drop into debugger on failure
pytest --pdb

# Drop into debugger on first failure
pytest -x --pdb

# Show full traceback
pytest --tb=long
```

### Using pytest.set_trace()

```python
def test_something():
    result = some_function()
    
    # Drop into debugger here
    import pytest; pytest.set_trace()
    
    assert result == expected
```

### Using breakpoint()

```python
async def test_async_function():
    result = await some_async_function()
    
    # Drop into debugger (Python 3.7+)
    breakpoint()
    
    assert result == expected
```

---

## Common Test Patterns

### Testing Async Functions

```python
import pytest

@pytest.mark.asyncio
async def test_async_resource():
    """Test async resource function."""
    result = await get_capabilities.fn()
    assert "tools" in result
```

### Using Fixtures

```python
def test_with_workspace(tmp_workspace):
    """Test using temporary workspace fixture."""
    assert tmp_workspace.exists()
    assert (tmp_workspace / ".augment").exists()
```

### Parametrized Tests

```python
@pytest.mark.parametrize("focus_areas,expected", [
    ("all", ["sql injection", "xss", "auth"]),
    ("auth", ["authentication", "authorization"]),
    ("crypto", ["encryption", "hashing"]),
])
async def test_security_focus_areas(focus_areas, expected):
    """Test different security focus areas."""
    result = await security_review_prompt.fn(
        file_path="test.py",
        focus_areas=focus_areas
    )
    
    content = result[0].content.lower()
    for term in expected:
        assert term in content
```

### Testing Exceptions

```python
import pytest
from fastmcp.exceptions import ResourceError

async def test_invalid_workspace_raises_error():
    """Test that invalid workspace raises ResourceError."""
    with pytest.raises(ResourceError, match="Workspace not found"):
        await get_workspace_settings.fn("/nonexistent/path")
```

### Mocking

```python
from unittest.mock import AsyncMock, patch

async def test_with_mock():
    """Test with mocked dependency."""
    with patch("augment_mcp.auggie.run_auggie") as mock_auggie:
        mock_auggie.return_value = "mocked response"
        
        result = await augment_review.fn(
            instruction="test",
            paths=["test.py"]
        )
        
        assert result == "mocked response"
        mock_auggie.assert_called_once()
```

---

## Performance Testing

### Benchmark Tests

```bash
# Install pytest-benchmark
pip install pytest-benchmark

# Run benchmarks
pytest --benchmark-only

# Save benchmark results
pytest --benchmark-save=baseline

# Compare against baseline
pytest --benchmark-compare=baseline
```

### Example Benchmark Test

```python
def test_search_performance(benchmark, tmp_workspace):
    """Benchmark workspace search performance."""
    # Create test files
    for i in range(100):
        (tmp_workspace / f"file{i}.py").write_text("test content\n" * 100)
    
    # Benchmark the search
    result = benchmark(
        search_workspace.fn,
        workspace_path=str(tmp_workspace),
        query="test"
    )
    
    assert result["total_matches"] > 0
```

---

## Continuous Monitoring

### Coverage Badge

Add to README.md:
```markdown
[![codecov](https://codecov.io/gh/yourusername/augment-mcp-tool/branch/main/graph/badge.svg)](https://codecov.io/gh/yourusername/augment-mcp-tool)
```

### Test Status Badge

```markdown
[![Tests](https://github.com/yourusername/augment-mcp-tool/workflows/Tests/badge.svg)](https://github.com/yourusername/augment-mcp-tool/actions)
```

---

## Troubleshooting

### Common Issues

**Issue:** Tests hang indefinitely
```bash
# Solution: Add timeout
pytest --timeout=30
```

**Issue:** Async tests not running
```bash
# Solution: Install pytest-asyncio
pip install pytest-asyncio

# Add to pytest.ini or pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Issue:** Import errors
```bash
# Solution: Install package in editable mode
pip install -e .
```

**Issue:** Fixture not found
```bash
# Solution: Check conftest.py is in correct location
# Fixtures in tests/conftest.py are available to all tests
```

---

## Next Steps

1. ✅ Install test dependencies
2. ✅ Set up test directory structure
3. ✅ Create conftest.py with fixtures
4. ✅ Write first test
5. ✅ Run tests and verify
6. ✅ Set up CI/CD
7. ✅ Add coverage reporting
8. ✅ Configure pre-commit hooks

