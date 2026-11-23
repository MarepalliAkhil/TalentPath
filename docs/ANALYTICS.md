# Analytics: metric definitions (week 4A)

Every number is computed on the server from the records in the database when the
page loads (`backend/analytics/metrics.py`). Nothing is typed in by hand. Each
section returns a one-line text summary, a table (the same numbers as its chart)
and, where it helps, a Recharts chart with a **Chart / Table** switch. Every
table can be downloaded as CSV with the same filters and scope.

On the demo, the data is **synthetic**: the seed moves made-up candidates through
the stages, so the numbers show how the metrics work, not how any real team hires.

## Who sees what

| Role | Hiring analytics | People analytics |
| --- | --- | --- |
| hr_admin | Every job | Yes |
| Recruiter | Jobs they created | No (403) |
| Hiring manager | Published jobs assigned to them | No (403) |
| Employee, candidate | No (403) | No (403) |

Scope uses the same `visible_jobs` rule as the rest of the app, so a recruiter
never sees another recruiter's numbers, interviewers or HIRA actions. CSV export
uses the same scope and is recorded in the audit log (`analytics.exported`).
Cells that start with `=`, `+`, `-` or `@` get a leading `'`, so a spreadsheet
cannot run them as formulas.

## Filters

- **Date range** (`from`, `to`, IST dates). Default: the last 180 days, at most
  two years. Hiring metrics include applications **created** in the range; people
  metrics use the range for attendance and mobility, and the range's end year
  for leave.
- **Department**: hiring metrics by the job's department, people metrics by the
  employee's department.

## Statistics used

- **Median and 80th percentile**: linear interpolation between closest ranks
  (the common "type 7" definition: rank = (n − 1) × p on the sorted values),
  rounded to one decimal. Empty lists show "n/a", never 0.
- **Rates**: `100 × part / whole`, one decimal; "n/a" when the whole is 0.
- **Days** between two events: exact elapsed time divided by 24 hours.

## Hiring

| Metric | Definition |
| --- | --- |
| Time to hire | From the application's creation to its move to **Hired**. Median, 80th percentile and the number of hires. |
| Time in each stage | For Applied, Screening, Interview and Offer: the time from entering the stage to leaving it, from the status history. A stage is measured only once the application has left it (time already spent), so open applications do not drag the figure down. Median and 80th percentile. |
| Funnel conversion | Applications that ever **reached** each stage (from the status history, so a later rejection still counts the stages reached), and the % of the previous stage. |
| Source effectiveness | Per source (career site, internal, referral, job board): applications, % reaching Interview, % hired. Applications record their source; candidates choose career site, referral or job board when applying; internal applications are marked internal. |
| Offers | Offers that left draft, by outcome, plus decline reasons as given by candidates. **Acceptance rate = accepted / (accepted + declined + expired)**. A hired offer stays "accepted". |
| Interviewer load and scorecard timeliness | Per interviewer: interviews assigned (not cancelled), scorecards already due (interview completed and the 24-hour due time passed), % submitted on time, and the median hours from the interview's end to submission. |
| HIRA automation | Counts from HIRA's append-only activity log for jobs in scope: interviews scheduled, reschedules handled, feedback chased, reminders sent, interviewers replaced, and Needs-you items raised. |
| Match score versus outcome | Per fit band (Strong, Good, Partial, Low) from the stored week 2 score: applications, % reaching Interview and % reaching Offer or Hired. **Labelled synthetic**: on demo data it shows the mechanics, not evidence that the score predicts outcomes. |

## People (hr_admin only)

| Metric | Definition |
| --- | --- |
| Leave utilisation by type | For the filter's end year: days **credited** (grants, accruals, carry-forward and HR adjustments from the leave ledger) and days **taken** (approved requests starting that year). % used = taken / credited. Loss of pay has no credit, so it shows days taken only. |
| Absenteeism trend (weekly) | Per ISO week: working person-days (weekly offs and holidays excluded, from each person's joining date) with no check-in and no approved leave, as a % of working person-days. Planned leave counts as neither present nor absent. Days before the first recorded check-in are left out, so weeks before attendance tracking began do not show as 100 % absent. Today is excluded. |
| Late check-in trend (weekly) | Late check-ins as a % of check-ins, per ISO week. "Late" uses the location's shift start plus grace minutes, the same flag as the attendance page. |
| Onboarding completion | Joiners with a checklist, checklists fully done, completion rate, tasks done and tasks overdue (not done and past the due date). |
| Internal mobility moves | Moves recorded by internal hires in the date range (from, to, date), and the number of internal applications in the range. |

## Endpoints

| Endpoint | Returns |
| --- | --- |
| `GET /api/analytics/hiring?from=&to=&department=` | Hiring sections |
| `GET /api/analytics/people?from=&to=&department=` | People sections (hr_admin) |
| `GET /api/analytics/<report>/<section>.csv?...` | One section's table as CSV |

Each section: `{key, title, summary, columns, rows, chart, note}`. Policy action:
`analytics.read` (recruiter, hiring_manager, hr_admin), with the people report
further limited to hr_admin in the view.

## Tests

`backend/tests/test_analytics.py` builds a small fixture with known answers and
checks medians and percentiles, time to hire and time in stage, funnel
conversion, sources, offer acceptance and decline reasons, score versus outcome,
HIRA automation scope, leave utilisation, absenteeism and late trends,
onboarding and mobility counts, role scoping (no data across recruiters),
filters, CSV export and formula-safe cells.
