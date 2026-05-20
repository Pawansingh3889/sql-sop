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
