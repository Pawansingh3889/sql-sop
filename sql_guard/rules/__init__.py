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
    CommentedOutCode,
    CountDistinctUnbounded,
    FunctionOnIndexedColumn,
    GroupByOrdinal,
    HardcodedValues,
    LeadingWildcardLike,
    MissingLimit,
    MissingSemicolon,
    MissingTableAlias,
    MixedCaseKeywords,
    NotInWithSubquery,
    OrAcrossColumns,
    OrderByWithoutLimit,
    SelectStar,
    SubqueryCouldBeJoin,
    TruncateTable,
    UnionWithoutAll,
    WindowMissingPartition
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
    OrAcrossColumns(),
    TruncateTable(),
    CountDistinctUnbounded(),
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


def get_rules(enabled_ids: set[str] | None = None, disabled_ids: set[str] | None = None) -> list[Rule]:
    """Return filtered list of rules based on config."""
    rules = ALL_RULES
    if enabled_ids:
        rules = [r for r in rules if r.id in enabled_ids]
    if disabled_ids:
        rules = [r for r in rules if r.id not in disabled_ids]
    return rules
