"""Rule registry — auto-discovers all rules."""

from __future__ import annotations

from sql_guard.rules.base import Rule
from sql_guard.rules.errors import (
    DeleteWithoutWhere,
    DropWithoutIfExists,
    GrantRevoke,
    InsertWithoutColumns,
    StringConcatInWhere,
    UpdateWithoutWhere,
)
from sql_guard.rules.warnings import (
    FunctionOnIndexedColumn,
    GroupByOrdinal,
    HardcodedValues,
    MissingLimit,
    MissingSemicolon,
    MissingTableAlias,
    MixedCaseKeywords,
    OrderByWithoutLimit,
    SelectStar,
    SubqueryCouldBeJoin,
    CommentedOutCode,
    UnionWithoutAll,
    WindowMissingOrderPartition
)
from sql_guard.rules.structural import (
    DeeplyNestedSubquery,
    ImplicitCrossJoin,
    UnusedCTE,
)
from sql_guard.rules.tsql import (
    CursorDeclaration,
    DeprecatedOuterJoin,
    WithNolock,
    XpCmdshell,
)

ALL_RULES: list[Rule] = [
    # Errors (E001-E006)
    DeleteWithoutWhere(),
    DropWithoutIfExists(),
    GrantRevoke(),
    StringConcatInWhere(),
    InsertWithoutColumns(),
    UpdateWithoutWhere(),
    # Warnings (W001-W012)
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
    WindowMissingOrderPartition(),
    GroupByOrdinal(),
    # Structural (S001-S003)
    ImplicitCrossJoin(),
    DeeplyNestedSubquery(),
    UnusedCTE(),
    # T-SQL specific (T001-T004)
    WithNolock(),
    XpCmdshell(),
    CursorDeclaration(),
    DeprecatedOuterJoin(),
]


def get_rules(enabled_ids: set[str] | None = None, disabled_ids: set[str] | None = None) -> list[Rule]:
    """Return filtered list of rules based on config."""
    rules = ALL_RULES
    if enabled_ids:
        rules = [r for r in rules if r.id in enabled_ids]
    if disabled_ids:
        rules = [r for r in rules if r.id not in disabled_ids]
    return rules
