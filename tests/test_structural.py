"""Tests for structural rules (S001-S003)."""

from __future__ import annotations


from sql_guard.rules.structural import (
    DeeplyNestedSubquery,
    ImplicitCrossJoin,
    UnusedCTE,
)


class TestImplicitCrossJoin:
    def test_comma_join_detected(self) -> None:
        sql = "SELECT * FROM orders, customers WHERE orders.id = customers.order_id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    def test_explicit_join_passes(self) -> None:
        sql = "SELECT * FROM orders JOIN customers ON orders.id = customers.order_id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    def test_single_table_passes(self) -> None:
        sql = "SELECT * FROM orders WHERE id = 1"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # Regression: previous regex missed any FROM with table aliases.
    def test_comma_join_with_aliases_detected(self) -> None:
        sql = "SELECT * FROM orders o, customers c WHERE o.cust_id = c.id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    # Regression: previous regex missed schema-qualified table names.
    def test_comma_join_with_schema_qualified_detected(self) -> None:
        sql = "SELECT * FROM raw.orders, raw.customers WHERE raw.orders.cust_id = raw.customers.id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    # Regression: previous regex missed three-or-more-way comma joins.
    def test_comma_join_three_tables_detected(self) -> None:
        sql = (
            "SELECT * FROM orders o, customers c, products p "
            "WHERE o.cust_id = c.id AND o.product_id = p.id"
        )
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    # Regression: previous regex missed multi-line FROM clauses.
    def test_comma_join_multiline_detected(self) -> None:
        sql = "SELECT *\nFROM orders o,\n     customers c\nWHERE o.cust_id = c.id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    # Function call with comma-separated args is not a comma-join.
    def test_function_call_with_comma_args_passes(self) -> None:
        sql = "SELECT SPLIT_TO_ARRAY(s, ',') FROM events"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # Subquery with comma in SELECT list is not a comma-join.
    def test_subquery_with_comma_in_select_passes(self) -> None:
        sql = "SELECT * FROM (SELECT a, b, c FROM t) AS sub"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # VALUES with multiple rows is not a comma-join.
    def test_values_clause_passes(self) -> None:
        sql = "SELECT * FROM (VALUES (1, 'a'), (2, 'b'), (3, 'c')) AS v(id, label)"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # Snowflake / Postgres LATERAL after a comma is a real lateral join.
    def test_snowflake_lateral_flatten_passes(self) -> None:
        sql = "SELECT * FROM events e, LATERAL FLATTEN(input => e.tags) AS f"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    def test_postgres_lateral_passes(self) -> None:
        sql = "SELECT * FROM t1 t, LATERAL (SELECT * FROM t2 WHERE t2.id = t.id) AS sub"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # LEFT/RIGHT/FULL OUTER JOIN should not flag.
    def test_left_outer_join_passes(self) -> None:
        sql = "SELECT * FROM orders o LEFT OUTER JOIN customers c ON o.cust_id = c.id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # String literal containing comma in WHERE is not a comma-join.
    def test_string_literal_with_comma_passes(self) -> None:
        sql = "SELECT * FROM orders WHERE customer = 'Smith, J'"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # DELETE FROM single table should not flag.
    def test_delete_from_passes(self) -> None:
        sql = "DELETE FROM orders WHERE id = 1"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is None

    # Comments between tables are stripped before scanning.
    def test_comment_between_tables_still_detected(self) -> None:
        sql = "SELECT * FROM orders o, /* legacy joined here */ customers c WHERE o.cust_id = c.id"
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"

    # Comma-join inside a CTE is detected.
    def test_comma_join_inside_cte_detected(self) -> None:
        sql = (
            "WITH joined AS ("
            "  SELECT * FROM orders o, customers c WHERE o.cust_id = c.id"
            ") SELECT * FROM joined"
        )
        result = ImplicitCrossJoin().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S001"


class TestDeeplyNestedSubquery:
    def test_shallow_passes(self) -> None:
        sql = "SELECT * FROM (SELECT id FROM users) sub"
        result = DeeplyNestedSubquery().check_statement(sql, 1, "test.sql")
        assert result is None

    def test_deep_nesting_detected(self) -> None:
        sql = "SELECT * FROM (SELECT * FROM (SELECT * FROM (SELECT 1) a) b) c"
        result = DeeplyNestedSubquery().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S002"
        assert "nested" in result.message.lower()

    def test_no_subquery_passes(self) -> None:
        sql = "SELECT id, name FROM users WHERE active = true"
        result = DeeplyNestedSubquery().check_statement(sql, 1, "test.sql")
        assert result is None


class TestUnusedCTE:
    def test_used_cte_passes(self) -> None:
        sql = "WITH active AS (SELECT * FROM users WHERE active) SELECT * FROM active"
        result = UnusedCTE().check_statement(sql, 1, "test.sql")
        assert result is None

    def test_unused_cte_detected(self) -> None:
        sql = "WITH unused AS (SELECT 1) SELECT * FROM orders"
        result = UnusedCTE().check_statement(sql, 1, "test.sql")
        assert result is not None
        assert result.rule_id == "S003"
        assert "unused" in result.message.lower()

    def test_no_cte_passes(self) -> None:
        sql = "SELECT * FROM orders"
        result = UnusedCTE().check_statement(sql, 1, "test.sql")
        assert result is None
