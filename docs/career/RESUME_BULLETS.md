# Resume bullets: TalentPath

Every number below is measured or counted from the repository (sources in brackets). Recount before each application: the test counts grow.

**TalentPath: hire-to-onboard HR platform** · Django 5.2, DRF, Channels, PostgreSQL, React 18, TypeScript · [github.com/MarepalliAkhil/TalentPath](https://github.com/MarepalliAkhil/TalentPath) · live demo: `<vercel link>`

- Built a full-stack hire-to-onboard platform alone (career site, screening, interview scheduling, offers, one-click hire, onboarding, leave and attendance) for 5 roles, backed by 1,374 automated backend tests on PostgreSQL plus Vitest and Playwright suites in GitHub Actions CI. *(pytest run 2026-11-23; `.github/workflows/ci.yml`)*
- Designed deny-by-default authorization from one JSON policy file (110 actions) shared by the Django API and the React UI, with a generated test that calls every endpoint as every role and anonymous. *(`shared/policy.json`, `backend/tests/test_policy.py`)*
- Built an explainable, deterministic resume-to-job fit score (0-100, weighted components, reason chips) on a 214-skill taxonomy with synonyms; 16/20 correct on held-out resumes, and a counterfactual fairness check of 120 identity-only variants with 0 score changes. *(`docs/MATCHING.md`)*
- Implemented an interview scheduler that proposes slots from interviewers' hours, holds them for 30 minutes and prevents double booking with a PostgreSQL exclusion constraint (btree_gist), verified by a concurrent-booking test. *(`backend/interviews/`, `docs/HIRA.md`)*
- Wrote rule-based assistants with no language model (intents, spelling correction, Hinglish, BM25 retrieval) that answer only from the asker's own records: 35/44 held-out questions for candidates, 27/32 for HR questions. *(`docs/ASK_HIRA.md`, `docs/HR.md`)*
- Deployed on free tiers (Vercel, Render Docker, Neon, cron-job.org) with strict production settings, field-level encryption, a zero-query health check and scheduled jobs that are also caught up on read, so a missed cron run never changes what users see. *(`docs/DEPLOY.md`, `backend/tests/test_ops.py`, `test_lazy_jobs.py`)*

Short version for a one-line projects section:

- TalentPath: solo full-stack HR platform (Django, React, PostgreSQL) from job post to onboarding; explainable matching (16/20 held out), deny-by-default policy for 110 actions, 1,374 backend tests, deployed free on Vercel, Render and Neon.
