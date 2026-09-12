"""Tests for the git-changed-only filter."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sql_guard.git_filter import changed_files, filter_to_changed


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


# --changed-base must name a revision, never a git option -------------------


@pytest.mark.parametrize(
    "base",
    ["--output=/tmp/sql-sop-should-not-exist", "-o/tmp/x", "--exit-code", "--help"],
)
def test_changed_base_rejects_option_like_values(base: str, tmp_path: Path, monkeypatch):
    """git reads a leading `-` as an option, so those values never reach it."""
    repo = _git_repo(tmp_path)
    monkeypatch.chdir(repo)
    with pytest.raises(ValueError, match="must be a git revision"):
        changed_files(base=base)


def test_option_like_base_does_not_reach_git(tmp_path: Path, monkeypatch):
    """The rejected value must not have been acted on before validation."""
    repo = _git_repo(tmp_path)
    monkeypatch.chdir(repo)
    target = tmp_path / "written-by-git"
    with pytest.raises(ValueError):
        changed_files(base=f"--output={target}")
    assert not target.exists()


def test_ordinary_ref_still_accepted(tmp_path: Path, monkeypatch):
    repo = _git_repo(tmp_path)
    (repo / "a.sql").write_text("SELECT 1;\n")
    _git("add", "a.sql", cwd=repo)
    _git("commit", "-q", "-m", "init", cwd=repo)
    monkeypatch.chdir(repo)
    assert changed_files(base="HEAD") is not None
