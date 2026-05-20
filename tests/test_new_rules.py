"""Tests for v0.6.0 rules + W019."""

from __future__ import annotations

from sql_guard.rules.errors import AlterAddNotNullNoDefault, DropColumn
from sql_guard.rules.tsql import CreateIndexWithoutOnline
from sql_guard.rules.warnings import (
    AssertionMalformed,
    CountDistinctUnbounded,
    CrossJoinExplicit,
    LeadingWildcardLike,
    OrAcrossColumns,
    ScalarUdfInWhere,
    SelectDistinctSuspicious,
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
    assert (
        _stmt(
            rule,
            "ALTER TABLE orders ADD status VARCHAR(20) NOT NULL DEFAULT 'NEW';",
        )
        is None
    )


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
    assert (
        _stmt(
            rule,
            "CREATE INDEX ix_orders_date ON orders (order_date) WITH (ONLINE = ON);",
        )
        is None
    )


def test_t005_flags_clustered_unique_variants():
    rule = CreateIndexWithoutOnline()
    assert (
        _stmt(
            rule,
            "CREATE UNIQUE NONCLUSTERED INDEX ix ON orders (id);",
        )
        is not None
    )


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
    assert _stmt(rule, "SELECT COUNT(DISTINCT user_id) FROM events LIMIT 1;") is None


def test_w019_handles_whitespace_in_count_distinct():
    rule = CountDistinctUnbounded()
    finding = _stmt(rule, "SELECT COUNT (  DISTINCT  user_id) FROM events;")
    assert finding is not None
    assert finding.rule_id == "W019"


def test_w019_does_not_fire_on_plain_count():
    rule = CountDistinctUnbounded()
    assert _stmt(rule, "SELECT COUNT(*) FROM events;") is None
    assert _stmt(rule, "SELECT COUNT(user_id) FROM events;") is None


# W023 scalar-udf-in-where ----------------------------------------------------


def test_w023_flags_dbo_udf_in_where():
    rule = ScalarUdfInWhere()
    finding = _stmt(
        rule,
        "SELECT order_id FROM orders WHERE dbo.fn_IsHighValue(total) = 1;",
    )
    assert finding is not None
    assert finding.rule_id == "W023"
    assert finding.severity == "warning"


def test_w023_flags_schema_udf_in_where():
    rule = ScalarUdfInWhere()
    finding = _stmt(
        rule,
        "SELECT id FROM t WHERE myschema.fn_X(col) = 1;",
    )
    assert finding is not None
    assert finding.rule_id == "W023"


def test_w023_passes_len_builtin_in_where():
    rule = ScalarUdfInWhere()
    assert _stmt(rule, "SELECT id FROM users WHERE LEN(name) > 5;") is None


def test_w023_passes_upper_builtin_in_where():
    rule = ScalarUdfInWhere()
    assert _stmt(rule, "SELECT id FROM users WHERE UPPER(name) = 'X';") is None


def test_w023_passes_udf_in_select_list_only():
    rule = ScalarUdfInWhere()
    assert _stmt(rule, "SELECT dbo.fn_X(col) FROM t WHERE id = 1;") is None


def test_w023_flags_udf_in_having():
    rule = ScalarUdfInWhere()
    finding = _stmt(
        rule,
        "SELECT col, COUNT(*) FROM t GROUP BY col HAVING dbo.fn_X(col) > 0;",
    )
    assert finding is not None
    assert finding.rule_id == "W023"


def test_w023_flags_udf_in_join_on():
    rule = ScalarUdfInWhere()
    finding = _stmt(
        rule,
        "SELECT a.id FROM a JOIN b ON dbo.fn_X(a.id) = b.id;",
    )
    assert finding is not None
    assert finding.rule_id == "W023"


def test_w023_flags_inner_where_in_exists():
    rule = ScalarUdfInWhere()
    finding = _stmt(
        rule,
        "SELECT id FROM t WHERE EXISTS (SELECT 1 FROM x WHERE dbo.fn_X(col) = 1);",
    )
    assert finding is not None
    assert finding.rule_id == "W023"


def test_w023_passes_plain_where():
    rule = ScalarUdfInWhere()
    assert _stmt(rule, "SELECT id FROM orders WHERE total > 1000;") is None


def test_w023_passes_table_column_reference():
    rule = ScalarUdfInWhere()
    assert _stmt(rule, "SELECT id FROM t WHERE x.y = 1;") is None


# W015 join-function-on-column ------------------------------------------------


def test_w015_flags_upper_function_in_join_on():
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    finding = _line(rule, "JOIN customers c ON UPPER(o.email) = UPPER(c.email)")
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
    assert _line(rule, "JOIN customers c ON o.email_lower = c.email_lower") is None


def test_w015_does_not_flag_function_in_where_only():
    """W003 owns the WHERE case; W015 should stay quiet there."""
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    assert _line(rule, "WHERE UPPER(email) = 'A@B.COM'") is None


def test_w015_does_not_flag_clean_join_with_dirty_where():
    """W015 must stop at the next clause keyword so it doesn't poach W003's WHERE case."""
    from sql_guard.rules.warnings import JoinFunctionOnColumn

    rule = JoinFunctionOnColumn()
    sql = (
        "SELECT * FROM orders o "
        "JOIN customers c ON o.customer_id = c.id "
        "WHERE UPPER(o.email) = 'A@B.COM'"
    )
    assert _line(rule, sql) is None


# W022 cross-join-explicit ----------------------------------------------------


def test_w022_flags_explicit_cross_join():
    rule = CrossJoinExplicit()
    finding = _line(rule, "SELECT * FROM products p CROSS JOIN regions r;")
    assert finding is not None
    assert finding.rule_id == "W022"
    assert finding.severity == "warning"


def test_w022_flags_cross_join_case_insensitive():
    rule = CrossJoinExplicit()
    finding = _line(rule, "select * from products cross join regions;")
    assert finding is not None
    assert finding.rule_id == "W022"


def test_w022_passes_regular_inner_join():
    rule = CrossJoinExplicit()
    assert _line(rule, "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id;") is None


def test_w022_passes_left_join():
    rule = CrossJoinExplicit()
    assert (
        _line(
            rule,
            "SELECT * FROM orders o LEFT JOIN customers c ON o.customer_id = c.id;",
        )
        is None
    )


def test_w022_flags_cross_join_with_subquery():
    rule = CrossJoinExplicit()
    finding = _line(
        rule, "SELECT * FROM calendar_dates CROSS JOIN (SELECT 1 AS n UNION ALL SELECT 2);"
    )
    assert finding is not None
    assert finding.rule_id == "W022"


def test_w022_does_not_flag_cross_join_inside_trailing_comment():
    # 'CROSS JOIN' mentioned in a trailing comment must not trip the rule.
    rule = CrossJoinExplicit()
    assert (
        _line(
            rule,
            "SELECT * FROM orders o JOIN customers c ON o.id = c.id;  -- avoid CROSS JOIN here",
        )
        is None
    )


# W024 select-distinct-suspicious ---------------------------------------------


def test_w024_flags_distinct_with_inner_join():
    rule = SelectDistinctSuspicious()
    finding = _stmt(
        rule,
        "SELECT DISTINCT c.id, c.name FROM customers c JOIN orders o ON c.id = o.customer_id;",
    )
    assert finding is not None
    assert finding.rule_id == "W024"
    assert finding.severity == "warning"


def test_w024_flags_distinct_with_left_join():
    rule = SelectDistinctSuspicious()
    sql = "SELECT DISTINCT a.id FROM a LEFT JOIN b ON a.id = b.a_id;"
    assert _stmt(rule, sql) is not None


def test_w024_flags_distinct_with_join_multiline():
    rule = SelectDistinctSuspicious()
    sql = (
        "SELECT DISTINCT\n  c.id, c.name\nFROM customers c\nJOIN orders o ON c.id = o.customer_id;"
    )
    assert _stmt(rule, sql) is not None


def test_w024_case_insensitive():
    rule = SelectDistinctSuspicious()
    assert _stmt(rule, "select distinct a from x join y on x.id = y.id;") is not None


def test_w024_does_not_flag_distinct_alone():
    # Single-table DISTINCT is fine -- no JOIN cardinality blow-up to mask.
    rule = SelectDistinctSuspicious()
    assert _stmt(rule, "SELECT DISTINCT country FROM customers;") is None


def test_w024_does_not_flag_count_distinct_with_join():
    # Aggregate-DISTINCT is a different pattern; the regex anchors on
    # "SELECT DISTINCT" directly, not "COUNT(DISTINCT ...)".
    rule = SelectDistinctSuspicious()
    sql = "SELECT COUNT(DISTINCT c.id) FROM customers c JOIN orders o ON c.id = o.customer_id;"
    assert _stmt(rule, sql) is None


def test_w024_does_not_flag_sum_distinct_with_join():
    rule = SelectDistinctSuspicious()
    sql = "SELECT SUM(DISTINCT amount) FROM payments p JOIN customers c ON p.cust_id = c.id;"
    assert _stmt(rule, sql) is None


def test_w024_does_not_flag_join_without_distinct():
    rule = SelectDistinctSuspicious()
    assert _stmt(rule, "SELECT a.id FROM a JOIN b ON a.id = b.a_id;") is None


def test_w024_does_not_flag_distinct_inside_string_literal():
    rule = SelectDistinctSuspicious()
    sql = "INSERT INTO log(msg) SELECT 'SELECT DISTINCT x JOIN y' FROM t JOIN u ON t.id = u.id;"
    # Outer SELECT does not have DISTINCT; the literal mentions it.
    assert _stmt(rule, sql) is None


def test_w024_does_not_flag_distinct_inside_comment():
    rule = SelectDistinctSuspicious()
    sql = "-- SELECT DISTINCT x FROM y JOIN z\nSELECT id FROM t;"
    assert _stmt(rule, sql) is None


def test_w024_message_mentions_join_or_grouping():
    rule = SelectDistinctSuspicious()
    finding = _stmt(
        rule,
        "SELECT DISTINCT a FROM x JOIN y ON x.id = y.id;",
    )
    assert finding is not None
    msg = finding.message.lower()
    assert "join" in msg or "grouping" in msg


# W025 assertion-malformed ---------------------------------------------------


def test_w025_passes_on_row_count_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: row_count > 0") is None


def test_w025_passes_on_row_count_with_large_integer():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: row_count >= 100") is None


def test_w025_passes_on_unique_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: unique(batch_id)") is None


def test_w025_passes_on_not_null_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: not_null(weight)") is None


def test_w025_passes_on_column_literal_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: weight > 0") is None


def test_w025_passes_on_column_string_literal_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: status = 'paid'") is None


def test_w025_flags_predicate_with_no_operator():
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: row_count")
    assert finding is not None
    assert finding.rule_id == "W025"
    assert finding.severity == "warning"


def test_w025_flags_non_numeric_rhs():
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: row_count > zero")
    assert finding is not None
    assert finding.rule_id == "W025"


def test_w025_flags_unique_without_parens():
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: unique batch_id")
    assert finding is not None
    assert finding.rule_id == "W025"


def test_w025_flags_freeform_text():
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: weight is positive")
    assert finding is not None
    assert finding.rule_id == "W025"


def test_w025_does_not_fire_on_non_assert_comment():
    rule = AssertionMalformed()
    assert _line(rule, "-- this is just a comment") is None


def test_w025_does_not_fire_on_plain_sql():
    rule = AssertionMalformed()
    assert _line(rule, "SELECT * FROM users WHERE id = 1;") is None


def test_w025_does_not_fire_on_assert_mentioned_inside_other_comment():
    # `-- @assert:` appearing as a substring inside a longer comment is
    # not an assertion -- it is prose describing the feature. The rule
    # anchors `--` to start-of-line specifically to avoid this case.
    rule = AssertionMalformed()
    assert _line(
        rule,
        "-- sql-sop reads `-- @assert: row_count > 0` comments",
    ) is None


def test_w025_passes_on_qualified_unique_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: unique(orders.batch_id)") is None


def test_w025_passes_on_qualified_not_null_predicate():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: not_null(production.weight)") is None


def test_w025_passes_on_qualified_column_comparison():
    rule = AssertionMalformed()
    assert _line(rule, "-- @assert: orders.total > 0") is None


def test_w025_flags_double_qualified_column():
    # `schema.table.column` is two dots; v1 supports one. Anything
    # deeper falls through to malformed.
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: schema.table.column > 0")
    assert finding is not None
    assert finding.rule_id == "W025"


def test_w025_message_includes_offending_predicate():
    rule = AssertionMalformed()
    finding = _line(rule, "-- @assert: weight is positive")
    assert finding is not None
    assert "weight is positive" in finding.message
