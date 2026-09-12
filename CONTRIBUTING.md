# Contributing to sql-sop

sql-sop is a rule-based SQL linter published on PyPI. Contributions
are welcome; the rules below keep the project fast, stable, and
trustworthy to downstream users.

Before you start, skim:

- [**`GOVERNANCE.md`**](GOVERNANCE.md) — roles, first-PR-wins, why the
  licence will stay MIT.
- [**`CODE_OF_CONDUCT.md`**](CODE_OF_CONDUCT.md) — behavioural bar.
- [**`SECURITY.md`**](SECURITY.md) — false-negative / bypass reports go
  there, not in a public issue.

## The Prime Directive

**Every rule has tests that cover both "fires on bad SQL" and "does
not fire on safe SQL".** Rule IDs are public API — `E001`, `W001`, etc.
appear in downstream users' pre-commit configs and CI badges. Don't
renumber, don't silently change default severity, don't remove
without a deprecation window.

## Quick Start

```bash
git clone https://github.com/YOUR_USERNAME/sql-sop.git
cd sql-sop
pip install -e ".[python]"
pytest -q            # 78 tests across SQL + Python scanning
ruff check .
```

Try the CLI locally:

```bash
sql-sop check tests/fixtures/errors.sql
```

## How to Contribute

1. **Find or open an issue.** Watch labels `good first issue`,
   `help wanted`, `new-rule`.
2. **Claim it** by commenting — 7-day soft claim per `GOVERNANCE.md`.
3. **Branch.** `feature/<short-name>` or `bugfix/<short-name>`.
4. **Code + test.**
5. **Before pushing:** `ruff check .`, `pytest -q`.
6. **Open the PR.** Conventional commit style, one logical change per
   commit.

## Adding a new rule

The common case. Walkthrough:

1. Pick the next unused ID in the appropriate family (`E00N` for
   errors, `W0NN` for warnings, `S00N` for structural, `P00N` for
   Python-scanner rules).
2. Add the class to the matching file under `sql_guard/rules/`.
3. Register it in `sql_guard/rules/__init__.py` (import + append to
   `ALL_RULES`).
4. Add a fixture line to `tests/fixtures/errors.sql` or
   `tests/fixtures/warnings.sql` (or create a new fixture if the
   pattern is complex).
5. Add at least two tests in `tests/test_rules.py`:
   - fires on the new fixture line
   - does **not** fire on a tempfile with safe SQL (use the
     `tmp_path` fixture — see `test_e006_update_with_where_ok` for
     the pattern)
6. Update the README rule table and the "Rules" count in the Key
   Numbers block.

Rule naming conventions:

- kebab-case, verb-oriented (`delete-without-where`, not
  `deleteWithoutWhere` or `check-delete`)
- message tells the user what's wrong in one line
- suggestion tells them what to do instead

## Code Standards

- Python 3.10+.
- Line length 100.
- Type hints on public API.
- Every rule class has a docstring citing the SQL hazard it catches.

## Removing or renaming a rule

This is a breaking change for downstream users. Process:

1. Open an issue naming the rule, the reason for removal, and the
   deprecation window (one minor version minimum).
2. Land a warning in the rule's output pointing at the replacement.
3. After the deprecation window, the removal lands in a new minor
   version with the change in `README.md`.

## Reporting bugs

Open an issue with:

- Exact SQL that triggers or fails to trigger
- Rule ID involved (`E001`, `W001`, etc.)
- sql-sop version (`sql-sop --version`)
- Python version, OS

## Feature requests

Open an issue describing:

- What SQL pattern should be caught (or stop being caught)
- Why it's dangerous / safe
- Examples of the pattern in real code

## Recognition

Merged PRs land in the git history permanently. The README credits
substantial contributors when appropriate.
