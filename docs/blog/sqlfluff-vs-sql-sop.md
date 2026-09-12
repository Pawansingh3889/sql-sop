# sqlfluff vs sql-sop - when to use which

sqlfluff is the big dog of Python SQL tooling. 800+ rules, dialect-aware,
first-class dbt integration, active maintainer team, and years of
production use across thousands of companies. If you asked me "which
linter should my data team adopt?" my answer is sqlfluff, every time.

So why does sql-sop exist?

Because the two projects aren't solving the same problem, and when I
needed the second shape I couldn't find a good one. This post is a
plain-language comparison so you can pick the right tool for your
situation - or use both.

## The short answer

> Use **sqlfluff** for dialect-aware formatting, dbt integration, and
> comprehensive lint coverage of a SQL codebase.
>
> Use **sql-sop** as a pre-commit hook that catches the "this would
> delete production" class of mistakes in under 0.1 seconds, on
> every commit, zero config.

You can (and probably should) use both. sql-sop runs locally on every
commit; sqlfluff runs in CI once a minute. They don't overlap much in
practice.

## Side-by-side

| | sql-sop | sqlfluff |
|---|---|---|
| Rule count | 23 (focused) | 800+ (comprehensive) |
| Config needed | Zero | `.sqlfluff` with dialect + profile |
| Speed (200 files) | ~0.08s | ~45s |
| Dialect-aware | No (dialect-neutral regex) | Yes (12+ dialects) |
| Formatter (fix mode) | No | Yes |
| dbt integration | No | First-class (`sqlfluff fix models/`) |
| Pre-commit hook | Yes | Yes |
| GitHub Action | Yes (in Marketplace) | Community-maintained |
| Catches DELETE-without-WHERE | Yes | Via custom rules |
| Catches SQL injection in Python | Yes (libCST scanner) | No (SQL-only) |
| Language | Python | Python |
| License | MIT | MIT |
| Maintainer team | Solo (for now) | ~20 active |
| Age | ~1 year | ~5 years |

## The real mental model

The way I think about them:

**sqlfluff is a spell-checker for your entire SQL codebase.** Run it in
CI on every PR. Accept the 45-second build time because you want dialect
awareness, auto-formatting, and 800-rule coverage.

**sql-sop is a smoke detector for the kitchen.** Wire it to your
pre-commit hook. If you write `DELETE FROM orders;` and try to commit,
it fires in under a second. It doesn't know Snowflake from Postgres - it
doesn't need to.

Smoke detectors and spell-checkers serve different purposes. No house
ships only one.

## Where sqlfluff is clearly better

- **Formatting.** sql-sop only lints; sqlfluff fixes and reformats.
- **Dialect accuracy.** sqlfluff's parser knows Snowflake's variant
  syntax, BigQuery's wildcards, MS SQL's `TOP`. sql-sop uses regex, so
  it makes trade-offs.
- **dbt projects.** sqlfluff is de facto in the dbt ecosystem. Ten
  years from now it'll still be the right answer for dbt.
- **Rule depth.** 800 rules vs 23. If you want every edge case covered,
  sqlfluff is the only answer.
- **Large codebases.** 10,000+ SQL files? sqlfluff's parser-based
  approach scales better than regex on that order of magnitude.
- **Team adoption.** sqlfluff has a mature config file and inherited-
  rule system. Teams need that.

## Where sql-sop is useful (and sqlfluff isn't quite the right shape)

- **Pre-commit hook speed.** Developers abandon hooks that take more than
  a couple of seconds. 0.08 seconds is imperceptible; 45 seconds is
  painful enough that people `--no-verify`. That's the main reason
  sql-sop exists.
- **Zero-config starting point.** You can `pip install sql-sop` and get
  useful output in the next five seconds. sqlfluff requires picking a
  dialect and tuning a profile; that's the right investment for a team
  but an overhead for a first commit.
- **Catching SQL injection patterns in Python.** sql-sop's
  `--include-python` mode walks your Python source with libCST and
  flags f-string interpolation inside `.execute()`, `text()`,
  `.read_sql()`, etc. sqlfluff doesn't do this because it's out of
  scope for a SQL linter.
- **The "smoke detector" rule count.** 23 rules is small enough to
  read in one sitting. Every rule has a dedicated test. The whole
  ruleset fits in memory. For the pre-commit shape, that's a feature,
  not a limitation.
- **Regex + AST hybrid, small surface.** sqlfluff's parser is brilliant
  but it's a lot to embed in a pre-commit hook. sql-sop is ~2000 lines
  of Python, most of it regex patterns.

## Honest shortcomings of sql-sop

- **Dialect-neutral means some false positives.** `W001 select-star`
  triggers even in a materialized-view definition where `SELECT *` is
  intentional. Future plan: `-- noqa: W001` inline disables.
- **Structural rules are shallow.** `S001-S003` use sqlparse, which is
  decent for basic AST but not production-grade. Complex nested queries
  can defeat the depth check.
- **No fix mode.** You can't run `sql-sop --fix` the way you can with
  `sqlfluff fix`.
- **Small community.** One maintainer, ~300 downloads/month. If you
  need something in the next 24 hours, sqlfluff's 20-person team will
  get to you first.
- **Newer.** A year of production use is not five years of production
  use.

## When to use both together

A concrete setup I run in a production data pipeline:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Pawansingh3889/sql-sop
    rev: v0.4.1
    hooks:
      - id: sql-guard
        args: [--severity, error]  # fast, block on real dangers
```

```yaml
# .github/workflows/ci.yml (excerpt)
jobs:
  sqlfluff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: |
          pip install sqlfluff
          sqlfluff lint --dialect postgres .
```

Pre-commit catches the dangerous stuff in under a second; CI runs
sqlfluff at leisure and enforces the style guide. Developers never feel
the cost of either.

## If you're picking one

- **You maintain a dbt project.** Use sqlfluff. Don't look back.
- **You have a SQL-heavy Python backend and want pre-commit safety.**
  Use sql-sop. Add sqlfluff later if you expand the SQL codebase.
- **You're a solo dev who just wants a lint in your next commit.**
  Use sql-sop for five seconds. Add sqlfluff when it starts paying off.
- **You have a mature data team across multiple dialects.** Use
  sqlfluff. Everything else is a distraction.

## Honest footnote

I'm the author of sql-sop, so take the comparison with that bias in
mind. The benchmark number (0.08s vs 45s) was run on my machine
against a 200-file corpus; your mileage varies. sqlfluff's 800 rules
are mostly opt-in - the default rule set is more like 80, which is still
vastly more than sql-sop's 23.

None of this is a zero-sum argument. sqlfluff is excellent. sql-sop
exists because I wanted a smaller, faster shape for the pre-commit
surface, and writing it was cheaper than bending sqlfluff into that
shape. If you end up picking sqlfluff after reading this, that's a
reasonable outcome.

---

*The sql-sop repo and PyPI package are here:*

- *Repo: <https://github.com/Pawansingh3889/sql-sop>*
- *PyPI: `pip install sql-sop`*

*sqlfluff's home:*

- *Repo: <https://github.com/sqlfluff/sqlfluff>*
- *PyPI: `pip install sqlfluff`*
