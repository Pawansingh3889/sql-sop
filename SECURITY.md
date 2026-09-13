# Security policy

sql-sop is a SQL linter. The primary security concern is **false
negatives** — a dangerous pattern the linter misses and users trust
it to catch. This document sets out how to report those and what to
expect.

## Supported versions

The latest minor version series on PyPI is supported. Older series
receive security fixes for 90 days after a newer minor ships.

| Version | Status | Support ends |
| --- | --- | --- |
| 0.4.x | current | — |
| 0.3.x | supported | 90 days after 0.5.0 ships |
| 0.2.x and older | unsupported | already ended |

Always upgrade to the latest release before filing a bug.

## Threat model

sql-sop is a static analyser. It does not execute SQL, connect to
databases, or send telemetry. The surfaces that matter:

| Surface | Protection | Where |
| --- | --- | --- |
| Rule coverage | Every rule has fires-on-bad + does-not-fire-on-safe tests | `tests/test_rules.py` |
| SQL parsing | Optional sqlparse for structural rules; regex for single-line | `sql_guard/rules/*.py` |
| Python file scanning | libCST for AST-level extraction, opt-in via `[python]` extra | `sql_guard/python_scanner.py`, `tests/test_python_scanner.py` |
| PyPI trusted publishing | GitHub Actions OIDC, no long-lived tokens | `.github/workflows/release.yml` |

What a report should cover:

- **False negatives** — SQL that should trigger a rule but doesn't.
  Highest priority.
- **False positives that waste user time at scale** — a rule that
  fires on safe SQL patterns common in real codebases.
- **Rule bypasses via regex gaps** — if you can craft input that
  looks dangerous to a reader but doesn't trigger the rule.
- **Supply-chain concerns** — an upstream dependency (sqlparse,
  libCST) with a CVE that affects how sql-sop parses user input.

## Reporting a vulnerability

**Do not open a public GitHub issue for a security problem.**

Report privately via the GitHub security advisory form:

<https://github.com/Pawansingh3889/sql-sop/security/advisories/new>

Include:

1. **What you found** — one-sentence description.
2. **Reproduction** — the SQL string that bypasses / over-triggers
   the rule, and the expected behaviour.
3. **Rule ID** involved, if any (`E001`, `W001`, etc.).
4. **Impact** — what kind of real-world vulnerability could reach
   production if a user relied on sql-sop.
5. **Suggested fix** — optional. Regex adjustment or a new test case.

## What to expect

| Severity | Initial response | Fix target |
| --- | --- | --- |
| Critical (rule bypass on documented-dangerous pattern) | within 48 hours | within 7 days |
| High (false positive on widespread safe pattern) | within 5 days | next patch release |
| Medium | within 7 days | next minor release |
| Low / info | within 14 days | when scoped |

## Coordinated disclosure

Default 90 days. Sooner if the fix has shipped to PyPI and you agree.

## Scope

**In scope:**

- Everything in `sql_guard/`
- Tests in `tests/`
- CI workflows in `.github/workflows/`
- The published PyPI artefact (`sql-sop`)

**Out of scope:**

- Upstream CVEs in sqlparse or libCST (report upstream; link the
  advisory here so we can pin the fix)
- User misconfiguration of pre-commit hooks
- Policy questions ("why isn't rule X built-in?") — open a feature
  request issue instead

## Previous advisories

None.
