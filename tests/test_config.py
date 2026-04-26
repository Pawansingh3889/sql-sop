"""Tests for ``.sql-guard.yml`` config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from sql_guard.config import Config, find_config, load


def _write(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_empty_config_when_no_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    cfg = load()
    assert cfg == Config()


def test_loads_explicit_path(tmp_path: Path):
    p = tmp_path / ".sql-guard.yml"
    _write(p, "disable:\n  - W005\n  - t001\nignore:\n  - vendor/\ninclude_python: true\n")
    cfg = load(p)
    assert cfg.disable == {"W005", "T001"}
    assert cfg.ignore == ["vendor/"]
    assert cfg.include_python is True
    assert cfg.source == p


def test_walks_up_to_find_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    project = tmp_path / "proj"
    nested = project / "src" / "deep"
    nested.mkdir(parents=True)
    _write(project / ".sql-guard.yml", "disable: [W001]\n")
    monkeypatch.chdir(nested)
    found = find_config()
    assert found is not None
    assert found.parent == project


def test_yaml_must_be_mapping(tmp_path: Path):
    p = tmp_path / ".sql-guard.yml"
    _write(p, "- just\n- a\n- list\n")
    with pytest.raises(ValueError):
        load(p)


def test_load_handles_yaml_alias(tmp_path: Path):
    p = tmp_path / ".sql-guard.yaml"  # also-supported extension
    _write(p, "disable:\n  - W001\n")
    cfg = load(p)
    assert "W001" in cfg.disable
