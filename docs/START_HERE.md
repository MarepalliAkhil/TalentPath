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

Open http://localhost:5173. The Vite dev server proxies `/api`, `/sitemap.xml`, `/robots.txt` and the live-update socket `/ws` to the backend on port 8000, so cookies stay first-party.

When `package.json` gains a dependency (week 2 added `@dnd-kit/core` for the pipeline board, week 3A added `recharts` for the HIRA activity chart), run `npm install` once and commit the updated `package-lock.json`. After that, `npm ci` installs exactly what the lockfile pins (CI uses `npm ci`).

Frontend checks:

```bat
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

CI runs `npm ci`, so `package-lock.json` must be committed and in sync with `package.json`.

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

Extra demo staff exist too (for example `kabir.mehta@demo.example`, a recruiter, and the week 3B employees such as `rahul.verma@demo.example`). The 60 synthetic candidates use `@candidates.example` addresses with the same password. Week 3B adds `joiner@demo.example` (Ishaan Malhotra), a candidate with an accepted offer, ready for the one-click hire.

After week 2's seed every open job has 5 to 15 applications across all stages. Most jobs screen blind (identity revealed at Interview); every fifth job does not, and a few reveal only at Offer. For the richest demo (resumes with projects and a fictional college), run `python manage.py seed --reset` once.

## 7. Things to try

1. Browse http://localhost:5173/jobs, filter by department, location, work mode or skill. Try the skill `JS` or `k8s`.
2. Sign in as the candidate, open a job, apply with any PDF or DOCX under 5 MB. Try a renamed image to see the content check.
3. Sign in as the recruiter: open **My jobs**, then **Candidates**, open an application to read the extracted resume and move it to screening. The candidate gets a bell notification and a simulated email.
4. Sign in as HR admin: invite a staff member, look at **Audit log** and **Simulated emails**.
5. Forgot password: use `candidate@demo.example`, then open the demo inbox link (shown when `VITE_DEMO_MODE=true` and the backend has `DEMO_MODE=true`).

### Week 2 walkthrough

1. **Ranked list with explanations.** Sign in as `recruiter@demo.example` → **My jobs** → **Candidates** on "Senior Backend Engineer (Python)". Candidates are ranked by fit score with reason chips. Filter by band (Strong, Good…), skill (try `JS` or `Postgres`) or stage. Choose **Explain** to open the drawer: score breakdown, "What would raise this score", skill evidence, the resume and notes.
2. **Blind candidate.** Rows showing a lock and `Candidate #7F3A`-style codes are blind: the drawer says so, the resume shows `[hidden]` for name, contacts, address and college, and there is no download link.
3. **Move to Interview to reveal.** Choose **Board**. Drag a card by its handle, or use **Move to** on the card (keyboard friendly). Move a blind candidate from Screening to Interview: the card now shows the real name, and the reveal is in **Audit log** (as hr_admin). Choosing **Not selected** asks for a reason; the candidate gets a short, kind message with matching open jobs, never the reason or score. Tick several Applied cards for bulk actions. Open the same board in a second browser window to see live updates.
4. **Hiring-manager note.** Sign in as `manager@demo.example` → **Board** on an assigned job → **Details and notes** on a Screening card → write a note and choose **Thumbs up**. Managers cannot move cards.
5. **Candidate asks Ask HIRA.** Sign in as `candidate@demo.example`, open **Ask HIRA** (bottom right) and choose "What is my application status?". Try "jobs that match my skills", "hyd mein python naukri", "is the screening fair" and "Talk to a recruiter" (the recruiter sees the message as a note). Logged out, Ask HIRA on the career site does job search and FAQs only.
6. **Fairness check.** Sign in as `admin@demo.example` → **Fairness check** → **Run the check**: "120 variants tested, 0 score changes." See `docs/MATCHING.md` for what this does and does not prove.

### Week 3A walkthrough (HIRA, interviews, scorecards, offers)

Run `python manage.py seed --reset` first. The demo candidate is **Sneha Iyer** (`candidate@demo.example`). Times are shown in IST.

1. **HIRA briefing.** Sign in as `recruiter@demo.example`. HIRA's popup says what it did while you were away (counts from its activity log) and lists what needs you. Choose **Play** to hear it (counts only, never names) or **Mute voice**. Close it: it shows once per browser session. Open **HIRA activity** for KPI tiles, actions by day (switch **Chart / Table**), the Needs you list and the filterable log.
2. **Move a candidate to Interview.** **My jobs** → **Board** on "Java Backend Engineer". Sneha Iyer's card is in Applied (HR revealed her early in the demo seed, so you can find her). Use **Move to** → Screening, then **Move to** → Interview. HIRA offers 3 to 5 slots straight away (open her card: the **Interviews** section says how many). The job's **Interview plan** tab shows the rounds, pools and the **Let HIRA schedule** switch.
3. **Candidate picks a slot.** Sign in as `candidate@demo.example`. Under **Your interviews**, choose a time: it is held for 30 minutes ("Held for you until …"). Choose **Confirm this time**. You get a bell notification and a simulated email with an `.ics` invite (**Add to calendar**). The meeting link is marked simulated. You can **Reschedule** twice, until 12 hours before. The same email has a single-use link (`/schedule/…`, see **Simulated emails** as admin) that works without signing in.
4. **Interviewer submits a scorecard.** Sign in as `employee@demo.example` → **My interviews** → **Needs your feedback** → **Fill in scorecard**. Rate each area 1 to 5 (1, 2 and 5 need a comment), choose a recommendation and submit. Only now can you read the other interviewers' scorecards. **My availability** sets working hours and blocked time.
5. **Draft and approve an offer.** As the recruiter: **My jobs** → **Candidates** on "Senior Backend Engineer (Python)" → **Explain** on Sneha Iyer (Interview stage). The **Interviews** section shows every round passed with averages and recommendations. Choose **Draft offer**, fill in the pay (₹ per year) and dates, **Save draft**, then **Send for approval**. Sign in as `manager@demo.example` → **Offers** → **Awaiting my approval** → **Approve**. Sign in as `admin@demo.example` → **Offers** → **Approve**. Back as the recruiter → **Offers** → **All offers** → open it → **Send to candidate** (a branded demo PDF letter is generated).
6. **Candidate accepts.** As `candidate@demo.example` → **Your offers** → **View and respond** → open the letter, type `Sneha Iyer` and choose **Accept offer**. This records an acknowledgement (time and a hash of the IP), not a legal e-signature. The application stays at Offer until someone chooses **Hire** (week 3B below).
7. **Cron work.** Reminders, expired holds, overdue scorecards and offer expiry run on the tick (see the command below). Run it a few times; it never sends the same reminder twice.

See `docs/HIRA.md` for every rule and number.

### Week 3B walkthrough (hire to onboard, leave, attendance, HR assistant)

Run `python manage.py seed --reset` first (it takes a little longer now). Times and dates are IST.

1. **Hire the accepted candidate.** Sign in as `admin@demo.example` (or `kabir.mehta@demo.example`, the job's recruiter) → **Offers** → open **Ishaan Malhotra**'s accepted offer for "Frontend Engineer (React)" → **Hire**. The dialog lists what will happen; choose **Hire now**. The offer page shows the new employee ID; **See onboarding progress** opens the checklist. The job's openings go down by one (it closes at zero), and his other open applications, if any, are withdrawn.
2. **Sign in as the new employee.** Sign out, then sign in as `joiner@demo.example` (same password). The same login is now an employee: you land on **Welcome** with the employee ID, first day, manager (Vikram Natarajan), buddy, checklist and first-week plan. Tick **I have read and accept** on "Read and acknowledge the code of conduct": the progress bar moves.
3. **Apply for leave with a clash warning.** **Leave** → leave type **Casual leave** → **From**: the working day six working days after his first day (open **Team calendar** and move to that month: it is the day on which three of Vikram's reports are already off). Before you apply, the form shows **Days counted: 1 day** and "3 of 5 people in Vikram Natarajan's team are already off on …". It is a warning, not a block: choose **Apply for 1 day**. (New joiners can book against the casual leave they will have accrued by then.)
4. **The manager approves.** Sign in as `manager@demo.example` → **Approvals**. The request shows the reason and the same team warning. Choose **Approve** → **Approve**. Try **Do not approve** on another request: it needs a reason.
5. **Ask HIRA for the balance.** Sign in as `joiner@demo.example` again → **Ask HIRA** (bottom right) → "how many leaves do i have left" (or "meri kitni chutti baki hai"). Try "apply casual leave next friday": HIRA shows a confirmation card with the engine's check (before his first day it explains which rule is not met) and sends nothing until you press **Confirm**; the card's Confirm calls the same leave API as the form. Also try "who is my buddy", "upcoming holidays", "what is the sandwich rule".
6. **More to see.** **Attendance**: check in (office or remote; no location is recorded), and request a correction for a missed check-out. **Team calendar**: peers see who is off but not why; `manager@demo.example` sees reasons under **My reports**. **Approvals** as `admin@demo.example` shows escalated requests under Needs attention. **Onboarding** (manager, buddy or HR) shows every joiner's progress. **HR settings** (admin) edits leave rules, the work policy and holidays per location. **Policies and holidays** lists the rules and the holiday calendar (demo data: verify the dates).

See `docs/HR.md` for every rule and number, and the assistant's measured accuracy.

## 8. Useful commands

| Task | Command (in `backend` with the venv active) |
| --- | --- |
| Wipe and re-seed demo data | `python manage.py seed --reset` |
| Create a real HR admin | `set BOOTSTRAP_ADMIN_PASSWORD=...` then `python manage.py bootstrap_admin --email you@company.com --name "Your Name"` |
| Call the cron hooks locally | `curl -X POST -H "X-Internal-Secret: <INTERNAL_TICK_SECRET>" http://localhost:8000/api/internal/tick` |
| Nightly hook (leave accrual, carry-forward, missing check-outs) | same command with `/api/internal/nightly` |
| Measure the HR assistant | `python manage.py evaluate_hr --split tune` and `--split holdout` (add `--show-misses`) |
| Stop the database | `docker compose down` (add `-v` to delete its data) |
| Re-parse resumes after an extractor change | `python manage.py reparse_profiles` (`--all` for everything) |
| Re-score after changing `matching/weights.py` | `python manage.py rescore` |
| Measure matching against the labelled pairs | `python manage.py evaluate_matching --verbose` |
| Measure Ask HIRA intent accuracy | `python manage.py evaluate_hira --verbose` |
| Run HIRA's cron work now (reminders, holds, scorecards, offer expiry) | `curl -X POST -H "X-Internal-Secret: <INTERNAL_TICK_SECRET>" http://localhost:8000/api/internal/tick` |

## Troubleshooting

- **`Missing required environment variables`**: run `python ..\scripts\generate_env.py` inside `backend`.
- **`connection refused` on port 55432**: Docker Desktop is not running, or the `db` container is stopped (`docker compose up -d db`).
- **`password authentication failed for user "talentpath"`**: you are reaching a different Postgres, usually one installed on Windows. The Docker database listens on **55432** for this reason; check `DATABASE_URL` in `backend\.env` ends in `127.0.0.1:55432/talentpath`. `netstat -ano | findstr :543` shows what is listening.
- **Typing commands into the `npm run dev` window does nothing**: that window is busy running Vite. Use a new terminal for tests.
- **403 `CSRF failed` in the browser**: open the app through http://localhost:5173 (not port 8000), so the CSRF cookie and the API share an origin.
