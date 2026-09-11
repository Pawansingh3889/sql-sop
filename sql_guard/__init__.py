"""sql-guard — fast rule-based SQL linter."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("sql-sop")
except PackageNotFoundError:  # pragma: no cover — only hit before install
    __version__ = "0.0.0+unknown"

from sql_guard.fluent import SqlGuard as SqlGuard
