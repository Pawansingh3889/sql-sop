"""End-to-end tests for the sql-sop command-line interface."""

import json
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from sql_guard import __version__
from sql_guard.cli import app


def test_version_uses_sql_sop_name() -> None:
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"sql-sop {__version__}"


def test_list_rules_shows_dbt_pack() -> None:
    # The dbt rules are built per project (--dbt), but their metadata are
    # class attributes, so list-rules can catalogue them without a
    # discovered dbt project.
    result = CliRunner().invoke(app, ["list-rules"])

    assert result.exit_code == 0
    for rule_id in ("DBT001", "DBT002", "DBT003", "DBT004", "DBT005", "DBT006", "DBT007"):
        assert rule_id in result.stdout
    assert "--dbt" in result.stdout


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


def test_module_invocation_version() -> None:
    # `python -m sql_guard` is the entry point for environments where the
    # scripts dir is not on PATH; it must run the same CLI as `sql-sop`.
    proc = subprocess.run(
        [sys.executable, "-m", "sql_guard", "version"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert proc.stdout.startswith("sql-sop")


def test_module_invocation_prog_name() -> None:
    # __main__.py pins prog_name so the usage line says sql-sop, not
    # "python -m sql_guard".
    proc = subprocess.run(
        [sys.executable, "-m", "sql_guard", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "Usage: sql-sop" in proc.stdout


def test_module_invocation_check(tmp_path: Path) -> None:
    sql_file = tmp_path / "ok.sql"
    sql_file.write_text("SELECT id FROM t LIMIT 10;\n", encoding="utf-8")

    proc = subprocess.run(
        [sys.executable, "-m", "sql_guard", "check", str(sql_file)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert proc.returncode == 0
    assert "no issues found" in proc.stdout
