"""dbt project discovery helpers.

When sql-sop is invoked with ``--dbt`` it needs to know where the dbt
project lives so it can read ``dbt_project.yml`` and any ``schema.yml``
files. This module owns that discovery. It does not parse Jinja or run
any rule logic; rules in :mod:`sql_guard.rules.dbt` consume the
:class:`DbtProject` it produces.

Scope discipline: static reads only. No subprocess, no ``dbt compile``,
no DB connection. See the dbt-aware rule pack ADR for the rationale.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


# Default model-paths used by dbt when the key is absent from
# dbt_project.yml. Matches dbt's own default ("models") as of dbt 1.7.
_DEFAULT_MODEL_PATHS = ("models",)


@dataclass(frozen=True)
class DbtModelEntry:
    """A model declaration read from a ``schema.yml`` file.

    Only the fields the dbt-aware rule pack actually reads are captured.
    Anything else in the YAML is ignored. Extending this is cheap when a
    new rule needs another field.
    """

    name: str
    has_tests: bool
    description: str | None
    source_file: Path


@dataclass(frozen=True)
class DbtProject:
    """A discovered dbt project.

    ``root`` is the directory containing ``dbt_project.yml``.
    ``model_paths`` are absolute paths to the configured model dirs.
    ``models`` is the merged set of model entries across every
    ``schema.yml`` found under ``model_paths``.
    """

    root: Path
    model_paths: tuple[Path, ...]
    models: tuple[DbtModelEntry, ...] = field(default_factory=tuple)


def find_dbt_project(start: Path) -> Path | None:
    """Walk up from ``start`` looking for ``dbt_project.yml``.

    Returns the absolute path to the YAML file, or ``None`` if no
    ``dbt_project.yml`` is found before reaching the filesystem root.

    ``start`` may be either a file or a directory. If a file is given
    the search begins in its parent directory.
    """
    current = start.resolve()
    if current.is_file():
        current = current.parent
    while True:
        candidate = current / "dbt_project.yml"
        if candidate.is_file():
            return candidate
        if current.parent == current:
            return None
        current = current.parent


def load_dbt_project(project_yml: Path) -> DbtProject:
    """Read ``dbt_project.yml`` and discover models under model-paths.

    Parses the YAML, resolves ``model-paths`` (falling back to dbt's
    default of ``models``), then walks each model dir for
    ``schema.yml`` files and pulls model entries out of them.

    The function is forgiving: a malformed ``schema.yml`` produces an
    empty contribution rather than raising. Linting must not crash
    because somebody left a comment-only stub in their schema.yml.
    """
    project_yml = project_yml.resolve()
    root = project_yml.parent

    with project_yml.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    raw_paths = data.get("model-paths") or list(_DEFAULT_MODEL_PATHS)
    model_paths = tuple((root / rel).resolve() for rel in raw_paths)

    models: list[DbtModelEntry] = []
    for model_dir in model_paths:
        if not model_dir.is_dir():
            continue
        for schema_file in model_dir.rglob("schema.yml"):
            models.extend(_read_schema_yml(schema_file))

    return DbtProject(root=root, model_paths=model_paths, models=tuple(models))


def _read_schema_yml(schema_file: Path) -> list[DbtModelEntry]:
    """Parse one ``schema.yml`` into ``DbtModelEntry`` rows.

    Models without a ``name`` key are skipped (malformed). A model is
    considered to have tests if it carries either a top-level ``tests``
    key (dbt <=1.4 spelling) or a ``data_tests`` key (dbt >=1.5
    spelling). The dbt-aware rule pack accepts both.
    """
    try:
        with schema_file.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError:
        return []

    entries: list[DbtModelEntry] = []
    for model in data.get("models") or []:
        if not isinstance(model, dict):
            continue
        name = model.get("name")
        if not isinstance(name, str) or not name:
            continue
        has_tests = bool(model.get("tests") or model.get("data_tests"))
        description = model.get("description")
        if description is not None and not isinstance(description, str):
            description = str(description)
        entries.append(
            DbtModelEntry(
                name=name,
                has_tests=has_tests,
                description=description,
                source_file=schema_file,
            )
        )
    return entries
