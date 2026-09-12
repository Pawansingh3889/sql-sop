# Announcement posts - multi-channel

Four drafts for the same news, tuned to each channel's conventions. Use
whichever matches the channel you're posting to; don't cross-post the
LinkedIn version to Hacker News.

The anchor claim is the same across all: you scanned real OSS SQL and
found N real hazards. You need to actually run sql-sop on a real corpus
first and fill in the numbers - the drafts below use placeholders in
`<angle brackets>`.

---

## 1. LinkedIn - long, professional, workplace-safe

```
sql-sop v0.4.0 - a small update on a small project.

It's a rule-based SQL linter. 23 rules, 78 tests, runs as a pre-commit
hook or GitHub Action, instant feedback. ~300 monthly downloads from PyPI
- modest numbers, but enough to confirm other people hit the same pain.

To sanity-check coverage, I ran it this weekend against the SQL inside
the top <N> PyPI packages that ship raw queries. The harness flagged:

- <X> DELETE-without-WHERE patterns
- <Y> implicit cross joins
- <Z> f-string interpolation inside .execute() calls (classic SQL
  injection surface)

All pre-production, all catchable with a pre-commit hook.

The project has open rule-request issues tagged "good-first-issue" if
you want to ship your first OSS PR. Comparison with sqlfluff and a
hosted playground coming next.

Repo: https://github.com/Pawansingh3889/sql-sop
Install: pip install sql-sop
```

Notes:
- No emoji, no hashtags, no "excited to share" opener.
- Numbers come from an actual scan - don't post until you've run it.
- Ends with a soft CTA (good-first-issues) that doesn't beg for stars.

---

## 2. Twitter / X - one post or a small thread

**Single-post version:**

```
sql-sop v0.4.0 is out. Scanned the SQL inside the top <N> PyPI packages
and flagged <X> DELETE-without-WHERE, <Y> implicit cross joins, <Z>
f-string SQL-injection patterns. Pre-commit hook + GitHub Action, 0.08s
across 200 files.

pip install sql-sop
github.com/Pawansingh3889/sql-sop
```

**Thread version (use if the scan results are strong):**

```
1/ sql-sop v0.4.0 - rule-based SQL linter. 23 rules, pre-commit + GHA,
0.08s across 200 files. pip install sql-sop

2/ Ran it against real SQL inside the top <N> PyPI packages this weekend.
Flagged <X> DELETE-without-WHERE, <Y> cross joins, <Z> f-string injection
patterns. All pre-production, all catchable with a pre-commit hook.

3/ Not trying to replace sqlfluff (800 rules, formatting, dialects).
sql-sop is the fast first pass: catches 80% of real hazards with zero
config. Complements sqlfluff, doesn't compete.

4/ Ten "good-first-issue" rule requests up on the repo - each one is
~20 LOC, well-scoped, existing templates to mimic. Great first OSS PR
if you've been looking for one.

github.com/Pawansingh3889/sql-sop
```

---

## 3. Reddit - /r/Python, /r/dataengineering, /r/SQL

Reddit rewards honesty over polish. Lead with the self-disclosure.

```
Title: [Show] sql-sop - small rule-based SQL linter (308 downloads/month,
want to grow it the right way)

Hi r/<sub>,

I maintain sql-sop - a PyPI package that lints SQL for the "this would
delete production" class of mistakes. ~300 monthly downloads, 23 rules,
runs as pre-commit + GitHub Action.

Two things I'd genuinely like feedback on:

1) I ran it against SQL inside the top <N> PyPI packages. Caught <X>
DELETE-without-WHERE, <Y> implicit cross joins, <Z> f-string injection
patterns. Am I missing obvious categories that sqlfluff covers but I
don't? Honest comparison is here:
https://github.com/Pawansingh3889/sql-sop/blob/main/docs/blog/sqlfluff-vs-sql-sop.md

2) I just opened 10 "good-first-issue" rule requests. If you've been
wanting to ship a first OSS PR, each one is ~20 LOC with a template to
mimic. Feedback on which rule ideas look useful vs noisy would help.

Not trying to replace sqlfluff. sql-sop is the fast pre-commit pass
that catches 80% of real hazards with zero config. They complement each
other.

Repo: https://github.com/Pawansingh3889/sql-sop
Install: pip install sql-sop

Happy to answer anything.
```

---

## 4. Hacker News - Show HN

HN replies reward terse, factual, evidence-heavy posts. No marketing
speak. Keep it under 150 words in the body.

```
Title: Show HN: sql-sop - a rule-based SQL linter that runs in pre-commit

Body:

sql-sop is a rule-based SQL linter. 23 rules, 78 tests, runs as a CLI,
a pre-commit hook, or a GitHub Action. Written in pure Python with
optional sqlparse (for AST rules) and libCST (for Python scanning).

Scanned SQL inside the top <N> PyPI packages for calibration. Flagged:
- <X> DELETE-without-WHERE
- <Y> implicit cross joins
- <Z> f-string interpolation in .execute() calls

0.08s across 200 files. Benchmark vs sqlfluff: 560x faster on the same
corpus (sqlfluff is ~800 rules and does a lot more - different tool for
different jobs).

Repo: https://github.com/Pawansingh3889/sql-sop
PyPI: pip install sql-sop

Honest comparison with sqlfluff:
https://github.com/Pawansingh3889/sql-sop/blob/main/docs/blog/sqlfluff-vs-sql-sop.md

Feedback welcome.
```

---

## Posting sequence (don't do them all the same hour)

1. **LinkedIn Monday or Wednesday morning UK time** - workplace audience
   skims LinkedIn before stand-up.
2. **Reddit Tuesday afternoon UTC** - highest subreddit engagement
   window.
3. **Twitter / X same as Reddit** - retweet from the Reddit thread if
   it gets traction.
4. **Hacker News Sunday-Monday UK morning (US east coast waking up)** -
   only if you have real scan numbers. HN punishes vanity posts.

Don't post to all four in 24 hours; you'll look like you're spamming.
Space them across 3-5 days.

---

## Pre-flight checklist

Before posting anywhere:

- [ ] Real scan numbers filled in (no `<angle brackets>` left)
- [ ] Repo has issue templates live
- [ ] Good-first-issue tickets are seeded and labelled
- [ ] CLI feedback prompt is in the latest released version
- [ ] README links still work
- [ ] `pip install sql-sop` works on a clean venv
- [ ] GitHub Discussions enabled
- [ ] "Who's using sql-sop?" discussion pinned
