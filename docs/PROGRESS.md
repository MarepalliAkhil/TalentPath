# Progress

Legend: ✅ built · 🧪 built, waiting for its first local test run · ⬜ planned

> Backend verified on 2026-11-21: migrations apply cleanly, `seed` creates 25 open jobs, 60 candidates and 103 applications, and `pytest` passes 465 of 465. Items stay 🧪 until the frontend checks (`npm run lint`, `typecheck`, `vitest`, `build`, Playwright) also pass.

## Week 1: foundation, accounts, jobs, career site, applications

| # | Item | Status |
| --- | --- | --- |
| 1 | Repo structure, `shared/policy.json`, `shared/brand.json`, CI, `.gitignore`, `.env.example` files, docker-compose, README | ✅ |
| 2 | Candidate registration, staff accounts by hr_admin (invite email), login, logout, password reset via simulated outbox, profile, role redirects, shared sidebar layout, profile menu (Profile, Log out) | 🧪 |
| 3 | Departments, locations, job levels, skills taxonomy (214 skills with synonyms, seeded by migration) | 🧪 |
| 4 | Jobs: create, edit, publish, close, reopen, delete drafts; hiring manager per job; role scoping | 🧪 |
| 5 | Public career site: home, search with filters, job detail with clean slugs, unique titles, meta descriptions, JobPosting JSON-LD, sitemap.xml, robots.txt, real 404 | 🧪 |
| 6 | Applications: PDF/DOCX upload (5 MB, checked by content), server-side text extraction, encrypted text, compressed and encrypted original in PostgreSQL, duplicates blocked, My applications, recruiter list | 🧪 |
| 7 | Notifications: bell, simulated emails for application received and status changes | 🧪 |
| 8 | Seed: 10 departments, 6 locations, 6 levels, 12 staff across all roles, 25 open jobs (+1 draft, +1 closed), 60 synthetic candidates with generated resumes, applications in every status | 🧪 |
| 9 | Docs: START_HERE, ARCHITECTURE, DECISIONS, PROGRESS | ✅ |
| T | Tests: policy matrix for every endpoint × every role + anonymous; auth, rate limits, CSRF, reset; jobs; career site and SEO; resume limits and encryption; isolation; frontend pages, forms, sidebar per role, axe, 390 px; Playwright smoke | 🧪 |

Deployment groundwork already in place: `/api/ping` with zero queries, `POST /api/internal/tick` and `/nightly` behind a secret header, single-use WebSocket tickets, in-memory channel layer without `REDIS_URL`, files compressed in PostgreSQL, settings that refuse to start without required variables, Dockerfile for Render.

## Week 2: explainable matching, blind screening, fairness, pipeline, Ask HIRA

> Built 2026-11-21. In the build sandbox (SQLite, Python 3.10) the backend suite passed 609 tests (2 Postgres-only tests skipped there), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox (Windows-only native binaries), so those items stay 🧪 until they pass on your machine.

| Item | Status |
| --- | --- |
| A. Profile extraction: sections, taxonomy n-gram skills with synonyms, evidence per skill (encrypted snippets), experience years with internships separate and "unknown" never guessed, versioned ParsedProfile, `reparse_profiles` | ✅ |
| B. Fit score 0-100 with bands, documented weights in one module, reason chips, "what would raise this score", stored with version and time, recompute on arrival / job skill change / version change, `rescore` | ✅ |
| B. Recruiter ranked list with band, skill and stage filters and an explanation drawer | 🧪 |
| C. Blind screening per job (default on), candidate codes, server-side redacted resume, original file withheld, automatic reveal at Interview or Offer, early reveal by hr_admin with reason, audited | ✅ |
| D. Counterfactual fairness tests and structural test in CI; hr_admin Fairness check page | ✅ backend · 🧪 page |
| E. Pipeline board: dnd-kit drag plus keyboard "Move to", server-enforced transitions, reasons for rejection, candidate-only withdraw, hiring-manager notes and thumbs at Screening/Interview, bulk moves with confirmation, audit, live updates, kind rejection messages with matching jobs | ✅ backend · 🧪 UI |
| F. Ask HIRA: rule-based engine (Hinglish, spell-correct, intents, BM25), own-data-only answers, logged-out limits, message to recruiter, accessible widget with mobile bottom sheet | ✅ backend · 🧪 UI |
| G. Evaluation: matching 18/20 tune, 16/20 holdout; Ask HIRA 44/44 tune, 35/44 holdout (see MATCHING.md and ASK_HIRA.md) | ✅ measured |
| H. Seed: every open job 5-15 applications across all stages, varied fit, blind and revealed jobs, rejection reasons, hiring-manager notes, knowledge entries | ✅ |
| I. Week 1 follow-ups: CI uses `npm ci`; hr_admin can create jobs (policy + tests) | ✅ (commit the updated package-lock.json first) |

## Week 3A: HIRA the recruiting coordinator, interviews, scorecards, offers

> Built 2026-11-22. In the build sandbox (SQLite, Python 3.10) the backend suite passed (the PostgreSQL-only exclusion-constraint and thread-concurrency tests are skipped there and run on your machine), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox, and `recharts` could not be installed there, so frontend items stay 🧪 until they pass on your machine.

| Item | Status |
| --- | --- |
| A. Interview plans per job (ordered rounds, duration, mode, pool, 1 or a panel), default plan, plan editor; interviewer skills, weekly working hours and blocked time (IST) | ✅ backend · 🧪 UI |
| B. HIRA scheduling: 3-5 slots, panel common time, 24 hours ahead, working hours, weekly load balancing; 30-minute holds; exclusion constraint + locked transactions; signed single-use email links; `.ics` invites and simulated links; 24 h / 1 h reminders via tick; reschedules (2, until 12 h before); decline with replacement; no-show; manual scheduling when HIRA is off; append-only activity log mirrored to the audit log | ✅ backend · 🧪 UI |
| C. Login briefing once per session (counts from the log, Needs you list, optional spoken version), HIRA activity page (KPIs, Recharts chart with table view, filters), HIRA image slots with initials fallback | ✅ backend · 🧪 UI |
| D. Scorecards from the job (skills + communication + problem solving), comments required for 1/2/5, independent until you submit, due 24 h after, chased, Needs you after 48 h, per-round summary in the candidate drawer | ✅ backend · 🧪 UI |
| E. Offers: draft, hiring manager then hr_admin approval (with reject reasons), branded demo PDF letter, send, accept by typed name (not an e-signature), decline, expiry, revoke; encrypted details; `offer_accepted` event for week 3B | ✅ backend · 🧪 UI |
| F. Seed: plans for every job, 15 interviewers with skills and hours, past and future interviews, submitted and overdue scorecards, offers in every state, 14 days of HIRA history | ✅ |
| Tests: slot rules, holds, constraint and concurrency (PostgreSQL), links, reminders, reschedules, declines, no-shows, scorecards, offers, briefing, allowed and denied for every new endpoint; Vitest and Playwright specs for the new screens | ✅ backend · 🧪 frontend |

## Week 3B: one-click hire to onboard, leave, attendance, team calendar, HR assistant

> Built 2026-11-22. In the build sandbox (SQLite, Python 3.10) the backend suite passed (run in batches; the two PostgreSQL-only tests are skipped there), ruff, TypeScript and ESLint were clean. Vitest, the Vite build and Playwright could not run in the sandbox, so frontend items stay 🧪 until they pass on your machine. See `docs/HR.md`.

| Item | Status |
| --- | --- |
| A. One-click hire from an accepted offer in one transaction: Hired, employee record and ID, same login becomes employee (audited, sessions revoked), prorated leave, department checklist with owners and due dates, buddy rules, first-week plan, other applications withdrawn, openings down and job closed when filled; Welcome page; onboarding progress for manager, buddy and HR | ✅ backend · 🧪 UI |
| B. Leave policy engine as data per location (5 types, quota, monthly or yearly credit, proration, carry-forward cap, notice, backdating, max days, half days, documents, sandwich rule), holiday calendars, preview with day count, cancellation; manager then HR above a threshold; delegation; escalation after 48 hours with a Needs attention list; idempotent accrual and carry-forward | ✅ backend · 🧪 UI |
| C. Team calendar (team level, reasons only for the manager and HR) and clash warnings while applying and approving (inform, never block) | ✅ backend · 🧪 UI |
| D. Attendance: web check-in/out with office or remote, shift with late/early flags, missing check-out detection, regularisation approved by the reporting manager, monthly summaries for employee, manager and HR; no location tracking | ✅ backend · 🧪 UI |
| E. HR assistant in Ask HIRA: balance, apply leave with a confirmation card (never submits by itself), holidays, buddy/manager, onboarding, attendance, pending for me, policy answers with a source link; own data only | ✅ backend · 🧪 UI |
| E. Evaluation: 64 questions (typos, Hinglish), tuning 32/32, holdout 27/32 (84 %) | ✅ measured |
| F. Seed: 30 employees with managers and buddies, two locations with holiday calendars (demo data to verify), leave in every state incl. delegated and escalated, 30 days of attendance, three people mid-onboarding, one accepted offer ready to hire | ✅ |
| Tests: hire atomicity and rules, every leave rule, approvals, delegation, escalation, privacy, clash thresholds, attendance, assistant intents and confirmation card, HR settings, allowed and denied for every new endpoint; Vitest and Playwright specs for the new screens | ✅ backend · 🧪 frontend |

## Week 4: growth, analytics, launch

| Item | Status |
| --- | --- |
| Skill-gap career map and internal mobility | ⬜ |
| Hiring analytics | ⬜ |
| "For Phenom, TurboHire, Darwinbox and Keka" page | ⬜ |
| Deployment: Vercel, Render (Docker), Neon, cron-job.org; fill in `frontend/vercel.json` rewrites | ⬜ |
