# sql-sop

[![CI](https://github.com/Pawansingh3889/sql-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/Pawansingh3889/sql-guard/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sql-sop)](https://pypi.org/project/sql-sop/)
[![Python](https://img.shields.io/pypi/pyversions/sql-sop)](https://pypi.org/project/sql-sop/)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Marketplace](https://img.shields.io/badge/GitHub%20Marketplace-sql--sop-a07aff?logo=githubactions&logoColor=white)](https://github.com/marketplace/actions/sql-sop)
[![Playground](https://img.shields.io/badge/playground-try%20online-a07aff)](https://pawansingh3889.github.io/sql-guard/)
[![Downloads](https://img.shields.io/pypi/dm/sql-sop?color=a07aff)](https://pypi.org/project/sql-sop/)
[![codecov](https://codecov.io/gh/Pawansingh3889/sql-guard/branch/main/graph/badge.svg)](https://codecov.io/gh/Pawansingh3889/sql-guard)

> Part of the [Governed Agent Stack](https://github.com/Pawansingh3889/governed-agent-stack): free, on-prem building blocks for an AI agent you can point at a real database and audit.

## Links
- [GitHub](https://github.com/Pawansingh3889/sql-guard)
- [PyPI](https://pypi.org/project/sql-sop/)
- [Download Stats](https://pypistats.org/packages/sql-sop)
- Install: `pip install sql-sop`
- [Profile](https://github.com/Pawansingh3889)
- **Contributing:** [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`ROADMAP.md`](ROADMAP.md) · [`GOVERNANCE.md`](GOVERNANCE.md) · [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) · [`SECURITY.md`](SECURITY.md) · [`NOTICE`](NOTICE)

## Companion tools

sql-sop composes with a few other small on-prem tools:

- **[sql-explorer-mcp](https://github.com/Pawansingh3889/sql-explorer-mcp)**: read-only MCP server that lets an AI introspect and query SQL Server / Postgres / SQLite; sql-sop is one of its safety layers, rejecting dangerous queries before they run.
- **[FloorMind](https://github.com/Pawansingh3889/FloorMind)**: on-prem NL→SQL agent that generates SQL via a local LLM; sql-sop validates every generated query before execution.

The dbt-aware rule pack (DBT001+) extends sql-sop into dbt projects. See the [ADR](https://github.com/Pawansingh3889/sql-guard/issues?q=is%3Aissue+label%3AADR) for the broader roadmap.

## Why Does This Exist?

One bad SQL query can delete production data, expose customer records, or bring down a database. Most teams only find out after the damage is done. sql-sop catches dangerous patterns automatically, before the query ever runs, in 0.08 seconds.

### Key Numbers

| | |
|---|---|
| Rules | 44 (10 errors, 29 warnings, 5 Python-source); 49 with `--contract` |
| Tests | 277 |
| Coverage | 86% |
| Scan speed | 0.08s across 200 files |
| PyPI downloads | 500+/month |
| Version | 0.7.0 |

### Fluent API (v0.2.0)

```python
from sql_guard import SqlGuard

result = SqlGuard().enable("E001", "W001").scan("DELETE FROM users")
print(result.passed)    # False
print(result.summary()) # "1 error, 0 warnings in 1 statement"
```

---

Fast, rule-based SQL linter. 43 rules (38 SQL + 5 Python), with an optional Contracts pack (5 schema-aware rules) when you supply `--contract path.yml`. SQL Server-focused rules for T-SQL shops. Inline disable, project config, git-changed-only mode, and SARIF output for GitHub Code Scanning. 500+ monthly downloads on PyPI.

Catches dangerous SQL before it reaches production -- DELETE without WHERE, UPDATE without WHERE, SQL injection patterns, SELECT *, contract drift, and 40+ more. Runs as a **CLI tool**, **pre-commit hook**, and **GitHub Action**.

Built to catch dangerous patterns like DELETE without WHERE before they ever reach a production database.

For deeper AI-powered analysis, pair with [SQL Ops Reviewer](https://github.com/Pawansingh3889/sql-ops-reviewer).

---

## Quick start

**If sql-sop catches a real bug for you, a GitHub star is the easiest way
to help. It makes the project more discoverable for people with the same
problem.**

```bash
pip install sql-sop
sql-sop check .

# Also scan .py files for SQL hazards in execute()/read_sql() calls:
pip install "sql-sop[python]"
sql-sop check . --include-python
```

```
queries/create_orders.sql
  L3:  ERROR [E001] DELETE without WHERE clause -- this will delete all rows
         -> Add a WHERE clause to limit affected rows
  L7:  WARN  [W001] SELECT * -- specify columns explicitly
         -> Replace with: SELECT col1, col2, col3 FROM ...

Found 2 issues (1 error, 1 warning) in 1 file (0.001s)
```

## The two-layer SQL quality pipeline

Most teams have **no SQL review process**. Some use an AI linter. The problem: AI is slow, expensive, and overkill for catching `DELETE FROM users;`.

sql-sop and SQL Ops Reviewer solve this together:

```
                    ┌─────────────────────────────────────┐
                    │         YOUR SQL FILE                │
                    └──────────────┬──────────────────────┘
                                   │
          ┌────────────────────────┼────────────────────────┐
          │                        │                        │
          ▼                        │                        │
   LAYER 1: PRE-COMMIT             │              LAYER 2: CI
   ─────────────────               │              ──────────
   sql-guard                       │              SQL Ops Reviewer
                                   │
   When: before every commit       │              When: on every PR
   Speed: <0.2 seconds             │              Speed: 10-40 seconds
   How: regex pattern matching     │              How: Ollama LLM analysis
   Needs: nothing (pure Python)    │              Needs: 4-7 GB (AI model)
   Catches: 80% of issues          │              Catches: remaining 20%
                                   │
   ✓ DELETE without WHERE          │              ✓ wrong JOIN type
   ✓ SELECT *                      │              ✓ business logic errors
   ✓ SQL injection patterns        │              ✓ schema-aware suggestions
   ✓ missing LIMIT                 │              ✓ cross-table consistency
   ✓ DROP without IF EXISTS        │              ✓ performance rewrites
          │                        │                        │
          ▼                        │                        ▼
   commit blocked or passes        │              PR comment with findings
          │                        │                        │
          └────────────────────────┼────────────────────────┘
                                   │
                                   ▼
                         CLEAN SQL IN PRODUCTION
```

**Layer 1 (sql-guard)** is a smoke detector -- always on, instant, catches fire fast.
**Layer 2 (SQL Ops Reviewer)** is a fire inspector -- thorough, comes on every PR.

You want both.

---

## Set up the full pipeline (5 minutes)

### Step 1: Pre-commit hook (Layer 1)

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Pawansingh3889/sql-guard
    rev: v0.7.0
    hooks:
      - id: sql-guard
        args: [--severity, error]  # only block on errors locally
```

```bash
pip install pre-commit
pre-commit install
```

Now every `git commit` with `.sql` changes runs sql-guard automatically. Errors block the commit. Warnings are shown but don't block.

### Step 2: GitHub Actions (Layer 1 + Layer 2)

```yaml
# .github/workflows/sql-quality.yml
name: SQL Quality
on:
  pull_request:
    paths: ['**/*.sql']

permissions:
  contents: read
  pull-requests: write

jobs:
  # Layer 1: fast rule check (~2 seconds)
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Pawansingh3889/sql-guard@v1
        with:
          severity: warning

  # Layer 2: deep AI review (~30 seconds, runs after lint passes)
  review:
    needs: lint
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Pawansingh3889/sql-ops-reviewer@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

That's it. Two files. Every SQL change gets:
1. Instant rule-based lint (sql-guard)
2. Deep AI review with fix suggestions (SQL Ops Reviewer)

### Step 3 (optional): CLI for manual checks

```bash
pip install sql-sop

sql-sop check .                          # scan current directory
sql-sop check queries/ --severity error  # errors only
sql-sop check . --fail-fast              # stop on first error
sql-sop check . --disable E002 W008      # skip specific rules
sql-sop list-rules                       # show every registered rule
```

---

## Rules

### Errors (block commit by default)

| ID | Name | What it catches |
|---|---|---|
| E001 | `delete-without-where` | `DELETE FROM orders;` -- deletes all rows |
| E002 | `drop-without-if-exists` | `DROP TABLE users;` -- fails if table missing |
| E003 | `grant-revoke` | `GRANT SELECT ON users TO public;` -- privilege escalation |
| E004 | `string-concat-in-where` | `WHERE id = '' + @input` -- SQL injection |
| E005 | `insert-without-columns` | `INSERT INTO t VALUES (...)` -- breaks on schema change |
| E006 | `update-without-where` | `UPDATE orders SET status = 'x';` -- overwrites every row |
| E007 | `alter-add-not-null-no-default` | `ALTER TABLE t ADD c INT NOT NULL;` -- locks table for full rewrite |
| E008 | `drop-column` | `ALTER TABLE t DROP COLUMN c;` -- irreversible, breaks subscribers |

### Warnings (advisory by default)

| ID | Name | What it catches |
|---|---|---|
| W001 | `select-star` | `SELECT * FROM users` -- pulls unnecessary columns |
| W002 | `missing-limit` | Unbounded SELECT -- could return millions of rows |
| W003 | `function-on-column` | `WHERE YEAR(date) = 2024` -- kills index usage |
| W004 | `missing-alias` | JOIN without table aliases -- hard to read |
| W005 | `subquery-in-where` | `WHERE x IN (SELECT ...)` -- often slower than JOIN |
| W006 | `orderby-without-limit` | ORDER BY without LIMIT -- sorts entire result |
| W007 | `hardcoded-values` | `WHERE amount > 10000` -- use parameters |
| W008 | `mixed-case-keywords` | `select ... FROM` -- inconsistent casing |
| W009 | `missing-semicolon` | Statement not terminated with `;` |
| W010 | `commented-out-code` | `-- SELECT * FROM old_table` -- use version control |
| W011 | `union-without-all` | `UNION` between disjoint sets -- forces a deduplication sort, `UNION ALL` is faster when uniqueness is guaranteed |
| W012 | `group-by-ordinal` | `GROUP BY 1, 2` -- fragile to SELECT-list reorders |
| W013 | `window-missing-partition` | `OVER ()` -- unpredictable results and unclear intent |
| W014 | `case-without-else` | `CASE WHEN ... THEN ... END` -- unmatched rows return NULL |
| W015 | `join-function-on-column` | `JOIN customers c ON UPPER(o.email) = UPPER(c.email)` -- kills index seek |
| W016 | `not-in-with-subquery` | `WHERE id NOT IN (SELECT ...)` -- silently returns 0 rows on NULL |
| W017 | `leading-wildcard-like` | `WHERE name LIKE '%smith'` -- non-SARGable, full scan |
| W018 | `or-across-columns` | `WHERE a = 1 OR b = 2` -- defeats single-column indexes |
| W019 | `count-distinct-unbounded` | `COUNT(DISTINCT col)` with no WHERE / GROUP BY / LIMIT -- full sort + distinct over the whole table |
| W020 | `truncate-table` | `TRUNCATE TABLE staging;` -- bypasses triggers, resets identity |
| W022 | `cross-join-explicit` | `FROM products CROSS JOIN regions` -- Cartesian product, confirm intent |
| W023 | `scalar-udf-in-where` | `WHERE dbo.fn_X(col) = 1` -- row-by-row predicate evaluation |
| W024 | `select-distinct-suspicious` | `SELECT DISTINCT a, b FROM x JOIN y ON ...` -- DISTINCT often masks a missing join condition or GROUP BY |
| W025 | `assertion-malformed` | `-- @assert: <predicate>` comment whose predicate does not match the sql-sop grammar (`row_count <op> <int>`, `unique(<col>)`, `not_null(<col>)`, `<col> <op> <literal>`) |


### Structural (v0.3.0+, sqlparse-based)

Rules that need an AST view of the statement, parsed via sqlparse. Catch
issues that single-line regex matching cannot reliably see.

| ID | Name | What it catches |
|---|---|---|
| S001 | `implicit-cross-join` | `JOIN customers` with no `ON` / `USING` -- accidental Cartesian product |
| S002 | `deeply-nested-subquery` | Subqueries beyond 3 levels deep -- typically a refactor opportunity |
| S003 | `unused-cte` | `WITH x AS (...)` defined but never referenced |

### T-SQL (v0.5.0+)

Rules targeting SQL Server anti-patterns common in legacy stored procs
and SSRS datasets. Fire on text patterns that do not appear in BigQuery
or Postgres code, so they run unconditionally with near-zero false
positives on non-T-SQL input.

| ID | Name | What it catches |
|---|---|---|
| T001 | `with-nolock` | `SELECT * FROM t WITH (NOLOCK)` -- dirty reads |
| T002 | `xp-cmdshell` | `EXEC xp_cmdshell ...` -- shell-exec surface |
| T003 | `cursor-declaration` | `DECLARE c CURSOR FOR ...` -- row-by-row processing |
| T004 | `deprecated-outer-join` | `WHERE a.x *= b.y` -- removed in SQL Server 2012+ |
| T005 | `create-index-without-online` | `CREATE INDEX ix ON t (...)` -- locks table; add `WITH (ONLINE = ON)` |
| T006 | `select-into-without-typed-fields` | `SELECT * INTO target FROM source` -- destination schema is inferred at runtime |

### Contracts (opt-in via `--contract`)

Pass `--contract path/to/contract.yml` (or set `contract:` in
`.sql-guard.yml`) to lint queries against the expected schema. Without a
contract these rules are silent. Format is a thin subset of the open
data-contract space; see `tests/fixtures/contract_sample.yml` for a
working example.

| ID | Name | What it catches |
|---|---|---|
| C001 | `column-not-in-contract` | `SELECT o.bogus FROM orders o` -- column not declared for that table |
| C002 | `table-not-in-contract` | `SELECT * FROM ghost_table` -- table absent from the contract |
| C003 | `not-null-violation` | `INSERT INTO orders (id) VALUES (1)` -- omits a NOT NULL column |
| C004 | `primary-key-missing-on-insert` | INSERT omits a PK column with no default |
| C005 | `unmapped-fk` | `JOIN ... ON o.id = c.id` -- columns have no FK relationship in the contract |

Two helper subcommands round out the workflow:

```bash
# Bootstrap a contract from an existing database (requires sql-sop[snapshot]):
sql-sop schema-snapshot \
  --dsn "mssql+pyodbc://user:pass@host/db?driver=ODBC+Driver+18+for+SQL+Server" \
  --output contract.yml

# Validate a contract YAML structure before running rules (CI-friendly):
sql-sop validate-contract --contract contract.yml
```

### Python scanning (v0.4.0+, opt-in)

Enable with `pip install "sql-sop[python]"` and `--include-python`. Uses
libCST to walk Python source and extract SQL strings from `.execute()`,
`.read_sql()`, `sqlalchemy.text(...)` calls and `sql =`/`query =` style
assignments. Then applies every rule above, plus four that only make
sense at the Python level:

| ID | Name | What it catches |
|---|---|---|
| P001 | `fstring-in-execute` | `cursor.execute(f"... {user_input}")` -- SQL injection |
| P002 | `concat-in-execute` | `cursor.execute("..." + user_input)` -- SQL injection |
| P003 | `format-in-execute` | `.format()` or `%` interpolation into an execute call |
| P004 | `bare-variable-in-execute` | `cursor.execute(query)` where `query` is an unchecked variable |
| P005 | `sqlalchemy-text-fstring` | `sqlalchemy.text(f"... {var}")` -- SQL injection on the SQLAlchemy text() surface |

---

## Configuration

### Disable specific rules

```bash
sql-sop check . --disable E002 W008 W010
```

### Project config file (`.sql-guard.yml`)

Drop a `.sql-guard.yml` (or `.sql-guard.yaml`) at the repo root. The loader walks up from the current directory; CLI flags merge with and override these settings.

```yaml
disable:
  - W005
  - T001
ignore:
  - migrations/legacy/
  - vendor/
include_python: true
severity: warning
```

### Inline disable comments

Silence a known false positive on a single line, no project-wide override needed:

```sql
SELECT * FROM lookups; -- sql-guard: disable=W001
SELECT * FROM users  -- sql-guard: disable=W001,W002
WHERE name LIKE '%smith';

-- sql-guard: disable-next-line=W017
SELECT * FROM events WHERE name LIKE '%checkout';
```

A bare `-- sql-guard: disable` (no equals sign) silences every rule on the line. The same directives work in Python with `#` instead of `--`.

### Lint only changed files

For pre-commit and CI on big repos:

```bash
sql-sop check . --changed-only                      # working tree
sql-sop check . --changed-only --changed-base main  # vs a branch ref
```

Falls back to a full scan with a warning when not in a git repo.

### Severity filtering

```bash
sql-sop check . --severity error    # only show errors
sql-sop check . --severity warning  # show everything (default)
```

### Fail fast

```bash
sql-sop check . --fail-fast  # stop after first error found
```

### SARIF output for GitHub Code Scanning

Render findings inline on PRs in the GitHub Files Changed view:

```bash
sql-sop check . --format sarif --output results.sarif
```

In a GitHub Actions workflow:

```yaml
- run: sql-sop check . --format sarif --output sql-guard.sarif
- uses: github/codeql-action/upload-sarif@v3
  with:
    sarif_file: sql-guard.sarif
```

---

## Performance

sql-guard is designed to be fast:

- **Compiled regex** -- patterns compiled once at startup, reused per file
- **Two-pass scanning** -- single-line rules run first (8 of 20 SQL rules), multi-line parsing only when needed
- **Line-by-line streaming** -- files read line by line, not loaded entirely into memory
- **Early exit** -- `--fail-fast` stops on first error

```
Benchmark: 200 SQL files, 20 SQL rules
  sql-guard:  0.08 seconds
  sqlfluff:   45 seconds (560x slower)
```

---

## Production Use Case

In a regulated data environment, sql-sop runs as a pre-commit hook on all SQL that touches the database. Combined with read-only database users and container isolation, it forms part of a layered safety setup that prevents accidental writes to production.

---

## How it compares

| | sql-sop | sqlfluff | sql-lint |
|---|---|---|---|
| Rules | 31 (focused) | 800+ (comprehensive) | ~20 |
| Speed | <0.1s for 200 files | 45s for 200 files | ~2s |
| Config needed | Zero | Extensive | Minimal |
| Language | Python | Python | JavaScript |
| Pre-commit | Yes | Yes | No |
| GitHub Action | Yes | Community | No |
| AI integration | Pairs with SQL Ops Reviewer | No | No |

sql-sop is not a replacement for sqlfluff. It's a fast first pass that catches 80% of real issues with zero setup. If you need dialect-specific formatting and 800 rules, use sqlfluff. If you want instant feedback on dangerous SQL, use sql-guard.

---

## Contributing

```bash
git clone https://github.com/Pawansingh3889/sql-guard.git
cd sql-guard
pip install -e ".[dev]"
pytest
```

### Adding a new rule

1. Create a class in `sql_guard/rules/errors.py` or `warnings.py`
2. Inherit from `Rule`, set `id`, `name`, `severity`, `description`
3. Override `check_line()` for single-line rules or `check_statement()` for multi-line
4. Add to `ALL_RULES` in `sql_guard/rules/__init__.py`
5. Add a test in `tests/test_rules.py`
6. Add a trigger case in `tests/fixtures/`

```python
class MyNewRule(Rule):
    id = "W011"
    name = "my-rule"
    severity = "warning"
    description = "What this rule catches"
    multiline = False

    _pattern = Rule._compile(r"your regex here")

    def check_line(self, line, line_number, file):
        if self._pattern.search(line):
            return Finding(
                rule_id=self.id,
                severity=self.severity,
                file=file,
                line=line_number,
                message="What went wrong",
                suggestion="How to fix it",
            )
        return None
```

PRs welcome. Keep rules simple, keep patterns fast.

---

## Contributors

Thank you to the people who have shipped rules and code to sql-sop.

| Contributor | Contribution |
|---|---|
| [@tmchow](https://github.com/tmchow) | [W011 `union-without-all`](https://github.com/Pawansingh3889/sql-guard/pull/12). Flags `UNION` where `UNION ALL` would be safe and faster. |
| [@tmchow](https://github.com/tmchow) | [P005 `sqlalchemy-text-fstring`](https://github.com/Pawansingh3889/sql-guard/pull/25). Catches `sqlalchemy.text(f"...{var}")` patterns that defeat parameter binding. |
| [@mvanhorn](https://github.com/mvanhorn) | [W019 `count-distinct-unbounded`](https://github.com/Pawansingh3889/sql-guard/pull/29). Flags `COUNT(DISTINCT col)` without WHERE, GROUP BY, or LIMIT. |
| [@mvanhorn](https://github.com/mvanhorn) | [W015 `join-function-on-column`](https://github.com/Pawansingh3889/sql-guard/pull/33). JOIN-side companion to W003. Flags function calls wrapping columns inside `JOIN ... ON` predicates. |
| [@mvanhorn](https://github.com/mvanhorn) | [W023 `scalar-udf-in-where`](https://github.com/Pawansingh3889/sql-guard/pull/34). Flags schema-qualified scalar UDF calls inside WHERE, HAVING, and ON predicates. |
| [@Prabhu-1409](https://github.com/Prabhu-1409) | [W013 `window-without-partition`](https://github.com/Pawansingh3889/sql-guard/pull/21). Flags `OVER ()` without `PARTITION BY`, dialect-aware messaging for Postgres and Redshift. |
| [@hellozzm](https://github.com/hellozzm) | [W014 `case-without-else`](https://github.com/Pawansingh3889/sql-guard/pull/32). Walks `CASE`/`END` token-by-token; catches outer `CASE` without `ELSE` even when an inner `CASE` does have one. |
| [@vibeyclaw](https://github.com/vibeyclaw) | [W022 `cross-join-explicit`](https://github.com/Pawansingh3889/sql-guard/pull/31). Flags explicit `CROSS JOIN`. Strips trailing line comments before matching to avoid false positives on commentary. |

See [the full contributors graph](https://github.com/Pawansingh3889/sql-guard/graphs/contributors) on GitHub.

Want to add your name here? Pick a [`good first issue`](https://github.com/Pawansingh3889/sql-guard/labels/good%20first%20issue), follow [`CONTRIBUTING.md`](CONTRIBUTING.md), and check the [roadmap](ROADMAP.md) for the next batch of rules. v0.7 just shipped (contracts pack); v0.8 is shaping up around dialect-aware coverage.

---

## License

MIT
