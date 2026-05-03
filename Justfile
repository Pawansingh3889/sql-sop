# sql-guard development commands
# Install just: https://github.com/casey/just
# Run `just` (no args) to see all available commands

# Show available commands
default:
    @just --list

# Install dev dependencies (uv recommended for speed)
install:
    uv pip install -e ".[dev,structural]"

# Install via plain pip (fallback if uv is not available)
install-pip:
    pip install -e ".[dev,structural]"

# Run the full test suite
test:
    pytest tests/ -v

# Run tests with coverage report
cov:
    pytest tests/ -v --cov=sql_guard --cov-report=term --cov-report=xml

# Run only fast tests (skip integration / slow markers)
test-fast:
    pytest tests/ -v -m "not slow"

# Lint check (no auto-fix)
lint:
    ruff check sql_guard tests

# Auto-fix lint issues where possible
lint-fix:
    ruff check --fix sql_guard tests

# Format code with ruff
fmt:
    ruff format sql_guard tests

# Type check (non-blocking, prints warnings)
typecheck:
    -ty check sql_guard/

# Run lint + typecheck + tests in sequence (run before committing)
check: lint typecheck test

# Build sdist + wheel into dist/
build:
    python -m build

# Run sql-sop against the project's own examples (dogfooding)
dogfood:
    sql-sop check examples/

# Show the version sql-guard reports at runtime
version:
    @python -c "from sql_guard import __version__; print(__version__)"
