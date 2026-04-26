"""Parse inline ``-- sql-guard: disable=...`` and ``# sql-guard: disable=...`` comments.

The directives let users silence a known false positive on a single line
without disabling the rule project-wide. Two forms:

* ``-- sql-guard: disable=W001`` (or ``-- sql-guard: disable=W001,W003``)
  silences the listed rules on the same line.
* ``-- sql-guard: disable-next-line=W001`` silences them on the line that
  follows. Useful when the offending construct doesn't leave room for a
  trailing comment.

For Python source files the same directives work with ``#`` instead of
``--``. Whitespace inside the comment is tolerant; rule IDs are
case-insensitive in the directive but compared upper-case.

A bare ``-- sql-guard: disable`` (no equals sign or empty list) silences
all rules on that line. This mirrors ``# noqa`` from flake8/ruff.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_LINE_DIRECTIVE = re.compile(
    r"(?:--|\#)\s*sql-guard\s*:\s*disable(?:-next-line)?\s*(?:=\s*([\w,\s]*))?",
    re.IGNORECASE,
)
_NEXT_LINE_DIRECTIVE = re.compile(
    r"(?:--|\#)\s*sql-guard\s*:\s*disable-next-line\s*(?:=\s*([\w,\s]*))?",
    re.IGNORECASE,
)
_SAME_LINE_DIRECTIVE = re.compile(
    r"(?:--|\#)\s*sql-guard\s*:\s*disable(?!-next-line)\s*(?:=\s*([\w,\s]*))?",
    re.IGNORECASE,
)

ALL_RULES_TOKEN = "*"


@dataclass
class DisableMap:
    """Per-line disable directives extracted from a single file."""

    by_line: dict[int, set[str]] = field(default_factory=dict)

    def add(self, line: int, ids: set[str]) -> None:
        if line in self.by_line:
            self.by_line[line] |= ids
        else:
            self.by_line[line] = set(ids)

    def is_disabled(self, line: int, rule_id: str) -> bool:
        ids = self.by_line.get(line)
        if not ids:
            return False
        return ALL_RULES_TOKEN in ids or rule_id.upper() in ids


def _parse_ids(raw: str | None) -> set[str]:
    """Parse the rule ID list from a directive. Empty list = all rules."""
    if not raw or not raw.strip():
        return {ALL_RULES_TOKEN}
    return {part.strip().upper() for part in raw.split(",") if part.strip()}


def parse(content: str) -> DisableMap:
    """Build a per-line disable map for one file's content.

    Same-line directives apply to the line they appear on. ``disable-next-line``
    directives apply to the line below.
    """
    out = DisableMap()
    for line_no, line in enumerate(content.splitlines(), 1):
        next_line_match = _NEXT_LINE_DIRECTIVE.search(line)
        if next_line_match:
            out.add(line_no + 1, _parse_ids(next_line_match.group(1)))
            continue
        same_line_match = _SAME_LINE_DIRECTIVE.search(line)
        if same_line_match:
            out.add(line_no, _parse_ids(same_line_match.group(1)))
    return out
