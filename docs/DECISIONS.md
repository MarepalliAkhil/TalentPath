# Decisions

Short records of choices made while building. "Locked" items came from the project brief; the rest were decided during week 1 and can be revisited.

## Locked by the brief

- **L-1** Stack: React 18, Vite, TypeScript, Tailwind, TanStack Query, Zod; Django 5.2, DRF, SimpleJWT in HttpOnly cookies with CSRF, Channels; PostgreSQL; pytest, Vitest, Playwright, axe, ruff, ESLint.
- **L-2** Five roles with strict isolation; `shared/policy.json` is the single source of truth; deny by default; allowed and denied tests for every endpoint.
- **L-3** Argon2, UUID ids, audit log, AES-GCM field encryption with a blind index, rate limits on login and uploads, no secrets in the repo or frontend.
- **L-4** AI is deterministic and explainable first; any LLM layer is optional and off by default; gender, age, religion, caste, photo and college are never used for ranking.
- **L-5** Vercel + Render free + Neon free + cron-job.org, designed in from day one.

## Week 1 decisions

- **D-01 Brand config is shared JSON.** `shared/brand.json` holds the name, tagline, employer name, colours and the assistant (HIRA · Hiring Intelligence & Recruiting Assistant). Backend (emails, SEO) and frontend (Tailwind, HTML title) both read it. On Vercel, keep "Include files outside the root directory" enabled (the default) so the frontend build can read `../shared`.
- **D-02 UUID primary keys** on every model instead of a separate public id. URLs never expose counters.
- **D-03 Recruiters see and manage only the jobs they created.** Hiring managers see the published jobs assigned to them (read only). HR admins see every job and can edit or change status, but job creation stays with recruiters.
- **D-04 Out-of-scope objects return 404, not 403.** 403 means "your role may never do this" (policy); 404 means "not yours or does not exist".
- **D-05 Job status rules.** draft → open → closed → open (reopen). Publishing needs a hiring manager and at least one required skill. Closed jobs must be reopened before editing. Only drafts without applications can be deleted.
- **D-06 Application status in week 1.** Recruiters move applied → screening → interview → offer, or to "not selected" from any of those. `hired` exists in the model but is reserved for week 3's one-click hire. Candidates can withdraw until a final state.
- **D-07 Email stays plain text.** It is the login identifier and is needed for case-insensitive lookup. Phone, address, resume text and the resume file are encrypted. The phone has a blind index for future duplicate-candidate checks.
- **D-08 One application per job and candidate, ever.** A database constraint blocks duplicates, including after a withdrawal, to keep history simple. Revisit if re-applying becomes a requirement.
- **D-09 Resume types are detected from bytes.** Extensions and browser content types are ignored. Empty extraction (a scanned PDF) is accepted and shown as "no readable text"; OCR is out of scope.
- **D-10 Files in PostgreSQL (free mode).** Render's free disk is wiped on restart, so originals are stored compressed and encrypted in the database behind `files.storage.save_file/read_file`. An object-storage backend can replace it later without touching callers.
- **D-11 Rate limits use the local-memory cache.** Fine for one Render instance. Behind several instances, point `CACHES` at Redis. Set `NUM_PROXIES` on Render so client IPs come from `X-Forwarded-For`; the default 0 uses the direct peer and cannot be spoofed.
- **D-12 Skills taxonomy ships as a data migration** (214 skills, 131 tech and 83 non-tech, with synonyms), so every environment, tests included, has the same reference data without running the demo seed.
- **D-13 Simulated email.** Emails are rows in `EmailOutbox`, marked sent at once. HR admins read them in "Simulated emails". With `DEMO_MODE=true`, anyone can read mail for reserved `*.example` addresses through the demo inbox, so password reset can be tried on the public demo. Keep `DEMO_MODE` off for any real data.
- **D-14 Hand-written migrations.** The week 1 build environment had no Django install, so migrations were written by hand to match the models. CI runs `makemigrations --check`; if it reports drift, run `makemigrations` once and commit.
- **D-15 Demo password.** All demo accounts share `Demo@Pass2026` (override with `DEMO_PASSWORD`). It is documented on purpose because the demo is public; it protects nothing real. Real admins are created with `bootstrap_admin`, which reads the password from the environment.
- **D-16 ASGI server is daphne** (Channels' reference server). Local development uses `runserver` (WSGI) because week 1 has no live sockets in the UI.
- **D-17 Vercel rewrites hold a placeholder host** (`frontend/vercel.json`). The real Render URL is filled in during week 4's deployment.
- **D-18 No lockfile yet.** `package-lock.json` is created by the first `npm install`; commit it and switch CI to `npm ci`.
- **D-19 UI direction.** Light "glass over a soft colour field" look, deep ink sidebar, teal primary and burnt-orange accent; all colour pairs used for text pass WCAG AA (checked when choosing the palette). No web fonts are loaded, to stay fast and private.
