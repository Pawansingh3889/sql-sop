"""sql-sop CLI -- check SQL files for common issues."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from sql_guard import __version__, config as config_mod
from sql_guard.checker import check, discover_files
from sql_guard.contracts import Contract
from sql_guard.git_filter import filter_to_changed
from sql_guard.reporters import sarif as sarif_reporter
from sql_guard.reporters.terminal import print_result
from sql_guard.rules import ALL_RULES, CONTRACT_RULE_CLASSES
from sql_guard.rules.python_rules import PYTHON_RULES

app = typer.Typer(
    name="sql-sop",
    help="Fast rule-based SQL linter.",
    no_args_is_help=True,
)
console = Console()


@app.command("check")
def check_cmd(
    paths: list[str] = typer.Argument(default=None, help="Files or directories to check."),
    severity: str = typer.Option("warning", "--severity", "-s", help="Minimum severity: error or warning."),
    fail_fast: bool = typer.Option(False, "--fail-fast", help="Stop after first error."),
    disable: Optional[list[str]] = typer.Option(None, "--disable", "-d", help="Rule IDs to disable."),
    include_python: bool = typer.Option(
        False,
        "--include-python",
        help="Also scan .py files for SQL strings in execute() calls (requires sql-sop[python]).",
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to .sql-guard.yml (default: walk up from cwd).",
    ),
    changed_only: bool = typer.Option(
        False,
        "--changed-only",
        help="Lint only files reported as changed by git (working tree by default).",
    ),
    changed_base: Optional[str] = typer.Option(
        None,
        "--changed-base",
        help="Compare against this git ref instead of the working tree (e.g. origin/main).",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        "-f",
        help="Output format: terminal (default) or sarif (for GitHub Code Scanning).",
    ),
    output_path: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Write report to this file instead of stdout (sarif format only).",
    ),
    contract_path: Optional[Path] = typer.Option(
        None,
        "--contract",
        help=(
            "Path to a data-contract YAML. When set, contract rules (C001-) "
            "lint queries against the declared schema."
        ),
    ),
) -> None:
    """Check SQL files for common issues."""
    if not paths:
        paths = ["."]

    cfg = config_mod.load(config_path)

    disabled: set[str] = set()
    if cfg.disable:
        disabled |= cfg.disable
    if disable:
        disabled |= {d.upper() for d in disable}

    effective_include_python = include_python or cfg.include_python
    effective_ignore = cfg.ignore or None

    contract: Optional[Contract] = None
    effective_contract_path = contract_path or cfg.contract
    if effective_contract_path is not None:
        try:
            contract = Contract.from_file(effective_contract_path)
        except FileNotFoundError:
            console.print(
                f"[red]Contract file not found:[/red] {effective_contract_path}"
            )
            raise typer.Exit(code=2)
        except Exception as exc:
            console.print(
                f"[red]Failed to load contract {effective_contract_path}:[/red] {exc}"
            )
            raise typer.Exit(code=2)

    if changed_only:
        discovered = discover_files(
            paths, ignore=effective_ignore, include_python=effective_include_python
        )
        kept, used_git = filter_to_changed(discovered, base=changed_base)
        if not used_git:
            console.print(
                "[yellow]--changed-only: not in a git repo (or git unavailable); "
                "scanning all discovered files.[/yellow]"
            )
        else:
            paths = [str(p) for p in kept]
            if not paths:
                console.print("[green]OK[/green] no changed files to lint.")
                return

    result = check(
        paths,
        severity=severity,
        fail_fast=fail_fast,
        disabled_rules=disabled or None,
        ignore=effective_ignore,
        include_python=effective_include_python,
        contract=contract,
    )

    if output_format == "sarif":
        rendered = sarif_reporter.render(result)
        if output_path:
            output_path.write_text(rendered, encoding="utf-8")
            console.print(f"Wrote SARIF to {output_path}")
        else:
            sys.stdout.write(rendered)
            sys.stdout.write("\n")
    else:
        print_result(result)

    if result.error_count > 0:
        raise typer.Exit(code=1)


@app.command("list-rules")
def list_rules() -> None:
    """List all available lint rules."""
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("ID")
    table.add_column("Severity")
    table.add_column("Name")
    table.add_column("Description", style="dim")

    for rule in ALL_RULES:
        sev = "[red]error[/red]" if rule.severity == "error" else "[yellow]warning[/yellow]"
        table.add_row(rule.id, sev, rule.name, rule.description)

    for rule in PYTHON_RULES:
        sev = "[red]error[/red]" if rule.severity == "error" else "[yellow]warning[/yellow]"
        table.add_row(rule.id, sev, rule.name, rule.description)

    console.print(table)


@app.command()
def version() -> None:
    """Show version."""
    console.print(f"sql-guard {__version__}")
