"""Tests for the fluent API."""

from __future__ import annotations

from pathlib import Path

from sql_guard.fluent import SqlGuard

FIXTURES = Path(__file__).parent / "fixtures"


class TestScanClean:
    def test_scan_clean_sql_passes(self) -> None:
        result = SqlGuard().scan("SELECT id, name FROM users WHERE active = true LIMIT 10;")
        assert result.passed
        assert len(result.findings) == 0

    def test_result_bool_clean(self) -> None:
        result = SqlGuard().scan("SELECT id, name FROM users WHERE active = true LIMIT 10;")
        assert bool(result) is True


class TestScanSelectStar:
    def test_scan_select_star_warns(self) -> None:
        result = SqlGuard().scan("SELECT * FROM users;")
        assert not result.passed
        w001 = [f for f in result.findings if f.rule_id == "W001"]
        assert len(w001) >= 1
        assert w001[0].severity == "warning"


class TestScanDeleteWithoutWhere:
    def test_scan_delete_without_where_errors(self) -> None:
        result = SqlGuard().scan("DELETE FROM orders;")
        assert not result.passed
        e001 = [f for f in result.findings if f.rule_id == "E001"]
        assert len(e001) >= 1
        assert e001[0].severity == "error"


class TestEnableFilter:
    def test_enable_filters_rules(self) -> None:
        # Only enable W001 -- should catch SELECT * but not other rules
        result = SqlGuard().enable("W001").scan("SELECT * FROM users;")
        rule_ids = {f.rule_id for f in result.findings}
        assert "W001" in rule_ids
        # Other rules should not fire
        assert "W002" not in rule_ids

    def test_enable_multiple(self) -> None:
        result = SqlGuard().enable("E001", "W001").scan("DELETE FROM orders;\nSELECT * FROM users;")
        rule_ids = {f.rule_id for f in result.findings}
        assert rule_ids <= {"E001", "W001"}


class TestDisableFilter:
    def test_disable_filters_rules(self) -> None:
        # Disable W001 -- SELECT * should not be caught
        result = SqlGuard().disable("W001").scan("SELECT * FROM users;")
        w001 = [f for f in result.findings if f.rule_id == "W001"]
        assert len(w001) == 0

    def test_disable_error(self) -> None:
        result = SqlGuard().disable("E001").scan("DELETE FROM orders;")
        e001 = [f for f in result.findings if f.rule_id == "E001"]
        assert len(e001) == 0


class TestSeverityFilter:
    def test_severity_filter(self) -> None:
        # SQL with both error and warning: DELETE without WHERE + SELECT *
        sql = "DELETE FROM orders;\nSELECT * FROM users;"
        result = SqlGuard().severity("error").scan(sql)
        # Warnings should be filtered out
        assert all(f.severity == "error" for f in result.findings)

    def test_severity_passed_ignores_warnings(self) -> None:
        # SELECT * triggers only a warning
        result = SqlGuard().severity("error").scan("SELECT * FROM users;")
        assert result.passed

    def test_severity_invalid(self) -> None:
        try:
            SqlGuard().severity("critical")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass


class TestScanFile:
    def test_scan_file(self) -> None:
        result = SqlGuard().scan_file(FIXTURES / "errors.sql")
        assert not result.passed
        assert result.files_checked == 1
        assert len(result.errors) >= 1

    def test_scan_file_clean(self) -> None:
        result = SqlGuard().severity("error").scan_file(FIXTURES / "clean.sql")
        assert result.passed


class TestScanDir:
    def test_scan_dir(self) -> None:
        result = SqlGuard().scan_dir(FIXTURES)
        # errors.sql, warnings.sql, clean.sql, contract_drift.sql
        assert result.files_checked == 4
        assert len(result.findings) > 0


class TestResultSummary:
    def test_result_summary(self) -> None:
        result = SqlGuard().scan("DELETE FROM orders;\nSELECT * FROM users;")
        summary = result.summary()
        assert "error" in summary or "warning" in summary
        assert "1 file" in summary

    def test_result_summary_clean(self) -> None:
        result = SqlGuard().scan("SELECT id FROM users WHERE active = true LIMIT 10;")
        summary = result.summary()
        assert "no issues" in summary

    def test_result_summary_pluralization(self) -> None:
        result = SqlGuard().scan("DELETE FROM a;\nDELETE FROM b;")
        summary = result.summary()
        # Should have plural "errors"
        errors = result.errors
        if len(errors) > 1:
            assert "errors" in summary


class TestResultBool:
    def test_result_bool(self) -> None:
        clean = SqlGuard().scan("SELECT id FROM users WHERE active = true LIMIT 10;")
        assert bool(clean) is True

        dirty = SqlGuard().scan("DELETE FROM orders;")
        assert bool(dirty) is False

    def test_result_len(self) -> None:
        result = SqlGuard().scan("DELETE FROM orders;")
        assert len(result) > 0

        clean = SqlGuard().scan("SELECT id FROM users WHERE active = true LIMIT 10;")
        assert len(clean) == 0
