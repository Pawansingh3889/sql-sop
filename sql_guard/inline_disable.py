"""Parse inline ``-- sql-sop: disable=...`` and ``# sql-sop: disable=...`` comments.

The directives let users silence a known false positive on a single line
without disabling the rule project-wide. Two forms:

* ``-- sql-sop: disable=W001`` (or ``-- sql-sop: disable=W001,W003``)
  silences the listed rules on the same line.
* ``-- sql-sop: disable-next-line=W001`` silences them on the line that
  follows. Useful when the offending construct doesn't leave room for a
  trailing comment.

For Python source files the same directives work with ``#`` instead of
``--``. Whitespace inside the comment is tolerant; rule IDs are
case-insensitive in the directive but compared upper-case.

A bare ``-- sql-sop: disable`` (no equals sign or empty list) silences
all rules on that line. This mirrors ``# noqa`` from flake8/ruff.

The legacy ``sql-guard:`` prefix is still accepted but deprecated; it
stops working in 0.12.0. ``parse`` records when a file used the legacy
prefix (see ``legacy_directive_seen``) so the CLI can print a single
deprecation notice per run rather than once per line.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

_DIRECTIVE_PREFIX = r"(?:--|\#)\s*(?P<tool>sql-guard|sql-sop)\s*:\s*"

_LINE_DIRECTIVE = re.compile(
    _DIRECTIVE_PREFIX + r"disable(?:-next-line)?\s*(?:=\s*(?P<ids>[\w,\s]*))?",
    re.IGNORECASE,
)
_NEXT_LINE_DIRECTIVE = re.compile(
    _DIRECTIVE_PREFIX + r"disable-next-line\s*(?:=\s*(?P<ids>[\w,\s]*))?",
    re.IGNORECASE,
)
_SAME_LINE_DIRECTIVE = re.compile(
    _DIRECTIVE_PREFIX + r"disable(?!-next-line)\s*(?:=\s*(?P<ids>[\w,\s]*))?",
    re.IGNORECASE,
)

ALL_RULES_TOKEN = "*"

_LEGACY_PREFIX = "sql-guard"

# ``parse`` runs once per file, so the "a legacy directive was used" fact
# is kept here for the run's duration. ``checker.check`` resets it at the
# start of each run and reads it at the end; the CLI then prints the
# deprecation notice once per run.
_legacy_directive_seen = False


def legacy_directive_seen() -> bool:
    """Whether ``parse`` saw a ``sql-guard:`` directive since the last reset."""
    return _legacy_directive_seen


def reset_legacy_directive_seen() -> None:
    """Clear the legacy-prefix flag. Called once per run by ``checker.check``."""
    global _legacy_directive_seen
    _legacy_directive_seen = False


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
    directives apply to the line below. Both ``sql-sop:`` and the deprecated
    ``sql-guard:`` prefixes are accepted; seeing the legacy one raises the
    module flag read by ``legacy_directive_seen``.
    """
    global _legacy_directive_seen
    out = DisableMap()
    for line_no, line in enumerate(content.splitlines(), 1):
        directive = _NEXT_LINE_DIRECTIVE.search(line)
        target_line = line_no + 1
        if directive is None:
            directive = _SAME_LINE_DIRECTIVE.search(line)
            target_line = line_no
        if directive is None:
            continue
        if directive.group("tool").lower() == _LEGACY_PREFIX:
            _legacy_directive_seen = True
        out.add(target_line, _parse_ids(directive.group("ids")))
    return out
