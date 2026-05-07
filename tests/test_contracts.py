"""Tests for the contract-rules pack (C001-C005)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sql_guard.contracts import Contract
from sql_guard.rules.contracts import (
    ColumnNotInContract,
    NotNullViolation,
    PrimaryKeyMissingOnInsert,
    TableNotInContract,
    UnmappedForeignKey,
    build_contract_rules,
)

FIXTURES = Path(__file__).parent / "fixtures"
SAMPLE_CONTRACT = FIXTURES / "contract_sample.yml"


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


class TestContractLoader:
    def test_loads_from_file(self) -> None:
        contract = Contract.from_file(SAMPLE_CONTRACT)
        assert "orders" in contract.tables
        assert "customers" in contract.tables

    def test_orders_table_columns(self) -> None:
        contract = Contract.from_file(SAMPLE_CONTRACT)
        orders = contract.get_table("orders")
        assert orders is not None
        assert "id" in orders.columns
        assert orders.columns["id"].primary_key is True
        assert orders.columns["id"].has_default is True
        assert orders.columns["customer_id"].not_null is True
        assert orders.columns["customer_id"].foreign_key == "customers.id"

    def test_required_columns_excludes_pk_and_default(self) -> None:
        contract = Contract.from_file(SAMPLE_CONTRACT)
        orders = contract.get_table("orders")
        assert orders is not None
        # PK 'id' has has_default, so it's excluded. customer_id, total,
        # created_at are required (not_null and not PK).
        assert set(orders.required_columns) == {"customer_id", "total", "created_at"}

    def test_table_lookup_is_case_insensitive(self) -> None:
        contract = Contract.from_file(SAMPLE_CONTRACT)
        assert contract.get_table("ORDERS") is not None
        assert contract.get_table("Orders") is not None

    def test_unknown_table_returns_none(self) -> None:
        contract = Contract.from_file(SAMPLE_CONTRACT)
        assert contract.get_table("nonexistent") is None

    def test_from_dict_handles_shorthand_string_type(self) -> None:
        contract = Contract.from_dict(
            {"tables": {"t": {"columns": {"a": "varchar", "b": "bigint"}}}}
        )
        assert contract.get_table("t") is not None
        assert contract.get_table("t").columns["a"].type == "varchar"

    def test_from_dict_skips_malformed_columns(self) -> None:
        contract = Contract.from_dict(
            {"tables": {"t": {"columns": {"good": "varchar", "bad": 42}}}}
        )
        cols = contract.get_table("t").columns
        assert "good" in cols
        assert "bad" not in cols


# ---------------------------------------------------------------------------
# C001 column-not-in-contract
# ---------------------------------------------------------------------------


@pytest.fixture
def contract():
    return Contract.from_file(SAMPLE_CONTRACT)


def _stmt(rule, sql: str, line: int = 1):
    return rule.check_statement(sql, line, "test.sql")


class TestC001ColumnNotInContract:
    def test_flags_unknown_column(self, contract):
        rule = ColumnNotInContract(contract=contract)
        finding = _stmt(rule, "SELECT o.bogus_column FROM orders o;")
        assert finding is not None
        assert finding.rule_id == "C001"
        assert "bogus_column" in finding.message

    def test_passes_when_column_is_declared(self, contract):
        rule = ColumnNotInContract(contract=contract)
        assert _stmt(rule, "SELECT o.id, o.total FROM orders o;") is None

    def test_passes_when_table_not_in_contract(self, contract):
        # If the table isn't in the contract we don't have a baseline to
        # check against, so C001 stays silent (C002 owns that case).
        rule = ColumnNotInContract(contract=contract)
        assert _stmt(rule, "SELECT a.x FROM unknown_table a;") is None

    def test_handles_alias_or_table_name(self, contract):
        rule = ColumnNotInContract(contract=contract)
        # Bare table name (no alias) should still resolve.
        assert _stmt(rule, "SELECT orders.id FROM orders;") is None, (
            "table-name reference to a real column should pass"
        )
        finding = _stmt(rule, "SELECT orders.bogus FROM orders;")
        assert finding is not None and finding.rule_id == "C001"

    def test_no_op_without_contract(self):
        rule = ColumnNotInContract(contract=None)
        assert _stmt(rule, "SELECT o.bogus FROM orders o;") is None


# ---------------------------------------------------------------------------
# C002 table-not-in-contract
# ---------------------------------------------------------------------------


class TestC002TableNotInContract:
    def test_flags_unknown_table(self, contract):
        rule = TableNotInContract(contract=contract)
        finding = _stmt(rule, "SELECT * FROM ghost_table;")
        assert finding is not None
        assert finding.rule_id == "C002"

    def test_passes_for_known_table(self, contract):
        rule = TableNotInContract(contract=contract)
        assert _stmt(rule, "SELECT * FROM orders;") is None

    def test_flags_unknown_table_in_join(self, contract):
        rule = TableNotInContract(contract=contract)
        finding = _stmt(
            rule,
            "SELECT * FROM orders o JOIN ghosts g ON o.id = g.order_id;",
        )
        assert finding is not None
        assert finding.rule_id == "C002"

    def test_no_op_without_contract(self):
        rule = TableNotInContract(contract=None)
        assert _stmt(rule, "SELECT * FROM ghost_table;") is None


# ---------------------------------------------------------------------------
# C003 not-null-violation
# ---------------------------------------------------------------------------


class TestC003NotNullViolation:
    def test_flags_missing_not_null_column(self, contract):
        rule = NotNullViolation(contract=contract)
        # 'created_at' is NOT NULL in the contract; this INSERT omits it.
        finding = _stmt(
            rule,
            "INSERT INTO orders (customer_id, total) VALUES (1, 99.99);",
        )
        assert finding is not None
        assert finding.rule_id == "C003"
        assert finding.severity == "error"
        assert "created_at" in finding.message

    def test_passes_when_all_required_listed(self, contract):
        rule = NotNullViolation(contract=contract)
        assert (
            _stmt(
                rule,
                "INSERT INTO orders (customer_id, total, created_at) VALUES (1, 99.99, NOW());",
            )
            is None
        )

    def test_does_not_flag_unknown_table(self, contract):
        rule = NotNullViolation(contract=contract)
        # Tables not in the contract aren't C003's concern.
        assert _stmt(rule, "INSERT INTO ghost (a) VALUES (1);") is None

    def test_no_op_without_contract(self):
        rule = NotNullViolation(contract=None)
        assert _stmt(rule, "INSERT INTO orders (id) VALUES (1);") is None


# ---------------------------------------------------------------------------
# C004 primary-key-missing-on-insert
# ---------------------------------------------------------------------------


class TestC004PrimaryKeyMissingOnInsert:
    def test_passes_when_pk_has_default(self, contract):
        rule = PrimaryKeyMissingOnInsert(contract=contract)
        # 'orders.id' is PK with has_default in the sample contract, so
        # omitting it is fine.
        assert (
            _stmt(
                rule,
                "INSERT INTO orders (customer_id, total, created_at) VALUES (1, 99.99, NOW());",
            )
            is None
        )

    def test_flags_missing_pk_without_default(self):
        # Build a tiny contract where the PK has no default.
        contract = Contract.from_dict(
            {
                "tables": {
                    "audit": {
                        "columns": {
                            "id": {"type": "bigint", "primary_key": True, "not_null": True},
                            "msg": {"type": "varchar"},
                        }
                    }
                }
            }
        )
        rule = PrimaryKeyMissingOnInsert(contract=contract)
        finding = _stmt(rule, "INSERT INTO audit (msg) VALUES ('hi');")
        assert finding is not None
        assert finding.rule_id == "C004"
        assert "id" in finding.message

    def test_no_op_without_contract(self):
        rule = PrimaryKeyMissingOnInsert(contract=None)
        assert _stmt(rule, "INSERT INTO orders (customer_id) VALUES (1);") is None


# ---------------------------------------------------------------------------
# build_contract_rules helper
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# C005 unmapped-fk
# ---------------------------------------------------------------------------


class TestC005UnmappedForeignKey:
    def test_passes_when_fk_is_declared(self, contract):
        # contract_sample.yml has orders.customer_id -> customers.id
        rule = UnmappedForeignKey(contract=contract)
        sql = "SELECT * FROM orders o JOIN customers c ON o.customer_id = c.id;"
        assert _stmt(rule, sql) is None

    def test_passes_when_fk_declared_other_direction(self, contract):
        # The contract declares the FK on customer_id; the JOIN order
        # writes c.id = o.customer_id. Should still resolve.
        rule = UnmappedForeignKey(contract=contract)
        sql = "SELECT * FROM orders o JOIN customers c ON c.id = o.customer_id;"
        assert _stmt(rule, sql) is None

    def test_flags_join_with_no_declared_fk(self, contract):
        # orders.id -> customers.id is not a real FK in the contract;
        # the only relationship is orders.customer_id -> customers.id.
        rule = UnmappedForeignKey(contract=contract)
        sql = "SELECT * FROM orders o JOIN customers c ON o.id = c.id;"
        finding = _stmt(rule, sql)
        assert finding is not None
        assert finding.rule_id == "C005"
        assert "o.id" in finding.message and "c.id" in finding.message

    def test_passes_when_either_side_table_not_in_contract(self, contract):
        # If a table isn't in the contract at all, C002 owns the case.
        rule = UnmappedForeignKey(contract=contract)
        sql = "SELECT * FROM orders o JOIN ghosts g ON o.id = g.order_id;"
        assert _stmt(rule, sql) is None

    def test_no_op_without_contract(self):
        rule = UnmappedForeignKey(contract=None)
        sql = "SELECT * FROM orders o JOIN customers c ON o.id = c.id;"
        assert _stmt(rule, sql) is None


def test_build_contract_rules_with_contract_returns_all(contract):
    rules = build_contract_rules(contract)
    ids = {r.id for r in rules}
    assert ids == {"C001", "C002", "C003", "C004", "C005"}


def test_build_contract_rules_without_contract_returns_empty():
    rules = build_contract_rules(None)
    assert rules == []


# ---------------------------------------------------------------------------
# End-to-end integration: the contract pack against a fixture file.
# ---------------------------------------------------------------------------


def test_integration_contract_drift_fixture(contract):
    """Run the full check pipeline with --contract over the drift fixture.

    Asserts that every rule in C001-C005 (except C004, which uses an
    inline contract because the sample's PK has has_default=true) fires
    on the fixture.
    """
    from sql_guard.checker import check

    fixture = FIXTURES / "contract_drift.sql"
    result = check([str(fixture)], contract=contract)
    rule_ids = {f.rule_id for f in result.findings}

    # The four C-rules whose violation patterns the shared sample
    # contract can express.
    assert "C001" in rule_ids
    assert "C002" in rule_ids
    assert "C003" in rule_ids
    assert "C005" in rule_ids


def test_integration_check_without_contract_skips_c_rules(contract):
    """Without ``contract=``, the C-rules must not register."""
    from sql_guard.checker import check

    fixture = FIXTURES / "contract_drift.sql"
    result = check([str(fixture)])  # no contract
    rule_ids = {f.rule_id for f in result.findings}

    # No C-rule should have fired since no contract was loaded.
    assert not any(rid.startswith("C") for rid in rule_ids)
