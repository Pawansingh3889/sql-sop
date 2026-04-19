"""Tests for libCST-based Python scanning (P001-P004 plus SQL reuse)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("libcst")

from sql_guard import python_scanner
from sql_guard.checker import check, check_python_file, discover_files
from sql_guard.rules import get_rules

FIXTURES = Path(__file__).parent / "fixtures"
PY_FIXTURE = FIXTURES / "python_hazards.py"


# ---------------------------------------------------------------------------
# Scanner (extraction)
# ---------------------------------------------------------------------------


class TestScanner:
    def test_libcst_available(self) -> None:
        assert python_scanner.libcst_available() is True

    def test_extract_finds_fstring(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        assert any(h.kind == "fstring" and h.call_name == "execute" for h in hits)

    def test_extract_finds_concat(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        assert any(h.kind == "concat" for h in hits)

    def test_extract_finds_format(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        assert any(h.kind == "format" for h in hits)

    def test_extract_finds_percent(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        assert any(h.kind == "percent" for h in hits)

    def test_extract_finds_bare_name(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        assert any(h.kind == "name" and h.call_name == "execute" for h in hits)

    def test_extract_sql_literal_bodies(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        literals = [h.sql for h in python_scanner.iter_literal_sql(hits)]
        assert any("DELETE FROM audit_log" in s for s in literals)

    def test_extract_captures_variable_assignment(self) -> None:
        hits = python_scanner.extract_from_file(PY_FIXTURE)
        # `sql = "DELETE FROM staging"` must surface as a literal hit.
        assert any(h.kind == "literal" and "DELETE FROM staging" in h.sql for h in hits)
    def test_invalid_python_returns_empty(self) -> None:
        assert python_scanner.extract("def broken(:") == []


# ---------------------------------------------------------------------------
# Python-only rules (P001-P004)
# ---------------------------------------------------------------------------


class TestPythonRules:
    def _findings(self):
        rules = get_rules()
        return check_python_file(PY_FIXTURE, rules)

    def test_p001_fstring_flagged(self) -> None:
        f = self._findings()
        assert any(x.rule_id == "P001" for x in f)

    def test_p002_concat_flagged(self) -> None:
        f = self._findings()
        assert any(x.rule_id == "P002" for x in f)

    def test_p003_format_and_percent_flagged(self) -> None:
        f = self._findings()
        messages = [x.message for x in f if x.rule_id == "P003"]
        assert any(".format()" in m for m in messages)
        assert any("%" in m for m in messages)

    def test_p004_bare_variable_flagged(self) -> None:
        f = self._findings()
        assert any(x.rule_id == "P004" for x in f)

    def test_p004_is_warning_not_error(self) -> None:
        f = self._findings()
        p004 = [x for x in f if x.rule_id == "P004"]
        assert p004 and all(x.severity == "warning" for x in p004)

    def test_safe_parameterised_produces_no_p_findings(self) -> None:
        # The safe_parameterised function uses a literal SQL with a tuple
        # param — P-rules should not fire for it.
        hits = [
            h
            for h in python_scanner.extract_from_file(PY_FIXTURE)
            if "WHERE id = ?" in h.sql
        ]
        assert hits, "safe literal should be extracted"
        for hit in hits:
            assert hit.kind == "literal"


# ---------------------------------------------------------------------------
# Existing SQL rules re-applied to Python strings
# ---------------------------------------------------------------------------


class TestSqlRulesRunOnPython:
    def test_delete_without_where_in_python_is_flagged(self) -> None:
        rules = get_rules()
        findings = check_python_file(PY_FIXTURE, rules)
        assert any(x.rule_id == "E001" for x in findings)

    def test_disabled_rule_is_respected(self) -> None:
        rules = get_rules(disabled_ids={"E001"})
        findings = check_python_file(PY_FIXTURE, rules, disabled_rules={"E001"})
        assert not any(x.rule_id == "E001" for x in findings)


# ---------------------------------------------------------------------------
# Discovery + end-to-end check()
# ---------------------------------------------------------------------------


class TestDiscoveryAndCheck:
    def test_discover_skips_py_by_default(self) -> None:
        discovered = discover_files([str(FIXTURES)], include_python=False)
        assert not any(p.suffix == ".py" for p in discovered)

    def test_discover_picks_up_py_when_enabled(self) -> None:
        discovered = discover_files([str(FIXTURES)], include_python=True)
        assert any(p.name == "python_hazards.py" for p in discovered)

    def test_check_without_include_python_ignores_py(self) -> None:
        result = check([str(FIXTURES)])
        # No P-rule findings should appear when include_python=False.
        assert not any(f.rule_id.startswith("P") for f in result.findings)

    def test_check_with_include_python_surfaces_p_rules(self) -> None:
        result = check([str(FIXTURES)], include_python=True)
        ids = {f.rule_id for f in result.findings}
        assert {"P001", "P002", "P003", "P004"}.issubset(ids)
