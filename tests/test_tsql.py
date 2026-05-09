"""Tests for T-SQL-specific rules (T001-T006)."""

from __future__ import annotations

from sql_guard.rules.tsql import (
    CursorDeclaration,
    DeprecatedOuterJoin,
    SelectStarInto,
    WithNolock,
    XpCmdshell,
)
from sql_guard.rules.warnings import MissingLimit, OrderByWithoutLimit


def _check_line(rule, sql: str):
    return rule.check_line(sql, 1, "test.sql")


def _check_statement(rule, sql: str):
    return rule.check_statement(sql, 1, "test.sql")


# T001 with-nolock


def test_t001_flags_basic_nolock():
    rule = WithNolock()
    finding = _check_line(rule, "SELECT * FROM orders WITH (NOLOCK)")
    assert finding is not None
    assert finding.rule_id == "T001"
    assert finding.severity == "warning"


def test_t001_flags_nolock_with_whitespace():
    rule = WithNolock()
    assert _check_line(rule, "SELECT * FROM orders WITH ( NOLOCK )") is not None


def test_t001_case_insensitive():
    rule = WithNolock()
    assert _check_line(rule, "select * from t with (nolock)") is not None


def test_t001_does_not_flag_with_cte():
    rule = WithNolock()
    assert _check_line(rule, "WITH cte AS (SELECT 1) SELECT * FROM cte") is None


# T002 xp-cmdshell


def test_t002_flags_xp_cmdshell():
    rule = XpCmdshell()
    finding = _check_line(rule, "EXEC xp_cmdshell 'dir C:\\'")
    assert finding is not None
    assert finding.rule_id == "T002"
    assert finding.severity == "error"


def test_t002_case_insensitive():
    rule = XpCmdshell()
    assert _check_line(rule, "EXEC XP_CMDSHELL 'whoami'") is not None


def test_t002_does_not_flag_unrelated_procs():
    rule = XpCmdshell()
    assert _check_line(rule, "EXEC sp_executesql N'SELECT 1'") is None


# T003 cursor-declaration


def test_t003_flags_declare_cursor():
    rule = CursorDeclaration()
    finding = _check_line(rule, "DECLARE order_cursor CURSOR FOR SELECT id FROM orders")
    assert finding is not None
    assert finding.rule_id == "T003"
    assert finding.severity == "warning"


def test_t003_flags_declare_local_cursor():
    rule = CursorDeclaration()
    assert _check_line(rule, "DECLARE @c CURSOR") is not None


def test_t003_does_not_flag_declare_variable():
    rule = CursorDeclaration()
    assert _check_line(rule, "DECLARE @i INT = 0") is None


# T004 deprecated-outer-join


def test_t004_flags_star_equals():
    rule = DeprecatedOuterJoin()
    finding = _check_statement(rule, "SELECT * FROM a, b WHERE a.id *= b.id")
    assert finding is not None
    assert finding.rule_id == "T004"
    assert finding.severity == "error"


def test_t004_flags_equals_star():
    rule = DeprecatedOuterJoin()
    assert _check_statement(rule, "SELECT * FROM a, b WHERE a.id =* b.id") is not None


def test_t004_does_not_flag_compound_assignment():
    rule = DeprecatedOuterJoin()
    # @var *= expr is modern compound assignment, not an outer join.
    assert _check_statement(rule, "SET @counter *= 2") is None


def test_t004_does_not_flag_plain_assignment():
    rule = DeprecatedOuterJoin()
    assert _check_statement(rule, "SET @counter = 2") is None


def test_t004_does_not_flag_modern_joins():
    rule = DeprecatedOuterJoin()
    assert _check_statement(rule, "SELECT * FROM a LEFT OUTER JOIN b ON a.id = b.id") is None


# W002 / W006 FETCH NEXT regression coverage


def test_w002_accepts_tsql_fetch_next_pagination():
    rule = MissingLimit()
    sql = "SELECT id FROM orders ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY"
    assert _check_statement(rule, sql) is None


def test_w006_accepts_tsql_fetch_next_pagination():
    rule = OrderByWithoutLimit()
    sql = "SELECT id FROM orders ORDER BY id OFFSET 20 ROWS FETCH NEXT 10 ROWS ONLY"
    assert _check_statement(rule, sql) is None


def test_w002_still_accepts_fetch_first():
    rule = MissingLimit()
    sql = "SELECT id FROM orders ORDER BY id FETCH FIRST 10 ROWS ONLY"
    assert _check_statement(rule, sql) is None


# T006 select-into-without-typed-fields


def test_t006_flags_basic_select_star_into():
    rule = SelectStarInto()
    finding = _check_statement(rule, "SELECT * INTO staging_orders FROM orders;")
    assert finding is not None
    assert finding.rule_id == "T006"
    assert finding.severity == "warning"


def test_t006_flags_select_star_into_with_where():
    rule = SelectStarInto()
    sql = "SELECT * INTO archive_2024 FROM orders WHERE year = 2024;"
    assert _check_statement(rule, sql) is not None


def test_t006_flags_multiline_select_star_into():
    rule = SelectStarInto()
    sql = "SELECT *\nINTO staging_orders\nFROM orders;"
    assert _check_statement(rule, sql) is not None


def test_t006_case_insensitive():
    rule = SelectStarInto()
    assert _check_statement(rule, "select * into staging from orders;") is not None


def test_t006_does_not_flag_typed_columns():
    # The recommended pass form from the issue.
    rule = SelectStarInto()
    sql = "SELECT order_id, customer_id INTO staging_orders FROM orders;"
    assert _check_statement(rule, sql) is None


def test_t006_does_not_flag_single_column_into():
    rule = SelectStarInto()
    assert _check_statement(rule, "SELECT id INTO ids FROM orders;") is None


def test_t006_does_not_flag_select_star_without_into():
    rule = SelectStarInto()
    assert _check_statement(rule, "SELECT * FROM orders WHERE id = 1;") is None


def test_t006_does_not_flag_tsql_variable_assignment():
    # SELECT @x = COUNT(*) FROM ... is a T-SQL local-variable assignment,
    # not a SELECT * INTO target. No schema is being inferred.
    rule = SelectStarInto()
    assert _check_statement(rule, "SELECT @x = COUNT(*) FROM orders;") is None


def test_t006_does_not_flag_select_star_inside_cte():
    rule = SelectStarInto()
    sql = "WITH s AS (SELECT * FROM orders) SELECT id FROM s;"
    assert _check_statement(rule, sql) is None


def test_t006_message_mentions_runtime_schema():
    rule = SelectStarInto()
    finding = _check_statement(rule, "SELECT * INTO staging FROM orders;")
    assert finding is not None
    assert "runtime" in finding.message.lower() or "source" in finding.message.lower()
