# HIRA, the recruiting coordinator (week 3A)

HIRA (Hiring Intelligence & Recruiting Assistant; the name and subtitle come
from `shared/brand.json`) books interviews, reminds people, chases feedback and
tells recruiters what needs them. Everything is rule based and deterministic:
the same data and the same time always give the same result. There is no LLM.

Code: `backend/interviews/` (scheduling, scorecards), `backend/offers/`,
`backend/hira/activity.py` (log, briefing, Needs you). All rule numbers live in
`backend/interviews/rules.py`.

## 1. Interview plans

Every job has a plan of ordered rounds. A default plan is built the first time a
job needs one (and by the seed for every demo job):

| Round | Length | Mode | Interviewers | Pool |
| --- | --- | --- | --- | --- |
| Technical 1 | 60 min | Video | 1 | Interviewers whose skills overlap the job's required skills |
| Technical 2 | 60 min | Video | Panel of 2 | Same pool |
| Hiring manager | 45 min | Video | 1 | The job's hiring manager |
| HR | 30 min | Phone | 1 | HR admins |

Recruiters (own jobs) and hr_admin edit rounds, pools and **Let HIRA schedule**
on the job's **Interview plan** tab; hiring managers can read it. A round that
already has interviews cannot be removed.

Interviewers are staff with an interviewer profile: skills (set by hr_admin under
`/api/interviewers`) and working hours per weekday. Everyone keeps their own
hours and blocked time on **My interviews → My availability**. All times are
Asia/Kolkata (IST); the database stores UTC.

## 2. Scheduling rules

| Rule | Value |
| --- | --- |
| Earliest slot | 24 hours from now, rounded up to the next half hour (IST) |
| Look-ahead | 14 days |
| Slot starts | on the hour or half hour |
| Slots offered | up to 5 (aim 3 to 5), at most 2 per day and 2 hours apart |
| Hold while choosing | 30 minutes |
| Email link | signed, single use, expires after 72 hours; a new proposal retires older links |
| Candidate reschedules | 2, until 12 hours before the start |
| Reminders | 24 hours and 1 hour before (the 24-hour one is skipped for bookings made inside 12 hours) |
| Scorecard due | 24 hours after the interview ends |
| Chasing | when overdue, at most once every 24 hours |
| Needs you (feedback) | 48 hours after the interview ends without a scorecard |

**When HIRA acts.** When a candidate moves to Interview, HIRA starts the first
round that is not yet passed. When the last scorecard of a round arrives and the
round passed, HIRA starts the next round. Rejected, withdrawn or offer-stage
candidates have their open interviews cancelled and their time released.

**Finding slots** (`interviews/slots.py`). A time is offered only if the
candidate and the required number of pool members are all free:

1. inside each interviewer's working hours for that weekday (whole interview on one day);
2. not overlapping their blocked time;
3. not overlapping any active claim (an interview or an unexpired hold) for them or the candidate.

For a panel, HIRA needs common free time. Among free people it picks those with
the **fewest interviews that week** (Monday to Sunday, IST), then fewest overall,
then a stable id order, so load spreads evenly and the result is repeatable.

**Holding and booking** (`interviews/claims.py`). Busy time is stored as
`TimeClaim` rows (one per person). Every booking runs in a transaction that:

1. locks the people involved (`SELECT … FOR UPDATE` on their user rows, in id order to avoid deadlocks),
2. releases holds that have expired,
3. checks for clashes (claims and blocked time),
4. inserts the claims.

On PostgreSQL an **exclusion constraint** backs this up:
`EXCLUDE USING gist (person_id WITH =, tstzrange(starts_at, ends_at, '[)') WITH &&) WHERE (active)`
(migration `interviews/0002`, needs the `btree_gist` extension, which is a
trusted extension on PostgreSQL 13+ and on Neon). Two people can never be booked
twice for the same time, even when two requests arrive together. If a slot was
taken in the meantime, the candidate sees "That time is no longer free", the slot
stops being offered and HIRA offers fresh times if none are left.

**Confirmation** goes out in the app and as a simulated email with an `.ics`
calendar invite attached (also downloadable). Video interviews get a placeholder
link `https://meet.example/simulated/…`, in-person and phone details are marked
"simulated". Interviewers see the candidate's code instead of the name while the
job is still blind.

**Reschedules.** The candidate can ask twice, until 12 hours before. HIRA frees
the time, offers new slots (not the old time) and logs it. A third request is
refused kindly and becomes a Needs you item for the recruiter.

**Interviewer declines.** HIRA looks for someone else in the same pool who is
free at exactly that time (same checks, least loaded first). If nobody is free,
the interview goes back to picking, the candidate gets new slots (not counted as
their reschedule) and the recruiter gets a Needs you item.

**No-shows.** An interviewer on the interview can mark a no-show once it has
started (and before any feedback is in). The recruiter is notified.

**Let HIRA schedule off.** Nothing is proposed automatically. Recruiters use
**Schedule by hand** in the candidate drawer (round, start time in IST,
interviewers); the same claims, locks and constraint apply. Recruiters can also
press **Ask HIRA for slots** at any time.

**Cron.** `POST /api/internal/tick` (cron-job.org, every few minutes) releases
expired holds, marks finished interviews completed, sends reminders, chases
overdue scorecards and expires offers. Every task is idempotent (reminders use a
"sent at" column updated with a conditional `UPDATE`, so two ticks cannot send
twice).

## 3. Activity log and audit

Every HIRA action is a row in `HiraActivity`: action, job, application,
interview, reason code, before, after, time. Rows are **append-only** (the model
refuses updates and deletes; only `seed --reset` removes demo rows) and each one
is mirrored to the audit log as `hira.<action>`.

| Action | Counts in the briefing as |
| --- | --- |
| `interview_scheduled` | scheduled interviews |
| `reschedule_handled` | handled reschedules |
| `interviewer_replaced` | replaced interviewers |
| `scorecard_chased` | chased overdue scorecards |
| `reminder_sent` | sent reminders |
| `slots_proposed`, `next_round`, `hold_expired`, `manual_scheduled` | shown in the log only |
| `no_slots`, `replacement_failed`, `scorecard_overdue`, `reschedule_limit` | **Needs you** items |

**Needs you** lists the flagged rows whose problem is still open, checked
against the data when you look (for example the interview still has the
"no slots" flag, or the scorecard is still missing). Fix the problem and the item
disappears; the log row stays.

## 4. Login briefing and the activity page

When a recruiter or hr_admin opens the app, HIRA shows a popup **once per
browser session**: "While you were away, HIRA scheduled 5 interviews, handled 2
reschedules and chased 3 overdue scorecards; 1 item needs you." "Away" starts
when you last closed the briefing (first time: the last 7 days). Counts come
from the activity log only, scoped to your jobs (hr_admin: all jobs).

- **Play** reads the same sentence aloud with the browser's speech synthesis. It
  contains counts only, never candidate names or job titles. **Mute voice** is
  remembered on this device.
- **HIRA activity** (`/hira`): KPI tiles, actions by day (Recharts stacked bars
  with a **Table** view of the same numbers), the Needs you list and the full log
  with filters (action, IST date range, flagged only).

## 5. Scorecards

The template comes from the job: one row per required skill, plus Communication
and Problem solving, each rated 1 to 5 (1 weak, 3 meets the bar, 5 exceptional).
Ratings of **1, 2 and 5 need a comment**. The overall recommendation is strong
no, no, yes or strong yes. Comments and the summary are encrypted at rest.

- **Independent feedback:** an interviewer cannot see the other scorecards for
  that interview until they submit their own. The job's recruiter, its hiring
  manager and hr_admin read every submitted scorecard (unless they are an
  interviewer on that interview who has not submitted yet).
- **Outcome:** a round passes when every assigned interviewer has submitted and
  at least as many recommend yes or strong yes as no or strong no. Then HIRA
  starts the next round. After the last round the recruiter is told the
  candidate can get an offer. A round that leans no is left to the recruiter.
- The candidate drawer shows each round: time, interviewers, average per
  criterion, recommendation counts, and the week 2 match explanation below it.

## 6. Offers

Draft (recruiter or hr_admin, only after the final round passed) → **pending
approval** by the job's hiring manager → **pending approval** by hr_admin →
**approved** → **sent** (with a branded PDF letter, clearly marked as a demo) →
**accepted** or **declined** by the candidate, or **expired** after the expiry
date (cron). Either approver can **request changes** with a reason; the
recruiter edits and resubmits. The recruiter can **revoke** with a reason until
the candidate answers. Every step is audited.

- Offer details (designation, department, location, reporting manager, joining
  date, fixed and variable pay, joining bonus) are stored as encrypted JSON.
- The candidate accepts by typing their full name. The time and a keyed hash of
  the IP address are stored. This records the acknowledgement; it is not a legal
  electronic signature, and the UI says so.
- Accepting sends the `offers.events.offer_accepted` signal. Week 3B's one-click
  hire will listen to it; until then the application stays at Offer and "Hired"
  remains reserved.
- Candidates see only their own offers, and only once sent.

## 7. HIRA character images (slots)

Put optional WebP files in `frontend/public/hira/`:

| File | Used for |
| --- | --- |
| `hira.webp` | Default portrait, and the fallback for every pose |
| `hira-welcome.webp` | Login briefing, scheduling-link page |
| `hira-explain.webp` | HIRA activity page |
| `hira-attention.webp` | Login briefing when something needs you |
| `hira-celebrate.webp` | Reserved for week 3B (offer accepted) |
| `hira-thinking.webp` | Reserved |

The avatar tries the pose file, then `hira.webp`, then shows a clean "HI"
initials circle in the brand colours. A missing file never shows as a broken
image. Use square images of at least 256 × 256 px, under 60 KB each.

## 8. What this does not do (yet)

- Real calendars (Google, Outlook) and real meeting links: invites are `.ics` files and links are simulated.
- Time zones other than IST for interviewers or candidates.
- Recurring blocked time (block each period separately).
- Interviewer preferences beyond working hours and load (for example "max 3 a day").
- Week 3B: one-click hire from an accepted offer, onboarding.
