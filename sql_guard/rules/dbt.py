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
