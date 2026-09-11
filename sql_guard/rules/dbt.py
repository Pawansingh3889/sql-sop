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
from sql_guard.rules.base import Finding, Rule, strip_strings_and_comments


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


class DirectTableRef(Rule):
    """DBT002: raw table name in FROM/JOIN instead of ref()/source().

    Flags ``FROM orders`` / ``JOIN raw_db.orders`` where a dbt model
    should instead use ``{{ ref('orders') }}`` or
    ``{{ source('raw_db', 'orders') }}`` so dbt can build the dependency
    graph and run models in the right order.

    Design (see the ADR decision comment, issue #54): no Jinja
    preprocessing. The check walks the untouched file text looking for
    ``FROM`` / ``JOIN`` keywords and inspects whatever token follows:

    - Starts with ``{{``: already templated (``ref``, ``source``,
      ``this``, ``var``, or any other macro). Not this rule's concern.
    - Starts with ``(``: a subquery, not a table name. Skip.
    - A bare or dotted identifier: a candidate raw reference, unless it
      names a CTE defined earlier in the same statement (``WITH x AS
      (...)`` / ``, y AS (...)``) or falls under an allowlisted system
      schema (``information_schema``, ``pg_catalog``, and friends).

    Because nothing is rewritten or stripped before the scan, the line
    number reported is always the file's own line number.
    """

    id = "DBT002"
    name = "direct-table-ref"
    severity = "warning"
    description = "Raw table name in FROM/JOIN instead of ref()/source()"

    _keyword = re.compile(r"\b(?:FROM|JOIN)\b", re.IGNORECASE)
    _identifier = re.compile(r"[A-Za-z_][A-Za-z0-9_$]*(?:\.[A-Za-z_][A-Za-z0-9_$]*)*")
    _cte_name = re.compile(r"\bWITH\s+(\w+)\s+AS\b|,\s*(\w+)\s+AS\s*\(", re.IGNORECASE)

    # System/information schemas dbt users legitimately query directly.
    _allowlisted_schemas = frozenset(
        {"information_schema", "pg_catalog", "pg_temp", "sys", "mysql", "performance_schema"}
    )

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

        cleaned = strip_strings_and_comments(content)
        cte_names = {
            (m.group(1) or m.group(2)).upper() for m in self._cte_name.finditer(cleaned)
        }

        findings: list[Finding] = []
        for kw in self._keyword.finditer(cleaned):
            i = kw.end()
            while i < len(cleaned) and cleaned[i].isspace():
                i += 1
            rest = cleaned[i:]

            if rest.startswith(("{{", "(")):
                continue

            match = self._identifier.match(rest)
            if not match:
                continue
            name = match.group(0)

            parts = name.split(".")
            if parts[-1].upper() in cte_names:
                continue
            if any(p.lower() in self._allowlisted_schemas for p in parts):
                continue

            line = cleaned[: kw.start()].count("\n") + 1
            findings.append(
                Finding(
                    rule_id=self.id,
                    severity=self.severity,
                    file=file,
                    line=line,
                    message=f"Raw table reference '{name}' instead of ref()/source()",
                    suggestion=(
                        "Use {{ ref('model_name') }} for other dbt models or "
                        "{{ source('source_name', 'table_name') }} for raw sources."
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
