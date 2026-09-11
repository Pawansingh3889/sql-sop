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


class IncrementalWithoutUniqueKey(Rule):
    """DBT003: ``materialized='incremental'`` with no ``unique_key``.

    Reads the ``{{ config(...) }}`` call at the top of a model file
    (the common way to set per-model config) with a small targeted
    regex, not a general Jinja preprocessor -- see the ADR decision
    comment, issue #54. Silent for models that don't call ``config()``
    at all, since a model without a ``config()`` call cannot be
    materialized as incremental in the first place.

    Severity depends on ``incremental_strategy``, because a missing
    ``unique_key`` is not equally risky everywhere:

    - ``merge`` / ``delete+insert``: the merge key is how these
      strategies avoid duplicate rows. Missing it is silent data
      corruption. ``error``.
    - ``append`` / ``insert_overwrite``: neither strategy merges on a
      key (append never merges; insert_overwrite replaces by
      partition). Nothing to flag. Silent.
    - Strategy not set in the ``config()`` call: the adapter's default
      strategy varies (and isn't visible to a static file-level check),
      so guessing would risk exactly the false-positive rate
      GOVERNANCE.md warns against. ``warning``.
    """

    id = "DBT003"
    name = "incremental-without-unique-key"
    severity = "error"
    description = "materialized='incremental' with no unique_key"

    _config_call = re.compile(r"\{\{\s*config\s*\((?P<args>.*?)\)\s*[-]?\}\}", re.IGNORECASE | re.DOTALL)
    _materialized_incremental = re.compile(r"materialized\s*=\s*['\"]incremental['\"]", re.IGNORECASE)
    _unique_key = re.compile(r"\bunique_key\s*=")
    _incremental_strategy = re.compile(
        r"incremental_strategy\s*=\s*['\"](?P<strategy>[\w+-]+)['\"]", re.IGNORECASE
    )

    _KEY_REQUIRED_STRATEGIES = frozenset({"merge", "delete+insert"})
    _KEY_NOT_NEEDED_STRATEGIES = frozenset({"append", "insert_overwrite"})

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

        match = self._config_call.search(content)
        if not match:
            return []
        args = match.group("args")

        if not self._materialized_incremental.search(args):
            return []
        if self._unique_key.search(args):
            return []

        strategy_match = self._incremental_strategy.search(args)
        if strategy_match:
            strategy = strategy_match.group("strategy").lower()
            if strategy in self._KEY_NOT_NEEDED_STRATEGIES:
                return []
            severity = "error" if strategy in self._KEY_REQUIRED_STRATEGIES else "warning"
            strategy_note = f"incremental_strategy='{strategy}'"
        else:
            severity = "warning"
            strategy_note = "incremental_strategy not set"

        line = content[: match.start()].count("\n") + 1
        return [
            Finding(
                rule_id=self.id,
                severity=severity,
                file=file,
                line=line,
                message=f"materialized='incremental' with no unique_key ({strategy_note})",
                suggestion=(
                    "Add unique_key=... to the config() call, or use "
                    "incremental_strategy='append' if there is genuinely "
                    "nothing to merge on."
                ),
            )
        ]


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
