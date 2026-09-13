# GitHub Marketplace release - checklist

A Marketplace listing gives sql-sop its own discoverable page with an
install count badge. Separate from PyPI, same code. One-time setup,
~10 minutes.

## Pre-flight

- [x] `action.yml` exists at repo root (already true).
- [x] Action has a unique `name` field (`sql-sop`).
- [ ] Action has `author` field filled in (added in this commit).
- [ ] Action has `branding` with icon + colour (added in this commit).
- [ ] Repo is public on GitHub (already true).
- [ ] Release notes draft ready (below).

## Release notes draft - v0.4.1

Tag name: `v0.4.1`
Release title: `v0.4.1 - GitHub Marketplace launch + engagement pack`

### Body

```markdown
## What's new

sql-sop v0.4.1 is primarily a distribution release - same 23 rules, same
engine, now listed on the GitHub Marketplace with a proper install flow
and branding.

### Added
- **GitHub Marketplace listing** - sql-sop's GitHub Action is now
  searchable and installable directly from the Marketplace.
- **Issue templates** - `rule-request.yml` and `bug-report.yml`
  structured forms, `config.yml` to route usage questions to Discussions.
- **CLI feedback CTA** - when findings are reported, sql-sop now prints
  a link to the rule-request template so patterns we don't catch yet
  become issues.
- **`--include-python` surfaced in the GitHub Action** - previously only
  reachable via CLI args.

### Changed
- `action.yml` now declares `author` and `branding` (required for
  Marketplace).

### Community
- Ten `good-first-issue` tickets have been opened covering proposed new
  rules (W011-W018, S004, P005).
- GitHub Discussions is now enabled with a pinned "Who's using sql-sop?"
  thread.
- A comparison post with sqlfluff is published in `docs/blog/`.

### Upgrade

```bash
pip install --upgrade sql-sop
```

Or, for the GitHub Action:

```yaml
- uses: Pawansingh3889/sql-sop@v0.4.1
  with:
    paths: '.'
    severity: warning
    include-python: 'true'  # new
```

Full changelog: https://github.com/Pawansingh3889/sql-sop/blob/main/CHANGELOG.md
```

## Publishing steps

1. **Land the engagement branch** - merge the changes in this PR (new
   `.github/ISSUE_TEMPLATE/`, updated `action.yml`, updated
   `reporters/terminal.py`, new `docs/engagement/*`, new `docs/blog/*`,
   new `playground/*`).

2. **Bump version in `pyproject.toml`** to `0.4.1` and update
   `CHANGELOG.md` with the block above (without the fenced wrapping).

3. **Tag and push**:

   ```bash
   cd sql-sop
   git tag -a v0.4.1 -m "v0.4.1 - Marketplace launch + engagement pack"
   git push origin v0.4.1
   ```

4. **Create GitHub Release**:

   - GitHub web UI: Releases -> Draft a new release -> Choose tag
     `v0.4.1`.
   - Title: `v0.4.1 - GitHub Marketplace launch + engagement pack`.
   - Body: paste the release-notes draft above (drop the outer fence).
   - **Tick "Publish this Action to the GitHub Marketplace"** - this
     is the step that creates the listing.
   - Primary category: **Code quality**.
   - Secondary category: **Continuous integration**.
   - Accept Marketplace terms.
   - Click Publish release.

5. **Verify the listing** - visit
   <https://github.com/marketplace/actions/sql-sop> (URL slug may
   differ) within ~30 minutes. Check the install button works and
   the Readme preview looks right.

6. **Publish to PyPI** - tag-push triggers the existing CI release
   workflow if one is wired up; otherwise:

   ```bash
   python -m build
   python -m twine upload dist/sql_sop-0.4.1*
   ```

## If the Marketplace rejects the name

GitHub sometimes flags action names that are too generic. If `sql-sop`
is rejected, rename to `sql-sop-linter` in `action.yml` - the package
name on PyPI is separate and doesn't need to change.

## Post-release

- [ ] Update README with a "GitHub Marketplace" badge pointing to the
      listing URL.
- [ ] Announce on LinkedIn / Twitter using the copy from
      `announcement-posts.md` (include the Marketplace link in the text).
- [ ] Submit the listing URL to the
      [awesome-actions](https://github.com/sdras/awesome-actions) list
      via PR.
