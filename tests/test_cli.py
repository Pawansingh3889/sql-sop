"""End-to-end tests for the sql-sop command-line interface."""

import json
from pathlib import Path

from typer.testing import CliRunner

from sql_guard import __version__
from sql_guard.cli import app


def test_version_uses_sql_sop_name() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"sql-sop {__version__}"


def test_sarif_stdout_is_valid_json_when_dbt_warns(tmp_path: Path) -> None:
    # --dbt without a dbt_project.yml prints an advisory warning. It must
    # land on stderr so stdout stays parseable SARIF JSON.
    sql_file = tmp_path / "q.sql"
    sql_file.write_text("SELECT * FROM t;\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["check", str(sql_file), "--dbt", "--format", "sarif"]
    )

    assert result.exit_code == 0
    assert "no dbt_project.yml found" in result.stderr
    assert "--dbt" not in result.stdout
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["tool"]["driver"]["name"] == "sql-guard"
