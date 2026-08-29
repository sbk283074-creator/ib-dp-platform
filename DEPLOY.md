# Deploy — IB DP Question Bank

Full-stack app on **Netlify** (one platform):

| Layer        | Where it runs                                                       |
|--------------|--------------------------------------------------------------------|
| Frontend     | Static build (`frontend/dist`) served by Netlify CDN               |
| API          | Netlify Function `netlify/functions/api.js` (Express ⇢ `serverless-http`) |
| Figures      | Netlify Blob store `figures`, served by `netlify/functions/figure.js` |
| Database     | **Turso** (hosted libSQL) in production; local SQLite for dev      |

The frontend is **unchanged** — it still calls `/api/*` and `/figures/*`, and the
`netlify.toml` redirects map those to the functions. No code changes needed in `frontend/`.

---

## 0. What was already verified (this session)

- Backend refactor (`better-sqlite3` ⇢ dual-mode `@libsql/client`) boots clean.
- **Local mode**: `GET /api/questions` → `total = 9969`; facets, paper-templates (9),
  progress endpoints all respond; `POST /api/questions` → `GET` round-trip works and
  auto-derives `category='past'`, `review_status='new'`.
- **Turso `file:` mode** (no network creds): DDL via `executeMultiple`, `ALTER TABLE`
  migrations, paper-template seed through the Turso transaction wrapper, and a real
  `POST`→`GET` write/read round-trip all succeed; the row persists in the libSQL file.

---

## 1. Prerequisites (install once)

```bash
# Netlify CLI (already installed here: netlify-cli/26.2.0)
npm i -g netlify-cli

# Turso CLI  — NOT installed yet. Pick one:
brew install tursodatabase/tap/turso        # macOS (Homebrew)
#   or
curl -sSfL https://get.tur.so | bash        # any platform
#   or create the DB from the Turso web dashboard (no CLI needed)
```

Accounts: a [Netlify](https://app.netlify.com) account and a [Turso](https://turso.tech) account.

---

## 2. Local smoke test (recommended before going live)

From the repo root (this uses the **local SQLite** engine — `TURSO_URL` unset):

```bash
npm install                      # root: function deps
cd backend && npm install && cd ..   # backend: better-sqlite3 + express for local dev

TURSO_URL="" PORT=3001 node backend/src/index.js &
curl -s http://localhost:3001/api/health        # -> {"ok":true,...}
curl -s 'http://localhost:3001/api/questions?limit=1'   # -> {"total":9969,...}
```

Stop the server when done (`kill %1`). The live DB is `backend/data/app.db` (9,969 rows).

> Optional permanent local backend (macOS): `launchctl load ~/Library/LaunchAgents/com.ibdp.backend.plist`
> (plist already exists). Do this **once**; it keeps the local API on `:3001` across reboots.

---

## 3. Create the Turso database (production)

```bash
turso login
turso db create ibdp
turso db show ibdp --url            # -> copy the libsql:// URL
turso db tokens create ibdp --expiration none   # -> copy the token (long-lived)
#   or, for a shorter-lived token: turso db token create ibdp --read-write --expiration 30d
```

You now have two values:
- `TURSO_URL`  — e.g. `libsql://ibdp-xxxx.turso.io`
- `TURSO_AUTH_TOKEN` — the token string

> The app opens the DB and runs **all migrations automatically** on first boot
> (`CREATE TABLE IF NOT EXISTS` + 20 column migrations + indexes + paper-template seed).
> You do **not** need to run any SQL by hand.

### Load the data into Turso (one time)

The app only creates schema; it does **not** copy your 9,969 local questions.
Use the bundled loader — it reuses `backend/src/db.js`, so the Turso schema +
migrations are created **identically** to what the running function expects, then
copies every table (`questions`, `books`, `knowledge_points`, `paper_templates`,
`progress`, `wrong_notebook`, `reports`, `question_usage`, …) with `INSERT OR REPLACE`
(idempotent — safe to re-run):

```bash
TURSO_URL="libsql://ibdp-xxxx.turso.io" \
TURSO_AUTH_TOKEN="your-token-here" \
node scripts/migrate-to-turso.mjs
```

If it fails partway, just re-run — the loader is idempotent.

---

## 4. Link the Netlify site & set secrets

> The site `ib-dp-platform` is **already created and linked** (`.netlify/state.json`
> present) in this project, and `netlify.toml` already uses the correct
> `external_node_modules = [...]` syntax. If you're starting fresh elsewhere, run
> `netlify init` (or `netlify sites:create --name ib-dp-platform`) first. Note:
> `netlify sites:create` can hang in some CI shells — the REST API
> (`POST /api/v1/sites` with a bearer token) is a reliable alternative.

```bash
netlify login            # already authenticated on this machine
# Set the two required production env vars (also in Site settings → Environment):
netlify env:set TURSO_URL      "libsql://ibdp-xxxx.turso.io"
netlify env:set TURSO_AUTH_TOKEN "your-token-here"
```

> The figure function (`@netlify/blobs` `getStore('figures')`) auto-resolves the site
> blob store at runtime — **no extra env vars needed** for serving images in prod.

---

## 5. Upload the 89,004 figure images to Blob storage

9.2 GB across 89,004 files. The script is **resumable** (skips keys already present),
so you can re-run it after an interruption.

```bash
netlify login                         # needed so the CLI knows the site
npm run upload-figures                # walks backend/public/figures -> Blob store 'figures'
```

Notes:
- Keys = path relative to `backend/public/figures` (e.g. `paper_aa_hl_p1/abc.jpg`),
  which is exactly the `/figures/<key>` path the frontend requests. No frontend change.
- `npm run upload-figures` auto-resolves `NETLIFY_SITE_ID` (from `.netlify/state.json`)
  and `NETLIFY_AUTH_TOKEN` (from the local CLI config) after `netlify login`.
- For CI, set `NETLIFY_SITE_ID` + `NETLIFY_AUTH_TOKEN` explicitly.
- If the upload fails with a Blobs **401**, generate a Netlify personal access token
  (User settings → Applications → New access token) and run:
  `NETLIFY_AUTH_TOKEN="<pat>" npm run upload-figures`.
- Expect this to take a while (9.2 GB). Watch the `uploaded/skipped/failed` counters.

---

## 6. Build & deploy

```bash
npm run build          # cd frontend && npm install && npm run build  ->  frontend/dist
npm run deploy         # netlify deploy --prod
```

Netlify reads `netlify.toml`:
- build → `npm run build`, publish → `frontend/dist`
- `functions` dir = `netlify/functions`, bundled with `esbuild`
- `better-sqlite3` and `@libsql/client` are `external` (never bundled; resolved at runtime)
- redirects: `/api/*` → api function, `/figures/*` → figure function, `/*` → SPA

---

## 7. Verify the live site

```bash
SITE=https://<your-site>.netlify.app

curl -s $SITE/.netlify/functions/api/health          # -> {"ok":true}
curl -s "$SITE/.netlify/functions/api/questions?limit=1"   # -> {"total":9969,...}
curl -s -o /dev/null -w '%{http_code}\n' "$SITE/figures/<any-key>.jpg"   # -> 200
```

(`<any-key>` = a real figure path from the DB, e.g. `paper_aa_hl_p1/abc.jpg`.)

Or just open the site in a browser and browse questions.

---

## 8. Local development against Netlify (`netlify dev`)

```bash
netlify login
TURSO_URL="file:/tmp/ibdp_dev.db" netlify dev     # builds frontend, runs both functions locally
```

`netlify dev` serves the frontend + functions together and emulates the Blob store
(requires `netlify login`). The `TURSO_URL=file:...` uses a throwaway local libSQL file
so you don't touch production data.

---

## 9. Known limitations / decisions

- **Turso transactions are best-effort.** libSQL over HTTP has no session-wide
  transaction, so `db.transaction(fn)` runs statements sequentially (each autocommits)
  in Turso mode, but uses real `BEGIN/COMMIT/ROLLBACK` locally. Fine for this
  single-user study app; documented in `backend/src/db.js`.
- **`better-sqlite3` is local-only.** It is marked `external` and dynamically imported
  only when `TURSO_URL` is unset, so Netlify's build never compiles the native module.
- **Figures live in Blob, not Git.** They are 9.2 GB and excluded from the repo; the
  upload script populates Blob storage. If you wipe Blob storage, re-run `npm run upload-figures`.
- **DB data is not in Git either.** The 9,969 questions live in `backend/data/app.db`
  (local) and Turso (prod). Back up Turso via `turso db shell ibdp .dump` periodically.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Build fails: `vite: command not found` | `cd frontend && npm install` (now also in build script) |
| API returns 500 / `tURSO` auth error | Re-check `TURSO_URL` + `TURSO_AUTH_TOKEN` in Netlify env; ensure token not expired |
| Figures 404 in prod | Run `npm run upload-figures` again (resumable); confirm keys match DB paths |
| `Could not find better-sqlite3` on Netlify | Should not happen (external + never imported in Turso mode). If seen, confirm `TURSO_URL` is set in prod env |
| Cold-start slowness | Normal first hit; `db.init()` is cached per function instance (warm starts reuse it) |
