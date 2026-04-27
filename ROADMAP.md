# sql-sop roadmap

This is the maintainer's working roadmap. It tells you what's likely to land in upcoming releases, what's deliberately out of scope, and where contributions are most welcome. It's a living document — open an issue to discuss anything that surprises you.

Last updated: 2026-04-27.

## Current release

**v0.6.x** is in maintenance. Headline features as of v0.6.1 on PyPI: 38 rules (33 SQL + 5 Python), T-SQL safety pack (T001-T005), migration guards, inline `-- sql-guard: disable=...` directives, `.sql-guard.yml` config, `--changed-only` flag, SARIF 2.1.0 output for GitHub Code Scanning, libCST scanner for Python source.

`main` is at 39 rules after [W013 window-without-partition](https://github.com/Pawansingh3889/sql-guard/pull/21) merged 2026-04-26. **v0.6.2 patch release pending** to ship W013 to PyPI users.

## v0.7 — Performance Rules Pack

**Theme:** catch SQL patterns that compile fine and run slowly. Builds on the v0.6 W017 / W018 / W019 trio (leading wildcard, OR across columns, count-distinct-unbounded).

The performance-traps angle is already in sql-sop's tagline and matches what real users hit in production. v0.7 doubles down with a coordinated set of new rules + sharper messaging on existing ones.

### In scope

New performance-flavoured warning rules. Each is a single rule mirroring the W019 shape (one regex or libCST visitor, fixture line, two tests, README entry, CHANGELOG bullet). Specific candidates:

- **cross-join-without-on** — flag explicit `CROSS JOIN` or implicit cartesian (comma-separated FROM with no WHERE binding the join) where the result is likely unintended.
- **function-on-indexed-column** — `WHERE UPPER(email) = 'x'` defeats a B-tree index. Flag function calls applied to columns inside WHERE or JOIN ON predicates, with an allowlist for cases that are actually fine (e.g. `LOWER(email)` against a functional index).
- **scalar-udf-in-where** — scalar UDFs in WHERE force row-by-row evaluation in T-SQL. Initially T-SQL flavour; Postgres equivalent (`VOLATILE` functions in WHERE) as a follow-up.
- **negate-of-equality** — `WHERE NOT col = x` and `col != x` defeat range-based index access in many engines. Flag with rationale.
- **select-star-in-view-or-cte** — `SELECT *` inside a view or CTE freezes the column list and surprises downstream callers when the underlying table changes. Flag with suggestion to enumerate.

Also in scope:

- **Dialect-aware messaging on existing rules.** W019's bypass list already recognises `WHERE`, `GROUP BY`, `LIMIT`, `TOP`, `FETCH NEXT`. Other rules could similarly adjust suggestion text per dialect (Postgres advice for Postgres queries, T-SQL for T-SQL, etc.). Where the rule fires the same but the fix differs, the message should be specific.
- **`--severity` threshold improvements.** Currently uppercases input; should accept comma-separated lists like `--severity error,warning` and reject typos with a clear error.
- **Self-benchmark on every release.** Add a tiny perf gate to CI that asserts sql-sop stays under N ms per 1000 lines of SQL on a fixture corpus. Catches regressions caused by adding rules.

### Out of scope for v0.7

- LSP server / IDE integration (queued for v0.9+)
- sqlglot-based AST detection (queued for v0.8 or later — major architecture change)
- New output formats beyond SARIF (text, JSON, SARIF already cover the realistic CI matrix)
- Auto-fix application (some rules already include suggestion text; actually applying fixes is a v1.0 candidate)
- Plugin system for third-party rules (out of scope until the core rule API is stable)

### Contribution shape for v0.7

Each new rule follows the same pattern. See `sql_guard/rules/warnings.py:CountDistinctUnbounded` (W019) for the canonical example, and [PR #29](https://github.com/Pawansingh3889/sql-guard/pull/29) for the full review cycle.

PR checklist:

1. New rule class registered in `sql_guard/rules/__init__.py`
2. Fixture line in `tests/fixtures/warnings.sql`
3. "Fires on bad SQL" test in `tests/test_rules.py`
4. "Does not fire on safe SQL" test
5. README rule table + Key Numbers count updated
6. CHANGELOG entry under `## [Unreleased]` → `### Added`
7. Conventional commit style (`feat(rules): add Wxxx ...`)

The W019 mvanhorn PR ([#29](https://github.com/Pawansingh3889/sql-guard/pull/29)) and W013 Prabhu PR ([#21](https://github.com/Pawansingh3889/sql-guard/pull/21)) are good references for the full review cycle, including how rebases get handled when main moves.

## v0.8 — Dialect-Aware Coverage (tentative)

**Theme:** expand dialect-specific safety packs.

The T-SQL pack (T001-T005) already exists. v0.8 adds Postgres and Redshift packs, plus a dialect detection layer in the rule engine so individual rules don't have to invent their own detection.

### In scope (subject to v0.7 outcomes)

- **Postgres pack (P-prefix-Postgres rules, naming TBD).** Examples: `SERIAL` discouraged in favour of `GENERATED ALWAYS AS IDENTITY`, JSONB anti-patterns (`->>` chains where `jsonb_path_query` fits), `LATERAL` join misuse.
- **Redshift pack.** `SORTKEY` / `DISTKEY` reminders, `IDENTITY(seed, step)` syntax checks, the bits where Redshift diverges from Postgres SQL.
- **Dialect detection** from file path (`migrations/redshift/*.sql` infers Redshift), from `.sql-guard.yml` config (`dialect: postgres`), or from an inline comment marker (`-- sql-guard: dialect=postgres`).

### Out of scope for v0.8

- Snowflake or BigQuery packs (sqlfluff covers those well; sql-sop's wedge is T-SQL + migration safety + Python source scanning)

## v0.9 and beyond — directional, not committed

- **LSP server** for editor integration. Probably built on the existing libCST + rule engine, exposing diagnostics over the LSP protocol.
- **VSCode extension** that wraps the LSP server.
- **sqlglot-based AST detection** for rules where regex hits its ceiling. Big change; would involve a dual code path during transition.
- **Plugin system** for third-party rule authors. Only after the core rule API has been stable for two minor versions.

## Always-welcome contributions

These don't need to wait for a milestone:

- Bug reports with minimal repro SQL and expected vs actual output
- New test cases that exercise edge conditions in existing rules, especially dialect quirks
- Documentation fixes (typos, clearer examples in README rule tables)
- Performance improvements where benchmarked (don't optimise without data — `pytest --benchmark` numbers in the PR description)

## Always out of scope

- Generic Python linting (use [ruff](https://github.com/astral-sh/ruff))
- Generic SQL formatting (use [sqlfluff](https://github.com/sqlfluff/sqlfluff))
- Database connection or query execution. sql-sop is static analysis; runtime concerns belong elsewhere.
- ORM-specific rules beyond Python + SQLAlchemy via libCST. Django ORM, Pandas, polars are not the focus.
- Rules without a concrete bad-pattern + good-pattern example. Style preferences without measurable impact don't make the cut.

## How to read this document

The version themes are aspirational. A v0.7 PR that doesn't fit the performance theme but is a clear win still has a good chance of landing — the theme orients new contributions, it doesn't gate every merge. If you're not sure whether something belongs, open an issue and ask before writing the code.
