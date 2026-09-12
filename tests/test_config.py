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


def test_new_name_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / ".sql-sop.yml"
    _write(p, "disable:\n  - W001\n")
    found = find_config()
    assert found == p
    captured = capsys.readouterr()
    assert captured.out == ""
    cfg = load()
    assert "W001" in cfg.disable


def test_new_name_yaml_alias(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / ".sql-sop.yaml"
    _write(p, "disable:\n  - W002\n")
    found = find_config()
    assert found == p
    captured = capsys.readouterr()
    assert captured.out == ""
    cfg = load()
    assert "W002" in cfg.disable


def test_old_name_only_emits_deprecation_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / ".sql-guard.yml"
    _write(p, "disable:\n  - W001\n")
    found = find_config()
    assert found == p
    captured = capsys.readouterr()
    assert "Notice:" in captured.out
    assert ".sql-guard.yml is deprecated and will stop working in 0.12.0" in captured.out
    cfg = load()
    assert "W001" in cfg.disable


def test_both_present_prefers_sql_sop_and_warns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    monkeypatch.chdir(tmp_path)
    sop = tmp_path / ".sql-sop.yml"
    guard = tmp_path / ".sql-guard.yml"
    _write(sop, "disable:\n  - W001\n")
    _write(guard, "disable:\n  - W002\n")
    found = find_config()
    assert found == sop
    captured = capsys.readouterr()
    assert "Warning:" in captured.out
    assert "using .sql-sop.yml and ignoring .sql-guard.yml" in captured.out
    cfg = load()
    assert "W001" in cfg.disable
    assert "W002" not in cfg.disable

