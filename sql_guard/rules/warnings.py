"""Warning rules (W001-W010) -- advisory, don't block commits by default."""

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


class WindowMissingOrderPartition(Rule):
    """W013: OVER() without ORDER BY / PARTITION BY can yield unpredictable results."""

    id = "W013"
    name = "window-missing-order-partition"
    severity = "warning"
    description = "OVER() without ORDER BY or PARTITION BY may lead to unpredictable results and unclear intent."
    multiline = True

    _over_pattern = Rule._compile(r"\bOVER\s*\(")
    _valid_pattern = Rule._compile(r"OVER\s*\(\s*[^)]*(ORDER\s+BY|PARTITION\s+BY)[^)]*\)")

    def has_valid_over_clause(self, statement: str) -> bool:
        # If no OVER(...) clause → nothing to warn
        if not self._over_pattern.search(statement):
            return True

        # Valid only if ORDER BY or PARTITION BY exists inside OVER(...)
        return bool(self._valid_pattern.search(statement))
    

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not self.has_valid_over_clause(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="Missing ORDER BY / PARTITION BY in OVER clause",
                suggestion="Add ORDER BY for deterministic results and PARTITION BY to define window groups clearly",
            )
        return None