# Start here

Everything below is for **Windows cmd.exe**. Run the commands from the repository root (the `talentpath` folder) unless a step says otherwise.

## 1. Prerequisites

- Python 3.12 or newer (`python --version`)
- Node.js 22 LTS (`node --version`)
- Docker Desktop, running (`docker --version`)
- Git

## 2. Database (PostgreSQL in Docker)

```bat
docker compose up -d db
docker compose ps
```

Wait until the `db` service shows `healthy`.

## 3. Backend

```bat
cd backend
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python ..\scripts\generate_env.py
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py seed
python manage.py runserver
```

- `generate_env.py` creates `backend\.env` with fresh random keys. It never overwrites an existing `.env`. The file is ignored by git.
- `makemigrations --check` should print `No changes detected`. The migrations were written by hand (see DECISIONS.md, D-14). If it reports changes, run `python manage.py makemigrations` once and commit the result.
- The server refuses to start if a required variable is missing. That is intentional.
- Health check: http://localhost:8000/api/ping returns `{"status": "ok"}`.

Run the backend tests (with the database container running):

```bat
cd backend
.venv\Scripts\activate
ruff check .
pytest
```

## 4. Frontend

Open a second terminal:

```bat
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

Open http://localhost:5173. The Vite dev server proxies `/api`, `/sitemap.xml` and `/robots.txt` to the backend on port 8000, so cookies stay first-party.

Frontend checks:

```bat
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

After the first `npm install`, commit the generated `package-lock.json` and switch the CI install step to `npm ci`.

## 5. End-to-end tests (Playwright)

Keep the backend running with the seed loaded. Playwright starts the frontend dev server itself.

```bat
cd frontend
npx playwright install chromium
npm run e2e
```

Tests run twice: desktop (1440 px) and mobile (390 px), with axe checks and a horizontal-overflow check on every page.

## 6. Demo logins

All demo accounts share one password: **`Demo@Pass2026`** (set `DEMO_PASSWORD` before seeding to change it). Everything is fictional; the `.example` domain is reserved and never receives mail.

| Role | Email | Lands on |
| --- | --- | --- |
| Candidate | `candidate@demo.example` | `/candidate` (My applications) |
| Recruiter | `recruiter@demo.example` | `/recruiter` |
| Hiring manager | `manager@demo.example` | `/manager` |
| Employee | `employee@demo.example` | `/employee` |
| HR admin | `admin@demo.example` | `/admin` |

Extra demo staff exist too (for example `kabir.mehta@demo.example`, a recruiter). The 60 synthetic candidates use `@candidates.example` addresses with the same password.

## 7. Things to try

1. Browse http://localhost:5173/jobs, filter by department, location, work mode or skill. Try the skill `JS` or `k8s`.
2. Sign in as the candidate, open a job, apply with any PDF or DOCX under 5 MB. Try a renamed image to see the content check.
3. Sign in as the recruiter: open **My jobs**, then **Applicants**, open an application to read the extracted resume and move it to screening. The candidate gets a bell notification and a simulated email.
4. Sign in as HR admin: invite a staff member, look at **Audit log** and **Simulated emails**.
5. Forgot password: use `candidate@demo.example`, then open the demo inbox link (shown when `VITE_DEMO_MODE=true` and the backend has `DEMO_MODE=true`).

## 8. Useful commands

| Task | Command (in `backend` with the venv active) |
| --- | --- |
| Wipe and re-seed demo data | `python manage.py seed --reset` |
| Create a real HR admin | `set BOOTSTRAP_ADMIN_PASSWORD=...` then `python manage.py bootstrap_admin --email you@company.com --name "Your Name"` |
| Call the cron hooks locally | `curl -X POST -H "X-Internal-Secret: <INTERNAL_TICK_SECRET>" http://localhost:8000/api/internal/tick` |
| Stop the database | `docker compose down` (add `-v` to delete its data) |

## Troubleshooting

- **`Missing required environment variables`**: run `python ..\scripts\generate_env.py` inside `backend`.
- **`connection refused` on port 55432**: Docker Desktop is not running, or the `db` container is stopped (`docker compose up -d db`).
- **`password authentication failed for user "talentpath"`**: you are reaching a different Postgres, usually one installed on Windows. The Docker database listens on **55432** for this reason; check `DATABASE_URL` in `backend\.env` ends in `127.0.0.1:55432/talentpath`. `netstat -ano | findstr :543` shows what is listening.
- **Typing commands into the `npm run dev` window does nothing**: that window is busy running Vite. Use a new terminal for tests.
- **403 `CSRF failed` in the browser**: open the app through http://localhost:5173 (not port 8000), so the CSRF cookie and the API share an origin.
