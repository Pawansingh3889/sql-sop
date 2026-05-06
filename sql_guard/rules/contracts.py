"""Contract rules (C001-...) -- require a loaded data contract to fire.

These rules are only added to the active rule list when ``--contract`` is
passed (or ``contract:`` is set in ``.sql-guard.yml``). Without a contract
they are silent. The contract structure is defined in ``sql_guard.contracts``.
"""

from __future__ import annotations

import re

from sql_guard.contracts import Contract
from sql_guard.rules.base import Finding, Rule


class ContractRule(Rule):
    """Base class for contract-aware rules.

    Subclasses receive a Contract instance at construction time. When the
    contract is None, the rule no-ops, which keeps the registry shape stable
    even when ``--contract`` is not provided.
    """

    def __init__(self, contract: Contract | None = None) -> None:
        self.contract = contract


class ColumnNotInContract(ContractRule):
    """C001: Column referenced in SQL is not declared in the contract for the table.

    Walks ``table.column`` and ``alias.column`` references and looks each one
    up against the contract. A miss is a finding. ``SELECT *`` cannot be
    checked column-by-column at this layer, so this rule complements W001
    rather than replacing it.
    """

    id = "C001"
    name = "column-not-in-contract"
    severity = "warning"
    description = "Column reference not declared in the contract for that table"
    multiline = True

    # alias.column or table.column references in the body of a statement.
    _qualified_ref = re.compile(r"\b([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\b")
    # FROM/JOIN clauses, with an optional alias (with or without AS).
    _from_table = re.compile(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)(?:\s+(?:AS\s+)?([A-Za-z_][\w]*))?",
        re.IGNORECASE,
    )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.contract:
            return None

        # Build alias -> table-name map. Bare table references map to themselves.
        aliases: dict[str, str] = {}
        for m in self._from_table.finditer(statement):
            table_name = m.group(1).lower()
            alias = (m.group(2) or m.group(1)).lower()
            aliases[alias] = table_name

        if not aliases:
            return None

        # First miss wins. The reporter is happier with one finding per
        # statement than with a scatter of duplicates.
        for m in self._qualified_ref.finditer(statement):
            ref_alias = m.group(1).lower()
            ref_col = m.group(2).lower()
            if ref_alias not in aliases:
                continue
            table_name = aliases[ref_alias]
            table = self.contract.get_table(table_name)
            if table is None:
                continue
            if ref_col not in table.columns:
                return Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=start_line,
                    message=(
                        f"Column '{ref_col}' is not declared in the contract "
                        f"for table '{table_name}'"
                    ),
                    suggestion=(
                        f"Either add '{ref_col}' to the contract or correct the column name"
                    ),
                )
        return None


class TableNotInContract(ContractRule):
    """C002: Statement references a table that has no entry in the contract.

    Useful when a contract is expected to cover the whole schema. Disable
    this rule if you only want to lint a subset of tables and intentionally
    leave others out.
    """

    id = "C002"
    name = "table-not-in-contract"
    severity = "warning"
    description = "Statement references a table not declared in the contract"
    multiline = True

    _from_table = re.compile(
        r"\b(?:FROM|JOIN|INTO|UPDATE)\s+([A-Za-z_][\w]*)",
        re.IGNORECASE,
    )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.contract:
            return None
        for m in self._from_table.finditer(statement):
            table_name = m.group(1)
            if self.contract.get_table(table_name) is None:
                return Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=start_line,
                    message=f"Table '{table_name}' is not declared in the contract",
                    suggestion=(
                        "Either add the table to the contract or disable C002 "
                        "for partial-coverage contracts"
                    ),
                )
        return None


class NotNullViolation(ContractRule):
    """C003: INSERT omits a NOT NULL column declared in the contract.

    Only triggers on parenthesised column lists, e.g.
    ``INSERT INTO orders (id, customer_id) VALUES (...)``. Bare
    ``INSERT INTO orders VALUES (...)`` already triggers E005
    (insert-without-columns) which is the more general fix.
    """

    id = "C003"
    name = "not-null-violation"
    severity = "error"
    description = "INSERT omits a column declared NOT NULL in the contract"
    multiline = True

    _insert = re.compile(
        r"\bINSERT\s+INTO\s+([A-Za-z_][\w]*)\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.contract:
            return None
        m = self._insert.search(statement)
        if not m:
            return None

        table_name = m.group(1)
        table = self.contract.get_table(table_name)
        if table is None:
            return None

        listed_cols = {c.strip().strip('[]`"').lower() for c in m.group(2).split(",")}
        missing = [c for c in table.required_columns if c not in listed_cols]

        if missing:
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message=(
                    f"INSERT into '{table_name}' is missing NOT NULL "
                    f"columns: {', '.join(sorted(missing))}"
                ),
                suggestion=(
                    "Include every NOT NULL column in the INSERT column "
                    "list and the VALUES tuple, or add a default in the contract"
                ),
            )
        return None


class PrimaryKeyMissingOnInsert(ContractRule):
    """C004: INSERT into a contract table omits its primary key (and no default).

    Tracks PK columns separately from generic NOT NULL because the failure
    mode is different: a missing PK becomes a constraint violation at write
    time, not a NULL coalescing surprise.
    """

    id = "C004"
    name = "primary-key-missing-on-insert"
    severity = "error"
    description = "INSERT into a contract table omits the primary key with no default"
    multiline = True

    _insert = re.compile(
        r"\bINSERT\s+INTO\s+([A-Za-z_][\w]*)\s*\(([^)]+)\)",
        re.IGNORECASE,
    )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.contract:
            return None
        m = self._insert.search(statement)
        if not m:
            return None

        table_name = m.group(1)
        table = self.contract.get_table(table_name)
        if table is None or not table.primary_keys:
            return None

        listed_cols = {c.strip().strip('[]`"').lower() for c in m.group(2).split(",")}
        missing_pks = [
            pk
            for pk in table.primary_keys
            if pk not in listed_cols and not table.columns[pk].has_default
        ]

        if missing_pks:
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message=(
                    f"INSERT into '{table_name}' is missing primary key "
                    f"column(s): {', '.join(sorted(missing_pks))}"
                ),
                suggestion=(
                    "Either include the primary key in the INSERT or "
                    "declare has_default: true in the contract"
                ),
            )
        return None


class UnmappedForeignKey(ContractRule):
    """C005: JOIN predicate uses columns the contract has no foreign key for.

    Catches accidental cross-table joins where the contract declares no
    relationship between the two columns. Walks every ``alias.col =
    alias.col`` equality inside a ``JOIN ... ON`` clause and checks
    whether either side has a ``foreign_key: other_table.col`` pointing
    at the other side. Equalities involving tables not in the contract
    are skipped (C002 owns that case).
    """

    id = "C005"
    name = "unmapped-fk"
    severity = "warning"
    description = "JOIN ... ON uses columns with no FK relationship in the contract"
    multiline = True

    _from_table = re.compile(
        r"\b(?:FROM|JOIN)\s+([A-Za-z_][\w]*)(?:\s+(?:AS\s+)?([A-Za-z_][\w]*))?",
        re.IGNORECASE,
    )
    _join_on_block = re.compile(
        r"\bJOIN\s+[A-Za-z_][\w]*(?:\s+(?:AS\s+)?[A-Za-z_][\w]*)?\s+ON\s+(.+?)"
        r"(?=\bWHERE\b|\bGROUP\s+BY\b|\bORDER\s+BY\b|\bHAVING\b|\bJOIN\b|;|$)",
        re.IGNORECASE | re.DOTALL,
    )
    _equality = re.compile(
        r"\b([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\s*=\s*([A-Za-z_][\w]*)\.([A-Za-z_][\w]*)\b"
    )

    def _fk_resolves(
        self,
        source_table_name: str,
        source_col: str,
        target_table_name: str,
        target_col: str,
    ) -> bool:
        if self.contract is None:
            return False
        source_table = self.contract.get_table(source_table_name)
        if source_table is None:
            return False
        col = source_table.columns.get(source_col)
        if col is None or not col.foreign_key:
            return False
        ref_table, _, ref_col = col.foreign_key.partition(".")
        return (
            ref_table.lower() == target_table_name.lower() and ref_col.lower() == target_col.lower()
        )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.contract:
            return None

        # alias -> table for every FROM/JOIN target.
        aliases: dict[str, str] = {}
        for m in self._from_table.finditer(statement):
            table_name = m.group(1).lower()
            alias = (m.group(2) or m.group(1)).lower()
            aliases[alias] = table_name

        if not aliases:
            return None

        for join_match in self._join_on_block.finditer(statement):
            on_body = join_match.group(1)
            for eq in self._equality.finditer(on_body):
                left_alias, left_col = eq.group(1).lower(), eq.group(2).lower()
                right_alias, right_col = eq.group(3).lower(), eq.group(4).lower()

                left_table = aliases.get(left_alias)
                right_table = aliases.get(right_alias)
                if left_table is None or right_table is None:
                    continue

                # Both tables must be in the contract -- C002 owns the
                # "table not in contract" case.
                if (
                    self.contract.get_table(left_table) is None
                    or self.contract.get_table(right_table) is None
                ):
                    continue

                # Either column may declare the FK; check both directions.
                if self._fk_resolves(left_table, left_col, right_table, right_col):
                    continue
                if self._fk_resolves(right_table, right_col, left_table, left_col):
                    continue

                return Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=start_line,
                    message=(
                        f"JOIN on '{left_alias}.{left_col} = "
                        f"{right_alias}.{right_col}' has no foreign-key "
                        f"declaration in the contract"
                    ),
                    suggestion=(
                        "Add a foreign_key: <table>.<column> entry to the "
                        "owning column in the contract, or correct the JOIN"
                    ),
                )
        return None


CONTRACT_RULE_CLASSES: list[type[ContractRule]] = [
    ColumnNotInContract,
    TableNotInContract,
    NotNullViolation,
    PrimaryKeyMissingOnInsert,
    UnmappedForeignKey,
]


def build_contract_rules(contract: Contract | None) -> list[ContractRule]:
    """Instantiate every contract rule with the given (or empty) contract."""
    if contract is None:
        return []
    return [rule_class(contract=contract) for rule_class in CONTRACT_RULE_CLASSES]
