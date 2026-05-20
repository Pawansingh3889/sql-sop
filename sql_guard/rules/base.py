"""Base rule class — all rules inherit from this."""

from __future__ import annotations

import re
from dataclasses import dataclass


_SQL_STRING = re.compile(r"'(?:[^']|'')*'")
_SQL_LINE_COMMENT = re.compile(r"--[^\n]*")
_SQL_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def strip_strings_and_comments(text: str) -> str:
    """Replace SQL string literals and comments with empty equivalents.

    Single-quoted strings (with `''` escapes), `--` line comments, and
    `/* ... */` block comments are all removed (strings collapse to ``''``,
    comments to empty). Useful before paren-depth or keyword scanning so
    commas, parentheses, or keywords inside literals/comments do not
    affect the scan.
    """
    text = _SQL_STRING.sub("''", text)
    text = _SQL_LINE_COMMENT.sub("", text)
    text = _SQL_BLOCK_COMMENT.sub("", text)
    return text


@dataclass
class Finding:
    """A single issue found by a rule."""

    rule_id: str
    severity: str  # "error" | "warning"
    file: str
    line: int
    message: str
    suggestion: str | None = None


class Rule:
    """Base class for all lint rules.

    Rules compile their regex patterns once at init time.
    Single-pass rules check one line at a time.
    Multi-line rules receive the full statement.
    """

    id: str = ""
    name: str = ""
    severity: str = "warning"  # "error" | "warning"
    description: str = ""
    multiline: bool = False  # True if rule needs full statement context

    def check_line(self, line: str, line_number: int, file: str) -> Finding | None:
        """Check a single line. Override for single-pass rules."""
        return None

    def check_statement(self, statement: str, start_line: int, file: str) -> Finding | None:
        """Check a full SQL statement. Override for multi-line rules."""
        return None

    def check_file(self, file: str) -> list[Finding]:
        """Check a whole file once. Override for file-level rules.

        Returns a list so a single file-level rule can produce multiple
        findings in one pass (a project-aware rule fires once per
        offending model, for example). Default is an empty list so
        existing line / statement rules pay nothing.
        """
        return []

    @staticmethod
    def _compile(pattern: str) -> re.Pattern:
        """Compile a regex pattern with IGNORECASE. Called once at init."""
        return re.compile(pattern, re.IGNORECASE)
