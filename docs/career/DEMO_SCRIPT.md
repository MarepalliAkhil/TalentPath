# Two-minute demo: one candidate, from shortlist to first week

**The story:** Ishaan Malhotra applied for "Frontend Engineer (React)". We follow him from the recruiter's ranked list to his first leave request as an employee. One person, one flow, every role touching it.

**Before you start** (on the live site or locally):
- Fresh demo data: the live site resets nightly; locally run `python manage.py seed --reset`.
- Open two browser windows: a normal one signed in as `admin@demo.example`, and a private one for `joiner@demo.example` (password `Demo@Pass2026`). Signing in during the demo wastes time.
- On the live site, open it once a minute before you start so the free server is awake.
- Rehearse with a timer. Stop talking while a page loads.

| Time | Screen | Do | Say |
| --- | --- | --- | --- |
| 0:00 | `/for-recruiters` | Scroll once past the four company sections | "TalentPath is a hire-to-onboard platform I built alone: Django and PostgreSQL, React and TypeScript. I'll follow one candidate, Ishaan, from shortlist to his first week." |
| 0:12 | Admin → **All jobs** → "Frontend Engineer (React)" → **Candidates** | Point at the ranked list, open **Explain** on Ishaan | "Recruiters see candidates ranked by a 0-to-100 fit score. It's not a black box: every score has reasons, evidence from the resume and what would raise it. No language model: it's deterministic and tested, 16 of 20 on a held-out set." |
| 0:35 | Same job → **Board** | Point at the stage columns | "Screening is blind until the Interview stage: names are hidden. A fairness check swaps only names, gender words, colleges and cities, and the score never moves." |
| 0:48 | **Offers** → Ishaan's accepted offer | Point at the approval trail, then **Hire** → **Hire now** | "HIRA, the assistant, booked his interviews from interviewers' free time; the database itself refuses double bookings. The offer went through two approvals and he accepted. One click hires him: one transaction creates his employee ID, onboarding checklist, buddy and leave balance." |
| 1:10 | Private window: `joiner@demo.example` → **Welcome** | Tick the code-of-conduct item; progress moves | "Same login, now an employee. He sees his manager, buddy and first-week plan." |
| 1:22 | **Leave** → Casual leave on the clash day from `docs/START_HERE.md` | Show "Days counted" and the team warning, then **Apply** | "Leave rules are data per location: accrual, carry-forward, the sandwich rule. Here it warns that three of five teammates are already off. It informs, never blocks." |
| 1:40 | **Ask HIRA** → "meri kitni chutti baki hai" | Show the answer | "The HR assistant understands typos and Hinglish and only reads his own records." |
| 1:50 | Back to `/for-recruiters` → **How it is built** | Point at the numbers | "Permissions come from one deny-by-default policy file shared by the API and the UI, and every number on this page is counted from the repository at build time. Thanks, the code and docs are on GitHub." |

**If something goes wrong:** say "the free server is waking up, this is the honest version of free hosting" and continue on the next step. If the hire was already done earlier, skip 0:48 and show Ishaan's employee ID on the offer page.

**If they ask for more:** the analytics page (`/analytics` as admin), the interview scheduling link (`docs/HIRA.md`), or the all-routes test (`frontend/e2e/routes.spec.ts`).
