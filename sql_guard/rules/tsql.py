"""T-SQL-specific rules for SQL Server shops.

These rules target anti-patterns that are SQL Server specific or most
common in T-SQL stored-procedure codebases (manufacturing MES/ERP, legacy
enterprise, SSRS datasets). They fire on text patterns that do not appear
in BigQuery or Postgres code, so they can run unconditionally with near-
zero false-positive rate on non-T-SQL input.

See https://github.com/Pawansingh3889/sql-guard/issues/22 for scope.
"""

from __future__ import annotations

from sql_guard.rules.base import Finding, Rule


class WithNolock(Rule):
    """T001: ``WITH (NOLOCK)`` hint allows dirty reads.

    Common performance band-aid in T-SQL that silently permits reading
    uncommitted data. Users should address the underlying blocking
    (indexes, transaction scope, or SNAPSHOT isolation) instead.
    """

    id = "T001"
    name = "with-nolock"
    severity = "warning"
    description = "WITH (NOLOCK) allows dirty reads; fix the underlying blocking"
    multiline = False

    _pattern = Rule._compile(r"\bWITH\s*\(\s*NOLOCK\s*\)")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="WITH (NOLOCK) allows dirty reads",
                suggestion="Use READ COMMITTED SNAPSHOT or fix the blocking instead",
            )
        return None


class XpCmdshell(Rule):
    """T002: ``xp_cmdshell`` executes OS-level commands.

    Remote-code-execution surface. Should never appear in application
    SQL. If you genuinely need it, it belongs in a locked-down DBA
    runbook, not in a stored procedure.
    """

    id = "T002"
    name = "xp-cmdshell"
    severity = "error"
    description = "xp_cmdshell executes arbitrary OS commands"
    multiline = False

    _pattern = Rule._compile(r"\bxp_cmdshell\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="xp_cmdshell executes OS-level commands",
                suggestion="Remove; shell exec should not appear in application SQL",
            )
        return None


class CursorDeclaration(Rule):
    """T003: ``DECLARE ... CURSOR`` is row-by-row processing.

    Set-based SQL is usually orders of magnitude faster. Cursors are
    legitimate for genuinely procedural work (admin scripts, one-offs)
    but rarely belong in hot paths or stored procs called per request.
    """

    id = "T003"
    name = "cursor-declaration"
    severity = "warning"
    description = "Cursor-based iteration is usually slower than set-based SQL"
    multiline = False

    _pattern = Rule._compile(r"\bDECLARE\s+\S+\s+CURSOR\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="DECLARE ... CURSOR processes rows one at a time",
                suggestion="Rewrite as set-based SQL where possible",
            )
        return None


class DeprecatedOuterJoin(Rule):
    """T004: ``*=`` and ``=*`` outer-join syntax.

    Deprecated since SQL Server 2005, unsupported in SQL Server 2012 and
    later (database compatibility level 90 or higher). Still appears in
    legacy stored procs and migrated code.

    Note: modern T-SQL also supports compound-assignment operators
    (``SET @x *= 2``). The regex uses a negative lookbehind to avoid
    matching ``@var *= expr`` as an outer join.
    """

    id = "T004"
    name = "deprecated-outer-join"
    severity = "error"
    description = "Old-style *= / =* outer joins are unsupported in SQL Server 2012+"
    multiline = True

    _pattern = Rule._compile(r"(?<![@\w])\w+\s*(?:\*=|=\*)\s*\w+")

    def check_statement(
        self, statement: str, start_line: int, file: str
    ) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="Deprecated *= or =* outer-join syntax",
                suggestion="Use LEFT OUTER JOIN or RIGHT OUTER JOIN",
            )
        return None
