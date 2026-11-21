# TalentPath

A "hire to onboard" talent platform, built as a portfolio project: a candidate finds a job, applies with a resume, is screened, interviewed and hired, and later works as an employee. Every person, company and job in it is fictional.

> **TalentPath** is a working name. The product name, tagline, colours and the assistant name (HIRA) live only in [`shared/brand.json`](shared/brand.json), so renaming is a one-line change.

## Stack

| Layer | Choice |
| --- | --- |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS, TanStack Query, Zod |
| Backend | Django 5.2, Django REST Framework, SimpleJWT in HttpOnly cookies with CSRF, Channels |
| Data | PostgreSQL (Docker locally, Neon in production) |
| Quality | pytest, Vitest, Playwright, axe, ruff, ESLint |
| Hosting target | Vercel (frontend), Render free tier (backend, Docker), Neon free tier (database), cron-job.org (scheduled calls) |

## Quick start (Windows cmd.exe)

See **[docs/START_HERE.md](docs/START_HERE.md)** for the full walkthrough and demo logins.

```bat
docker compose up -d db
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
python ..\scripts\generate_env.py
python manage.py migrate
python manage.py seed
python manage.py runserver
```

In a second terminal:

```bat
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Repository layout

```
backend/            Django project (apps: core, accounts, org, jobs, files, applications, notifications, seeding)
frontend/           React app (Vite)
shared/policy.json  Single source of truth for permissions (deny by default)
shared/brand.json   Product name, tagline, colours, assistant name
docs/               START_HERE, ARCHITECTURE, DECISIONS, PROGRESS
scripts/            Helper scripts (generate_env.py)
.github/workflows/  CI: backend tests on PostgreSQL, ruff, frontend lint, typecheck, vitest, build
```

## Status

Week 1 of 4 is built. The plan and progress are tracked in [docs/PROGRESS.md](docs/PROGRESS.md).
