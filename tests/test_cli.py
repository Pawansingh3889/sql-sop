"""End-to-end tests for the sql-sop command-line interface."""

from typer.testing import CliRunner

from sql_guard import __version__
from sql_guard.cli import app


def test_version_uses_sql_sop_name() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"sql-sop {__version__}"
