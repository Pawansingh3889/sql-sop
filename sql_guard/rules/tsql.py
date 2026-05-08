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

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
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


class CreateIndexWithoutOnline(Rule):
    """T005: ``CREATE INDEX`` without ``WITH (ONLINE = ON)``.

    Default index builds take a Sch-M lock for the duration. On a busy
    multi-million-row table that can be a multi-minute outage of all
    readers and writers. Enterprise Edition supports online index
    builds; pass ``WITH (ONLINE = ON)`` to keep the table available.
    Standard / Express Edition cannot do online builds, so suppress this
    rule on those servers via ``--disable T005``.
    """

    id = "T005"
    name = "create-index-without-online"
    severity = "warning"
    description = "CREATE INDEX without ONLINE=ON locks the table for the build"
    multiline = True

    _pattern = Rule._compile(r"\bCREATE\s+(?:UNIQUE\s+)?(?:CLUSTERED\s+|NONCLUSTERED\s+)?INDEX\b")
    _has_online_on = Rule._compile(r"\bONLINE\s*=\s*ON\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement) and not self._has_online_on.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="CREATE INDEX without WITH (ONLINE = ON) holds a Sch-M lock",
                suggestion="Add WITH (ONLINE = ON) on Enterprise; disable T005 on Standard/Express",
            )
        return None


class SelectStarInto(Rule):
    """T006: ``SELECT * INTO target`` infers column types at runtime.

    T-SQL's ``SELECT * INTO new_table FROM source`` derives the schema of
    ``new_table`` from whatever the source produces at execution time.
    If the source columns change shape (a column added, type widened, an
    index changed) the destination table silently adopts those changes,
    and any code reading from ``new_table`` finds the schema has shifted
    underneath it. The data-integrity hit is delayed and hard to trace.

    Recommended pattern: ``CREATE TABLE new_table (...)`` with explicit
    typed columns, then ``INSERT INTO new_table (col1, col2, ...) SELECT
    ...``. The destination schema lives in source control and a contract
    breakage shows up as a compile error rather than silently propagated
    wrong types.

    The rule fires only on the wildcard form. ``SELECT col1, col2 INTO
    target FROM source`` still derives types from source columns but at
    least names what is being copied; it stays a green path and gets
    caught (if a column type drifts) by the contracts pack at C001/C003.

    Suppress with an inline ``-- noqa: T006`` comment on the same line,
    or use the project-wide ``-- sql-guard: disable=T006`` directive.
    """

    id = "T006"
    name = "select-into-without-typed-fields"
    severity = "warning"
    description = (
        "SELECT * INTO derives the destination schema from the source at runtime"
    )
    multiline = True

    _pattern = Rule._compile(r"\bSELECT\s+\*\s+INTO\s+\S+")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message=(
                    "SELECT * INTO derives the destination schema from the source "
                    "at runtime -- silent breakage when the source changes shape"
                ),
                suggestion=(
                    "CREATE TABLE target (col1 TYPE, ...) explicitly, then "
                    "INSERT INTO target (col1, ...) SELECT col1, ... FROM source"
                ),
            )
        return None
