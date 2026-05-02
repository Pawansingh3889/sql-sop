# Changelog

All notable changes to **sql-sop** are logged here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
sql-sop uses [Semantic Versioning](https://semver.org/).

Rule removals and rule ID renames are **breaking changes** that require
a deprecation window (see `GOVERNANCE.md` § Scope discipline).

## [Unreleased]

## [0.7.0] - 2026-05-02

Headline release: schema-aware linting via the new **Contracts pack**, three community-contributed rules (W014 / W015 / W022), and the `schema-snapshot` and `validate-contract` subcommands. Core registry is 43 rules (10 errors, 28 warnings, 5 Python-source). With `--contract` enabled the registry grows to 48 rules (12 errors, 31 warnings, 5 Python-source). Without `--contract` behaviour is identical to v0.6.x and there are no breaking changes.

### Added

- **W014 `case-without-else`** - warns when a `CASE ... END` block has
  no `ELSE` branch, so unmatched rows return `NULL`. Walks the
  statement token-by-token tracking nesting, so an outer `CASE` with no
  `ELSE` still fires even when an inner `CASE` does have one. Fires per
  unmatched block. Suggests adding `ELSE NULL` for explicitness.
  Contributed by [@hellozzm](https://github.com/hellozzm)
  ([#32](https://github.com/Pawansingh3889/sql-guard/pull/32)).
- **W015 `join-function-on-column`** - warns when a function wraps a
  column inside a `JOIN ... ON` predicate, the JOIN-side companion to W003.
  `JOIN customers c ON UPPER(o.email) = UPPER(c.email)` defeats every
  index on the joined column. The pattern stops at the next clause keyword
  (`WHERE`, `GROUP BY`, `ORDER BY`, `HAVING`, the next `JOIN`, or `UNION`)
  so a clean JOIN with a dirty WHERE leaves W015 quiet and lets W003 own
  that case. Contributed by [@mvanhorn](https://github.com/mvanhorn)
  ([#33](https://github.com/Pawansingh3889/sql-guard/pull/33)).
- **W022 `cross-join-explicit`** - warns on explicit `CROSS JOIN`. Cross
  joins multiply every row in the left table with every row in the right
  table (a Cartesian product). Almost always a mistake unless the author
  intends a calendar-grid or lookup-table generation pattern. The pattern
  strips trailing line comments before matching so `-- avoid CROSS JOIN`
  in a trailing comment does not trip the rule. Suppress with
  `-- sql-guard: disable=W022` on the same line. Contributed by
  [@vibeyclaw](https://github.com/vibeyclaw)
  ([#31](https://github.com/Pawansingh3889/sql-guard/pull/31)).
- **Contract Rules pack (C001-C005)** - new `--contract path.yml` flag
  loads a data contract describing the expected schema and lints SQL
  against it. Without a contract the rules are silent, so the addition
  is fully backwards-compatible. The contract format is a thin subset
  of the [open data-contract space](https://github.com/datacontract/datacontract-cli):
  tables -> columns -> type / not_null / primary_key / foreign_key /
  has_default. Contract path can also be supplied via `contract:` in
  `.sql-guard.yml`, resolved relative to the config file.
  - **C001 `column-not-in-contract`** (warning): SQL references a column
    that isn't declared in the contract for that table.
  - **C002 `table-not-in-contract`** (warning): statement touches a table
    not declared in the contract. Disable for partial-coverage contracts.
  - **C003 `not-null-violation`** (error): INSERT omits a column that the
    contract marks as NOT NULL with no default.
  - **C004 `primary-key-missing-on-insert`** (error): INSERT omits a
    primary-key column that has no default in the contract.
  - **C005 `unmapped-fk`** (warning): JOIN predicate uses two columns the
    contract has no foreign-key relationship for. Catches accidental
    cross-table joins where the schema declares no relationship between
    the two columns. Resolves the FK in either direction so the JOIN
    column order doesn't matter.
- **`sql-sop schema-snapshot --dsn ... --output contract.yml`** - new
  subcommand. Connects to a live database via SQLAlchemy, introspects
  tables / columns / PKs / FKs / nullable, and writes a contract-shaped
  YAML. Bootstraps the contract workflow: take a snapshot of an existing
  database, commit it as `contract.yml`, then lint queries against it
  via `--contract`. Requires `pip install "sql-sop[snapshot]"`. Supports
  `--schema` (override default schema) and `--include-table` (repeatable,
  for partial snapshots).
- **`sql-sop validate-contract --contract contract.yml`** - new
  subcommand. Loads the contract, validates structure, prints
  table/column/PK/FK counts, exits non-zero on parse failure. Useful in
  CI before `check --contract` so a malformed contract fails fast with a
  readable error rather than an obscure check-time crash.
- W023 `scalar-udf-in-where`: warns on `<schema>.<name>(...)` calls in
  `WHERE`/`HAVING`/`ON` clauses, the canonical T-SQL scalar-UDF
  anti-pattern. Built-ins (no schema prefix) are unaffected.
  ([#30](https://github.com/Pawansingh3889/sql-guard/issues/30))

## [0.6.2] - 2026-04-27

### Added

- **W013 `window-without-partition`** - warns on window functions
  using `OVER ()` without `PARTITION BY`, flagging non-deterministic
  ordering and full-result-set scans. Dialect-aware messaging across
  Postgres and Redshift. Contributed by
  [@Prabhu-1409](https://github.com/Prabhu-1409)
  ([#21](https://github.com/Pawansingh3889/sql-guard/pull/21)). Resolves #9.

### Repository

- Added [`ROADMAP.md`](ROADMAP.md) describing the v0.7 Performance
  Rules Pack milestone, tentative v0.8 dialect-aware coverage
  direction, and the always-out-of-scope set.
- Added README Contributors section crediting external rule authors
  (currently @tmchow, @mvanhorn, @Prabhu-1409).
- Added `scripts/scaffold_rule.py` for new contributors to generate
  the boilerplate snippets for a new rule.

## [0.6.1] - 2026-04-26

### Added
- **W019 `count-distinct-unbounded`** - warns on `COUNT(DISTINCT col)`
  with no `WHERE`, `GROUP BY`, or `LIMIT` restricting the scope. Forces
  a full sort + distinct pass over the entire table, a frequent perf
  surprise on prod. Bypass list also recognises T-SQL `TOP` and
  `FETCH FIRST/NEXT`. Contributed by [@mvanhorn](https://github.com/mvanhorn)
  ([#29](https://github.com/Pawansingh3889/sql-guard/pull/29)). Resolves #7.

## [0.6.0] - 2026-04-26

### Added
- **E007 `alter-add-not-null-no-default`** - errors on
  `ALTER TABLE ... ADD col TYPE NOT NULL` without a `DEFAULT`. Forces a
  full table rewrite under a schema-modify lock; suggests adding a default
  or splitting into add-nullable / backfill / set-not-null phases.
- **E008 `drop-column`** - errors on `ALTER TABLE ... DROP COLUMN`.
  Irreversible without backup, breaks replication subscribers, and any
  rollback to the previous deploy fails.
- **W017 `leading-wildcard-like`** - warns on `LIKE '%foo'` with a leading
  wildcard. Non-SARGable; the optimiser cannot use a B-tree index and
  falls back to a full scan. Recognises `N''` (NVARCHAR) literals and
  the `_` single-character wildcard.
- **W018 `or-across-columns`** - warns on `WHERE a = 1 OR b = 2` across
  different columns. Defeats single-column indexes; suggests rewriting
  as `UNION ALL` of two indexed queries.
- **W020 `truncate-table`** - warns on `TRUNCATE TABLE`. Bypasses DELETE
  triggers, resets identity, and gets blocked by FK references.
- **T005 `create-index-without-online`** (T-SQL) - warns when
  `CREATE INDEX` lacks `WITH (ONLINE = ON)`. Default builds hold a
  Sch-M lock for the duration; on busy tables that's a multi-minute
  outage. Suggests disabling on Standard / Express where ONLINE is
  unavailable.
- **Inline disable directives**: `-- sql-guard: disable=W001,W003` (or
  `-- sql-guard: disable-next-line=W001`) silences the listed rules on
  the same or following line. Also recognises `# sql-guard: disable=...`
  in Python source. A bare `-- sql-guard: disable` silences all rules
  on that line.
- **Project config file**: `.sql-guard.yml` (or `.yaml`) at the repo root
  supports `disable:`, `ignore:`, `include_python:`, and `severity:`
  fields. The loader walks up from the cwd. CLI flags merge with and
  override the config.
- **`--changed-only`** flag on `check`. Calls `git diff --name-only`
  (working tree by default; pass `--changed-base origin/main` to compare
  against a ref) and intersects the result with discovered files.
  Speeds up pre-commit on large codebases. Falls back to a full scan
  with a warning when not in a git repo.
- **SARIF output**: `--format sarif` (`-f sarif`) emits a SARIF 2.1.0
  document suitable for the `github/codeql-action/upload-sarif` action,
  so findings render inline on PRs in GitHub Code Scanning. Optional
  `--output results.sarif` writes to a file instead of stdout.

- **P005 `sqlalchemy-text-fstring`** - errors on `sqlalchemy.text(f"...{var}")`.
  Same SQL-injection hazard P001 catches for `cursor.execute()`, but on the
  `sqlalchemy.text()` surface. P001 now skips `text()` call sites so P005
  handles them with a sqlalchemy-specific message and suggestion
  (mirrors the existing P004 `call_name != "text"` guard).
  ([#10](https://github.com/Pawansingh3889/sql-guard/issues/10))
- **W016 `not-in-with-subquery`** - warns on `WHERE col NOT IN (SELECT ...)`.
  When the subquery returns any `NULL`, the predicate evaluates to `UNKNOWN`
  for every outer row and the query silently returns zero results. Suggests
  `NOT EXISTS` or `LEFT JOIN ... WHERE ... IS NULL` instead.

### Changed
- `pyyaml` is now a runtime dependency (used by `.sql-guard.yml` loader).
- `--disable` rule IDs are normalised to upper case so `--disable w001`
  and `--disable W001` behave the same.
- Codecov coverage tracking enabled on `main` (baseline 86.05%).

### Changed
- Codecov coverage tracking enabled on `main` (baseline 86.05%).

## [0.5.0] - 2026-04-20

### Added
- **T001 `with-nolock`** - warns on `WITH (NOLOCK)` table hints. Causes
  dirty reads. Commonly used as a performance band-aid instead of
  fixing the underlying blocking (indexes, transaction scope, or
  SNAPSHOT isolation).
- **T002 `xp-cmdshell`** - errors on `EXEC xp_cmdshell`. Shell-execution
  surface that should never appear in application SQL.
- **T003 `cursor-declaration`** - warns on `DECLARE ... CURSOR`.
  Row-by-row processing where set-based SQL usually does better.
- **T004 `deprecated-outer-join`** - errors on `*=` and `=*` old-style
  outer-join syntax. Deprecated in SQL Server 2005, unsupported in
  SQL Server 2012 and later. Uses a negative lookbehind to avoid
  matching modern compound-assignment expressions such as `SET @x *= 2`.
- **W012 `group-by-ordinal`** - warns when `GROUP BY` uses positional
  ordinals (`GROUP BY 1, 2`) instead of explicit column names. Ordinal
  references are fragile to `SELECT` list reorders: inserting or
  removing a column silently changes what the query groups by.
  Explicit names are self-documenting and refactor-safe.

### Changed
- W002 `missing-limit` and W006 `orderby-without-limit` now recognise
  T-SQL's `OFFSET n ROWS FETCH NEXT m ROWS ONLY` pagination pattern as
  a bounded query. Previously only `FETCH FIRST` was recognised.
- Single-source the package version via importlib.metadata in sql_guard/__init__.py. pyproject.toml is now the only place a release number is hard-coded.
- sqlparse is now a core dependency. Previously only in the [structural] extra, which meant S001-S003 silently no-op'd for users without it.
- README counts refreshed: 29 rules (6E/12W/3S/4T/4P), version 0.5.0, pre-commit rev v0.5.0.

### Fixed
- `test_duration_tracked` no longer fails on fast hardware where
  `time.perf_counter` resolution is coarser than the scan duration.
  Assertion relaxed from `> 0` to `>= 0` with an explicit float type check.
- Added W014: warn on OVER() without ORDER BY / PARTITION BY to flag non-deterministic window 
  functions.

## [0.4.1] - 2026-04-19

### Added
- **GitHub Marketplace listing** — `action.yml` now declares `author` and
  `branding` (icon: `shield`, colour: `purple` — safety framing, visually
  distinct from the `check-square`/`blue` default that most linter
  Actions use), plus the previously CLI-only `--include-python` surfaced
  as an action input. Ready to
  publish via the Release UI's "Publish this Action to the GitHub
  Marketplace" toggle.
- **CLI feedback CTA** — when findings are reported, the terminal
  reporter prints a single dim line pointing at the rule-request issue
  template. Never fires on clean runs. Converts each real lint surface
  into a silent engagement ask.
- **Rule-request issue form** — `.github/ISSUE_TEMPLATE/rule-request.yml`
  captures pattern, fail/pass examples, proposed severity, and whether
  the reporter plans to open a PR. Complements the existing
  `feature_request.yml` (which stays for non-rule enhancements).
- **Issue-template config** — `.github/ISSUE_TEMPLATE/config.yml` now
  routes usage questions to `Discussions/Q&A` and use-case posts to
  `Discussions/Show-and-tell`, reducing issue-tracker noise.
- **Comparison post** — `docs/blog/sqlfluff-vs-sql-sop.md` — honest
  side-by-side with sqlfluff, positioning sql-sop as a pre-commit
  "smoke detector" alongside sqlfluff's "spell-checker". Includes a
  recommended dual-setup example.
- **Hosted playground (scaffold)** — `playground/index.html` + deploy
  README. Single-file Pyodide-based in-browser linter, ready to serve
  from GitHub Pages or Cloudflare Pages. No bundler, no build step.
- **Engagement pack** — `docs/engagement/` holds ten
  good-first-issue rule drafts (W011-W018, S004, P005 placeholders),
  a "Who's using sql-sop?" Discussion draft, multi-channel
  announcement post drafts (LinkedIn / Twitter / Reddit / HN), and a
  Marketplace release checklist.

### Contributor paperwork (landed in this release as well)
- `NOTICE`, `GOVERNANCE.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md` with the "Adding a new rule" walkthrough. Existing
  bug-report and feature-request templates, PR template with the
  rule-addition checklist, CODEOWNERS routing reviews,
  first-contributor welcome workflow, PR-title validator.

### Changed
- **Licence stays MIT, deliberately.** `NOTICE` explains: the package
  has been consumed as MIT on PyPI since v0.1.0; relicensing silently
  is a breaking change for downstream users whose compliance pipelines
  are configured around the current licence.

## [0.4.0] - 2026-04

### Added
- **libCST-based Python scanner** — `sql-sop check --include-python`
  walks Python source via libCST (install with `pip install "sql-sop[python]"`).
  Four new rules (`P001`–`P004`) catch SQL injection in `.execute()`,
  `.read_sql()`, and `sqlalchemy.text(...)` calls:
  - P001 `fstring-in-execute` — `cursor.execute(f"... {user_input}")`
  - P002 `concat-in-execute` — `cursor.execute("..." + user_input)`
  - P003 `format-in-execute` — `.format()` / `%` interpolation
  - P004 `bare-variable-in-execute` — `cursor.execute(query)`

### Added (SQL rules)
- **E006 `update-without-where`** — silent twin of E001. Catches
  `UPDATE table SET col = 'x'` with no `WHERE` before it rewrites every
  row. Registered in `ALL_RULES`, fixture line in `tests/fixtures/errors.sql`,
  two tests (fires + does-not-fire-when-WHERE-present).

### Fixed
- **Pattern 16 word-boundary** — `(product|plu).*waste` was greedy-matching
  `production...waste`. Tightened to `\b(product|plu)\b.*waste`.

## [0.3.0] - 2026-04

### Added
- **Structural rules (S001–S003)** via sqlparse AST:
  - S001 `implicit-cross-join` — missing `ON` / `USING` in `JOIN`
  - S002 `deeply-nested-subquery` — subqueries beyond 3 levels deep
  - S003 `unused-cte` — `WITH` clause defined but never referenced
- **Fluent API** — `SqlGuard().enable("E001").scan("DELETE FROM users")`

## [0.2.0]

### Added
- Pre-commit hook + GitHub Action distributions
- Initial CLI with `check` command

## [0.1.0]

### Added
- First release. Core rule engine with 5 errors + 10 warnings.
