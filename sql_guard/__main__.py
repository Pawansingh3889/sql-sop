"""Entry point for ``python -m sql_guard``.

Runs the same Typer app as the ``sql-sop`` console script, for setups
where the scripts directory is not on ``PATH`` (some CI images and
Windows environments) or where the linter must run under a specific
interpreter. ``prog_name`` keeps the help banner saying ``sql-sop``
instead of ``python -m sql_guard``.
"""

from sql_guard.cli import app

if __name__ == "__main__":
    app(prog_name="sql-sop")
