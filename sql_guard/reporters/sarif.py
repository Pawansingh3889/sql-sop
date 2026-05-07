"""SARIF 2.1.0 output for GitHub Code Scanning.

GitHub's ``codeql/upload-sarif`` action ingests this format and renders
findings inline on PRs. Spec:
https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html
"""

from __future__ import annotations

import json
from pathlib import Path

from sql_guard import __version__
from sql_guard.checker import CheckResult
from sql_guard.rules import ALL_RULES
from sql_guard.rules.python_rules import PYTHON_RULES

INFO_URI = "https://github.com/Pawansingh3889/sql-guard"
SARIF_SCHEMA = (
    "https://docs.oasis-open.org/sarif/sarif/v2.1.0/cos02/schemas/sarif-schema-2.1.0.json"
)


def _level(severity: str) -> str:
    """Map sql-guard severity to SARIF level."""
    return {"error": "error", "warning": "warning"}.get(severity, "note")


def _all_rule_descriptors() -> list[dict]:
    """Build the SARIF rule catalogue."""
    descriptors: list[dict] = []
    for rule in [*ALL_RULES, *PYTHON_RULES]:
        descriptors.append(
            {
                "id": rule.id,
                "name": rule.name,
                "shortDescription": {"text": rule.description},
                "fullDescription": {"text": rule.description},
                "defaultConfiguration": {"level": _level(rule.severity)},
                "helpUri": INFO_URI,
            }
        )
    return descriptors


def build(result: CheckResult) -> dict:
    """Build the SARIF document as a Python dict."""
    results: list[dict] = []
    for finding in result.findings:
        sarif_result = {
            "ruleId": finding.rule_id,
            "level": _level(finding.severity),
            "message": {"text": finding.message},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {
                            "uri": str(Path(finding.file).as_posix()),
                        },
                        "region": {"startLine": max(1, finding.line)},
                    },
                }
            ],
        }
        if finding.suggestion:
            sarif_result["message"]["text"] += f" -- {finding.suggestion}"
        results.append(sarif_result)

    return {
        "$schema": SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "sql-guard",
                        "version": __version__,
                        "informationUri": INFO_URI,
                        "rules": _all_rule_descriptors(),
                    },
                },
                "results": results,
            }
        ],
    }


def render(result: CheckResult) -> str:
    """Serialize the SARIF document as JSON suitable for upload-sarif."""
    return json.dumps(build(result), indent=2)
