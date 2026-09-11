"""dbt-aware rule pack (DBT001-DBT00N).

Opt-in via the ``--dbt`` CLI flag. Each rule consumes a
:class:`sql_guard.dbt.DbtProject` describing the discovered project
layout and reads ``schema.yml`` / ``dbt_project.yml`` at lint time.
Silent unless ``--dbt`` is supplied; existing users see no behaviour
change.

Severity split, per the ADR:
- ``warning``: DBT001, DBT002, DBT005, DBT006
- ``error``:   DBT003, DBT004, DBT007
"""

from __future__ import annotations

import re
from pathlib import Path

from sql_guard.dbt import DbtProject
from sql_guard.rules.base import Finding, Rule


class ModelWithoutTest(Rule):
    """DBT001: dbt model has no ``tests:`` entry in ``schema.yml``.

    A model is reported untested when either:

    - It is not declared in any ``schema.yml`` under the project's
      ``model-paths`` (so it has no metadata at all, tests included).
    - It is declared in ``schema.yml`` but the entry carries neither a
      ``tests:`` key (dbt <=1.4 spelling) nor a ``data_tests:`` key
      (dbt >=1.5 spelling). The discovery layer normalises both into
      :attr:`sql_guard.dbt.DbtModelEntry.has_tests`.

    Fires once per .sql file inside the project's ``model-paths``.
    Files outside those paths (macros, analyses, seeds, snapshots) are
    skipped so the rule does not fire on infrastructure that isn't a
    model. Silent unless ``--dbt`` is supplied because the rule is only
    registered when :func:`sql_guard.rules.build_dbt_rules` is called
    with a discovered :class:`DbtProject`.
    """

    id = "DBT001"
    name = "model-without-test"
    severity = "warning"
    description = "dbt model has no tests: entry in schema.yml"

    def __init__(self, project: DbtProject) -> None:
        self._project = project

    def check_file(self, file: str) -> list[Finding]:
        path = Path(file)
        if path.suffix != ".sql":
            return []

        resolved = path.resolve()
        in_models = any(
            _is_relative_to(resolved, model_dir) for model_dir in self._project.model_paths
        )
        if not in_models:
            return []

        model_name = path.stem
        entry = next(
            (m for m in self._project.models if m.name == model_name),
            None,
        )
        if entry is not None and entry.has_tests:
            return []

        return [
            Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=1,
                message=f"dbt model '{model_name}' has no tests: entry in schema.yml",
                suggestion=(
                    "Add a tests: (or data_tests:) block for this model in "
                    "schema.yml, or add the model to schema.yml if it is "
                    "missing entirely."
                ),
            )
        ]


class SelectStarInMart(Rule):
    """DBT005: ``SELECT *`` in a model under a mart directory.

    Refines W001 (``select-star``) with dbt context: a ``SELECT *``
    inside a view or CTE freezes the column list at whatever the
    underlying table has today, and a mart is the layer downstream
    tools and dashboards actually query, so the surprise lands on
    someone who isn't looking at this file when the source table
    changes shape.

    "Mart" is a naming convention, not a dbt concept, so this checks a
    path segment named ``marts`` (case-insensitive) inside the
    project's configured ``model-paths``. v1 hardcodes that default;
    a configurable glob is future work, not plumbed through the CLI
    yet.

    ``checker.check_file`` drops a W001 finding on the same
    ``file:line`` as a DBT005 finding so the two rules don't double-
    report one ``SELECT *`` (see the ADR decision comment, issue #54).
    W001 itself stays a plain-SQL rule with no dbt awareness; the
    dedup lives in the checker, not in either rule.
    """

    id = "DBT005"
    name = "select-star-in-mart"
    severity = "warning"
    description = "SELECT * in a mart model"

    _select_star = re.compile(r"\bSELECT\s+\*\s+FROM\b", re.IGNORECASE)
    _MART_SEGMENT = "marts"

    def __init__(self, project: DbtProject) -> None:
        self._project = project

    def _mart_dir_for(self, resolved: Path) -> bool:
        for model_dir in self._project.model_paths:
            if not _is_relative_to(resolved, model_dir):
                continue
            parts = resolved.relative_to(model_dir).parts
            if any(part.lower() == self._MART_SEGMENT for part in parts):
                return True
        return False

    def check_file(self, file: str) -> list[Finding]:
        path = Path(file)
        if path.suffix != ".sql":
            return []

        resolved = path.resolve()
        if not self._mart_dir_for(resolved):
            return []

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []

        findings: list[Finding] = []
        for line_number, line in enumerate(content.splitlines(), 1):
            if self._select_star.search(line):
                findings.append(
                    Finding(
                        rule_id=self.id,
                        severity=self.severity,
                        file=file,
                        line=line_number,
                        message=(
                            "SELECT * in a mart model -- the column list freezes "
                            "and surprises downstream consumers when the "
                            "underlying table changes shape"
                        ),
                        suggestion="Enumerate the columns explicitly.",
                    )
                )
        return findings


def _is_relative_to(child: Path, parent: Path) -> bool:
    """Cross-version Path.is_relative_to helper.

    Python's ``Path.is_relative_to`` was added in 3.9 and is fine on the
    supported versions, but the inline ``try / except ValueError``
    works regardless of platform path-resolution quirks on Windows.
    """
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
