"""End-to-end tests for the sql-sop command-line interface."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
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
    # "python -m sql_guard". TERM=dumb stops rich styling the help text:
    # on GitHub runners it adds ANSI codes between "Usage:" and "sql-sop".
    proc = subprocess.run(
        [sys.executable, "-m", "sql_guard", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "TERM": "dumb"},
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


def test_check_missing_contract_exits_2(tmp_path: Path) -> None:
    sql_file = tmp_path / "a.sql"
    sql_file.write_text("SELECT id FROM t LIMIT 10;\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["check", str(sql_file), "--contract", "nope.yml"])

    assert result.exit_code == 2
    assert "Contract file not found: nope.yml" in result.stderr
    assert result.stdout == ""


def test_check_invalid_contract_yaml_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.sql").write_text("SELECT id FROM t LIMIT 10;\n", encoding="utf-8")
    (tmp_path / "bad.yml").write_text("tables: [unclosed\n", encoding="utf-8")
    # Run from tmp_path so the error message carries the short relative
    # path the user typed (rich wraps long absolute paths at 80 chars).
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["check", "a.sql", "--contract", "bad.yml"])

    assert result.exit_code == 2
    assert "Failed to load contract bad.yml:" in result.stderr
    assert result.stdout == ""


def test_check_invalid_dbt_project_yaml_exits_2(tmp_path: Path) -> None:
    (tmp_path / "dbt_project.yml").write_text("name: [unclosed\n", encoding="utf-8")
    model_dir = tmp_path / "models"
    model_dir.mkdir()
    sql_file = model_dir / "a.sql"
    sql_file.write_text("SELECT id FROM t LIMIT 10;\n", encoding="utf-8")

    result = CliRunner().invoke(app, ["check", str(sql_file), "--dbt"])

    assert result.exit_code == 2
    assert "Failed to load dbt project" in result.stderr
    assert result.stdout == ""


def test_check_changed_only_outside_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Outside a git repo, --changed-only warns on stderr and still lints
    # every discovered file; tmp_path is outside any git repo.
    sql_file = tmp_path / "a.sql"
    sql_file.write_text("SELECT * FROM t LIMIT 10;\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(app, ["check", "a.sql", "--changed-only"])

    assert result.exit_code == 0
    assert "--changed-only: not in a git repo" in result.stderr
    assert "W001" in result.stdout


def test_check_sarif_output_writes_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.sql").write_text("SELECT * FROM t LIMIT 10;\n", encoding="utf-8")
    # Run from tmp_path so the status line names the short relative path
    # the user typed (rich wraps long absolute paths at 80 chars).
    monkeypatch.chdir(tmp_path)

    result = CliRunner().invoke(
        app, ["check", "a.sql", "--format", "sarif", "--output", "r.sarif"]
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Wrote SARIF to r.sarif" in result.stderr
    doc = json.loads((tmp_path / "r.sarif").read_text(encoding="utf-8"))
    assert doc["version"] == "2.1.0"


def test_check_disable_flag_suppresses_rule(tmp_path: Path) -> None:
    sql_file = tmp_path / "a.sql"
    sql_file.write_text("SELECT * FROM t LIMIT 10;\n", encoding="utf-8")

    baseline = CliRunner().invoke(app, ["check", str(sql_file)])
    assert "W001" in baseline.stdout

    result = CliRunner().invoke(app, ["check", str(sql_file), "--disable", "W001"])

    assert result.exit_code == 0
    assert "W001" not in result.stdout
    assert "no issues found" in result.stdout


def test_check_config_disable_suppresses_rule(tmp_path: Path) -> None:
    sql_file = tmp_path / "a.sql"
    sql_file.write_text("SELECT * FROM t LIMIT 10;\n", encoding="utf-8")
    config_file = tmp_path / ".sql-sop.yml"
    config_file.write_text("disable:\n  - W001\n", encoding="utf-8")

    result = CliRunner().invoke(
        app, ["check", str(sql_file), "--config", str(config_file)]
    )

    assert result.exit_code == 0
    assert "W001" not in result.stdout
    assert "no issues found" in result.stdout
