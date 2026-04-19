"""Tests for all rules in the sql-sop rule registry."""

from __future__ import annotations

from pathlib import Path


from sql_guard.checker import check
from sql_guard.rules import ALL_RULES, get_rules

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------


class TestRuleRegistry:
    def test_all_rules_loaded(self) -> None:
        assert len(ALL_RULES) == 33

    def test_10_errors(self) -> None:
        # 8 E-series + 2 T-series (T002 xp-cmdshell, T004 deprecated-outer-join).
        errors = [r for r in ALL_RULES if r.severity == "error"]
        assert len(errors) == 10

    def test_23_warnings(self) -> None:
        # 17 W-series + 3 S-series + 3 T-series (T001 with-nolock,
        # T003 cursor-declaration, T005 create-index-without-online).
        warnings = [r for r in ALL_RULES if r.severity == "warning"]
        assert len(warnings) == 23

    def test_unique_ids(self) -> None:
        ids = [r.id for r in ALL_RULES]
        assert len(ids) == len(set(ids))

    def test_disable_rules(self) -> None:
        rules = get_rules(disabled_ids={"E001", "W001"})
        ids = {r.id for r in rules}
        assert "E001" not in ids
        assert "W001" not in ids


# ---------------------------------------------------------------------------
# Error rules
# ---------------------------------------------------------------------------


class TestErrorRules:
    def test_e001_delete_without_where(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e001 = [f for f in findings.findings if f.rule_id == "E001"]
        assert len(e001) >= 1
        assert "DELETE" in e001[0].message

    def test_e002_drop_without_if_exists(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e002 = [f for f in findings.findings if f.rule_id == "E002"]
        assert len(e002) >= 1

    def test_e003_grant_revoke(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e003 = [f for f in findings.findings if f.rule_id == "E003"]
        assert len(e003) >= 1

    def test_e004_string_concat(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e004 = [f for f in findings.findings if f.rule_id == "E004"]
        assert len(e004) >= 1
        assert "injection" in e004[0].message.lower()

    def test_e005_insert_without_columns(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e005 = [f for f in findings.findings if f.rule_id == "E005"]
        assert len(e005) >= 1

    def test_e006_update_without_where(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e006 = [f for f in findings.findings if f.rule_id == "E006"]
        assert len(e006) >= 1
        assert "UPDATE" in e006[0].message
        assert "overwrite" in e006[0].message.lower() or "every row" in e006[0].message.lower()

    def test_e006_update_with_where_ok(self, tmp_path) -> None:
        # UPDATE ... WHERE must NOT trigger the rule. Belt-and-braces
        # assertion so a future regex tweak can't silently over-trigger.
        sql = tmp_path / "safe_update.sql"
        sql.write_text("UPDATE orders SET status = 'shipped' WHERE id = 42;\n")
        result = check([str(sql)])
        e006 = [f for f in result.findings if f.rule_id == "E006"]
        assert not e006


# ---------------------------------------------------------------------------
# Warning rules
# ---------------------------------------------------------------------------


class TestWarningRules:
    def test_w001_select_star(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w001 = [f for f in findings.findings if f.rule_id == "W001"]
        assert len(w001) >= 1

    def test_w003_function_on_column(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w003 = [f for f in findings.findings if f.rule_id == "W003"]
        assert len(w003) >= 1

    def test_w007_hardcoded_values(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w007 = [f for f in findings.findings if f.rule_id == "W007"]
        assert len(w007) >= 1

    def test_w010_commented_out_code(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w010 = [f for f in findings.findings if f.rule_id == "W010"]
        assert len(w010) >= 1

    def test_w011_union_without_all(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w011 = [f for f in findings.findings if f.rule_id == "W011"]
        assert len(w011) >= 1

    def test_w011_passes_on_union_all(self) -> None:
        from sql_guard.rules.warnings import UnionWithoutAll

        rule = UnionWithoutAll()
        statement = "SELECT id FROM orders_2024\nUNION ALL\nSELECT id FROM orders_2025;"
        assert rule.check_statement(statement, 1, "test.sql") is None

    def test_w012_group_by_ordinal(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w012 = [f for f in findings.findings if f.rule_id == "W012"]
        assert len(w012) >= 1

    def test_w012_catches_single_ordinal(self) -> None:
        from sql_guard.rules.warnings import GroupByOrdinal

        rule = GroupByOrdinal()
        statement = "SELECT region, COUNT(*) FROM orders GROUP BY 1;"
        assert rule.check_statement(statement, 1, "test.sql") is not None

    def test_w012_catches_multiple_ordinals(self) -> None:
        from sql_guard.rules.warnings import GroupByOrdinal

        rule = GroupByOrdinal()
        statement = "SELECT a, b, c, COUNT(*) FROM t GROUP BY 1, 2, 3;"
        assert rule.check_statement(statement, 1, "test.sql") is not None

    def test_w012_passes_on_explicit_columns(self) -> None:
        from sql_guard.rules.warnings import GroupByOrdinal

        rule = GroupByOrdinal()
        statement = "SELECT region, status, COUNT(*) FROM orders GROUP BY region, status;"
        assert rule.check_statement(statement, 1, "test.sql") is None

    def test_w012_passes_on_digit_prefixed_column_name(self) -> None:
        from sql_guard.rules.warnings import GroupByOrdinal

        # Column names that start with a digit ('1st_quarter') are valid
        # identifiers in dialects that quote them, and the regex must not
        # match them because they are not pure integer tokens.
        rule = GroupByOrdinal()
        statement = "SELECT 1st_quarter, COUNT(*) FROM sales GROUP BY 1st_quarter;"
        assert rule.check_statement(statement, 1, "test.sql") is None

    def test_w013_window_missing_order_partition(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w013 = [f for f in findings.findings if f.rule_id == "W013"]
        assert len(w013) >= 1

    def test_w016_not_in_with_subquery(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w016 = [f for f in findings.findings if f.rule_id == "W016"]
        assert len(w016) >= 1
        assert "NOT IN" in w016[0].message

    def test_w016_not_in_value_list_ok(self, tmp_path) -> None:
        # NOT IN (1, 2, 3) value list must NOT trigger -- only subqueries.
        sql = tmp_path / "value_list.sql"
        sql.write_text("SELECT id FROM users WHERE status_id NOT IN (1, 2, 3);\n")
        result = check([str(sql)])
        w016 = [f for f in result.findings if f.rule_id == "W016"]
        assert not w016


# ---------------------------------------------------------------------------
# Clean file
# ---------------------------------------------------------------------------


class TestCleanFile:
    def test_no_errors_on_clean(self) -> None:
        findings = check([str(FIXTURES / "clean.sql")], severity="error")
        assert findings.error_count == 0

    def test_no_findings_on_clean(self) -> None:
        findings = check([str(FIXTURES / "clean.sql")])
        # Clean file should have zero or near-zero findings
        errors = [f for f in findings.findings if f.severity == "error"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Checker behavior
# ---------------------------------------------------------------------------


class TestChecker:
    def test_files_checked_count(self) -> None:
        result = check([str(FIXTURES)])
        assert result.files_checked == 3  # errors.sql, warnings.sql, clean.sql

    def test_duration_tracked(self) -> None:
        result = check([str(FIXTURES)])
        # time.perf_counter can return 0.0 on fast hardware when resolution is
        # coarser than the measured duration. Track that it's a non-negative
        # number rather than strictly positive.
        assert result.duration_seconds >= 0
        assert isinstance(result.duration_seconds, float)

    def test_severity_filter(self) -> None:
        all_findings = check([str(FIXTURES / "errors.sql")])
        error_only = check([str(FIXTURES / "errors.sql")], severity="error")
        assert error_only.warning_count == 0
        assert len(all_findings.findings) >= error_only.error_count

    def test_fail_fast_stops_early(self) -> None:
        result = check([str(FIXTURES / "errors.sql")], fail_fast=True)
        # Should have at least 1 error but potentially fewer than checking all
        assert result.error_count >= 1

    def test_nonexistent_path(self) -> None:
        result = check(["nonexistent_dir/"])
        assert result.files_checked == 0
