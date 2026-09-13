"""CLI tests for ``check --changed-only`` when git reports nothing to lint."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sql_guard.cli import app


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _clean_repo(tmp_path: Path) -> Path:
    """A git repo with one committed SQL file and no pending changes."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    _git("config", "commit.gpgsign", "false", cwd=repo)
    # SELECT * would trip W001 if the file were linted, so an empty result
    # proves the file was filtered out rather than checked and passed.
    (repo / "a.sql").write_text("SELECT * FROM t;\n", encoding="utf-8")
    _git("add", "a.sql", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    return repo


def test_sarif_stdout_is_valid_empty_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(_clean_repo(tmp_path))

    result = CliRunner().invoke(app, ["check", ".", "--changed-only", "--format", "sarif"])

    assert result.exit_code == 0
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"] == []
    assert "no changed files to lint" in result.stderr


def test_sarif_output_file_is_valid_empty_report(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _clean_repo(tmp_path)
    monkeypatch.chdir(repo)

    result = CliRunner().invoke(
        app, ["check", ".", "--changed-only", "--format", "sarif", "--output", "r.sarif"]
    )

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "Wrote SARIF to r.sarif" in result.stderr
    doc = json.loads((repo / "r.sarif").read_text(encoding="utf-8"))
    assert doc["runs"][0]["results"] == []


def test_terminal_format_keeps_early_exit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(_clean_repo(tmp_path))

    result = CliRunner().invoke(app, ["check", ".", "--changed-only"])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert "no changed files to lint" in result.stderr
