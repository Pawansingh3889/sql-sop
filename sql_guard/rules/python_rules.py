"""Python-only SQL hazards (P001-P005).

These rules fire on SQL strings reached from Python source via the libCST
scanner. They complement the regex-based E/W/S rules: those look at SQL
text, while P-rules look at *how* a string is being built before it hits
``execute(...)``.

Rules in this module never fire on ``.sql`` files; the checker only
invokes them via the Python scanner path.
"""

from __future__ import annotations

from dataclasses import dataclass

from sql_guard.python_scanner import ExtractedSql
from sql_guard.rules.base import Finding


@dataclass
class PythonRule:
    """Marker base class for rules driven by Python AST extraction."""

    id: str
    name: str
    severity: str
    description: str

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:  # pragma: no cover - abstract
        raise NotImplementedError


class FStringInExecute(PythonRule):
    """P001: f-string passed directly to an execute-like call."""

    def __init__(self) -> None:
        super().__init__(
            id="P001",
            name="fstring-in-execute",
            severity="error",
            description="f-string passed to .execute() -- SQL injection risk",
        )

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:
        # sqlalchemy.text(f"...") is handled by the more specific P005 rule
        # (SqlalchemyTextFstring). Skip here to avoid double-firing.
        if hit.kind == "fstring" and hit.call_name and hit.call_name != "text":
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=hit.line,
                message=f"f-string passed to .{hit.call_name}() -- SQL injection risk",
                suggestion="Use parameterised queries: cursor.execute('... WHERE id = ?', (user_id,))",
            )
        return None


class ConcatInExecute(PythonRule):
    """P002: string + variable concatenation passed to execute-like call."""

    def __init__(self) -> None:
        super().__init__(
            id="P002",
            name="concat-in-execute",
            severity="error",
            description="String concatenation passed to .execute() -- SQL injection risk",
        )

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:
        if hit.kind == "concat" and hit.call_name:
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=hit.line,
                message=f"String concatenation passed to .{hit.call_name}() -- SQL injection risk",
                suggestion="Use parameterised queries instead of '...' + variable",
            )
        return None


class FormatInExecute(PythonRule):
    """P003: str.format() result passed to execute-like call."""

    def __init__(self) -> None:
        super().__init__(
            id="P003",
            name="format-in-execute",
            severity="error",
            description=".format() result passed to .execute() -- SQL injection risk",
        )

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:
        if hit.kind in ("format", "percent") and hit.call_name:
            method = ".format()" if hit.kind == "format" else "% interpolation"
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=hit.line,
                message=f"{method} result passed to .{hit.call_name}() -- SQL injection risk",
                suggestion="Use parameterised queries instead of format-string interpolation",
            )
        return None


class BareVariableInExecute(PythonRule):
    """P004: raw variable name passed to execute without sqlalchemy.text() wrapping."""

    def __init__(self) -> None:
        super().__init__(
            id="P004",
            name="bare-variable-in-execute",
            severity="warning",
            description="Raw variable passed to .execute() -- verify it is not user-controlled",
        )

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:
        if hit.kind == "name" and hit.call_name and hit.call_name != "text":
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=hit.line,
                message=f"Variable passed to .{hit.call_name}() -- verify it is not user-controlled",
                suggestion="Prefer a literal SQL string or sqlalchemy.text(query) with bound parameters",
            )
        return None


class SqlalchemyTextFstring(PythonRule):
    """P005: f-string wrapped in ``sqlalchemy.text(...)`` re-introduces SQL injection."""

    def __init__(self) -> None:
        super().__init__(
            id="P005",
            name="sqlalchemy-text-fstring",
            severity="error",
            description="f-string passed to sqlalchemy.text() -- SQL injection risk",
        )

    def check(self, hit: ExtractedSql, file: str) -> Finding | None:
        if hit.kind == "fstring" and hit.call_name == "text":
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=hit.line,
                message="f-string passed to sqlalchemy.text() -- SQL injection risk",
                suggestion=('Use bound parameters: text("... WHERE id = :id"), {"id": user_id}'),
            )
        return None


PYTHON_RULES: list[PythonRule] = [
    FStringInExecute(),
    ConcatInExecute(),
    FormatInExecute(),
    BareVariableInExecute(),
    SqlalchemyTextFstring(),
]
