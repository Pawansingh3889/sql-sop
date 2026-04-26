"""Warning rules (W001-W020) -- advisory, don't block commits by default."""

from __future__ import annotations

from sql_guard.rules.base import Finding, Rule


class SelectStar(Rule):
    """W001: SELECT * pulls all columns."""

    id = "W001"
    name = "select-star"
    severity = "warning"
    description = "SELECT * fetches all columns -- specify what you need"
    multiline = False

    _pattern = Rule._compile(r"\bSELECT\s+\*\s+FROM\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="SELECT * -- specify columns explicitly",
                suggestion="Replace with: SELECT col1, col2, col3 FROM ...",
            )
        return None


class MissingLimit(Rule):
    """W002: SELECT without LIMIT on potentially large result set."""

    id = "W002"
    name = "missing-limit"
    severity = "warning"
    description = "Unbounded SELECT could return millions of rows"
    multiline = True

    _select = Rule._compile(r"\bSELECT\b")
    _limit = Rule._compile(r"\b(LIMIT|TOP|FETCH\s+(FIRST|NEXT))\b")
    _aggregate = Rule._compile(r"\b(COUNT|SUM|AVG|MIN|MAX|GROUP\s+BY)\b")
    _into = Rule._compile(r"\bINTO\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if (
            self._select.search(statement)
            and not self._limit.search(statement)
            and not self._aggregate.search(statement)
            and not self._into.search(statement)
        ):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="SELECT without LIMIT -- could return unbounded rows",
                suggestion="Add LIMIT to prevent full table scan",
            )
        return None


class FunctionOnIndexedColumn(Rule):
    """W003: Function wrapping a column in WHERE kills index usage."""

    id = "W003"
    name = "function-on-column"
    severity = "warning"
    description = "Function on column in WHERE prevents index usage"
    multiline = False

    _pattern = Rule._compile(
        r"\bWHERE\b.*\b(YEAR|MONTH|DAY|DATE|UPPER|LOWER|TRIM|CAST|CONVERT|SUBSTRING|COALESCE)\s*\("
    )

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="Function on column in WHERE -- kills index usage",
                suggestion="Move the function to the value side: WHERE date >= '2024-01-01'",
            )
        return None


class MissingTableAlias(Rule):
    """W004: Multi-table JOIN without table aliases."""

    id = "W004"
    name = "missing-alias"
    severity = "warning"
    description = "JOINs without aliases make queries hard to read"
    multiline = True

    _join = Rule._compile(r"\bJOIN\b")
    _alias = Rule._compile(r"\bJOIN\s+\S+\s+(AS\s+)?\w+\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._join.search(statement) and not self._alias.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="JOIN without table alias",
                suggestion="Add aliases: JOIN orders o ON o.id = ...",
            )
        return None


class SubqueryCouldBeJoin(Rule):
    """W005: Subquery in WHERE that could be a JOIN."""

    id = "W005"
    name = "subquery-in-where"
    severity = "warning"
    description = "Subquery in WHERE may be slower than a JOIN"
    multiline = True

    _pattern = Rule._compile(r"\bWHERE\b.*\bIN\s*\(\s*SELECT\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="Subquery in WHERE -- consider using JOIN instead",
                suggestion="Replace WHERE x IN (SELECT ...) with JOIN",
            )
        return None


class OrderByWithoutLimit(Rule):
    """W006: ORDER BY without LIMIT sorts entire result set."""

    id = "W006"
    name = "orderby-without-limit"
    severity = "warning"
    description = "ORDER BY without LIMIT sorts the entire result set"
    multiline = True

    _orderby = Rule._compile(r"\bORDER\s+BY\b")
    _limit = Rule._compile(r"\b(LIMIT|TOP|FETCH\s+(FIRST|NEXT))\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._orderby.search(statement) and not self._limit.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="ORDER BY without LIMIT -- sorts entire result set",
                suggestion="Add LIMIT to avoid sorting unbounded data",
            )
        return None


class HardcodedValues(Rule):
    """W007: Hardcoded numeric values in WHERE (magic numbers)."""

    id = "W007"
    name = "hardcoded-values"
    severity = "warning"
    description = "Hardcoded values make queries hard to maintain"
    multiline = False

    _pattern = Rule._compile(r"\bWHERE\b.*[=<>]\s*\d{3,}")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="Hardcoded numeric value in WHERE clause",
                suggestion="Use a parameter or named constant instead",
            )
        return None


class MixedCaseKeywords(Rule):
    """W008: Inconsistent keyword casing (SELECT vs select)."""

    id = "W008"
    name = "mixed-case-keywords"
    severity = "warning"
    description = "Inconsistent keyword casing reduces readability"
    multiline = False

    _keywords = [
        "SELECT", "FROM", "WHERE", "JOIN", "INSERT", "UPDATE", "DELETE",
        "CREATE", "DROP", "ALTER", "ORDER BY", "GROUP BY", "HAVING", "LIMIT",
    ]

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            return None
        has_upper = False
        has_lower = False
        for kw in self._keywords:
            if kw in stripped:
                has_upper = True
            if kw.lower() in stripped and kw not in stripped:
                has_lower = True
        if has_upper and has_lower:
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="Mixed case SQL keywords",
                suggestion="Use consistent casing -- either all UPPER or all lower",
            )
        return None


class MissingSemicolon(Rule):
    """W009: SQL statement not terminated with semicolon."""

    id = "W009"
    name = "missing-semicolon"
    severity = "warning"
    description = "Statements should end with a semicolon"
    multiline = True

    _statement_start = Rule._compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER)\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._statement_start.search(statement) and not statement.rstrip().endswith(";"):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="Statement not terminated with semicolon",
                suggestion="Add ; at the end of the statement",
            )
        return None


class CommentedOutCode(Rule):
    """W010: Large blocks of commented-out SQL code."""

    id = "W010"
    name = "commented-out-code"
    severity = "warning"
    description = "Commented-out code should be removed -- use version control"
    multiline = False

    _pattern = Rule._compile(r"^\s*--\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP)\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="Commented-out SQL code",
                suggestion="Remove dead code -- it's in version control history",
            )
        return None


class GroupByOrdinal(Rule):
    """W012: GROUP BY <positional-ordinal> is terse but brittle."""

    id = "W012"
    name = "group-by-ordinal"
    severity = "warning"
    description = (
        "GROUP BY by column position silently breaks if the SELECT list is "
        "reordered: a column insert or move changes which columns group"
    )
    multiline = True

    # \b\d+\b only matches a pure integer token. Column names like 1st_quarter
    # stay intact because '1' is followed by a word character, so the trailing
    # word boundary does not hold — no false positives on digit-prefixed names.
    _pattern = Rule._compile(r"\bGROUP\s+BY\s+\d+\b(\s*,\s*\d+\b)*")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="GROUP BY by ordinal position -- fragile, reorder-sensitive",
                suggestion="Use explicit column names in GROUP BY to survive SELECT list reorders",
            )
        return None


class UnionWithoutAll(Rule):
    """W011: UNION without ALL forces sort-and-dedupe."""

    id = "W011"
    name = "union-without-all"
    severity = "warning"
    description = "UNION forces sort-and-dedupe -- use UNION ALL when duplicates are impossible"
    multiline = True

    _pattern = Rule._compile(r"\bUNION\b(?!\s+ALL\b)")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="UNION without ALL -- sort-and-dedupe may be unnecessary",
                suggestion="Use UNION ALL if duplicate rows are impossible or undesired to remove",
            )
        return None


class NotInWithSubquery(Rule):
    """W016: NOT IN with subquery silently returns zero rows on NULL."""

    id = "W016"
    name = "not-in-with-subquery"
    severity = "warning"
    description = "NOT IN with subquery returns zero rows if subquery contains NULL"
    multiline = True

    _pattern = Rule._compile(r"\bNOT\s+IN\s*\(\s*SELECT\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="NOT IN with subquery -- returns zero rows if subquery has NULL",
                suggestion="Use NOT EXISTS or LEFT JOIN ... WHERE ... IS NULL instead",
            )
        return None


class LeadingWildcardLike(Rule):
    """W017: ``LIKE '%foo'`` with a leading wildcard is non-SARGable.

    The optimizer cannot use a B-tree index when the pattern starts with
    ``%`` (or ``_``), so the engine falls back to a full scan. Trailing
    wildcards (``LIKE 'foo%'``) are fine. For real substring search,
    full-text indexing or trigram indexes are the right tool.
    """

    id = "W017"
    name = "leading-wildcard-like"
    severity = "warning"
    description = "LIKE '%foo' defeats indexes -- forces a full scan"
    multiline = False

    # Match LIKE followed by a quoted string starting with % or _ wildcard.
    _pattern = Rule._compile(r"\bLIKE\s+(?:N)?'[%_]")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="LIKE pattern starts with a wildcard -- non-SARGable",
                suggestion="Restructure the query, or use full-text / trigram indexing",
            )
        return None


class OrAcrossColumns(Rule):
    """W018: ``WHERE a = 1 OR b = 2`` across different columns.

    Forces the optimizer to either scan or do an expensive index union.
    The two-query UNION ALL rewrite is usually faster and lets each side
    pick its own index. Same column with multiple OR'd values
    (``a = 1 OR a = 2``) is fine -- that becomes an IN list.
    """

    id = "W018"
    name = "or-across-columns"
    severity = "warning"
    description = "OR across different columns often defeats single-column indexes"
    multiline = True

    # Two equality predicates joined by OR where the column names differ.
    # Conservative: we only flag when both sides are simple `col = literal`.
    _pattern = Rule._compile(
        r"\bWHERE\b[^;]*?\b(\w+)\s*=\s*\S+\s+OR\s+(\w+)\s*=\s*\S+",
    )

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        m = self._pattern.search(statement)
        if m and m.group(1).lower() != m.group(2).lower():
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message=f"OR across columns ({m.group(1)} / {m.group(2)}) often defeats indexes",
                suggestion="Consider rewriting as UNION ALL of two indexed queries",
            )
        return None


class TruncateTable(Rule):
    """W020: ``TRUNCATE TABLE`` bypasses triggers and the row-by-row log.

    Faster than DELETE for clearing a table, but: no DELETE triggers
    fire, identity columns reset (T-SQL), foreign-key references can
    block it, and partial-rollback granularity is lost. If you actually
    want a fast clear and accept those tradeoffs that's fine -- this is
    a warning, not an error.
    """

    id = "W020"
    name = "truncate-table"
    severity = "warning"
    description = "TRUNCATE skips triggers, resets identity, blocks on FKs"
    multiline = False

    _pattern = Rule._compile(r"\bTRUNCATE\s+TABLE\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="TRUNCATE TABLE bypasses triggers and resets identity",
                suggestion="Use DELETE if triggers or partial rollback matter",
            )
        return None


class CountDistinctUnbounded(Rule):
    """W019: ``COUNT(DISTINCT col)`` on an unfiltered table.

    ``COUNT(DISTINCT col)`` forces a full sort + distinct pass over the
    rows it sees. On a large unfiltered table that's a frequent perf
    surprise on prod. The rule fires when the same statement has neither
    a ``WHERE`` clause nor a ``GROUP BY`` (which already partitions the
    work) nor a ``LIMIT`` restricting the scope.
    """

    id = "W019"
    name = "count-distinct-unbounded"
    severity = "warning"
    description = "COUNT(DISTINCT) without WHERE/GROUP BY/LIMIT scans the whole table"
    multiline = True

    _count_distinct = Rule._compile(r"\bCOUNT\s*\(\s*DISTINCT\b")
    _where = Rule._compile(r"\bWHERE\b")
    _group_by = Rule._compile(r"\bGROUP\s+BY\b")
    _limit = Rule._compile(r"\b(LIMIT|TOP|FETCH\s+(FIRST|NEXT))\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if (
            self._count_distinct.search(statement)
            and not self._where.search(statement)
            and not self._group_by.search(statement)
            and not self._limit.search(statement)
        ):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="COUNT(DISTINCT) without WHERE/GROUP BY -- full table sort + distinct",
                suggestion="Add a WHERE/LIMIT to restrict scope, or pre-aggregate with GROUP BY",
            )
        return None


class WindowMissingPartition(Rule):
    """W013: OVER() without PARTITION BY can yield unpredictable results."""

    id = "W013"
    name = "window-missing-partition"
    severity = "warning"
    description = "OVER() without PARTITION BY may lead to unpredictable results and unclear intent."
    multiline = True

    _over_pattern = Rule._compile(r"\bOVER\s*\(")
    _partition_pattern = Rule._compile(r"PARTITION\s+BY")

    def has_valid_over_clause(self, statement: str) -> bool:
        # If no OVER(...) → nothing to check
        if not self._over_pattern.search(statement):
            return True

        # Valid only if PARTITION BY exists
        return bool(self._partition_pattern.search(statement))

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.has_valid_over_clause(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="Missing PARTITION BY in OVER clause",
                suggestion="Add PARTITION BY to define window groups clearly",
            )
        return None
