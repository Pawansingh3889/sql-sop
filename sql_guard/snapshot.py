"""Database introspection -> contract YAML.

The ``sql-sop schema-snapshot`` subcommand connects to a live database
via SQLAlchemy, walks every table, and writes a contract YAML in the
format that ``--contract`` consumes. This bootstraps the typical
"I don't have a contract yet" workflow: take a snapshot of the existing
schema, commit it as ``contract.yml``, and start linting against it.

SQLAlchemy is imported lazily so the linter's core install stays light.
Users who want this feature install ``sql-sop[snapshot]``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class SnapshotError(RuntimeError):
    """Raised on snapshot failure with a user-readable message."""


def _require_sqlalchemy() -> Any:
    try:
        import sqlalchemy  # type: ignore[import-untyped]
    except ImportError as exc:
        raise SnapshotError(
            "schema-snapshot requires SQLAlchemy. "
            "Install with: pip install \"sql-sop[snapshot]\""
        ) from exc
    return sqlalchemy


def _column_to_dict(column: Any, primary_keys: set[str], fk_targets: dict[str, str]) -> dict[str, Any]:
    """Convert a SQLAlchemy column to the contract column dict shape."""
    out: dict[str, Any] = {"type": str(column.type)}
    if not column.nullable:
        out["not_null"] = True
    if column.name in primary_keys:
        out["primary_key"] = True
    if column.default is not None or column.server_default is not None:
        out["has_default"] = True
    if column.name in fk_targets:
        out["foreign_key"] = fk_targets[column.name]
    return out


def introspect(
    dsn: str,
    schema: str | None = None,
    include_tables: list[str] | None = None,
) -> dict[str, Any]:
    """Connect to ``dsn`` and return a contract-shaped dict.

    Args:
        dsn: SQLAlchemy connection string, e.g.
            ``mssql+pyodbc://user:pass@host/dbname?driver=ODBC+Driver+18+for+SQL+Server``.
        schema: Optional schema/owner name. Defaults to the dialect default
            (``dbo`` on SQL Server, ``public`` on Postgres, etc.).
        include_tables: If given, restrict the snapshot to these tables.
    """
    sa = _require_sqlalchemy()
    engine = sa.create_engine(dsn)
    try:
        inspector = sa.inspect(engine)
        table_names = inspector.get_table_names(schema=schema)
        if include_tables:
            wanted = {t.lower() for t in include_tables}
            table_names = [t for t in table_names if t.lower() in wanted]

        out: dict[str, Any] = {"tables": {}}
        for table_name in table_names:
            columns = inspector.get_columns(table_name, schema=schema)
            pks = inspector.get_pk_constraint(table_name, schema=schema)
            pk_columns = set(pks.get("constrained_columns") or [])
            fks = inspector.get_foreign_keys(table_name, schema=schema)
            fk_targets: dict[str, str] = {}
            for fk in fks:
                # Foreign key entry shape: {'constrained_columns': ['customer_id'],
                #                           'referred_table': 'customers',
                #                           'referred_columns': ['id'], ...}
                src_cols = fk.get("constrained_columns") or []
                ref_table = fk.get("referred_table")
                ref_cols = fk.get("referred_columns") or []
                for src_col, ref_col in zip(src_cols, ref_cols):
                    if ref_table and ref_col:
                        fk_targets[src_col] = f"{ref_table}.{ref_col}"

            cols_dict: dict[str, Any] = {}
            for column in columns:
                cols_dict[column["name"]] = _column_to_dict_from_inspector(
                    column, pk_columns, fk_targets
                )
            out["tables"][table_name] = {"columns": cols_dict}

        return out
    finally:
        engine.dispose()


def _column_to_dict_from_inspector(
    column: dict[str, Any],
    primary_keys: set[str],
    fk_targets: dict[str, str],
) -> dict[str, Any]:
    """Same shape as ``_column_to_dict`` but takes the inspector dict form."""
    out: dict[str, Any] = {"type": str(column.get("type", ""))}
    if column.get("nullable") is False:
        out["not_null"] = True
    if column["name"] in primary_keys:
        out["primary_key"] = True
    if column.get("default") is not None or column.get("server_default") is not None:
        out["has_default"] = True
    if column["name"] in fk_targets:
        out["foreign_key"] = fk_targets[column["name"]]
    return out


def write_snapshot(snapshot: dict[str, Any], output_path: str | Path) -> None:
    """Write a snapshot dict to YAML, sorted for stable diffs."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(snapshot, sort_keys=True, default_flow_style=False),
        encoding="utf-8",
    )
