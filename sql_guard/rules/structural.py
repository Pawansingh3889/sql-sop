"""Structural rules (S001-S003) using sqlparse for deeper pattern detection.

Regex-based rules check text patterns. Structural rules parse the SQL into
tokens and check the actual query structure. This catches patterns that
regex misses, like implicit cross joins or deeply nested subqueries.

Based on PyCon DE 2026: "Practical Refactoring with Syntax Trees" (Direr).
Applies AST-based analysis to SQL instead of Python.
"""

from __future__ import annotations

import re

from sql_guard.rules.base import Finding, Rule, strip_strings_and_comments

try:
    import sqlparse
    from sqlparse.sql import Parenthesis

    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False


class ImplicitCrossJoin(Rule):
    """S001: Implicit cross join via comma-separated tables in FROM.

    Detects ``SELECT * FROM orders, customers WHERE ...`` and the realistic
    variants the older regex missed: aliased tables, schema-qualified
    names, three-or-more-way joins, and multi-line layout. The scan walks
    from each ``FROM`` keyword tracking parenthesis depth, stopping at
    ``WHERE`` / ``GROUP BY`` / ``ORDER BY`` / ``HAVING`` / ``LIMIT`` /
    ``UNION`` / ``EXCEPT`` / ``INTERSECT`` / explicit ``JOIN``, and flags
    the first depth-0 comma it finds. Commas inside parenthesised
    sub-expressions (function calls with multiple args, ``VALUES`` rows,
    inline subqueries) do not trip the rule. Comma followed by
    ``LATERAL`` is treated as a legitimate Snowflake/Postgres lateral
    join and not flagged.

    Suppress with an inline ``-- noqa: S001`` comment on the same line, or
    use the project-wide ``-- sql-guard: disable=S001`` directive.
    """

    id = "S001"
    name = "implicit-cross-join"
    severity = "warning"
    description = "Comma-separated tables in FROM clause create an implicit cross join"
    multiline = True

    _from_pattern = re.compile(r"\bFROM\b", re.IGNORECASE)
    # Keywords that end the FROM clause. Scan stops here without flagging.
    _stop_pattern = re.compile(
        r"\b("
        r"WHERE|"
        r"GROUP\s+BY|ORDER\s+BY|HAVING|"
        r"LIMIT|FETCH|OFFSET|"
        r"INNER\s+JOIN|"
        r"LEFT\s+(?:OUTER\s+)?JOIN|"
        r"RIGHT\s+(?:OUTER\s+)?JOIN|"
        r"FULL\s+(?:OUTER\s+)?JOIN|"
        r"CROSS\s+JOIN|"
        r"NATURAL\s+(?:INNER\s+|LEFT\s+|RIGHT\s+|FULL\s+)?JOIN|"
        r"JOIN|"
        r"UNION|EXCEPT|INTERSECT"
        r")\b",
        re.IGNORECASE,
    )
    # LATERAL after a comma is a real Snowflake/Postgres lateral join, not
    # an implicit cross join. Skip past it.
    _lateral_pattern = re.compile(r"\s*LATERAL\b", re.IGNORECASE)

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        cleaned = strip_strings_and_comments(statement)
        n = len(cleaned)

        for from_match in self._from_pattern.finditer(cleaned):
            # Skip "DELETE FROM" — single-target DELETE; Postgres uses
            # "USING" for multi-table, MySQL has its own form. A bare
            # comma after DELETE FROM is invalid syntax in most dialects,
            # so we don't try to interpret it.
            preceding = cleaned[: from_match.start()].rstrip().upper()
            if preceding.endswith("DELETE"):
                continue

            depth = 0
            i = from_match.end()
            while i < n:
                ch = cleaned[i]

                if ch == "(":
                    depth += 1
                    i += 1
                    continue
                if ch == ")":
                    depth -= 1
                    if depth < 0:
                        # Unbalanced — FROM was inside a subquery that
                        # has now closed. Stop scanning this match.
                        break
                    i += 1
                    continue

                if depth != 0:
                    i += 1
                    continue

                stop = self._stop_pattern.match(cleaned, i)
                if stop:
                    break

                if ch == ";":
                    break

                if ch == ",":
                    # Suppress for `, LATERAL ...` — valid lateral join.
                    if self._lateral_pattern.match(cleaned, i + 1):
                        i += 1
                        continue
                    line_offset = statement[:i].count("\n")
                    return Finding(
                        rule_id=self.id,
                        severity=self.severity,
                        file=file,
                        line=start_line + line_offset,
                        message="Implicit cross join via comma-separated tables in FROM",
                        suggestion="Use explicit JOIN syntax: FROM a INNER JOIN b ON a.id = b.id",
                    )

                i += 1
        return None


class DeeplyNestedSubquery(Rule):
    """S002: Subquery nested more than 2 levels deep.

    Deeply nested subqueries are hard to read and often perform poorly.
    Consider using CTEs (WITH clause) instead.
    """

    id = "S002"
    name = "deeply-nested-subquery"
    severity = "warning"
    description = "Subquery nested more than 2 levels deep -- consider using CTEs"
    multiline = True

    MAX_DEPTH = 2

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if not HAS_SQLPARSE:
            return None

        try:
            parsed = sqlparse.parse(statement)
            if not parsed:
                return None
            depth = self._max_paren_depth(parsed[0])
            if depth > self.MAX_DEPTH:
                return Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=start_line,
                    message=f"Subquery nested {depth} levels deep (max {self.MAX_DEPTH})",
                    suggestion="Refactor using CTEs (WITH clause) for readability",
                )
        except Exception:
            pass
        return None

    def _max_paren_depth(self, token, depth: int = 0) -> int:
        """Recursively find maximum parenthesis nesting depth."""
        max_d = depth
        if hasattr(token, "tokens"):
            for t in token.tokens:
                if isinstance(t, Parenthesis):
                    max_d = max(max_d, self._max_paren_depth(t, depth + 1))
                else:
                    max_d = max(max_d, self._max_paren_depth(t, depth))
        return max_d


class UnusedCTE(Rule):
    """S003: CTE defined in WITH clause but never referenced in main query.

    Dead CTEs add complexity without benefit and confuse readers.
    """

    id = "S003"
    name = "unused-cte"
    severity = "warning"
    description = "CTE defined but never referenced in the main query"
    multiline = True

    _cte_name_pattern = Rule._compile(r"\bWITH\s+(\w+)\s+AS\b|\b,\s*(\w+)\s+AS\s*\(")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        upper = statement.upper()
        if "WITH" not in upper:
            return None

        import re

        cte_names = []
        for m in re.finditer(r"\bWITH\s+(\w+)\s+AS\b", statement, re.IGNORECASE):
            cte_names.append(m.group(1))
        for m in re.finditer(r",\s*(\w+)\s+AS\s*\(", statement, re.IGNORECASE):
            cte_names.append(m.group(1))

        if not cte_names:
            return None

        # Find the main query (everything after the last CTE closing paren)
        # Simple heuristic: text after the last top-level SELECT
        parts = re.split(r"\)\s*SELECT\b", statement, flags=re.IGNORECASE)
        if len(parts) < 2:
            return None
        main_query = parts[-1].upper()

        for name in cte_names:
            if name.upper() not in main_query:
                return Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=start_line,
                    message=f"CTE '{name}' is defined but never referenced",
                    suggestion="Remove the unused CTE or reference it in the main query",
                )
        return None
