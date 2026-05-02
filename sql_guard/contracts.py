"""Data contract loader and types.

A contract describes the expected schema of a database in YAML so that the
linter can flag queries that disagree with it. The format is a deliberate
subset of the open data-contract space: tables -> columns -> type / nullable
/ primary-key / foreign-key. Compatible in spirit with the tools at
https://github.com/datacontract/datacontract-cli but lighter, since the
linter only needs the structure, not the semantics.

Example::

    tables:
      orders:
        columns:
          id:           {type: bigint,    not_null: true,  primary_key: true}
          customer_id:  {type: bigint,    not_null: true,  foreign_key: customers.id}
          total:        {type: decimal,   not_null: true}
          status:       {type: varchar}
          created_at:   {type: timestamp, not_null: true}
      customers:
        columns:
          id:    {type: bigint,  not_null: true, primary_key: true}
          name:  {type: varchar, not_null: true}
          email: {type: varchar}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ContractColumn:
    """A single column declaration inside a contract table."""

    name: str
    type: str = ""
    not_null: bool = False
    primary_key: bool = False
    foreign_key: str | None = None  # "table.column"
    has_default: bool = False


@dataclass
class ContractTable:
    """A table inside a contract, indexed by lower-case column name."""

    name: str
    columns: dict[str, ContractColumn] = field(default_factory=dict)

    @property
    def primary_keys(self) -> list[str]:
        return [c.name for c in self.columns.values() if c.primary_key]

    @property
    def required_columns(self) -> list[str]:
        """Columns that must appear in an INSERT (NOT NULL, no default, not auto-PK)."""
        return [
            c.name
            for c in self.columns.values()
            if c.not_null and not c.has_default and not c.primary_key
        ]


@dataclass
class Contract:
    """A loaded data contract describing the expected schema."""

    tables: dict[str, ContractTable] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: str | Path) -> "Contract":
        """Load a contract from a YAML file."""
        raw = Path(path).read_text(encoding="utf-8")
        return cls.from_dict(yaml.safe_load(raw) or {})

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Contract":
        """Build a contract from a parsed YAML dict."""
        contract = cls()
        for table_name, table_data in (data.get("tables") or {}).items():
            table = ContractTable(name=table_name)
            cols = (table_data or {}).get("columns") or {}
            for col_name, col_data in cols.items():
                if isinstance(col_data, str):
                    # Shorthand: a bare string is the column type.
                    col = ContractColumn(name=col_name, type=col_data)
                elif isinstance(col_data, dict):
                    col = ContractColumn(
                        name=col_name,
                        type=str(col_data.get("type", "")),
                        not_null=bool(col_data.get("not_null", False)),
                        primary_key=bool(col_data.get("primary_key", False)),
                        foreign_key=col_data.get("foreign_key"),
                        has_default=bool(col_data.get("has_default", False)),
                    )
                else:
                    # Skip malformed entries silently; the linter shouldn't crash on a
                    # half-written contract during development.
                    continue
                table.columns[col_name.lower()] = col
            contract.tables[table_name.lower()] = table
        return contract

    def get_table(self, name: str) -> ContractTable | None:
        """Look up a table by name, case-insensitively."""
        return self.tables.get(name.lower())
