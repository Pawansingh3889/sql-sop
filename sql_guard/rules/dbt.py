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


class ModelWithoutDescription(Rule):
    """DBT006: dbt model listed in schema.yml has no ``description:``.

    Catches metadata drift after a refactor: a model gets renamed or
    split, someone adds the new entry to schema.yml so DBT001 stays
    quiet, but the description never gets written. Silent for a model
    that isn't in schema.yml at all -- that's DBT001's job, not this
    rule's; flagging both for the same missing entry would be the kind
    of double-noise the ADR (issue #54) explicitly wants to avoid.
    """

    id = "DBT006"
    name = "model-without-description"
    severity = "warning"
    description = "dbt model has no description: in schema.yml"

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
        if entry is None:
            # Not in schema.yml at all -- DBT001 covers that gap.
            return []
        if entry.description:
            return []

        return [
            Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=1,
                message=f"dbt model '{model_name}' has no description: in schema.yml",
                suggestion=f"Add a description: to the '{model_name}' entry in schema.yml.",
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
