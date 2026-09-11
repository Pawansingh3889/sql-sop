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


class UnquotedVarInterpolation(Rule):
    """DBT007: ``{{ var(...) }}`` interpolated into SQL with no quotes.

    Named and scored deliberately conservative (see the ADR decision
    comment, issue #54): ``var()`` values come from ``dbt_project.yml``
    or the CLI at compile time, set by the project author, not
    untrusted runtime input. This is not an injection risk. The real
    failure mode is that an unquoted interpolation produces a syntax
    error, or silently the wrong literal, the day someone sets that var
    to a value containing whitespace or a quote. ``warning``, not
    ``error``.

    Flags ``{{ var(...) }}`` when the character immediately before and
    after it is not ``'``. Deliberately narrow: a var() call used
    inside a Jinja control block (``{% if var('flag') %}``) is a
    different delimiter and never matches; a var() call nested inside
    another Jinja expression (``{{ config(threshold=var('x')) }}``)
    has no ``{{`` of its own immediately before ``var`` and doesn't
    match either. Both are correctly out of scope, not interpolation
    into SQL text.
    """

    id = "DBT007"
    name = "unquoted-var-interpolation"
    severity = "warning"
    description = "{{ var(...) }} interpolated into SQL without quotes"

    _var_call = re.compile(r"\{\{\s*var\s*\(.*?\)\s*\}\}", re.IGNORECASE | re.DOTALL)

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

        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return []

        findings: list[Finding] = []
        for match in self._var_call.finditer(content):
            before = content[match.start() - 1] if match.start() > 0 else ""
            after = content[match.end()] if match.end() < len(content) else ""
            if before == "'" and after == "'":
                continue

            line = content[: match.start()].count("\n") + 1
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=line,
                    message="{{ var(...) }} interpolated without surrounding quotes",
                    suggestion=(
                        "Wrap it in quotes: '{{ var(...) }}', unless this is "
                        "deliberately a bare numeric value."
                    ),
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
