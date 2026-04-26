"""Error rules (E001-E008) -- these block commits."""

from __future__ import annotations

from sql_guard.rules.base import Finding, Rule


class DeleteWithoutWhere(Rule):
    """E001: DELETE statement without WHERE clause."""

    id = "E001"
    name = "delete-without-where"
    severity = "error"
    description = "DELETE without WHERE affects all rows in the table"
    multiline = True

    _pattern = Rule._compile(r"\bDELETE\s+FROM\s+\S+")
    _has_where = Rule._compile(r"\bWHERE\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement) and not self._has_where.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="DELETE without WHERE clause -- this will delete all rows",
                suggestion="Add a WHERE clause to limit affected rows",
            )
        return None


class DropWithoutIfExists(Rule):
    """E002: DROP TABLE/VIEW without IF EXISTS."""

    id = "E002"
    name = "drop-without-if-exists"
    severity = "error"
    description = "DROP without IF EXISTS will fail if the object doesn't exist"
    multiline = False

    _pattern = Rule._compile(r"\bDROP\s+(TABLE|VIEW|INDEX|SCHEMA|DATABASE)\s+(?!IF\s+EXISTS\b)")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="DROP without IF EXISTS",
                suggestion="Use DROP TABLE IF EXISTS to avoid errors",
            )
        return None


class GrantRevoke(Rule):
    """E003: GRANT or REVOKE in application code."""

    id = "E003"
    name = "grant-revoke"
    severity = "error"
    description = "Privilege changes should not be in application SQL"
    multiline = False

    _pattern = Rule._compile(r"^\s*(GRANT|REVOKE)\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="GRANT/REVOKE in application code",
                suggestion="Manage permissions through migration scripts or DBA tools",
            )
        return None


class StringConcatInWhere(Rule):
    """E004: String concatenation in WHERE clause -- SQL injection risk."""

    id = "E004"
    name = "string-concat-in-where"
    severity = "error"
    description = "String concatenation in WHERE creates SQL injection risk"
    multiline = True

    _where = Rule._compile(r"\bWHERE\b")
    _concat = Rule._compile(r"\+\s*@|\+\s*'|'\s*\+|\|\|")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._where.search(statement) and self._concat.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="String concatenation in WHERE clause -- SQL injection risk",
                suggestion="Use parameterised queries: WHERE id = @id",
            )
        return None


class InsertWithoutColumns(Rule):
    """E005: INSERT without explicit column list."""

    id = "E005"
    name = "insert-without-columns"
    severity = "error"
    description = "INSERT without column list breaks when schema changes"
    multiline = False

    _pattern = Rule._compile(r"\bINSERT\s+INTO\s+\S+\s+VALUES\b")

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="INSERT without explicit column list",
                suggestion="Specify columns: INSERT INTO table (col1, col2) VALUES ...",
            )
        return None


class UpdateWithoutWhere(Rule):
    """E006: UPDATE statement without WHERE clause.

    The silent twin of E001 (DELETE without WHERE). An UPDATE with no WHERE
    rewrites every row in the table — a one-character mistake that can
    silently corrupt an entire production table. E001 catches the deletion
    case but UPDATE without WHERE has been an unwatched footgun until now.
    """

    id = "E006"
    name = "update-without-where"
    severity = "error"
    description = "UPDATE without WHERE rewrites every row in the table"
    multiline = True

    _pattern = Rule._compile(r"\bUPDATE\s+\S+\s+SET\b")
    _has_where = Rule._compile(r"\bWHERE\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement) and not self._has_where.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="UPDATE without WHERE clause -- this will overwrite every row",
                suggestion="Add a WHERE clause to limit affected rows",
            )
        return None


class AlterAddNotNullNoDefault(Rule):
    """E007: ``ALTER TABLE ... ADD col TYPE NOT NULL`` without a DEFAULT.

    Adding a NOT NULL column with no default forces the engine to scan and
    rewrite every row, holding a schema-modify lock for the duration. On
    a busy multi-million-row table this is a multi-minute outage. Either
    supply a DEFAULT (cheap metadata-only change in modern engines) or
    split into add-nullable / backfill / set-not-null phases.
    """

    id = "E007"
    name = "alter-add-not-null-no-default"
    severity = "error"
    description = "ALTER TABLE ADD NOT NULL without DEFAULT locks the table"
    multiline = True

    _pattern = Rule._compile(
        r"\bALTER\s+TABLE\s+\S+\s+ADD\s+(?:COLUMN\s+)?\S+\s+\S+[\s\S]*?\bNOT\s+NULL\b"
    )
    _has_default = Rule._compile(r"\bDEFAULT\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement) and not self._has_default.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="ALTER TABLE ADD NOT NULL without DEFAULT will lock the table",
                suggestion=(
                    "Add a DEFAULT, or split into: ADD nullable + backfill + ALTER COLUMN NOT NULL"
                ),
            )
        return None


class DropColumn(Rule):
    """E008: ``ALTER TABLE ... DROP COLUMN``.

    Irreversible without a backup. Replication subscribers that still
    reference the column break immediately. Application rollback to the
    previous deploy fails because the column is gone. Even if you do
    want the column gone, the safe path is: stop reading from app,
    deploy, observe for a release cycle, then drop.
    """

    id = "E008"
    name = "drop-column"
    severity = "error"
    description = "DROP COLUMN is irreversible and breaks replication subscribers"
    multiline = True

    _pattern = Rule._compile(r"\bALTER\s+TABLE\s+\S+\s+DROP\s+COLUMN\b")

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        if self._pattern.search(statement):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=start_line,
                message="DROP COLUMN is irreversible -- subscribers and rollback break",
                suggestion="Stop reading the column for one release, then drop in a follow-up",
            )
        return None
