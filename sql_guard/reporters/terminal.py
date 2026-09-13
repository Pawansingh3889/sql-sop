"""Rich terminal reporter."""

from __future__ import annotations

from rich.console import Console

from sql_guard.checker import CheckResult

console = Console()


def print_result(result: CheckResult) -> None:
    """Print findings grouped by file."""
    if not result.findings:
        console.print(
            f"\n[green]OK[/green] {result.files_checked} files checked -- no issues found "
            f"[dim]({result.duration_seconds}s)[/dim]"
        )
        return

    # Group by file
    by_file: dict[str, list] = {}
    for f in result.findings:
        by_file.setdefault(f.file, []).append(f)

    console.print()
    for file, findings in sorted(by_file.items()):
        console.print(f"[bold]{file}[/bold]")
        for f in sorted(findings, key=lambda x: x.line):
            icon = "[red]ERROR[/red]" if f.severity == "error" else "[yellow]WARN[/yellow]"
            console.print(f"  L{f.line}:  {icon} [{f.rule_id}] {f.message}")
            if f.suggestion:
                console.print(f"         [dim]-> {f.suggestion}[/dim]")
        console.print()

    errors = result.error_count
    warnings = result.warning_count
    total = errors + warnings

    summary_parts = []
    if errors:
        summary_parts.append(f"[red]{errors} error{'s' if errors != 1 else ''}[/red]")
    if warnings:
        summary_parts.append(f"[yellow]{warnings} warning{'s' if warnings != 1 else ''}[/yellow]")

    console.print(
        f"Found {total} issue{'s' if total != 1 else ''} "
        f"({', '.join(summary_parts)}) "
        f"in {result.files_with_issues} file{'s' if result.files_with_issues != 1 else ''} "
        f"[dim]({result.duration_seconds}s)[/dim]"
    )

    # Soft CTA - only when we actually found things, never on clean runs.
    # Keep this single-line and dim so it doesn't drown out the real output.
    console.print(
        "[dim]Missing a pattern sql-sop should catch? "
        "File a rule request: "
        "https://github.com/Pawansingh3889/sql-sop/issues/new?template=rule-request.yml[/dim]"
    )
