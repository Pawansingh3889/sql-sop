"""Project-level configuration via ``.sql-guard.yml`` (or ``.sql-guard.yaml``).

Schema:

.. code-block:: yaml

    disable:
      - W005
      - T001
    ignore:
      - migrations/legacy/
      - vendor/
    include_python: true
    severity: warning

CLI flags always win over the config file. The loader looks for a
``.sql-guard.yml`` or ``.sql-guard.yaml`` walking up from the given
start directory. If neither exists, the loader returns an empty
``Config`` so the rest of the codebase doesn't have to special-case
"no config".

PyYAML is a hard dependency so the loader never silently skips a config
file the user wrote.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CONFIG_FILENAMES = (".sql-guard.yml", ".sql-guard.yaml")


@dataclass
class Config:
    """Resolved project config. Empty when no file is present."""

    disable: set[str] = field(default_factory=set)
    ignore: list[str] = field(default_factory=list)
    include_python: bool = False
    severity: str = "warning"
    contract: Path | None = None
    source: Path | None = None

    @classmethod
    def from_dict(cls, data: dict, source: Path | None = None) -> "Config":
        contract_value = data.get("contract")
        contract_path: Path | None = None
        if contract_value:
            raw_path = Path(str(contract_value))
            # Resolve contract paths relative to the config file when
            # supplied, so a project-root config can reference
            # ``schema/contract.yml`` without fully-qualified paths.
            if not raw_path.is_absolute() and source is not None:
                raw_path = source.parent / raw_path
            contract_path = raw_path
        return cls(
            disable={s.upper() for s in (data.get("disable") or [])},
            ignore=list(data.get("ignore") or []),
            include_python=bool(data.get("include_python", False)),
            severity=str(data.get("severity") or "warning"),
            contract=contract_path,
            source=source,
        )


def find_config(start: Path | None = None) -> Path | None:
    """Walk up from ``start`` (default: cwd) looking for a config file."""
    here = (start or Path.cwd()).resolve()
    for directory in (here, *here.parents):
        for name in CONFIG_FILENAMES:
            candidate = directory / name
            if candidate.is_file():
                return candidate
    return None


def load(path: Path | None = None) -> Config:
    """Load config from ``path`` if given, else search via ``find_config``.

    Returns an empty ``Config`` when no file is present so callers don't
    need to None-check.
    """
    config_path = path if path is not None else find_config()
    if config_path is None or not config_path.is_file():
        return Config()
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"{config_path}: expected a YAML mapping at the top level")
    return Config.from_dict(raw, source=config_path)
