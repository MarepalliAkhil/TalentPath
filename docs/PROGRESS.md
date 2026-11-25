# Progress

Legend: ✅ DONE (built and tested) · 🟡 PARTIAL · ⬜ NOT STARTED

> **Evidence, 2026-11-23 (your machine, PostgreSQL, after Week 4A):** backend `pytest` 1,374 passed and 1 error (a transactional test flushed migration data; fixed with `serialized_rollback=True`, D-69); Vitest 88 passed; Playwright 86 tests, 65 passed and the rest skipped on purpose (desktop-only or changing shared data); `npm run lint`, `typecheck` and `build` clean. Every item below that waited for that run (🧪) is now ✅.
> **Week 4B (2026-11-24, your machine):** `pytest` 1,393 passed; ruff, ESLint, TypeScript and Prettier clean; Vitest 94 passed; `npm run build` passes (warns only about the vercel.json placeholder and a 992 kB bundle); `pip-audit` clean; Playwright 72 passed, 28 skipped on purpose (desktop-only or already-changed demo data), 0 failed.
> **Week 4B (2026-11-24, build sandbox, SQLite):** backend suite passed in batches (PostgreSQL-only tests and `check --deploy` skipped there: no psycopg); ruff, TypeScript and ESLint clean. Not run in the sandbox: Prettier (npm registry blocked), Vitest, the Vite build and Playwright (Windows-only native binaries). Run them with the commands in `docs/DEPLOY.md` and the README.

> Backend verified on 2026-11-21: migrations apply cleanly, `seed` creates 25 open jobs, 60 candidates and 103 applications, and `pytest` passes 465 of 465. Items stay 🧪 until the frontend checks (`npm run lint`, `typecheck`, `vitest`, `build`, Playwright) also pass.

## Week 1: foundation, accounts, jobs, career site, applications

| # | Item | Status |
| --- | --- | --- |
| 1 | Repo structure, `shared/policy.json`, `shared/brand.json`, CI, `.gitignore`, `.env.example` files, docker-compose, README | ✅ |
| 2 | Candidate registration, staff accounts by hr_admin (invite email), login, logout, password reset via simulated outbox, profile, role redirects, shared sidebar layout, profile menu (Profile, Log out) | ✅ |
| 3 | Departments, locations, job levels, skills taxonomy (214 skills with synonyms, seeded by migration) | ✅ |
| 4 | Jobs: create, edit, publish, close, reopen, delete drafts; hiring manager per job; role scoping | ✅ |
| 5 | Public career site: home, search with filters, job detail with clean slugs, unique titles, meta descriptions, JobPosting JSON-LD, sitemap.xml, robots.txt, real 404 | ✅ |
| 6 | Applications: PDF/DOCX upload (5 MB, checked by content), server-side text extraction, encrypted text, compressed and encrypted original in PostgreSQL, duplicates blocked, My applications, recruiter list | ✅ |
| 7 | Notifications: bell, simulated emails for application received and status changes | ✅ |
| 8 | Seed: 10 departments, 6 locations, 6 levels, 12 staff across all roles, 25 open jobs (+1 draft, +1 closed), 60 synthetic candidates with generated resumes, applications in every status | ✅ |
| 9 | Docs: START_HERE, ARCHITECTURE, DECISIONS, PROGRESS | ✅ |
| T | Tests: policy matrix for every endpoint × every role + anonymous; auth, rate limits, CSRF, reset; jobs; career site and SEO; resume limits and encryption; isolation; frontend pages, forms, sidebar per role, axe, 390 px; Playwright smoke | ✅ |

Deployment groundwork already in place: `/api/ping` with zero queries, `POST /api/internal/tick` and `/nightly` behind a secret header, single-use WebSocket tickets, in-memory channel layer without `REDIS_URL`, files compressed in PostgreSQL, settings that refuse to start without required variables, Dockerfile for Render.

## Week 2: explainable matching, blind screening, fairness, pipeline, Ask HIRA

> Built 2026-11-21. In the build sandbox (SQLite, Python 3.10) the backend suite passed 609 tests (2 Postgres-only tests skipped there), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox (Windows-only native binaries), so those items stay 🧪 until they pass on your machine.

| Item | Status |
| --- | --- |
| A. Profile extraction: sections, taxonomy n-gram skills with synonyms, evidence per skill (encrypted snippets), experience years with internships separate and "unknown" never guessed, versioned ParsedProfile, `reparse_profiles` | ✅ |
| B. Fit score 0-100 with bands, documented weights in one module, reason chips, "what would raise this score", stored with version and time, recompute on arrival / job skill change / version change, `rescore` | ✅ |
| B. Recruiter ranked list with band, skill and stage filters and an explanation drawer | ✅ |
| C. Blind screening per job (default on), candidate codes, server-side redacted resume, original file withheld, automatic reveal at Interview or Offer, early reveal by hr_admin with reason, audited | ✅ |
| D. Counterfactual fairness tests and structural test in CI; hr_admin Fairness check page | ✅ |
| E. Pipeline board: dnd-kit drag plus keyboard "Move to", server-enforced transitions, reasons for rejection, candidate-only withdraw, hiring-manager notes and thumbs at Screening/Interview, bulk moves with confirmation, audit, live updates, kind rejection messages with matching jobs | ✅ |
| F. Ask HIRA: rule-based engine (Hinglish, spell-correct, intents, BM25), own-data-only answers, logged-out limits, message to recruiter, accessible widget with mobile bottom sheet | ✅ |
| G. Evaluation: matching 18/20 tune, 16/20 holdout; Ask HIRA 44/44 tune, 35/44 holdout (see MATCHING.md and ASK_HIRA.md) | ✅ measured |
| H. Seed: every open job 5-15 applications across all stages, varied fit, blind and revealed jobs, rejection reasons, hiring-manager notes, knowledge entries | ✅ |
| I. Week 1 follow-ups: CI uses `npm ci`; hr_admin can create jobs (policy + tests) | ✅ (commit the updated package-lock.json first) |

## Week 3A: HIRA the recruiting coordinator, interviews, scorecards, offers

> Built 2026-11-22. In the build sandbox (SQLite, Python 3.10) the backend suite passed (the PostgreSQL-only exclusion-constraint and thread-concurrency tests are skipped there and run on your machine), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox, and `recharts` could not be installed there, so frontend items stay 🧪 until they pass on your machine.

| Item | Status |
| --- | --- |
| A. Interview plans per job (ordered rounds, duration, mode, pool, 1 or a panel), default plan, plan editor; interviewer skills, weekly working hours and blocked time (IST) | ✅ |
| B. HIRA scheduling: 3-5 slots, panel common time, 24 hours ahead, working hours, weekly load balancing; 30-minute holds; exclusion constraint + locked transactions; signed single-use email links; `.ics` invites and simulated links; 24 h / 1 h reminders via tick; reschedules (2, until 12 h before); decline with replacement; no-show; manual scheduling when HIRA is off; append-only activity log mirrored to the audit log | ✅ |
| C. Login briefing once per session (counts from the log, Needs you list, optional spoken version), HIRA activity page (KPIs, Recharts chart with table view, filters), HIRA image slots with initials fallback | ✅ |
| D. Scorecards from the job (skills + communication + problem solving), comments required for 1/2/5, independent until you submit, due 24 h after, chased, Needs you after 48 h, per-round summary in the candidate drawer | ✅ |
| E. Offers: draft, hiring manager then hr_admin approval (with reject reasons), branded demo PDF letter, send, accept by typed name (not an e-signature), decline, expiry, revoke; encrypted details; `offer_accepted` event for week 3B | ✅ |
| F. Seed: plans for every job, 15 interviewers with skills and hours, past and future interviews, submitted and overdue scorecards, offers in every state, 14 days of HIRA history | ✅ |
| Tests: slot rules, holds, constraint and concurrency (PostgreSQL), links, reminders, reschedules, declines, no-shows, scorecards, offers, briefing, allowed and denied for every new endpoint; Vitest and Playwright specs for the new screens | ✅ |

## Week 3B: one-click hire to onboard, leave, attendance, team calendar, HR assistant

> Built 2026-11-22. In the build sandbox (SQLite, Python 3.10) the backend suite passed (run in batches; the two PostgreSQL-only tests are skipped there), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox, so frontend items stay 🧪 until they pass on your machine. See `docs/HR.md`.

| Item | Status |
| --- | --- |
| A. One-click hire from an accepted offer in one transaction: Hired, employee record and ID, same login becomes employee (audited, sessions revoked), prorated leave, department checklist with owners and due dates, buddy rules, first-week plan, other applications withdrawn, openings down and job closed when filled; Welcome page; onboarding progress for manager, buddy and HR | ✅ |
| B. Leave policy engine as data per location (5 types, quota, monthly or yearly credit, proration, carry-forward cap, notice, backdating, max days, half days, documents, sandwich rule), holiday calendars, preview with day count, cancellation; manager then HR above a threshold; delegation; escalation after 48 hours with a Needs attention list; idempotent accrual and carry-forward | ✅ |
| C. Team calendar (team level, reasons only for the manager and HR) and clash warnings while applying and approving (inform, never block) | ✅ |
| D. Attendance: web check-in/out with office or remote, shift with late/early flags, missing check-out detection, regularisation approved by the reporting manager, monthly summaries for employee, manager and HR; no location tracking | ✅ |
| E. HR assistant in Ask HIRA: balance, apply leave with a confirmation card (never submits by itself), holidays, buddy/manager, onboarding, attendance, pending for me, policy answers with a source link; own data only | ✅ |
| E. Evaluation: 64 questions (typos, Hinglish), tuning 32/32, holdout 27/32 (84 %) | ✅ measured |
| F. Seed: 30 employees with managers and buddies, two locations with holiday calendars (demo data to verify), leave in every state incl. delegated and escalated, 30 days of attendance, three people mid-onboarding, one accepted offer ready to hire | ✅ |
| Tests: hire atomicity and rules, every leave rule, approvals, delegation, escalation, privacy, clash thresholds, attendance, assistant intents and confirmation card, HR settings, allowed and denied for every new endpoint; Vitest and Playwright specs for the new screens | ✅ |

## Week 4A: skill-gap career map, internal mobility, analytics, For recruiters page, demo mode

> Built 2026-11-23. In the build sandbox (SQLite, Python 3.10) the backend suite passed in batches (the two PostgreSQL-only tests are skipped there), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox, so frontend items stay 🧪 until they pass on your machine. See `docs/ANALYTICS.md`.

| Item | Status |
| --- | --- |
| A. Skill graph as data (`shared/skill_graph.json`: 126 skills with prerequisites, related skills and an effort label); "Jobs you're closest to" from the same week 2 scorer; per-job map (have with evidence, required missing, nice-to-have missing) and a learning path that respects prerequisites; links only from `shared/learning_links.json` (61 official documentation homepages), text only otherwise; "Your next role" for employees; profile resume upload (parsed, encrypted, replaceable, deletable) | ✅ |
| B. Internal mobility: jobs marked internal, external or both; internal jobs with the employee's match and one-click apply from the profile resume; the manager is told at Interview (configurable per location: Interview or Offer, never at application) and the rule is shown before applying; same pipeline, blind screening, HIRA and scorecards; internal hire updates department, designation, level and manager on the same record (audited, no new account) | ✅ |
| C. Analytics: time to hire and time in stage (median, 80th percentile), funnel conversion, source effectiveness (new application source field, seeded), offers and decline reasons, interviewer load and scorecard timeliness, HIRA automation, match band versus outcome (labelled synthetic); people: leave utilisation, absenteeism and late trends, onboarding completion, mobility; summary + table + chart, date and department filters, CSV export; role scoping | ✅ |
| D. Public `/for-recruiters` page: intro, Try it in 60 seconds, one plain-text section per company (no logos, no brand colours), How it is built with numbers read from the repository at build time, Honest limits, About me; linked in the career site header and footer | ✅ |
| E. Demo mode (off by default): Try-as buttons, "Demo data, resets nightly" banner, demo accounts cannot change password or email, invite or edit staff, move or delete in bulk; upload limits; nightly reset of demo data only, audited | ✅ |
| Tests: learning path and curated links, same score as the recruiter view, profile resume limits and deletion, internal visibility, manager notice at Interview, internal hire without a new account, analytics on known fixtures (medians, percentiles, conversion, offers, timeliness, HIRA, utilisation, absenteeism, late), scoping, CSV, demo mode; allowed and denied for every new endpoint; Vitest and Playwright specs | ✅ |

## Week 4B: free deployment, final audit, interview material

| Item | Status | Evidence |
| --- | --- | --- |
| `render.yaml`: free plan, Singapore, Dockerfile, migrate then one Daphne on `$PORT`, health check `/api/ping` | ✅ | `render.yaml`, `backend/Dockerfile` |
| Production settings: DEBUG refused, hosts and origins from `RENDER_EXTERNAL_HOSTNAME` + `FRONTEND_DOMAIN`, Secure HttpOnly Lax cookies, proxy SSL header, HSTS, `sslmode=require`, `CONN_MAX_AGE=0`, refuses to start without required variables | ✅ | `tests/test_ops.py` (subprocess with production env); `check --deploy` test runs where psycopg is installed |
| Health check with zero queries, also for the unknown `Host` Render's checker may send | ✅ | `core/middleware.py`, `test_health_check_works_whatever_host_the_platform_sends` |
| Tick and nightly behind `X-Tick-Secret` (constant-time); tick cheap when nothing is due; nightly answers at once and resets the demo in the background, never twice at once | ✅ | `test_ops.py`, `test_demo_mode.py` |
| Correctness without cron: holds, finished interviews, accrual, delegation, escalation and missing check-outs are caught up on read | ✅ | `tests/test_lazy_jobs.py`; list in `docs/DEPLOY.md` |
| `first_run_free`: btree_gist with a clear error, migrate, seed only an empty database, never reset real data | ✅ | `tests/test_first_run_free.py` |
| `vercel.json`: Render URL in one place, build fails on the placeholder on Vercel, SPA fallback with real 404, CSP allowing the Render WebSocket, security headers, immutable hashed assets | ✅ | `frontend/src/test/deploy.test.tsx` (run on your machine) |
| Wake-up notice with retries on 502/503 (and 504 for reads) | ✅ | `deploy.test.tsx` |
| `docs/DEPLOY.md`: every variable, secret commands, Neon, Render, Vercel, cron-job.org, updating, `pg_dump`, free-tier limits | ✅ | |
| Security sweep: no secrets tracked, `.env` and test output ignored, source maps off, every endpoint in the policy matrix | ✅ | `git ls-files` grep; `.gitignore`; `vite.config.ts`; `test_every_route_is_a_policy_view_with_known_actions` |
| Dependency audits (`pip-audit`, `npm audit`) | 🟡 | 2026-11-24 on your machine: `pip-audit` no known vulnerabilities. `npm audit` 6 (3 moderate, 1 high, 2 critical), every fix a major upgrade, so not forced (D-79): vitest/tinypool are dev-only and never shipped; react-router's open redirect is closed in our code (`src/lib/redirect.ts`); its SSR issue does not apply (no SSR); zod's issue needs oversized input to client-side forms. Planned: one upgrade task for vitest 5, react-router 7 and zod 4, about 1 day. |
| Prettier in CI | ✅ | 2026-11-24: `npm run format` then `format:check` clean on your machine |
| All-routes Playwright test: every route for every role, fails on console errors, failed requests, missing alt text, duplicate titles; public titles and descriptions unique, JobPosting JSON-LD, sitemap and robots | ✅ | `frontend/e2e/routes.spec.ts`; 2026-11-24 on your machine: Playwright 72 passed, 28 skipped on purpose, 0 failed |
| robots.txt disallows every signed-in area, read from `shared/policy.json` | ✅ | `test_robots_txt` |
| README for recruiters, `docs/career/` (resume bullets, 30 interview Q&A, demo script, LinkedIn post) | ✅ | |

## Prompt 1: six roles, profiles, resume-first registration, application form, companies, email

| Item | Status | Evidence |
| --- | --- | --- |
| Six roles; data migration hr_admin → hr (admin@demo.example → admin), hiring_manager → manager, reversible, no rows lost | ✅ | `accounts/migrations/0002_six_roles.py`, `tests/test_roles_admin.py` |
| Admin: user CRUD without hard delete, deactivate, assign staff roles, assign managers, companies, departments, locations; cannot see candidates' documents | ✅ | `test_roles_admin.py`, policy matrix (allowed and denied for every endpoint) |
| Profile for all six roles: details, password, photo, notification preferences; locked fields changed only by admin with an audited reason; candidate resume history | ✅ | `tests/test_profiles.py`, `frontend/src/test/prompt1.test.tsx` |
| Registration needs a resume (PDF/DOCX, same checks) and pre-fills the profile | ✅ | `test_auth.py`, `test_profiles.py` |
| Multi-step application form with progress, drafts, screening questions, Terms and Privacy pages; scorer never sees CTC, DOB, college or personal fields | ✅ | `tests/test_application_form.py`, `tests/test_fairness.py` |
| Five fictional companies, 25 seeded jobs with full job pages, footer note | ✅ | `tests/test_companies.py`, `test_seed.py` |
| Demo banner and login demo buttons removed; Try-as only on For recruiters | ✅ | `test_demo_mode.py`, `week4a.test.tsx` |
| Email: console, Gmail SMTP, Brevo/Resend API; templates; outbox and bell; limits, retries, allowlist, send log | ✅ | `tests/test_email.py` (SMTP and API mocked) |
| Backend suite on SQLite in the work sandbox | ✅ | 2026-11-25: 1726 passed, 3 skipped, 0 failed (2 PostgreSQL-only tests not run there) |
| Vitest, Playwright and Prettier check on your machine | ⏳ | Run the commands in the Prompt 1 report |
| A real Gmail or Brevo send | ⏳ | Needs your App Password or API key (`docs/EMAIL.md`) |

### Not started (estimates, not begun on purpose)

| Item | Estimate |
| --- | --- |
| UI polish pass (separate task) | 2-3 days |
| Major dependency upgrades: vitest 5, react-router 7, zod 4 (clears the remaining `npm audit` findings) | 1 day |
| Real email delivery (SMTP or a provider) instead of the simulated outbox | 0.5-1 day |
| Several Render instances: Redis channel layer and cache, a real job queue instead of cron | 1-2 days |
| Object storage for files once PostgreSQL storage outgrows Neon's 1 GB | 1 day |
| SSO (Google Workspace / Microsoft) for staff | 1-2 days |
| Error monitoring (Sentry free tier) and uptime alerts | 0.5 day |
