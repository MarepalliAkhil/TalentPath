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

## Week 2: explainable matching and screening

| Item | Status |
| --- | --- |
| Explainable skill matching (deterministic, standard library) with reason chips | ⬜ |
| Blind screening mode (hide name, photo, college, age signals) | ⬜ |
| Counterfactual fairness test (swap protected attributes, ranking must not change) | ⬜ |
| Pipeline board (drag and keyboard accessible) | ⬜ |
| Candidate chatbot (rule-based first, LLM optional and off by default) | ⬜ |

## Week 3: HIRA (Hiring Intelligence & Recruiting Assistant), offers, onboarding, leave

| Item | Status |
| --- | --- |
| HIRA: interview scheduling from interviewer availability, reminders (tick), reschedules, login briefing | ⬜ |
| Offers and one-click hire to onboard (unlocks the `hired` status) | ⬜ |
| Leave policy engine, team calendar with clash warnings | ⬜ |
| HR assistant | ⬜ |

## Week 4: growth, analytics, launch

| Item | Status |
| --- | --- |
| Skill-gap career map and internal mobility | ⬜ |
| Hiring analytics | ⬜ |
| "For Phenom, TurboHire, Darwinbox and Keka" page | ⬜ |
| Deployment: Vercel, Render (Docker), Neon, cron-job.org; fill in `frontend/vercel.json` rewrites | ⬜ |
