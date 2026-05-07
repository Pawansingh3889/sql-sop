"""``--changed-only`` support: filter the file list to git-changed files.

Calls ``git diff --name-only --diff-filter=ACMR`` against the working
tree (or against ``base`` when supplied) and returns the resolved set
of paths. When the cwd is not inside a git repo, returns ``None`` so
the caller can decide whether to fall back to the full file list.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def _run_git(args: list[str]) -> list[str] | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def changed_files(base: str | None = None) -> set[Path] | None:
    """Return the set of changed files relative to ``base`` (or the working tree).

    ``base`` is any git ref. When None, returns files changed in the
    working tree (staged + unstaged + untracked). Returns ``None`` when
    git is unavailable or the cwd is not a git repo.
    """
    if _run_git(["rev-parse", "--git-dir"]) is None:
        return None

    out: set[Path] = set()
    if base:
        diff = _run_git(["diff", "--name-only", "--diff-filter=ACMR", base])
    else:
        # Working-tree diff against the index, plus the index itself, plus untracked.
        unstaged = _run_git(["diff", "--name-only", "--diff-filter=ACMR"]) or []
        staged = _run_git(["diff", "--name-only", "--diff-filter=ACMR", "--cached"]) or []
        untracked = _run_git(["ls-files", "--others", "--exclude-standard"]) or []
        diff = list({*unstaged, *staged, *untracked})
    if diff is None:
        return None

    for raw in diff:
        out.add(Path(raw).resolve())
    return out


def filter_to_changed(discovered: list[Path], base: str | None = None) -> tuple[list[Path], bool]:
    """Filter ``discovered`` to only the files git reports as changed.

    Returns ``(filtered_paths, used_git)``. When git isn't available the
    second element is False and the original list is returned unchanged.
    """
    changed = changed_files(base=base)
    if changed is None:
        return discovered, False
    keep = [p for p in discovered if p.resolve() in changed]
    return keep, True
