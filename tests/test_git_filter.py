"""Tests for the git-changed-only filter."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sql_guard.git_filter import filter_to_changed


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git("init", "-q", "-b", "main", cwd=repo)
    _git("config", "user.email", "test@example.com", cwd=repo)
    _git("config", "user.name", "test", cwd=repo)
    _git("config", "commit.gpgsign", "false", cwd=repo)
    return repo


def test_returns_unfiltered_when_not_in_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    discovered = [tmp_path / "a.sql", tmp_path / "b.sql"]
    kept, used_git = filter_to_changed(discovered)
    assert used_git is False
    assert kept == discovered


def test_keeps_only_changed_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _git_repo(tmp_path)
    (repo / "a.sql").write_text("SELECT 1;\n")
    (repo / "b.sql").write_text("SELECT 1;\n")
    _git("add", "a.sql", "b.sql", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    # Modify only a.sql.
    (repo / "a.sql").write_text("SELECT 2;\n")
    monkeypatch.chdir(repo)

    discovered = [(repo / "a.sql"), (repo / "b.sql")]
    kept, used_git = filter_to_changed(discovered)
    assert used_git is True
    assert [p.name for p in kept] == ["a.sql"]


def test_picks_up_untracked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = _git_repo(tmp_path)
    (repo / "tracked.sql").write_text("SELECT 1;\n")
    _git("add", "tracked.sql", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    (repo / "new.sql").write_text("SELECT 1;\n")
    monkeypatch.chdir(repo)

    discovered = [(repo / "tracked.sql"), (repo / "new.sql")]
    kept, used_git = filter_to_changed(discovered)
    assert used_git is True
    assert [p.name for p in kept] == ["new.sql"]
