"""Tests for the SARIF reporter."""

from __future__ import annotations

import json

from sql_guard.checker import CheckResult
from sql_guard.reporters import sarif as sarif_reporter
from sql_guard.rules.base import Finding


def _result(*findings: Finding) -> CheckResult:
    r = CheckResult()
    r.findings.extend(findings)
    r.files_checked = 1
    r.files_with_issues = 1 if findings else 0
    return r


def test_sarif_envelope_shape():
    doc = sarif_reporter.build(_result())
    assert doc["version"] == "2.1.0"
    assert "$schema" in doc
    runs = doc["runs"]
    assert len(runs) == 1
    assert runs[0]["tool"]["driver"]["name"] == "sql-guard"
    assert isinstance(runs[0]["tool"]["driver"]["rules"], list)


def test_sarif_emits_each_finding():
    finding = Finding(
        rule_id="W001",
        severity="warning",
        file="demo.sql",
        line=4,
        message="SELECT *",
        suggestion="list columns",
    )
    doc = sarif_reporter.build(_result(finding))
    results = doc["runs"][0]["results"]
    assert len(results) == 1
    r = results[0]
    assert r["ruleId"] == "W001"
    assert r["level"] == "warning"
    assert "list columns" in r["message"]["text"]
    loc = r["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"] == "demo.sql"
    assert loc["region"]["startLine"] == 4


def test_sarif_render_returns_valid_json():
    finding = Finding(rule_id="E001", severity="error", file="x.sql", line=1, message="m")
    blob = sarif_reporter.render(_result(finding))
    parsed = json.loads(blob)
    assert parsed["runs"][0]["results"][0]["ruleId"] == "E001"


def test_sarif_clamps_line_zero_to_one():
    # SARIF requires startLine >= 1; system findings with line=0 must be normalised.
    finding = Finding(rule_id="SYS", severity="error", file="x.sql", line=0, message="cannot read")
    doc = sarif_reporter.build(_result(finding))
    assert (
        doc["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 1
    )
