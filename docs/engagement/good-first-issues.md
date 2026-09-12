# Good first issues - 10 rule seeds

Paste each section below as a new GitHub Issue at:
<https://github.com/Pawansingh3889/sql-sop/issues/new?template=rule-request.yml>

or use the blank form if the template doesn't fit (structural rules).

For every issue, apply labels: `good-first-issue`, `help-wanted`,
`rule-request`. For structural ones (S-prefix), also `structural`.

Rule IDs below (W011-W018, S004, P005) are the next available slots in
each family; if you add rules in a different order, renumber accordingly.

---

## Issue 1 of 10

**Title:** `rule: W011 union-without-all - warn on UNION when UNION ALL would work`

**Body:**

`UNION` forces a sort-and-dedupe pass; `UNION ALL` concatenates. On large
result sets the difference is often an order of magnitude. In most real
queries people write `UNION` out of habit when `UNION ALL` is correct -
either because the two sides are already disjoint (e.g. different tables,
different date ranges) or because duplicate rows aren't possible given the
schema.

A `W011` rule warns on every `UNION` (not `UNION ALL`) so the author has
to actively justify the dedupe cost.

### Should fail

```sql
SELECT id FROM orders_2024
UNION
SELECT id FROM orders_2025;
```

### Should pass

```sql
SELECT id FROM orders_2024
UNION ALL
SELECT id FROM orders_2025;
```

### Implementation hints

- Mirror `W005 subquery-in-where` in `sql_guard/rules/warnings.py` - it's
  a single-statement multiline rule.
- Regex: `r"\bUNION\b(?!\s+ALL\b)"`
- Severity: `warning`.
- Add to `ALL_RULES` in `sql_guard/rules/__init__.py`.
- Test: copy the shape of `test_rules.py::test_missing_limit` - one
  triggering input, one non-triggering input.

Estimated LOC: ~25 code + ~15 test.

---

## Issue 2 of 10

**Title:** `rule: W012 group-by-ordinal - warn on GROUP BY 1, 2 (non-portable)`

**Body:**

`GROUP BY 1, 2` groups by output columns by position. It's terse but
brittle: if the SELECT list is reordered, the query silently produces
different results. Also non-portable (some dialects reject ordinals in
newer modes).

### Should fail

```sql
SELECT region, status, COUNT(*)
FROM orders
GROUP BY 1, 2;
```

### Should pass

```sql
SELECT region, status, COUNT(*)
FROM orders
GROUP BY region, status;
```

### Implementation hints

- Single-line rule in `sql_guard/rules/warnings.py`.
- Regex: `r"\bGROUP\s+BY\s+\d+(\s*,\s*\d+)*\b"` - matches `GROUP BY 1` or
  `GROUP BY 1, 2, 3`.
- Careful: don't trigger on `GROUP BY col1, col2` where the column names
  happen to start with digits (rare but possible).
- Severity: `warning`.

Estimated LOC: ~20 code + ~15 test.

---

## Issue 3 of 10

**Title:** `rule: W013 having-without-group-by - warn on HAVING without GROUP BY`

**Body:**

`HAVING` without `GROUP BY` is legal but almost always a mistake - the
author usually meant `WHERE`. The engine treats the whole result set as
one group, which can produce surprising row counts.

### Should fail

```sql
SELECT total FROM orders HAVING total > 1000;
```

### Should pass

```sql
SELECT region, SUM(total)
FROM orders
GROUP BY region
HAVING SUM(total) > 1000;
```

### Implementation hints

- Multi-line rule (`multiline = True`, override `check_statement`).
- Detect `HAVING` without a preceding `GROUP BY` in the same statement.
- Model after `W006 orderby-without-limit` which uses the same pattern.
- Severity: `warning`.

Estimated LOC: ~30 code + ~20 test.

---

## Issue 4 of 10

**Title:** `rule: W014 case-without-else - warn on CASE expression without ELSE`

**Body:**

`CASE WHEN ... THEN ... END` without an `ELSE` branch returns `NULL` for
unmatched rows. Often unintended - the author thought the `WHEN`
conditions were exhaustive but they aren't, or the downstream code
can't handle NULL.

### Should fail

```sql
SELECT CASE
  WHEN status = 'paid' THEN 1
  WHEN status = 'pending' THEN 0
END AS paid_flag
FROM orders;
```

### Should pass

```sql
SELECT CASE
  WHEN status = 'paid' THEN 1
  WHEN status = 'pending' THEN 0
  ELSE NULL
END AS paid_flag
FROM orders;
```

### Implementation hints

- Multi-line rule.
- Detect `CASE` ... `END` without `ELSE` between.
- Test with nested CASE expressions - make sure outer CASE without ELSE
  still triggers when inner CASE has ELSE.
- Severity: `warning`.

Estimated LOC: ~35 code + ~25 test.

---

## Issue 5 of 10

**Title:** `rule: W015 join-function-on-column - warn on JOIN ... ON f(col) = ...`

**Body:**

`W003 function-on-column` already catches function wrapping in `WHERE`.
The same pattern in `JOIN ... ON` is equally index-hostile but currently
slips through. Split into its own rule for clarity.

### Should fail

```sql
SELECT *
FROM orders o
JOIN customers c ON UPPER(o.email) = UPPER(c.email);
```

### Should pass

```sql
SELECT *
FROM orders o
JOIN customers c ON o.email_lower = c.email_lower;
```

### Implementation hints

- Single-line rule.
- Look at `W003` and reuse its function list (`YEAR|MONTH|UPPER|LOWER|...`).
- Regex: `r"\bJOIN\b.*\bON\b.*\b(YEAR|MONTH|DAY|UPPER|LOWER|TRIM|CAST|CONVERT|SUBSTRING)\s*\("`
- Severity: `warning`.

Estimated LOC: ~25 code + ~15 test.

---

## Issue 6 of 10

**Title:** `rule: W016 not-in-with-subquery - warn on NOT IN (SELECT ...)`

**Body:**

`NOT IN (SELECT ...)` silently returns zero rows if the subquery result
contains any `NULL`. One of the most common SQL footguns. Use
`NOT EXISTS` or `LEFT JOIN ... WHERE ... IS NULL` instead.

### Should fail

```sql
SELECT *
FROM customers
WHERE id NOT IN (SELECT customer_id FROM orders);
```

### Should pass

```sql
SELECT *
FROM customers c
WHERE NOT EXISTS (
  SELECT 1 FROM orders o WHERE o.customer_id = c.id
);
```

### Implementation hints

- Multi-line rule.
- Regex: `r"\bNOT\s+IN\s*\(\s*SELECT\b"`.
- Severity: `warning` (could argue `error` - open for discussion).

Estimated LOC: ~25 code + ~15 test.

---

## Issue 7 of 10

**Title:** `rule: W017 count-distinct-unbounded - warn on COUNT(DISTINCT col) without LIMIT/filter`

**Body:**

`COUNT(DISTINCT col)` on a large unfiltered table forces a full sort
and distinct pass. Often a perf surprise on prod. Warn when there's no
`WHERE`, `LIMIT`, or `GROUP BY` restricting the scope.

### Should fail

```sql
SELECT COUNT(DISTINCT user_id) FROM events;
```

### Should pass

```sql
SELECT COUNT(DISTINCT user_id) FROM events WHERE event_date >= CURRENT_DATE - 7;
```

### Implementation hints

- Multi-line rule.
- Look for `COUNT(DISTINCT ...)` and require either WHERE or GROUP BY in
  the same statement.
- Severity: `warning`.

Estimated LOC: ~30 code + ~20 test.

---

## Issue 8 of 10

**Title:** `rule: W018 cross-join-explicit - warn on explicit CROSS JOIN`

**Body:**

`S001 implicit-cross-join` catches `FROM a, b`. But explicit `CROSS JOIN`
slips through. Cross joins are rarely intentional outside of lookup-table
generation (calendars, cohort grids). Warn so the author confirms intent.

### Should fail

```sql
SELECT *
FROM products p
CROSS JOIN regions r;
```

### Should pass

```sql
SELECT *
FROM calendar_dates
CROSS JOIN (SELECT 1 AS n UNION ALL SELECT 2);
-- with an explicit "-- noqa: W018" comment to allow
```

### Implementation hints

- Single-line rule.
- Regex: `r"\bCROSS\s+JOIN\b"`.
- Severity: `warning`.
- Bonus: support `-- noqa: W018` comment to suppress.

Estimated LOC: ~20 code + ~15 test + (optional) noqa plumbing.

---

## Issue 9 of 10

**Title:** `rule: S004 window-without-partition - warn on OVER () without PARTITION BY`

**Body:**

`ROW_NUMBER() OVER ()` or `SUM(x) OVER ()` without `PARTITION BY` computes
over the entire result set. Sometimes intentional, often a bug - the
author forgot to specify the partition key.

### Should fail

```sql
SELECT
  user_id,
  ROW_NUMBER() OVER () AS rn
FROM events;
```

### Should pass

```sql
SELECT
  user_id,
  ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY event_time) AS rn
FROM events;
```

### Implementation hints

- Structural rule in `sql_guard/rules/structural.py`.
- Model after `S002 deeply-nested-subquery` - uses sqlparse tokens.
- Detect `OVER ( ... )` where the inner content lacks `PARTITION BY`.
- Severity: `warning`.

Estimated LOC: ~40 code + ~25 test.

---

## Issue 10 of 10

**Title:** `rule: P005 sqlalchemy-text-fstring - warn on sqlalchemy.text(f"...{var}")`

**Body:**

`sqlalchemy.text()` is the escape hatch for raw SQL in SQLAlchemy. If
you wrap an f-string inside it, you've defeated parameter binding and
re-introduced the SQL injection risk that P001-P004 catch for cursor
calls. Same vulnerability, different surface.

### Should fail

```python
from sqlalchemy import text
conn.execute(text(f"SELECT * FROM users WHERE id = {user_id}"))
```

### Should pass

```python
from sqlalchemy import text
conn.execute(
    text("SELECT * FROM users WHERE id = :id"),
    {"id": user_id},
)
```

### Implementation hints

- libCST rule in `sql_guard/rules/python_rules.py`.
- Model after `P001 fstring-in-execute`.
- Detect `sqlalchemy.text(<FormattedString>)` or `text(<FormattedString>)`.
- Severity: `error`.

Estimated LOC: ~30 code + ~25 test.

---

## Why this list works as a first-PR gauntlet

- Each rule is ~20-40 lines of code, all following an established template.
- Five mirror existing rules exactly (`W011`-`W012`, `W015`-`W016`, `W018`)
  so the reviewer workload is small.
- Two introduce new structural patterns (`W013`, `W014`, `S004`) giving
  more experienced contributors somewhere to stretch.
- One crosses the Python scanner boundary (`P005`) - good for devs who
  want to learn libCST.

Publishing these creates ten distinct "here's what I need" tickets that
look inviting instead of one monolithic TODO file.
