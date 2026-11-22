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

## Week 2 decisions

- **D-20 Fit-score weights.** Required skills 50, nice-to-have 15, evidence strength 20, experience 15; components that do not apply are dropped and the rest rescaled. All numbers live in `matching/weights.py`; changing one means bumping `SCORER_VERSION`. The weights were not changed after the first tuning run (18/20) and never after seeing the holdout.
- **D-21 Ambiguous skill words count only in a skills section.** Go, R, C, Ruby, Swift, Spark, Excel, Agile and similar are everyday words or names, so prose mentions are ignored. Trade-off: a resume that only mentions Go inside a sentence is not credited for Go.
- **D-22 Experience is unknown rather than guessed.** No parsable date range in an experience section gives `None`, scored at a neutral 0.5 for levels that need experience. Internships are reported separately and do not count as full-time years.
- **D-23 The scorer's input is a two-field object.** Structural tests fail the build if the scoring module imports anything but `dataclasses` and its weights, or mentions a protected field. Renaming its parameter from `candidate` to `facts` came from that test.
- **D-24 Blind screening defaults to on** for every job and reveals at Interview (configurable to Offer). While blind, staff get a stable code (`Candidate #` + first 4 hex of the application id), every identity field is `null`, resume text and evidence snippets are redacted on the server, and the original file is withheld (409 `identity_hidden`). Only hr_admin can reveal early, with a reason of at least 10 characters; every reveal, automatic or manual, is audited. Week 1 applications already at Interview or later were marked revealed by a data migration.
- **D-25 Redaction is pattern based**: the candidate's own name parts, email, phone, address and city; any email, phone (10+ digits), URL; personal labels (age, date of birth, gender…); and institution names (words like University, College, Institute, IIT/NIT/IIIT, plus a list of common Indian institutions). It can over-redact (a city named next to an institution) and could miss an unusual institution name; the scorer never depends on it.
- **D-26 Pipeline rules.** Applied → Screening → Interview → Offer, or Not selected from any of those; no skipping or going back. Not selected needs a reason from a fixed list (internal; never shown to the candidate). Withdrawn is the candidate's own action only. Hired stays reserved for week 3. Hiring managers read the board and add notes and thumbs up or down at Screening and Interview; they do not move cards. Bulk moves (to Screening or Not selected) are all or nothing.
- **D-27 Candidate-facing stage words** are customer safe: Received, Under review, Interview stage, Offer stage, Not progressing, Withdrawn. Rejection messages are short, never mention a score or reason, and suggest up to three open jobs that match skills on the candidate's resume.
- **D-28 Live updates.** Every move pushes a small `board` event to the job's recruiter, hiring manager and all hr_admins over the existing per-user WebSocket group; the board also polls every 20 seconds as a fallback. `daphne` is now in INSTALLED_APPS so `runserver` serves WebSockets locally; Vite proxies `/ws`. In production set `VITE_WS_URL` to the API host.
- **D-29 Ask HIRA is rule-based** (no LLM). Personal answers come only from the signed-in candidate's own records. Chat text is not stored; only a message a candidate chooses to send to a recruiter becomes an application note. Knowledge entries ship as a data migration and are refreshed by `seed`.
- **D-30 hr_admin can create jobs** (follow-up from week 1). A job belongs to whoever creates it; recruiters still see and edit only their own.
- **D-31 Seed favours a fresh reset.** Week 2 resumes add projects, certifications, a fictional college and a pronoun, so blind redaction and evidence strength have something to show. Existing week 1 data is topped up, not rewritten; run `python manage.py seed --reset` to get the richer resumes everywhere.

## Week 3A decisions

- **D-32 Busy time is one table with a database guarantee.** Interviews and 30-minute holds are `TimeClaim` rows per person. Bookings lock the people involved (`SELECT … FOR UPDATE`, id order), release expired holds, check, then insert; a PostgreSQL exclusion constraint (`btree_gist`, `tstzrange … &&`, active rows only) rejects any overlap that slips through. The constraint is added by a migration that runs only on PostgreSQL; SQLite scratch runs rely on the locked check alone.
- **D-33 Offering a slot does not block time; choosing it does.** HIRA offers up to 5 slots that were free when proposed. Choosing one holds it for 30 minutes; confirming books it. If someone else took the time first, the slot is withdrawn and fresh slots are offered when none are left. Offering many candidates the same free time is fine because only one can hold it.
- **D-34 Load balancing is per ISO week (IST).** Ties go to fewer interviews overall, then a stable id order, so results are repeatable in tests and demos.
- **D-35 Email links are signed, single use and expire (72 hours).** The signed value names a `LinkToken` row; a new proposal retires older links. The link page shows the job, round and times only, never the candidate's name.
- **D-36 Rounds pass by simple majority.** A round passes when every assigned interviewer has submitted and yes/strong yes are at least as many as no/strong no. HIRA then starts the next round; a round that leans no is left to the recruiter (no automatic rejection).
- **D-37 Needs you is computed, the log is not.** The activity log is append-only. A Needs you item is a flagged log row whose problem is still open in the data, checked on read, so items clear themselves when fixed without editing the log.
- **D-38 The briefing starts where you last closed it** (first time: the last 7 days) and shows once per browser session (`sessionStorage`). The spoken version uses the same counts-only sentence from the server.
- **D-39 Offer approval order is fixed:** the job's hiring manager, then hr_admin (straight to hr_admin when a job has no hiring manager). Either can request changes with a reason of 10+ characters; editing returns the offer to draft. Sending moves an Interview-stage application to Offer.
- **D-40 Acceptance is an acknowledgement, not an e-signature.** The typed name must match the profile name (case and spacing ignored); the time and an HMAC of the IP address (blind-index key) are stored, never the raw IP.
- **D-41 Offer letters are generated with the standard library** (a small PDF writer, Helvetica, brand colours from `brand.json`, a demo watermark) to avoid a new dependency. Amounts are written as "INR 24,00,000" because the built-in PDF font has no rupee sign; the web UI uses ₹.
- **D-42 Simulated email can carry one text attachment** (`EmailOutbox.attachment*`), used for `.ics` invites; hr_admin sees it in Simulated emails.
- **D-43 Recharts** draws the activity chart (requested in the brief). Every chart has a table view with the same numbers. `npm install` updates `package-lock.json` once; commit it so CI's `npm ci` works.

## Week 3B decisions

- **D-44 One transaction for the hire.** Application, employee record, role change, leave credit, checklist, buddy, first week, withdrawals and the job's openings are written together or not at all. Notifications go out only after the commit. The hire is a click by the job's recruiter or any hr_admin, not automatic on acceptance, so a person checks the joining details first.
- **D-45 The same login becomes an employee.** The candidate account changes role (audited as `users.role_changed`, sessions revoked) instead of a new account, so the person keeps one identity. Their applications stay private to them.
- **D-46 Employee IDs are `LW` + a number from 1001**, the next free number at hire time. Staff who predate week 3B get a record the first time one is needed (for example as a reporting manager).
- **D-47 The reporting line decides approvals, not the role name.** Leave and attendance corrections go to the reporting manager, skipping anyone on leave that day (delegation) and moving up after 48 hours (escalation, configurable). Longer than the HR threshold (5 days by default) also needs hr_admin. Nobody approves their own.
- **D-48 Leave rules are data per location.** `LeaveType` and `WorkPolicy` rows hold every number; hr_admin edits them on HR settings and every change is audited. Defaults live in `hr/defaults.py` and are applied by the seed and tests, never overwriting edits.
- **D-49 Balances are an append-only ledger with unique keys**, so accrual, grants, carry-forward, use and reversal are idempotent and every number can be explained. Monthly credit is `quota × m/12` rounded to half days, so twelve months add up to the quota exactly. Joiners earn from their joining month if they join by the 15th.
- **D-50 Booking ahead of accrual is allowed** within the year (and into next year against the projected balance). The balance never shows a negative number; the leave page shows "booked ahead of accrual" instead. Added after the hire walkthrough showed a new joiner could not book their first leave otherwise.
- **D-51 Sandwich rule** counts weekly offs and holidays only when leave sits on both sides, including leave from another request. A weekend at the very end of a request is not counted.
- **D-52 Clash warnings inform and never block**, for both the employee and the approver. The threshold is a share of the team (people sharing a manager) per location, 50 % by default. Peers see who is off; types and reasons only the team's manager and HR.
- **D-53 Attendance records no location.** Work mode is self-declared (office or remote). Late and early use one general shift per location with grace minutes; corrections go through the same approval line as leave.
- **D-54 The HR assistant never acts on its own.** "Apply leave" returns a confirmation card with the engine's result; only the employee's Confirm calls the normal leave API (same rules, same audit). Answers only read the asker's records; questions about a named colleague's leave are refused.
- **D-55 Holidays are demo data to verify.** The seed loads national, Telangana and Karnataka holidays for 2026 and early 2027 with a note on every row; moon-based dates can move by a day. HR replaces them on HR settings.
- **D-56 Ask HIRA is on every signed-in screen** (it was candidate-only). The main area has extra bottom padding so the floating button never covers a page's last control at 390 px.
- **D-57 No payroll or payments.** Loss of pay is recorded as unpaid leave only; nothing is calculated from it.

