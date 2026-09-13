"""Tests for the ``-- sql-sop:``/``-- sql-guard: disable=...`` directive parser and end-to-end suppression."""

from __future__ import annotations

import json
from pathlib import Path

from sql_guard import inline_disable
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


def test_parse_sql_sop_same_line_directive():
    dm = parse("SELECT * FROM t;  -- sql-sop: disable=W001\n")
    assert dm.is_disabled(1, "W001")
    assert not dm.is_disabled(1, "W002")


def test_parse_sql_sop_multiple_ids():
    dm = parse("SELECT * FROM t; -- sql-sop: disable=W001,W003\n")
    assert dm.is_disabled(1, "W001")
    assert dm.is_disabled(1, "W003")


def test_parse_sql_sop_disable_next_line():
    content = "-- sql-sop: disable-next-line=W001\nSELECT * FROM t;\n"
    dm = parse(content)
    assert dm.is_disabled(2, "W001")
    assert not dm.is_disabled(1, "W001")


def test_parse_sql_sop_bare_disable_silences_all():
    dm = parse("SELECT * FROM t; -- sql-sop: disable\n")
    assert dm.is_disabled(1, "W001")
    assert dm.is_disabled(1, "E001")
    assert ALL_RULES_TOKEN in dm.by_line[1]


def test_parse_sql_sop_python_hash_comment():
    dm = parse("# sql-sop: disable-next-line=P001\nq = f'SELECT {x}'\n")
    assert dm.is_disabled(2, "P001")


def test_parse_sql_sop_case_insensitive_ids():
    dm = parse("SELECT * FROM t; -- sql-sop: disable=w001\n")
    assert dm.is_disabled(1, "W001")


def test_check_file_respects_sql_sop_inline_disable(tmp_path: Path):
    sql = tmp_path / "demo.sql"
    sql.write_text("SELECT * FROM t; -- sql-sop: disable=W001\nSELECT * FROM other;\n")
    findings = check_file(sql, ALL_RULES)
    w001 = [f for f in findings if f.rule_id == "W001"]
    lines = sorted(f.line for f in w001)
    assert lines == [2]


def test_legacy_prefix_sets_flag_and_sql_sop_does_not():
    inline_disable.reset_legacy_directive_seen()
    parse("SELECT * FROM t; -- sql-sop: disable=W001\n")
    assert not inline_disable.legacy_directive_seen()

    inline_disable.reset_legacy_directive_seen()
    parse("SELECT * FROM t; -- sql-guard: disable=W001\n")
    assert inline_disable.legacy_directive_seen()
    inline_disable.reset_legacy_directive_seen()


def test_cli_legacy_directive_notice_once_on_stderr(tmp_path: Path):
    from typer.testing import CliRunner

    from sql_guard.cli import app

    # Two legacy directives in the run still produce a single notice.
    sql = tmp_path / "demo.sql"
    sql.write_text(
        "SELECT * FROM t; -- sql-guard: disable=W001\n"
        "-- sql-guard: disable-next-line=W002\n"
        "SELECT a, b FROM other;\n"
    )
    result = CliRunner().invoke(app, ["check", str(sql)])
    assert result.stderr.count("deprecated") == 1
    assert "0.12.0" in result.stderr
    # Diagnostics stay off stdout so `--format sarif` output stays parseable.
    assert "deprecated" not in result.stdout


def test_cli_sql_sop_directive_emits_no_notice(tmp_path: Path):
    from typer.testing import CliRunner

    from sql_guard.cli import app

    sql = tmp_path / "demo.sql"
    sql.write_text("SELECT * FROM t; -- sql-sop: disable=W001\n")
    result = CliRunner().invoke(app, ["check", str(sql)])
    assert "deprecated" not in result.stderr
    assert "deprecated" not in result.stdout


def test_cli_sarif_stdout_parseable_with_legacy_directive(tmp_path: Path):
    from typer.testing import CliRunner

    from sql_guard.cli import app

    sql = tmp_path / "demo.sql"
    sql.write_text("SELECT * FROM t; -- sql-guard: disable=W001\n")
    result = CliRunner().invoke(app, ["check", str(sql), "--format", "sarif"])
    assert "deprecated" in result.stderr
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"
