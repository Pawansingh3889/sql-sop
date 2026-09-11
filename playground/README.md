# sql-sop playground

A single-file, static HTML playground that runs sql-sop **in the user's
browser** via Pyodide. Paste SQL, click Lint, see rule output. No server,
no data exfiltration, no auth.

## Why a playground

People's first encounter with a linter is usually "does this catch the
bug I just saw?" A five-second in-browser check beats `pip install` for
that first-touch moment. The playground becomes the link you paste in
HN comments, LinkedIn replies, and code reviews.

The ruff team has [ruff-playground.astral.sh](https://play.ruff.rs/);
the sqlfluff team has [sqlfluff.com/try](https://sqlfluff.com/try).
This is the sql-sop equivalent.

## How it works

- `index.html` is the entire playground. ~200 lines, no bundler.
- On load it pulls Pyodide 0.26.3 from the jsDelivr CDN (~5-10 MB
  initial download, one-time per browser).
- `micropip.install('sql-sop')` grabs sql-sop from PyPI into the
  Pyodide virtual filesystem.
- `SqlGuard().scan(text)` runs the full Python ruleset, including the
  structural (sqlparse) rules.
- Findings are serialised to JSON and rendered in the right pane.

Since sql-sop has no native extensions and all its deps are pure Python,
Pyodide handles it with no extra wheels needed.

## Deploy to GitHub Pages

```bash
# On main (or a gh-pages branch if you prefer):
git checkout -b gh-pages-setup
# Add a Pages config:
```

In the repo on github.com:

1. Settings -> Pages.
2. Source: "Deploy from a branch".
3. Branch: `main`, folder `/playground`.
4. Save.

GitHub takes ~60 seconds, then the playground is live at
`https://pawansingh3889.github.io/sql-sop/`.

If you prefer a custom domain (e.g. `play.sqlsop.dev`), add a `CNAME`
file inside `playground/` with one line (your domain), then configure
the DNS A-records GitHub shows.

## Deploy to Cloudflare Pages (alternative)

1. <https://dash.cloudflare.com/> -> Workers & Pages -> Create -> Pages.
2. Connect the repo.
3. Build command: *(leave blank - static site)*.
4. Build output directory: `playground`.
5. Save.

Cloudflare gives you `sql-guard.pages.dev` within a minute. Faster
global CDN, unlimited requests on the free tier.

## Local dev

```bash
cd playground
python -m http.server 8000
open http://localhost:8000/
```

Any static-file server works - no build step.

## Customising the example SQL

The pre-filled SQL in the textarea is hard-coded near the top of
`index.html`. Edit the `<textarea>` `placeholder` attribute or initial
value. Keep it short and punchy; goal is to demonstrate three failure
modes in the first 10 seconds of a visitor's attention.

## Size and performance

Cold load: 5-10 seconds (Pyodide is ~5 MB compressed). Warm load
(same browser, cached): ~1 second. Lint of 1,000 lines of SQL: under
a second after warm.

Acceptable for a "playground" shape. Not acceptable for a CI runner -
which is why CLI + GitHub Action remain the primary distribution.

## Known limitations

- **No file upload (yet).** Single-textarea input only. Could be added
  in ~20 lines if demand appears.
- **No share-link.** The URL doesn't encode the pasted SQL. Could be
  added via `#sql=<base64>` fragment.
- **No dark/light toggle.** Dark only, matching the sql-sop terminal
  aesthetic.

All three are fine first-timer PRs if someone wants to contribute.

## Maintenance

Pyodide version is pinned in the CDN URL
(`pyodide/v0.26.3/full/pyodide.js`). Bump it yearly or when Pyodide
ships a Python version bump that matters. Test locally before shipping
- Pyodide's `micropip` behaviour changes between majors.

sql-sop version is NOT pinned - `micropip.install('sql-sop')` grabs the
latest from PyPI on each load. If a release has a regression, revert
the PyPI release; the playground follows automatically.
