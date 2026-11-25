# Interview questions and answers: TalentPath

Thirty questions an interviewer is likely to ask, with answers in my own words. Each answer points at the code or doc to open if they want proof. Practise saying them out loud in under a minute each.

## The project

**1. What is TalentPath, in one minute?**
A hire-to-onboard HR platform I built alone. A candidate finds a job and applies with a resume; the recruiter sees candidates ranked by an explainable fit score; an assistant called HIRA books interviews from interviewers' free time; interviewers submit scorecards; an offer goes through two approvals; one click turns the accepted candidate into an employee with an ID, a checklist and a buddy; and the same person then applies for leave and checks in. Django and PostgreSQL on the back, React and TypeScript on the front, deployed on free tiers.

**2. Why did you build this instead of a smaller project?**
I am applying to HR-tech companies, and their products cover exactly this journey. Building the whole flow forced me to deal with the hard parts that small projects skip: permissions across five roles, concurrency in scheduling, encrypted personal data, and data that must stay consistent across hiring and HR.

**3. What was the hardest part?**
Interview scheduling. Two people can try to book the same interviewer at the same moment, and a slot shown to a candidate must still be free when they click it. I solved it with 30-minute holds, locked transactions, and a PostgreSQL exclusion constraint so the database itself refuses overlapping bookings (question 11).

**4. What would you do differently?**
I would write the all-routes end-to-end test (every route for every role, failing on any console error) in week 1 instead of week 4. It is cheap, and it would have caught several small regressions earlier.

## Architecture

**5. Walk me through the architecture.**
The browser only talks to Vercel. Vercel serves the React app and rewrites `/api/*` to the Django backend on Render, so cookies are first-party. Django runs under one Daphne process that serves HTTP and WebSockets (Channels). Data is in Neon PostgreSQL, including uploaded files (compressed and encrypted), because Render's free disk is wiped on restart. cron-job.org calls a tick and a nightly endpoint. Diagram: `README.md` and `docs/ARCHITECTURE.md`.

**6. Why Django and not FastAPI or Node?**
The app is mostly relational data with strict rules: users, roles, jobs, applications, interviews, leave. Django gives me migrations, the ORM, transactions, admin and a mature auth story; DRF gives serializers and throttling; Channels adds WebSockets. I spent my time on the product, not on plumbing.

**7. How do WebSockets work when Vercel cannot proxy them?**
The browser asks the API for a ticket (`POST /api/realtime/ticket`), valid for 30 seconds and usable once, then opens the socket straight to Render with it. The socket also checks the origin. Everything still works by polling if the socket fails.

**8. Why one JSON policy file for permissions?**
So the backend and the frontend cannot disagree. `shared/policy.json` lists 110 actions and every page route with the roles allowed; the default is deny. Every API view declares its action, and a permission class checks it. The React router and menus read the same file. A test enumerates every URL and calls it as every role, so a new endpoint without a policy entry fails CI. (`backend/core/policy.py`, `tests/test_policy.py`)

**9. How do you authenticate?**
JWTs from SimpleJWT, but stored in HttpOnly cookies, not in local storage, so JavaScript cannot read them. Access tokens last 15 minutes; refresh tokens 7 days, rotated, with the old one blacklisted. Because cookies are sent automatically, every unsafe request also needs a CSRF token. Production cookies are Secure and SameSite=Lax.

**10. How is personal data protected?**
Sensitive fields (resume text and files, phone, address, offer terms, leave reasons) are encrypted with AES-GCM before they reach the database. To search an encrypted value, such as an email, I store a blind index: an HMAC with a separate key, so equality lookups work without decrypting. Keys come from the environment and the server refuses to start without them. (`backend/core/crypto.py`)

## Scheduling and data integrity

**11. How do you prevent double booking?**
Three layers. Slots shown are computed from working hours minus busy time. Picking a slot creates a 30-minute hold inside a transaction that locks the interviewer rows. And PostgreSQL has an exclusion constraint on (interviewer, time range) using `btree_gist`, so even a bug in my code cannot store two overlapping bookings. A test runs two bookings in parallel threads and expects exactly one to succeed.

**12. What happens if the cron job never runs?**
Nothing a user can see goes wrong. Anything a person reads is also caught up when it is read: expired holds are released, finished interviews are completed, leave is credited when balances are opened, overdue approvals escalate when the approvals list is loaded. Only time-based notifications (like "your interview is in an hour") need the tick. The list is in `docs/DEPLOY.md`.

**13. How is the one-click hire kept consistent?**
It is one database transaction: mark the application hired, create the employee record and ID, change the same login's role (sessions revoked), prorate leave, create the onboarding checklist and buddy, withdraw other applications, reduce openings and close the job if filled. If any step fails, none of it happens. Tests check the all-or-nothing behaviour.

**14. How is leave accrual made safe to run many times?**
Every credit is a ledger row with a unique key (employee, leave type, period). Running accrual twice inserts nothing the second time, so it can run on read, on the nightly job and again after an outage without double-crediting.

## Matching and AI

**15. How does the fit score work?**
It is deterministic and explainable. A resume is parsed into sections and skills (matched against a 214-skill taxonomy with synonyms, so `JS` means JavaScript), with evidence for each skill. The score is out of 100: required skills 50, nice-to-have 15, evidence strength 20, experience fit 15. Every score stores reason chips and "what would raise this score". (`docs/MATCHING.md`)

**16. How do you know it works?**
I hand-labelled 40 synthetic job and resume pairs with the band I expected (Strong, Good, Partial, Low) before running the scorer. I tuned on 20 and measured the other 20: 18/20 on tuning, 16/20 held out, and every miss was one band away. I did not tune away the held-out misses, because that would make the number meaningless, and CI fails if either number drops.

**17. How do you know it is fair?**
Blind screening hides identity until the Interview stage. And a counterfactual check rewrites resumes changing only the name, gendered words and pronouns, college and city, then rescores: 40 applications × 3 variants = 120 variants, 0 score changes (600 variants over the whole demo set, also 0). I am careful to say what this does not prove: it shows the score ignores those fields, not that the whole hiring process is fair.

**18. Why no language model?**
Predictability, privacy and cost. HR decisions need explanations and repeatable results, the data is personal, and the free tier has no budget for API calls. The rule-based approach is narrower, and I say so on the site.

**19. How does Ask HIRA understand questions?**
Normalise text, correct spelling against the app's vocabulary, map Hinglish words, detect the intent with rules, then answer from the asker's own records or retrieve a knowledge entry with BM25. Measured on held-out questions: 35 of 44. The HR assistant never acts by itself: "apply leave" returns a confirmation card, and only the employee's click submits it.

## Frontend

**20. How is the frontend organised?**
React 18 with TypeScript, TanStack Query for server state, Zod for form validation, Tailwind for styling. Pages per area, one API client that handles cookies, CSRF, token refresh and the "server is waking up" retry. Route guards read the shared policy file.

**21. What did you do for accessibility?**
Every page has one `h1`, labelled controls, keyboard alternatives (the pipeline board has "Move to" besides drag and drop), charts have a table view, and Playwright runs axe for WCAG 2.1 AA and checks a 390-pixel mobile width without horizontal scrolling.

**22. How is SEO handled on a single-page app?**
Public job pages set a unique title, meta description, canonical link and JobPosting JSON-LD from data the API prepares. The backend serves `sitemap.xml` (open jobs only) and `robots.txt` (derived from the policy file, so signed-in areas are disallowed). Unknown URLs return a real 404 status on Vercel.

## Testing and quality

**23. How do you test?**
pytest for the backend (1,374 test cases on PostgreSQL in my last full run), Vitest for components and hooks, Playwright for end-to-end flows with axe. CI runs ruff, ESLint, TypeScript, Prettier, the backend tests on a PostgreSQL service and the frontend build.

**24. Tell me about a bug you found late.**
A transactional test truncated every table, including the skills taxonomy that a migration seeds, so a later test failed with "skill does not exist", but only when run in a certain order on PostgreSQL. The fix was `serialized_rollback=True`, which restores migration data after such tests. Lesson: test isolation also means isolating seeded data.

**25. How do you know every page works for every role?**
`frontend/e2e/routes.spec.ts` reads the routes from the policy file, signs in as each role, visits every page it may open, follows links to pages with IDs, and fails on any console error, failed request, image without alt text or duplicate page title.

## Deployment and operations

**26. How did you deploy for free, and what are the limits?**
Vercel for the frontend, a Render free web service built from a Dockerfile, Neon free PostgreSQL, cron-job.org for scheduled calls. Limits: Render sleeps after 15 idle minutes and takes about a minute to wake; Neon gives 1 GB; one instance only. The app shows a "waking up" notice and retries.

**27. What does production mode enforce?**
It refuses to start without its secrets, with weak keys or with DEBUG on. Allowed hosts and CSRF origins are built from the Render and Vercel domains, never `*`. HTTPS redirect, HSTS, secure cookies, TLS to the database, and `manage.py check --deploy` passes. A test starts the settings in a subprocess with and without each variable.

**28. How do you protect the cron endpoints?**
They need a header `X-Tick-Secret`, compared with `hmac.compare_digest` so timing does not leak how much matched. The tick is cheap when nothing is due, and the nightly hook starts the demo reset in a background thread so it answers within cron-job.org's 30-second timeout, with a lock so two resets never overlap.

**29. How would you scale it?**
Add Redis for the channel layer and cache (one environment variable switches both), run several instances, move scheduled work to a real queue, move files to object storage, and add monitoring. The design already avoids local disk and in-process state that would block that.

**30. What did you learn?**
To decide rules once and enforce them in one place (the policy file, the leave engine, the database constraint), to measure instead of claiming (held-out sets, fairness test, counted test numbers), and to write down decisions as I go: `docs/DECISIONS.md` has 78 of them, which made the last weeks much faster.
