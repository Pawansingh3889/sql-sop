"""Tests for v0.6.0 rules + W019."""

from __future__ import annotations

from sql_guard.rules.errors import AlterAddNotNullNoDefault, DropColumn
from sql_guard.rules.tsql import CreateIndexWithoutOnline
from sql_guard.rules.warnings import (
    CountDistinctUnbounded,
    LeadingWildcardLike,
    OrAcrossColumns,
    TruncateTable,
)


def _line(rule, sql: str):
    return rule.check_line(sql, 1, "test.sql")


def _stmt(rule, sql: str):
    return rule.check_statement(sql, 1, "test.sql")


# E007 alter-add-not-null-no-default ------------------------------------------


def test_e007_flags_add_not_null_without_default():
    rule = AlterAddNotNullNoDefault()
    finding = _stmt(rule, "ALTER TABLE orders ADD status VARCHAR(20) NOT NULL;")
    assert finding is not None
    assert finding.rule_id == "E007"
    assert finding.severity == "error"


def test_e007_passes_when_default_supplied():
    rule = AlterAddNotNullNoDefault()
    assert _stmt(
        rule,
        "ALTER TABLE orders ADD status VARCHAR(20) NOT NULL DEFAULT 'NEW';",
    ) is None


def test_e007_passes_when_column_is_nullable():
    rule = AlterAddNotNullNoDefault()
    assert _stmt(rule, "ALTER TABLE orders ADD status VARCHAR(20) NULL;") is None


# E008 drop-column ------------------------------------------------------------


def test_e008_flags_drop_column():
    rule = DropColumn()
    finding = _stmt(rule, "ALTER TABLE orders DROP COLUMN legacy_id;")
    assert finding is not None
    assert finding.rule_id == "E008"
    assert finding.severity == "error"


def test_e008_does_not_flag_drop_table():
    rule = DropColumn()
    assert _stmt(rule, "DROP TABLE orders;") is None


# W017 leading-wildcard-like --------------------------------------------------


def test_w017_flags_leading_percent():
    rule = LeadingWildcardLike()
    finding = _line(rule, "WHERE name LIKE '%smith'")
    assert finding is not None
    assert finding.rule_id == "W017"


def test_w017_flags_leading_underscore():
    rule = LeadingWildcardLike()
    assert _line(rule, "WHERE code LIKE '_001'") is not None


def test_w017_passes_trailing_wildcard():
    rule = LeadingWildcardLike()
    assert _line(rule, "WHERE name LIKE 'smith%'") is None


def test_w017_handles_n_string_prefix():
    rule = LeadingWildcardLike()
    assert _line(rule, "WHERE name LIKE N'%smith'") is not None


# W018 or-across-columns ------------------------------------------------------


def test_w018_flags_or_across_different_columns():
    rule = OrAcrossColumns()
    finding = _stmt(rule, "SELECT * FROM t WHERE a = 1 OR b = 2;")
    assert finding is not None
    assert finding.rule_id == "W018"


def test_w018_passes_or_on_same_column():
    rule = OrAcrossColumns()
    assert _stmt(rule, "SELECT * FROM t WHERE a = 1 OR a = 2;") is None


# W020 truncate-table ---------------------------------------------------------


def test_w020_flags_truncate_table():
    rule = TruncateTable()
    finding = _line(rule, "TRUNCATE TABLE staging_orders;")
    assert finding is not None
    assert finding.rule_id == "W020"
    assert finding.severity == "warning"


def test_w020_does_not_flag_truncate_in_string():
    # Plain text "truncate" not followed by TABLE shouldn't fire.
    rule = TruncateTable()
    assert _line(rule, "-- consider truncating later") is None


# T005 create-index-without-online --------------------------------------------


def test_t005_flags_basic_create_index():
    rule = CreateIndexWithoutOnline()
    finding = _stmt(rule, "CREATE INDEX ix_orders_date ON orders (order_date);")
    assert finding is not None
    assert finding.rule_id == "T005"


def test_t005_passes_with_online_on():
    rule = CreateIndexWithoutOnline()
    assert _stmt(
        rule,
        "CREATE INDEX ix_orders_date ON orders (order_date) WITH (ONLINE = ON);",
    ) is None


def test_t005_flags_clustered_unique_variants():
    rule = CreateIndexWithoutOnline()
    assert _stmt(
        rule,
        "CREATE UNIQUE NONCLUSTERED INDEX ix ON orders (id);",
    ) is not None


# W019 count-distinct-unbounded -----------------------------------------------


def test_w019_flags_count_distinct_without_filter():
    rule = CountDistinctUnbounded()
    finding = _stmt(rule, "SELECT COUNT(DISTINCT user_id) FROM events;")
    assert finding is not None
    assert finding.rule_id == "W019"
    assert finding.severity == "warning"


def test_w019_passes_with_where():
    rule = CountDistinctUnbounded()
    assert (
        _stmt(
            rule,
            "SELECT COUNT(DISTINCT user_id) FROM events WHERE event_date >= '2024-01-01';",
        )
        is None
    )


def test_w019_passes_with_group_by():
    rule = CountDistinctUnbounded()
    assert (
        _stmt(
            rule,
            "SELECT tenant_id, COUNT(DISTINCT user_id) FROM events GROUP BY tenant_id;",
        )
        is None
    )


def test_w019_passes_with_limit():
    rule = CountDistinctUnbounded()
    assert (
        _stmt(rule, "SELECT COUNT(DISTINCT user_id) FROM events LIMIT 1;")
        is None
    )


def test_w019_handles_whitespace_in_count_distinct():
    rule = CountDistinctUnbounded()
    finding = _stmt(rule, "SELECT COUNT (  DISTINCT  user_id) FROM events;")
    assert finding is not None
    assert finding.rule_id == "W019"


def test_w019_does_not_fire_on_plain_count():
    rule = CountDistinctUnbounded()
    assert _stmt(rule, "SELECT COUNT(*) FROM events;") is None
    assert _stmt(rule, "SELECT COUNT(user_id) FROM events;") is None


# W015 join-function-on-column ------------------------------------------------


def test_w015_flags_upper_function_in_join_on():
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    finding = _line(
        rule, "JOIN customers c ON UPPER(o.email) = UPPER(c.email)"
    )
    assert finding is not None
    assert finding.rule_id == "W015"
    assert finding.severity == "warning"


def test_w015_flags_year_in_join_on():
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    finding = _line(rule, "JOIN events e ON YEAR(o.created_at) = YEAR(e.day)")
    assert finding is not None
    assert finding.rule_id == "W015"


def test_w015_passes_when_join_uses_materialized_columns():
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    assert _line(
        rule, "JOIN customers c ON o.email_lower = c.email_lower"
    ) is None


def test_w015_does_not_flag_function_in_where_only():
    """W003 owns the WHERE case; W015 should stay quiet there."""
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    assert _line(rule, "WHERE UPPER(email) = 'A@B.COM'") is None
