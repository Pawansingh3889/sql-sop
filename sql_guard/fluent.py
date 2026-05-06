"""Fluent API for sql-guard.

Provides a chainable builder pattern for programmatic SQL validation.

Usage:
    from sql_guard import SqlGuard

    result = (
        SqlGuard()
        .enable("E001", "E002", "W001")
        .severity("error")
        .scan("SELECT * FROM users WHERE 1=1")
    )

    # Or scan files:
    result = SqlGuard().scan_file("queries/report.sql")
    print(result.passed)       # True/False
    print(result.findings)     # List of Finding objects
    print(result.summary())    # "2 errors, 3 warnings in 1 file"
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from sql_guard.checker import check, check_file
from sql_guard.rules import get_rules
from sql_guard.rules.base import Finding


@dataclass
class ScanResult:
    """Result of a fluent API scan."""

    findings: list[Finding] = field(default_factory=list)
    files_checked: int = 0
    _severity_filter: str = "warning"

    @property
    def passed(self) -> bool:
        """True if no findings at or above the configured severity."""
        if self._severity_filter == "error":
            return not self.errors
        return len(self.findings) == 0

    @property
    def errors(self) -> list[Finding]:
        """Findings with severity 'error'."""
        return [f for f in self.findings if f.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        """Findings with severity 'warning'."""
        return [f for f in self.findings if f.severity == "warning"]

    def summary(self) -> str:
        """Human-readable summary string."""
        n_errors = len(self.errors)
        n_warnings = len(self.warnings)
        parts: list[str] = []
        if n_errors:
            parts.append(f"{n_errors} error{'s' if n_errors != 1 else ''}")
        if n_warnings:
            parts.append(f"{n_warnings} warning{'s' if n_warnings != 1 else ''}")
        if not parts:
            return f"no issues in {self.files_checked} file{'s' if self.files_checked != 1 else ''}"
        count_str = ", ".join(parts)
        return f"{count_str} in {self.files_checked} file{'s' if self.files_checked != 1 else ''}"

    def __len__(self) -> int:
        return len(self.findings)

    def __bool__(self) -> bool:
        return self.passed


class SqlGuard:
    """Chainable builder for SQL validation.

    Example::

        result = (
            SqlGuard()
            .enable("E001", "W001")
            .severity("error")
            .scan("DELETE FROM orders;")
        )
    """

    def __init__(self) -> None:
        self._enabled: set[str] | None = None
        self._disabled: set[str] | None = None
        self._severity: str = "warning"

    def enable(self, *rule_ids: str) -> SqlGuard:
        """Only enable specific rules (default: all)."""
        if self._enabled is None:
            self._enabled = set()
        self._enabled.update(rule_ids)
        return self

    def disable(self, *rule_ids: str) -> SqlGuard:
        """Disable specific rules."""
        if self._disabled is None:
            self._disabled = set()
        self._disabled.update(rule_ids)
        return self

    def severity(self, level: str) -> SqlGuard:
        """Set minimum severity filter ('error' or 'warning')."""
        if level not in ("error", "warning"):
            raise ValueError(f"severity must be 'error' or 'warning', got {level!r}")
        self._severity = level
        return self

    def scan(self, sql_string: str) -> ScanResult:
        """Scan a SQL string and return a ScanResult."""
        rules = get_rules(enabled_ids=self._enabled, disabled_ids=self._disabled)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sql",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(sql_string)
            tmp_path = Path(tmp.name)

        try:
            file_findings = check_file(tmp_path, rules)
        finally:
            tmp_path.unlink(missing_ok=True)

        if self._severity == "error":
            file_findings = [f for f in file_findings if f.severity == "error"]

        return ScanResult(
            findings=file_findings,
            files_checked=1,
            _severity_filter=self._severity,
        )

    def scan_file(self, path: str | Path) -> ScanResult:
        """Scan a single SQL file and return a ScanResult."""
        result = check(
            paths=[str(path)],
            severity=self._severity,
            disabled_rules=self._disabled,
        )

        # When enabled_ids is set, post-filter since check() only supports disabled
        findings = result.findings
        if self._enabled is not None:
            findings = [f for f in findings if f.rule_id in self._enabled]

        return ScanResult(
            findings=findings,
            files_checked=result.files_checked,
            _severity_filter=self._severity,
        )

    def scan_dir(self, path: str | Path, pattern: str = "**/*.sql") -> ScanResult:
        """Scan a directory for SQL files and return a ScanResult."""
        base = Path(path)
        sql_files = sorted(base.glob(pattern))

        rules = get_rules(enabled_ids=self._enabled, disabled_ids=self._disabled)
        all_findings: list[Finding] = []

        for sql_file in sql_files:
            file_findings = check_file(sql_file, rules)
            if self._severity == "error":
                file_findings = [f for f in file_findings if f.severity == "error"]
            all_findings.extend(file_findings)

        return ScanResult(
            findings=all_findings,
            files_checked=len(sql_files),
            _severity_filter=self._severity,
        )
