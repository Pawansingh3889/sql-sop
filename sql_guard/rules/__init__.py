"""Rule registry — auto-discovers all rules."""

from __future__ import annotations

from sql_guard.rules.base import Rule
from sql_guard.rules.errors import (
    AlterAddNotNullNoDefault,
    DeleteWithoutWhere,
    DropColumn,
    DropWithoutIfExists,
    GrantRevoke,
    InsertWithoutColumns,
    StringConcatInWhere,
    UpdateWithoutWhere,
)
from sql_guard.rules.warnings import (
    CaseWithoutElse,
    CommentedOutCode,
    CountDistinctUnbounded,
    CrossJoinExplicit,
    FunctionOnIndexedColumn,
    GroupByOrdinal,
    HardcodedValues,
    JoinFunctionOnColumn,
    LeadingWildcardLike,
    MissingLimit,
    MissingSemicolon,
    MissingTableAlias,
    MixedCaseKeywords,
    NotInWithSubquery,
    OrAcrossColumns,
    OrderByWithoutLimit,
    ScalarUdfInWhere,
    SelectStar,
    SubqueryCouldBeJoin,
    TruncateTable,
    UnionWithoutAll,
    WindowMissingPartition,
)
from sql_guard.rules.structural import (
    DeeplyNestedSubquery,
    ImplicitCrossJoin,
    UnusedCTE,
)
from sql_guard.rules.tsql import (
    CreateIndexWithoutOnline,
    CursorDeclaration,
    DeprecatedOuterJoin,
    WithNolock,
    XpCmdshell,
)
from sql_guard.rules.contracts import (
    CONTRACT_RULE_CLASSES,
    ColumnNotInContract,
    NotNullViolation,
    PrimaryKeyMissingOnInsert,
    TableNotInContract,
    UnmappedForeignKey,
    build_contract_rules,
)

__all__ = [
    "ALL_RULES",
    "CONTRACT_RULE_CLASSES",
    "ColumnNotInContract",
    "NotNullViolation",
    "PrimaryKeyMissingOnInsert",
    "Rule",
    "TableNotInContract",
    "UnmappedForeignKey",
    "build_contract_rules",
    "get_rules",
]

ALL_RULES: list[Rule] = [
    # Errors (E001-E008)
    DeleteWithoutWhere(),
    DropWithoutIfExists(),
    GrantRevoke(),
    StringConcatInWhere(),
    InsertWithoutColumns(),
    UpdateWithoutWhere(),
    AlterAddNotNullNoDefault(),
    DropColumn(),
    # Warnings (W001-W020 with gaps)
    SelectStar(),
    MissingLimit(),
    FunctionOnIndexedColumn(),
    MissingTableAlias(),
    SubqueryCouldBeJoin(),
    OrderByWithoutLimit(),
    HardcodedValues(),
    MixedCaseKeywords(),
    MissingSemicolon(),
    CommentedOutCode(),
    UnionWithoutAll(),
    WindowMissingPartition(),
    GroupByOrdinal(),
    NotInWithSubquery(),
    LeadingWildcardLike(),
    JoinFunctionOnColumn(),
    OrAcrossColumns(),
    TruncateTable(),
    CountDistinctUnbounded(),
    ScalarUdfInWhere(),
    CaseWithoutElse(),
    CrossJoinExplicit(),
    # Structural (S001-S003)
    ImplicitCrossJoin(),
    DeeplyNestedSubquery(),
    UnusedCTE(),
    # T-SQL specific (T001-T005)
    WithNolock(),
    XpCmdshell(),
    CursorDeclaration(),
    DeprecatedOuterJoin(),
    CreateIndexWithoutOnline(),
]


def get_rules(
    enabled_ids: set[str] | None = None,
    disabled_ids: set[str] | None = None,
    contract: "Contract | None" = None,  # noqa: F821 -- forward reference
) -> list[Rule]:
    """Return filtered list of rules based on config.

    If ``contract`` is provided, contract-aware rules (C001-...) are
    instantiated with that contract and appended. Without a contract they
    are silent and not registered.
    """
    rules = list(ALL_RULES)
    if contract is not None:
        rules = rules + list(build_contract_rules(contract))
    if enabled_ids:
        rules = [r for r in rules if r.id in enabled_ids]
    if disabled_ids:
        rules = [r for r in rules if r.id not in disabled_ids]
    return rules


# Forward import for type hints; placed at bottom to avoid circular import.
from sql_guard.contracts import Contract  # noqa: E402, F401
