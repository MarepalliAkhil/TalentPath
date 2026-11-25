# Deploying TalentPath for free

Four free services, one per job:

| Piece | Service | What runs there |
| --- | --- | --- |
| Frontend | **Vercel** (Hobby) | The React app (`frontend/`), plus a rewrite that forwards `/api/*`, `/sitemap.xml` and `/robots.txt` to Render |
| Backend | **Render** (free web service, Singapore) | Django + Channels on one Daphne process, built from `backend/Dockerfile` |
| Database | **Neon** (free) | PostgreSQL (also stores uploaded files, compressed and encrypted) |
| Jobs | **cron-job.org** (free) | Calls the backend's ping, tick and nightly endpoints on a schedule |

```mermaid
flowchart LR
  B[Browser] -->|"same origin: /, /api/*"| V[Vercel]
  V -->|"rewrite /api/* over HTTPS"| R[Render: Daphne]
  B -.->|"WebSocket + single-use ticket (direct)"| R
  R --> N[(Neon PostgreSQL)]
  C[cron-job.org] -->|"GET /api/ping, POST /api/internal/tick and /nightly + X-Tick-Secret"| R
```

Order of work: **1** secrets → **2** Neon and `first_run_free` → **3** Render → **4** paste the Render URL into `vercel.json` → **5** Vercel → **6** set `FRONTEND_DOMAIN` on Render → **7** cron-job.org.

---

## 1. Generate the secrets (once, on your PC)

Run each command in `cmd.exe` (any Python 3.12 works, for example the backend's `.venv`) and paste the output into a password manager.

| Secret | Command |
| --- | --- |
| `SECRET_KEY` | `python -c "import secrets;print(secrets.token_urlsafe(50))"` |
| `FIELD_ENCRYPTION_KEY` | `python -c "import base64,os;print(base64.urlsafe_b64encode(os.urandom(32)).decode())"` |
| `BLIND_INDEX_KEY` | the same command again (it **must** differ from `FIELD_ENCRYPTION_KEY`) |
| `INTERNAL_TICK_SECRET` | `python -c "import secrets;print(secrets.token_urlsafe(32))"` |

**Generate new encryption keys for production. Never reuse the keys in your local `backend/.env`. Back up `FIELD_ENCRYPTION_KEY` and `BLIND_INDEX_KEY` offline (a password manager and a printed or USB copy kept somewhere safe). If they are lost, every encrypted field in the database (phone numbers, addresses, resume text and files, offer terms, leave reasons) can never be read again; no one can recover them.**

---

## 2. Neon: create the database and run `first_run_free`

1. Sign up at neon.com and create a project. Region: **AWS Asia Pacific (Singapore)**, next to the Render service. PostgreSQL 16 or newer.
2. On the project dashboard choose **Connect**, keep **Connection pooling off** (the direct connection; Django opens a new connection per request, `CONN_MAX_AGE=0`), and copy the connection string. It looks like `postgresql://neondb_owner:...@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require`.
3. From your PC, prepare the database. In `cmd.exe`, quote every `set` line (the URL contains `&`, which cmd would otherwise treat as a new command). Use the **production** secrets from step 1, and `DJANGO_LOAD_DOTENV=0` so nothing is taken from your local `.env`:

```
cd C:\Users\akhim\Downloads\talentpath\backend
.venv\Scripts\activate
set "DJANGO_LOAD_DOTENV=0"
set "DATABASE_URL=postgresql://neondb_owner:...@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
set "SECRET_KEY=..."
set "FIELD_ENCRYPTION_KEY=..."
set "BLIND_INDEX_KEY=..."
set "INTERNAL_TICK_SECRET=..."
python manage.py first_run_free
```

`first_run_free` does three things, in order:

1. creates the `btree_gist` extension (the interview scheduler's no-double-booking constraint needs it). If Neon refuses, it stops with a clear message: open Neon's **SQL Editor** and run `CREATE EXTENSION IF NOT EXISTS btree_gist;`, then run the command again;
2. applies every migration;
3. seeds the demo data **only if the database has no accounts yet**. A database that already holds accounts is never seeded or reset. Run it as often as you like.

If you plan to set `DEMO_PASSWORD` on Render, set the same value here first (`set "DEMO_PASSWORD=..."`) so the seeded accounts use it.

---

## 3. Render: create the backend

1. Push the repository to GitHub (see the git commands in the report or README).
2. On render.com choose **New → Blueprint**, connect the repository and pick the branch. Render reads `render.yaml`: one free web service named `talentpath-api`, Docker build from `backend/Dockerfile` with the repository root as context, region Singapore, health check `/api/ping`.
3. Render asks for every value marked `sync: false`. Fill them in from the table below (leave `FRONTEND_DOMAIN` as a placeholder such as `example.vercel.app` for now; step 6 sets the real one). **Create.**
4. Wait for the first deploy. The container runs `python manage.py migrate` and then **one** Daphne process on `$PORT`. When it is live, open `https://<your-service>.onrender.com/api/ping`: it answers `{"status": "ok"}`.
5. Copy the service URL, for example `https://talentpath-api.onrender.com`.

### Render environment variables

Values in `render.yaml` are set for you; the rest Render asks for. Example values are empty on purpose.

| Variable | Value | Notes |
| --- | --- | --- |
| `PRODUCTION` | `true` | In `render.yaml`. Turns on the production rules below (Render also sets `RENDER=true`, which does the same). |
| `DEBUG` | `false` | In `render.yaml`. Production refuses to start with `DEBUG=true`. |
| `DEMO_MODE` | `true` | In `render.yaml`. Try-as buttons on the For recruiters page, demo restrictions and the nightly demo reset (there is no banner since Prompt 1). |
| `NUM_PROXIES` | `2` | In `render.yaml`. Vercel and Render's proxy, so rate limits see the real client IP. |
| `LOG_LEVEL` | `INFO` | In `render.yaml`. |
| `FRONTEND_DOMAIN` | `` | Your Vercel domain **without** `https://`, e.g. `talentpath-akhil.vercel.app`. Required in production. Builds `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `WS_ALLOWED_ORIGINS` and `SITE_URL`. |
| `DATABASE_URL` | `` | The Neon string from step 2. `sslmode=require` is added if missing; connections are not kept open (`CONN_MAX_AGE=0`). |
| `SECRET_KEY` | `` | Step 1. At least 32 characters. |
| `FIELD_ENCRYPTION_KEY` | `` | Step 1. URL-safe base64 of 32 bytes. **The same value used for `first_run_free`.** |
| `BLIND_INDEX_KEY` | `` | Step 1. Different from `FIELD_ENCRYPTION_KEY`. **Same value as for `first_run_free`.** |
| `INTERNAL_TICK_SECRET` | `` | Step 1. At least 24 characters. cron-job.org sends it as `X-Tick-Secret`. |
| `DEMO_PASSWORD` | `` | Optional. Leave empty to keep the documented demo password. |
| `REDIS_URL` | `` | Leave **empty** on the free plan: one instance uses the in-memory channel layer and cache. |
| `EMAIL_PROVIDER` | `console` | Optional. `console` sends nothing (emails stay in the Email log). For real mail use `api`: Render's free plan blocks SMTP ports. See `docs/EMAIL.md`. |
| `EMAIL_API_PROVIDER` | `` | With `api`: `brevo` or `resend`. |
| `EMAIL_API_KEY` | `` | With `api`: the provider's key. Secret. |
| `EMAIL_FROM` / `EMAIL_FROM_NAME` | `` / `TalentPath` | A sender address the provider has verified. |
| `EMAIL_ALLOWLIST` | `` | Optional. Comma-separated addresses or `@domains`; anything else is held, not sent. |
| `EMAIL_MAX_PER_RECIPIENT_PER_HOUR`, `EMAIL_MAX_PER_HOUR`, `EMAIL_DAILY_CAP` | `10`, `60`, `250` | Optional limits. |
| `RENDER_EXTERNAL_HOSTNAME` | (set by Render) | Added to `ALLOWED_HOSTS` automatically. |

Optional overrides (normally leave unset): `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `WS_ALLOWED_ORIGINS` (extra values, comma separated, added to the ones built from `FRONTEND_DOMAIN`), `SECURE_HSTS_SECONDS` (default one year in production), `THROTTLE_LOGIN`, `THROTTLE_REGISTER`, `THROTTLE_PASSWORD_RESET`, `THROTTLE_UPLOAD`, `THROTTLE_HIRA`, `THROTTLE_SCHEDULE_LINK`.

What production mode enforces (`backend/config/settings.py`, tested in `tests/test_ops.py`):

- refuses to start without `SECRET_KEY`, `DATABASE_URL`, `FIELD_ENCRYPTION_KEY`, `BLIND_INDEX_KEY`, `INTERNAL_TICK_SECRET` and `FRONTEND_DOMAIN`, with weak or malformed keys, or with `DEBUG=true`;
- `ALLOWED_HOSTS` = `RENDER_EXTERNAL_HOSTNAME` + `FRONTEND_DOMAIN`; CSRF and WebSocket origins = `https://FRONTEND_DOMAIN`;
- cookies `Secure`, `HttpOnly` (session tokens) and `SameSite=Lax`; HTTPS redirect, HSTS for one year, `SECURE_PROXY_SSL_HEADER`;
- database over TLS (`sslmode=require`), `CONN_MAX_AGE=0`;
- passes `python manage.py check --deploy` with no warnings (HSTS preload is silenced: `onrender.com` is Render's domain, not yours).

The health check `/api/ping` makes no database query. Render's health checker may send a `Host` header Django does not know (it has been seen sending `localhost:10000`); `core/middleware.py` answers `/api/ping` for such hosts without loosening `ALLOWED_HOSTS` for anything else.

---

## 4. Paste the Render URL into `frontend/vercel.json`

`vercel.json` cannot read environment variables, so the Render URL is written **literally, in one place**: the first rewrite.

```json
{
  "source": "/:path(api/.*|sitemap\\.xml|robots\\.txt)",
  "destination": "https://REPLACE-WITH-RENDER-SERVICE.onrender.com/:path"
}
```

Replace `REPLACE-WITH-RENDER-SERVICE.onrender.com` with your service host, e.g. `https://talentpath-api.onrender.com/:path`, then commit and push. Everything else is derived from it at build time: the WebSocket origin for live updates (Vercel cannot proxy WebSockets, so the browser connects straight to Render with a 30-second, single-use ticket). **The Vercel build fails while the placeholder is still there** (`frontend/build/vercelConfig.ts`); a local `npm run build` only warns.

`vercel.json` also:

- serves the app for every route the app has and nothing else, so unknown paths get a real **404** status (and the app's own "page not found" screen, from `dist/404.html`);
- sends security headers: a Content Security Policy (`default-src 'self'`, `connect-src 'self' wss://*.onrender.com`, no inline scripts, `frame-ancestors 'none'`), HSTS, `nosniff`, `Referrer-Policy`, `X-Frame-Options: DENY`, `Permissions-Policy` and `Cross-Origin-Opener-Policy`;
- caches hashed files under `/assets/` for a year (`immutable`) and never caches `index.html`.

The production build ships **no source maps**.

---

## 5. Vercel: create the frontend

1. On vercel.com choose **Add New → Project** and import the repository.
2. **Root Directory**: `frontend`. Framework preset: **Vite**. Build command `npm run build`, output directory `dist`, install command `npm ci` (the defaults).
3. Keep **"Include files outside the root directory in the Build Step"** on (the default): the build reads `shared/` (brand, policy, skill data) and, for the For recruiters page, counts tests in `backend/` and reads results in `docs/`.
4. Environment variables: none are required.

| Variable | Value | Notes |
| --- | --- | --- |
| `VITE_DEMO_MODE` | `true` | Optional. Shows the demo inbox link on Forgot password (the backend's `DEMO_MODE` must be on too). |
| `VITE_WS_URL` | `` | Optional, leave empty. Overrides the WebSocket origin derived from `vercel.json`. |

`VITE_*` values are compiled into the public JavaScript: **never put a secret in a Vercel variable.**

5. **Deploy.** Note the domain Vercel gives you, e.g. `talentpath-akhil.vercel.app` (Settings → Domains lets you pick the name).

---

## 6. Tell Render where the frontend lives

On Render → `talentpath-api` → **Environment**, set `FRONTEND_DOMAIN` to the Vercel domain from step 5 (no `https://`) and save. Render redeploys. Open the Vercel site, sign in with a demo account or a **Try as** button.

If you add a custom domain later, change `FRONTEND_DOMAIN` to it (or add the old one to `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS`).

---

## 7. cron-job.org: the jobs

Sign up at cron-job.org (free). Create three jobs against the **Render** URL (not the Vercel one):

| Job | URL | Method and header | Schedule |
| --- | --- | --- | --- |
| Keep-alive | `https://<service>.onrender.com/api/ping` | GET | every 14 minutes |
| Tick | `https://<service>.onrender.com/api/internal/tick` | POST, header `X-Tick-Secret: <INTERNAL_TICK_SECRET>` | every 15 minutes |
| Nightly | `https://<service>.onrender.com/api/internal/nightly` | POST, header `X-Tick-Secret: <INTERNAL_TICK_SECRET>` | every day at 02:30, time zone **Asia/Kolkata** |

In each job: **Advanced → Request method** and **Headers**; set the job's **time zone** to Asia/Kolkata. Wrong or missing secrets get `403`; the comparison is constant-time.

cron-job.org stops waiting after **30 seconds**. The tick is quick (under 20 database queries when nothing is due). The nightly hook does its quick work, then starts the demo reset in a background thread and answers at once (`"demo_reset": "started"`); a second call while a reset is running answers `"running"` and does nothing.

### What the jobs do, and what never waits for them

| Work | Hook | Also done on read, so correctness never depends on cron |
| --- | --- | --- |
| Release expired 30-minute interview holds | tick | Yes: whenever interviews, the scheduling link or scorecards are read (`interviews.coordinator.catch_up`), and every booking releases expired holds first |
| Mark finished interviews completed (so scorecards can be submitted) | tick | Yes: same `catch_up` |
| Interview reminders (24 h, 1 h) and chasing overdue feedback | tick | No: these are notifications at a time; without the tick they are not sent. Needs-you items are computed on read |
| Offer expiry | tick | Yes: accepting an expired offer marks it expired and refuses |
| Leave delegation and 48-hour escalation | tick | Yes: when approvals or HR's needs-attention list are read |
| Monthly accrual and yearly grants | nightly | Yes: when balances are read, leave is previewed or applied for (idempotent ledger keys) |
| Year-end carry-forward | nightly | No, but any later nightly catches up (keyed per year) |
| Missing check-outs | nightly | Partly: attendance summaries count a past day without a check-out as missing; the one-time notification needs the nightly |
| Demo reset (only with `DEMO_MODE=true`) | nightly | Not needed for correctness |
| Expired token and old simulated-email clean-up | nightly | Not needed for correctness |

The keep-alive ping keeps the free service awake, which uses most of Render's 750 free hours a month (a 31-day month is 744 hours). Render discourages keeping free services awake artificially; if you prefer, delete the keep-alive job and accept a wake-up wait of about a minute after 15 quiet minutes. The app shows "Waking up the server, this can take up to a minute" and retries by itself on 502, 503 and 504.

---

## Updating

- Push to the branch Render and Vercel watch. Render rebuilds and runs migrations on start (`autoDeploy: true`); Vercel builds every push.
- Changing a Render environment variable redeploys the service.
- Never change `FIELD_ENCRYPTION_KEY` or `BLIND_INDEX_KEY` on a database that already has data: encrypted fields would become unreadable.
- To rebuild the demo data by hand: run the nightly hook, or from your PC (step 2 settings) `python manage.py seed --reset` (removes only `*.example` demo data).

## Manual backup

Neon keeps a short restore window; for your own copy, dump to a file. With Docker Desktop running (no local PostgreSQL install needed):

```
cd C:\Users\akhim\Downloads
docker run --rm -v "%cd%":/backup postgres:17 pg_dump "postgresql://neondb_owner:...@ep-xxxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require" -Fc -f /backup/talentpath-backup.dump
```

Restore into an empty database:

```
docker run --rm -v "%cd%":/backup postgres:17 pg_restore --no-owner --no-privileges -d "<target DATABASE_URL>" /backup/talentpath-backup.dump
```

The dump contains encrypted fields as ciphertext; it is readable only with the same `FIELD_ENCRYPTION_KEY`, so back up the key separately (step 1).

## Free-tier limits (checked November 2026; they change, so check the providers' pages)

- **Render free web service:** spins down after 15 minutes without traffic and takes about a minute to wake; 750 free instance hours per workspace per month; the local disk is wiped on restart and redeploy (TalentPath keeps files in PostgreSQL for this reason). One instance, so the in-memory cache and channel layer are fine.
- **Neon free:** 1 GB of storage and 100 CU-hours of compute per project per month; the compute scales to zero after 5 minutes idle and wakes in under a second. Hitting a monthly limit suspends the compute until the next month; data is kept.
- **Vercel Hobby:** for personal, non-commercial projects.
- **cron-job.org:** free; each request times out after 30 seconds; custom headers and POST are supported.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Vercel build fails: "vercel.json still points at the placeholder" | Step 4. |
| Render deploy fails at start: "Missing required production environment variables: FRONTEND_DOMAIN" | Set it (step 3, then step 6). |
| `403 CSRF` when signing in on the live site | `FRONTEND_DOMAIN` does not match the address in the browser. |
| Live updates do not arrive | The CSP allows `wss://*.onrender.com`; check that `vercel.json` names your Render host and the browser console shows a WebSocket to it. Pages still refresh by polling. |
| Demo data looks garbled or "cannot decrypt" | `first_run_free` ran with different encryption keys than Render. Use the same keys, reset the demo (`seed --reset` with the right keys). |
| `first_run_free`: "Could not create the btree_gist extension" | Run `CREATE EXTENSION IF NOT EXISTS btree_gist;` in Neon's SQL Editor, then run the command again. |
