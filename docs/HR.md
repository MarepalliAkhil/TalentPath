# People operations: hire to onboard, leave, attendance, HR assistant (week 3B)

Everything here is rule based and deterministic. Rules that HR would change
(quotas, notice, sandwich rule, shift, thresholds, holidays) are **data per
location** that hr_admin edits on **HR settings**; the code only applies them.
There is no payroll and no payment of any kind.

Code: `backend/hr/` (models, `leave.py` engine, `onboarding.py`, `attendance.py`,
`team.py`, `assistant.py`, `defaults.py`), seed data in `backend/seeding/people.py`,
screens in `frontend/src/pages/hr/` and `frontend/src/components/hr.tsx`.

## 1. One-click hire to onboard

When a candidate accepts an offer, `offers.events.offer_accepted` fires and
`hr.signals` tells every hr_admin the hire is ready. The job's recruiter (or any
hr_admin) opens the offer and chooses **Hire** (`POST /api/offers/<id>/hire`,
action `onboarding.hire`). A dialog lists what will happen; **Hire now** runs it
in **one database transaction**. If any step fails, nothing is saved (tested by
forcing a failure half way).

| Step | What happens |
| --- | --- |
| Application | Offer → **Hired**, with a status-history row |
| Employee record | Employee ID (`LW1001`, `LW1002`…), designation, department, location, reporting manager and joining date from the offer |
| Login | The same account changes role from candidate to **employee**. The change is audited (`users.role_changed`) and the person's sessions are revoked, so the next sign-in carries the new role. Their applications stay theirs and private |
| Leave | Balances credited from the joining date and prorated (see 3) |
| Checklist | Generated from the template: items for everyone plus the department's own items, each with an owner and a due date in working days from the joining date |
| Buddy | Same department, joined at least 6 months before, fewest current buddies (people still onboarding), never the reporting manager or the joiner; ties go to the most recent joiner, then the employee ID |
| First week | Seven sessions over the first five working days (welcome, meet your manager, team, lunch with the buddy, product, policies, week-one check-in) |
| Other applications | Every other open application by the person is **withdrawn** (reason `hired_elsewhere`), live offers on them are revoked, their recruiters get a polite note |
| Job | Openings go down by one; the job **closes** when openings reach zero |
| Notifications | Welcome message to the joiner, the manager, the buddy and HR (after the transaction commits) |

**Welcome page.** The new employee's first sign-in lands on `/employee`, which
sends them to `/welcome` once: employee ID, first day, manager and buddy cards,
the checklist with progress and the first-week plan. Opening it records
`welcome_seen_at`.

**Checklist tasks** have three kinds: *Mark done*, *Read and acknowledge* and
*Upload a document* (PDF, PNG or JPEG up to 5 MB, checked by content, stored
compressed and encrypted like resumes). Owners: the joiner, the reporting
manager, the buddy, HR or the IT desk (any hr_admin completes HR and IT items).
Only the owner (or hr_admin) can complete a task. When the last task is done
the employee moves from *onboarding* to *active*.

**Who sees progress.** The reporting manager, the buddy and every hr_admin see
the joiner on **Onboarding**. hr_admin also gets a *Needs attention* list:
overdue checklist items, joiners without a buddy and escalated leave.

## 2. Who approves

The **reporting relationship decides, not the role name.** An employee-role team
lead approves their reports; a hiring manager who is not your manager cannot
approve your leave. Nobody approves their own leave or attendance correction,
and peers never see each other's requests.

## 3. Leave engine

### Leave types (per location, defaults)

| Type | Quota | Credited | Notice | Max in one request | Half days | Document | Sandwich | Carry forward |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Casual | 12 / year | monthly (1 a month) | 1 day | 3 days | yes | – | off | 0 |
| Sick | 10 / year | on 1 January | none; up to 7 days back | – | yes | after 2 days | off | 0 |
| Earned | 18 / year | monthly (1.5 a month) | 7 days | 15 days | no | – | **on** | up to 15 |
| Comp-off | 0 | HR adds days (worked on a holiday) | 1 day | 2 days | yes | – | off | 0 |
| Loss of pay | unpaid, no balance | – | 3 days | 30 days | yes | – | **on** | – |

hr_admin can change every field on **HR settings → Leave types**, per location:
yearly quota, monthly or yearly crediting, proration for joiners, carry-forward
cap, minimum notice, backdating window, maximum consecutive days, half days,
document after N days, the sandwich rule and active/inactive. Changes apply to
new requests at once and are audited.

### Counting days

- Weekly offs (default Saturday and Sunday, per location) and the location's
  holidays are **not counted**.
- **Sandwich rule on:** weekly offs and holidays that sit *between* two leave
  days are counted, including when the leave on one side is another request
  (Friday approved, now Monday: the weekend counts). A weekend at the very end
  of a request with nothing after it is not counted.
- A half day counts 0.5 and must start and end on the same date.
- Leave cannot cross 31 December (apply once per year) and is limited to 60
  calendar days per request.
- The preview (`POST /api/leave/preview`) shows the day-by-day breakdown, the
  days counted, every rule that fails and the team warnings **before** submitting.
  It never saves.

### Rules checked on every request

Notice (with the earliest allowed date), backdating window, joining date,
maximum consecutive days, half-day allowed, document required, overlap with
another open request (the other half of the same day is fine), balance
(pending requests are reserved, so two quick requests cannot both pass) and
whether HR also needs to approve.

### Balances, accrual and carry-forward

- Every change is a row in an append-only **ledger** with a unique key, so the
  nightly job can run any number of times without double credit
  (`grant:`, `accrual:<month>`, `carry:`, `lapse:`, `use:<request>`, `reversal:<request>`).
- **Monthly** types credit `quota × m/12` rounded to half days, so twelve
  months add up to exactly the quota. **Yearly** types are granted on 1 January.
- **Joiners** earn from their joining month if they join by the 15th, otherwise
  from the next month; yearly types are prorated the same way.
- **Booking ahead.** A request for a later month this year may use monthly
  accruals still to come before that month (for a future year: this year's
  carry-forward plus that year's accrual). The leave page then shows
  "booked ahead of accrual" instead of a negative balance.
- **Year end** (nightly, idempotent): unused days carry into the new year up to
  the cap; the rest lapses (a negative ledger row in the old year).
- hr_admin can adjust a balance (for example comp-off) with a note; audited.

### Approvals, delegation, escalation

1. The request goes to the **reporting manager**.
2. If it is longer than the location's **HR threshold** (default 5 days), the
   manager's approval moves it to **HR** (any hr_admin) for a second approval.
3. **Delegation:** if the approver is on approved leave that day, the request
   goes to *their* manager, and so on up the line. Pending requests are moved
   by the tick when an approver goes on leave.
4. **Escalation:** pending for more than **48 hours** (configurable per
   location) → it goes one level up, is flagged *escalated* and appears in HR's
   *Needs attention* list; hr_admin can then decide it directly.
5. Nobody left in the reporting line → HR.
6. Rejections need a reason (5+ characters), shown to the employee.
7. The employee can **cancel** before the start date; approved days return to
   the balance.

Every step is in the request's timeline (submitted, assigned, delegated,
escalated, approved, rejected, cancelled) and in the audit log.

## 4. Team calendar and clash warnings

- A **team** is the people who share a reporting manager. Managers can switch
  to **My reports**; hr_admin can open any team.
- The calendar shows approved and pending leave, holidays and joiners for a
  month. **Peers see who is off and when; the leave type and reason are shown
  only to the team's manager and hr_admin.**
- **Clash warning:** while applying (and while approving), if the team would
  drop below the location's availability threshold (default 50 %) on a counted
  day, the form says, for example, "2 of 4 people in Vikram Natarajan's team are
  already off on Tue 8 Dec (1 would be available)." Warnings **inform; they never
  block**. Rejected and cancelled leave does not count.

## 5. Attendance

- Web **check-in** (office or remote) and **check-out**. **No location is
  recorded.**
- General shift per location (default 09:30–18:30) with grace minutes (default
  15): later check-in is **late**, earlier check-out is **early**.
- The nightly job flags **missing check-outs** on earlier days and tells the
  person once.
- **Regularisation:** a correction for a past working day in the last 30 days
  (times, mode, reason), approved by the reporting manager (same line as leave;
  HR when there is none). Approval rewrites the day and recomputes the flags.
- Monthly summary for the employee; managers see their direct reports, hr_admin
  sees everyone.

## 6. HR assistant (Ask HIRA for employees)

Ask HIRA uses the same rule-based engine as the candidate assistant (normalise
Hinglish written in English letters → spell-correct → keyword intents → BM25 over
the handbook and the person's own leave rules). Staff with an employee record
get HR answers; everything else falls back to the general assistant.

| Intent | Example | Answer |
| --- | --- | --- |
| Leave balance | "meri kitni chutti baki hai" | Own balances per type, as a table |
| Apply leave | "apply casual leave next Friday" | A **confirmation card** with the engine's day count, errors and team warnings. The employee presses **Confirm**, which calls the normal leave API. **The assistant never submits by itself.** |
| Holidays | "upcoming holidays" | Next holidays at their location (marked as demo data to verify) |
| Buddy / manager | "who is my buddy" | Name and designation |
| Onboarding | "what is left in my onboarding" | Progress and next items |
| Attendance | "my attendance this month" | Present, office/remote, late, missing check-outs |
| Pending for me | "what's pending for me" | The leave and corrections waiting for this person, without reasons |
| Policy | "what is the sandwich rule" | The most relevant handbook or leave-rule passage, with a link to its source on **Policies and holidays** |

**Privacy:** answers only read the signed-in person's records. A question that
names a colleague's leave or attendance is refused ("I can only share your own
leave and attendance"). Reasons are never shown in the pending list.

### Evaluation

`python manage.py evaluate_hr --split tune` and `--split holdout` (add
`--show-misses`). 64 employee questions written before the first measurement,
including typos and Hinglish, split 32 tuning / 32 holdout. The holdout split
was only measured, never used to change the rules.

| Split | Intent accuracy |
| --- | --- |
| Tuning | **32 / 32 (100 %)** |
| Holdout | **27 / 32 (84 %)** |

Holdout misses, kept as they are:

| Question | Expected | Got |
| --- | --- | --- |
| how much earned leave do i have | leave balance | earned-leave policy |
| who approves my leave | my manager | pending for me |
| which documents do i still need to upload | onboarding status | sick-leave documents policy |
| did i miss any check outs | attendance this month | attendance policy |
| mere paas kya pending hai | pending for me | fallback |

The pattern: questions that mix a policy word (earned, documents, check-out)
with a personal one lean towards the policy answer. Fixing that belongs to a
future round with fresh holdout questions.

## 7. Demo data (seed)

`python manage.py seed --reset` adds, on top of weeks 1 to 3A:

- **30 employees** across departments in Hyderabad and Bengaluru with managers
  and buddies (the five demo logins are among them; `employee@demo.example` is
  Divya Pillai, an engineer who reports to Vikram Natarajan, `manager@demo.example`).
- **Holiday calendars** for both locations: national holidays plus Telangana
  (Hyderabad) and Karnataka (Bengaluru) state holidays for 2026 and early 2027,
  each marked "Demo data: verify against the official holiday list". Moon-based
  dates can move by a day.
- **Leave** in every state: pending, approved, rejected, cancelled, one
  delegated and one escalated request; comp-off credits.
- **Attendance** for the last 30 days with late and early days, missing
  check-outs and regularisations.
- **Three people mid-onboarding** with partly done checklists.
- **One accepted offer ready for the one-click hire:** Ishaan Malhotra
  (`joiner@demo.example`) for "Frontend Engineer (React)" (recruiter Kabir
  Mehta), reporting to Vikram Natarajan, joining about a week from the seed date.
  Three of Vikram's reports are already off six working days after that, so his
  first leave request shows a clash warning.

## 8. Scheduled work

| Hook | Work |
| --- | --- |
| Tick (`POST /api/internal/tick`) | Leave delegation and escalation (plus week 3A's interview work and offer expiry) |
| Nightly (`POST /api/internal/nightly`) | Monthly accrual and yearly grants, year-end carry-forward, missing check-outs (plus token and outbox clean-up) |

All of it is idempotent: running a hook twice changes nothing the second time.

## 9. Known limits

- Leave is counted in whole and half days; hourly leave is out of scope.
- A year-end carry-forward is computed once; leave for last year approved or
  cancelled after the carry-forward does not re-run it (HR can adjust).
- Holidays are demo data; HR must replace them with the official list.
- One general shift per location; rosters and night shifts are out of scope.
