"""Tests for the ``-- sql-guard: disable=...`` directive parser and end-to-end suppression."""

from __future__ import annotations

from pathlib import Path

from sql_guard.checker import check_file
from sql_guard.inline_disable import ALL_RULES_TOKEN, parse
from sql_guard.rules import ALL_RULES


def test_parse_same_line_directive():
    dm = parse("SELECT * FROM t;  -- sql-guard: disable=W001\n")
    assert dm.is_disabled(1, "W001")
    assert not dm.is_disabled(1, "W002")


def test_parse_multiple_ids():
    dm = parse("SELECT * FROM t; -- sql-guard: disable=W001,W003\n")
    assert dm.is_disabled(1, "W001")
    assert dm.is_disabled(1, "W003")


def test_parse_disable_next_line():
    content = "-- sql-guard: disable-next-line=W001\nSELECT * FROM t;\n"
    dm = parse(content)
    assert dm.is_disabled(2, "W001")
    assert not dm.is_disabled(1, "W001")


def test_parse_bare_disable_silences_all():
    dm = parse("SELECT * FROM t; -- sql-guard: disable\n")
    assert dm.is_disabled(1, "W001")
    assert dm.is_disabled(1, "E001")
    assert ALL_RULES_TOKEN in dm.by_line[1]


def test_parse_python_hash_comment():
    dm = parse("# sql-guard: disable-next-line=P001\nq = f'SELECT {x}'\n")
    assert dm.is_disabled(2, "P001")


def test_parse_case_insensitive_ids():
    dm = parse("SELECT * FROM t; -- sql-guard: disable=w001\n")
    assert dm.is_disabled(1, "W001")


def test_check_file_respects_inline_disable(tmp_path: Path):
    sql = tmp_path / "demo.sql"
    sql.write_text("SELECT * FROM t; -- sql-guard: disable=W001\nSELECT * FROM other;\n")
    findings = check_file(sql, ALL_RULES)
    w001 = [f for f in findings if f.rule_id == "W001"]
    # Line 1 is suppressed; line 2 still fires.
    lines = sorted(f.line for f in w001)
    assert lines == [2]


def test_check_file_respects_disable_next_line(tmp_path: Path):
    sql = tmp_path / "demo.sql"
    sql.write_text("-- sql-guard: disable-next-line=W001\nSELECT * FROM t;\n")
    findings = check_file(sql, ALL_RULES)
    assert not any(f.rule_id == "W001" for f in findings)
