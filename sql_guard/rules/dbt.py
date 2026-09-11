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


class HookWithDdl(Rule):
    """DBT004: destructive or structural DDL in pre_hook / post_hook.

    Reads the ``pre_hook`` / ``post_hook`` argument(s) of the
    ``{{ config(...) }}`` call with a targeted regex, not a general
    Jinja preprocessor (see the ADR decision comment, issue #54).
    Handles both a single string and a list of strings, since dbt
    accepts either.

    Severity splits the destructive from the structural: ``DROP`` /
    ``TRUNCATE`` / ``DELETE`` wipe data and are almost always a sign a
    hook is doing something that belongs in its own model or migration
    -- ``error``. ``ALTER`` is a common, sanctioned pattern (adding a
    cluster key, a table property tweak) and stays a ``warning`` so it
    is visible without blocking CI on something that is often fine.
    """

    id = "DBT004"
    name = "hook-with-ddl"
    severity = "error"
    description = "pre_hook/post_hook contains destructive or structural DDL"

    _config_call = re.compile(
        r"\{\{\s*config\s*\((?P<args>.*?)\)\s*[-]?\}\}", re.IGNORECASE | re.DOTALL
    )
    _hook_arg = re.compile(
        r"\b(pre_hook|post_hook)\s*=\s*(\[.*?\]|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")",
        re.IGNORECASE | re.DOTALL,
    )
    _quoted_string = re.compile(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"")
    _destructive = re.compile(r"\b(?:DROP|TRUNCATE|DELETE)\b", re.IGNORECASE)
    _structural = re.compile(r"\bALTER\b", re.IGNORECASE)

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

        config_match = self._config_call.search(content)
        if not config_match:
            return []
        args = config_match.group("args")
        line = content[: config_match.start()].count("\n") + 1

        findings: list[Finding] = []
        for hook_match in self._hook_arg.finditer(args):
            hook_name = hook_match.group(1)
            value_blob = hook_match.group(2)
            statements = [
                a or b for a, b in self._quoted_string.findall(value_blob) if (a or b)
            ]

            for statement in statements:
                if self._destructive.search(statement):
                    findings.append(
                        Finding(
                            rule_id=self.id,
                            severity="error",
                            file=file,
                            line=line,
                            message=f"{hook_name} contains DROP/TRUNCATE/DELETE",
                            suggestion=(
                                "Move destructive DDL out of pre_hook/post_hook "
                                "and into its own model or migration."
                            ),
                        )
                    )
                elif self._structural.search(statement):
                    findings.append(
                        Finding(
                            rule_id=self.id,
                            severity="warning",
                            file=file,
                            line=line,
                            message=f"{hook_name} contains ALTER",
                            suggestion=(
                                "Confirm this ALTER is intentional (e.g. a cluster "
                                "key or table property) and not leftover DDL."
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
