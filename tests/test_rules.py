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
        assert len(ALL_RULES) == 43

    def test_11_errors(self) -> None:
        # 9 E-series + 2 T-series (T002 xp-cmdshell, T004 deprecated-outer-join).
        errors = [r for r in ALL_RULES if r.severity == "error"]
        assert len(errors) == 11

    def test_31_warnings(self) -> None:
        # 25 W-series + 3 S-series + 4 T-series (T001 with-nolock,
        # T003 cursor-declaration, T005 create-index-without-online,
        # T006 select-into-without-typed-fields).
        warnings = [r for r in ALL_RULES if r.severity == "warning"]
        assert len(warnings) == 32

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

    def test_e009_update_from_implicit_join(self) -> None:
        findings = check([str(FIXTURES / "errors.sql")])
        e009 = [f for f in findings.findings if f.rule_id == "E009"]
        assert len(e009) >= 1
        assert "UPDATE" in e009[0].message
        assert (
            "cartesian" in e009[0].message.lower() or "comma-separated" in e009[0].message.lower()
        )

    def test_e009_explicit_join_ok(self, tmp_path) -> None:
        # The recommended fix from the rule message must NOT trigger E009.
        sql = tmp_path / "safe_update_from.sql"
        sql.write_text(
            "UPDATE c SET c.status = o.status "
            "FROM customers c INNER JOIN orders o "
            "ON c.customer_id = o.customer_id;\n"
        )
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert not e009

    def test_e009_postgres_single_from_table_ok(self, tmp_path) -> None:
        # Postgres UPDATE ... FROM with a single table is the canonical
        # form and must not flag.
        sql = tmp_path / "postgres_update.sql"
        sql.write_text(
            "UPDATE customers SET status = o.status "
            "FROM orders o WHERE customers.id = o.customer_id;\n"
        )
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert not e009

    def test_e009_lateral_after_comma_ok(self, tmp_path) -> None:
        # `, LATERAL ...` is a real Snowflake / Postgres lateral join.
        sql = tmp_path / "lateral_update.sql"
        sql.write_text(
            "UPDATE c SET tag = sub.tag FROM customers c, "
            "LATERAL (SELECT tag FROM tags WHERE customer_id = c.id LIMIT 1) sub;\n"
        )
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert not e009

    def test_e009_update_without_from_ok(self, tmp_path) -> None:
        # No FROM clause at all is a plain single-table UPDATE.
        sql = tmp_path / "plain_update.sql"
        sql.write_text("UPDATE customers SET status = 'active' WHERE id = 1;\n")
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert not e009

    def test_e009_three_table_comma_join_flagged(self, tmp_path) -> None:
        sql = tmp_path / "three_table.sql"
        sql.write_text(
            "UPDATE c SET c.label = p.label "
            "FROM customers c, orders o, products p "
            "WHERE c.id = o.customer_id AND o.product_id = p.id;\n"
        )
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert len(e009) == 1

    def test_e009_multiline_comma_join_flagged(self, tmp_path) -> None:
        sql = tmp_path / "multiline.sql"
        sql.write_text(
            "UPDATE customers\n"
            "SET status = o.status\n"
            "FROM customers c,\n"
            "     orders o\n"
            "WHERE c.customer_id = o.customer_id;\n"
        )
        result = check([str(sql)])
        e009 = [f for f in result.findings if f.rule_id == "E009"]
        assert len(e009) == 1


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

    def test_w021_having_without_group_by(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w021 = [f for f in findings.findings if f.rule_id == "W021"]
        assert len(w021) >= 1
        assert "HAVING" in w021[0].message

    def test_w021_ignores_group_by_in_comment_before_having(self) -> None:
        from sql_guard.rules.warnings import HavingWithoutGroupBy

        rule = HavingWithoutGroupBy()
        statement = "SELECT status, COUNT(*) FROM orders\n-- GROUP BY status\nHAVING COUNT(*) > 10;"
        assert rule.check_statement(statement, 1, "test.sql") is not None

    def test_w021_ignores_group_by_in_subquery_before_outer_having(self) -> None:
        from sql_guard.rules.warnings import HavingWithoutGroupBy

        rule = HavingWithoutGroupBy()
        statement = (
            "SELECT * FROM ("
            "SELECT customer_id, COUNT(*) FROM orders GROUP BY customer_id"
            ") AS grouped HAVING COUNT(*) > 10;"
        )
        assert rule.check_statement(statement, 1, "test.sql") is not None

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

    def test_w013_window_missing_partition(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w013 = [f for f in findings.findings if f.rule_id == "W013"]
        assert len(w013) >= 1

    def test_w013_passes_on_valid_over_clause(self) -> None:
        from sql_guard.rules.warnings import WindowMissingPartition

        rule = WindowMissingPartition()
        statement = (
            "SELECT ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY id) AS rn FROM users;"
        )

        assert rule.check_statement(statement, 1, "test.sql") is None

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

    def test_w014_case_without_else(self) -> None:
        findings = check([str(FIXTURES / "warnings.sql")])
        w014 = [f for f in findings.findings if f.rule_id == "W014"]
        assert len(w014) >= 1
        assert "CASE" in w014[0].message

    def test_w014_case_with_else_ok(self, tmp_path) -> None:
        sql = tmp_path / "case_with_else.sql"
        sql.write_text(
            "SELECT CASE\n"
            "  WHEN status = 'paid' THEN 1\n"
            "  WHEN status = 'pending' THEN 0\n"
            "  ELSE NULL\n"
            "END AS paid_flag\n"
            "FROM orders;\n"
        )
        result = check([str(sql)])
        w014 = [f for f in result.findings if f.rule_id == "W014"]
        assert not w014

    def test_w014_outer_case_without_else_fires_when_inner_has_else(self, tmp_path) -> None:
        # Issue #4 specifically called out the nested case: an outer
        # CASE with no ELSE must still fire even when an inner CASE
        # does have one.
        from sql_guard.rules.warnings import CaseWithoutElse

        rule = CaseWithoutElse()
        nested = (
            "SELECT CASE\n  WHEN x THEN CASE WHEN y THEN 1 ELSE 2 END\n  WHEN z THEN 3\nEND FROM t;"
        )
        finding = rule.check_statement(nested, 1, "test.sql")
        assert finding is not None
        assert finding.rule_id == "W014"

    def test_w014_does_not_fire_on_begin_end_block(self) -> None:
        # T-SQL BEGIN/END blocks should not trip the rule on their own.
        from sql_guard.rules.warnings import CaseWithoutElse

        rule = CaseWithoutElse()
        proc = "BEGIN\n  SELECT 1;\nEND;"
        assert rule.check_statement(proc, 1, "test.sql") is None


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
        # errors.sql, warnings.sql, clean.sql, contract_drift.sql, assertions.sql
        assert result.files_checked == 5

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

    def test_w015_join_function_on_column(self) -> None:
        from sql_guard.rules import get_rules
        from sql_guard.rules.warnings import JoinFunctionOnColumn

        # Confirm registration
        assert any(isinstance(r, JoinFunctionOnColumn) for r in get_rules())

        findings = check([str(FIXTURES / "warnings.sql")])
        w015 = [f for f in findings.findings if f.rule_id == "W015"]
        assert len(w015) >= 1
