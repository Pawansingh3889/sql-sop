"""Snapshot contract semantics against a real local SQLite schema."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import yaml

from sql_guard import snapshot
from sql_guard.contracts import Contract


def test_introspect_contract_shape(snapshot_dsn: str):
    data = snapshot.introspect(snapshot_dsn)
    assert set(data["tables"]) == {"customers", "orders", "audit"}
    customers = data["tables"]["customers"]["columns"]
    assert customers["id"] == {"type": "INTEGER", "primary_key": True, "not_null": True}
    assert customers["name"] == {"type": "VARCHAR(40)", "not_null": True}
    assert customers["email"] == {"type": "VARCHAR(80)"}
    orders = data["tables"]["orders"]["columns"]
    assert orders["customer_id"]["foreign_key"] == "customers.id"
    assert orders["status"]["has_default"] is True
    contract = Contract.from_dict(data)
    assert contract.tables["orders"].primary_keys == ["id"]
    assert contract.tables["orders"].required_columns == ["customer_id"]


@pytest.mark.parametrize(
    "tables, expected", [(["ORDERS", "customers"], {"orders", "customers"}), (["missing"], set())]
)
def test_introspect_table_filter(snapshot_dsn: str, tables: list[str], expected: set[str]):
    data = snapshot.introspect(snapshot_dsn, schema="main", include_tables=tables)
    assert set(data["tables"]) == expected


def test_snapshot_roundtrip_creates_parent(snapshot_dsn: str, tmp_path: Path):
    data = snapshot.introspect(snapshot_dsn)
    output = tmp_path / "nested" / "contract.yml"
    snapshot.write_snapshot(data, output)
    assert yaml.safe_load(output.read_text(encoding="utf-8")) == data
    assert Contract.from_file(output) == Contract.from_dict(data)
    first = output.read_bytes()
    snapshot.write_snapshot(data, output)
    assert output.read_bytes() == first


def test_missing_sqlalchemy_has_install_hint(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setitem(sys.modules, "sqlalchemy", None)
    with pytest.raises(snapshot.SnapshotError, match=r"sql-sop\[snapshot\]"):
        snapshot.introspect("sqlite://")


def test_engine_disposed_on_inspection_failure(monkeypatch: pytest.MonkeyPatch):
    engine = Mock()
    sa = Mock()
    sa.create_engine.return_value = engine
    sa.inspect.side_effect = RuntimeError("inspection failed")
    monkeypatch.setattr(snapshot, "_require_sqlalchemy", lambda: sa)
    with pytest.raises(RuntimeError, match="inspection failed"):
        snapshot.introspect("sqlite://")
    engine.dispose.assert_called_once_with()


@pytest.mark.parametrize("default_kind", ["default", "server_default"])
def test_column_object_preserves_constraints(default_kind: str):
    sa = pytest.importorskip("sqlalchemy")
    column = sa.Column("customer_id", sa.Integer, nullable=False, **{default_kind: "1"})
    assert snapshot._column_to_dict(column, {"customer_id"}, {"customer_id": "customers.id"}) == {
        "type": "INTEGER",
        "not_null": True,
        "primary_key": True,
        "has_default": True,
        "foreign_key": "customers.id",
    }


def test_column_object_omits_absent_constraints():
    sa = pytest.importorskip("sqlalchemy")
    column = sa.Column("note", sa.Text)
    assert snapshot._column_to_dict(column, set(), {}) == {"type": "TEXT"}
