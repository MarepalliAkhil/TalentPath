import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { dateRange, day, monthLabel, shiftMonth, thisMonth, type TeamCalendar } from '@/lib/hr';

type Cell = { status: 'approved' | 'pending'; half: string } | null;

function cellFor(cal: TeamCalendar, member: string, date: string): Cell {
  const entry = cal.entries.find((e) => e.employee === member && e.start <= date && date <= e.end);
  return entry ? { status: entry.status, half: entry.half } : null;
}

/** Team-level only: peers see who is off; the leave type and reason are shown to the team's manager and HR. */
export function TeamCalendarPage() {
  useDocumentTitle('Team calendar');
  const [month, setMonth] = useState(thisMonth());
  const [view, setView] = useState<'team' | 'reports'>('team');
  const query = useQuery({
    queryKey: ['team-calendar', month, view],
    queryFn: () => api<TeamCalendar>(`/team-calendar?month=${month}${view === 'reports' ? '&view=reports' : ''}`),
    retry: false,
  });

  const header = (
    <PageHeader
      title="Team calendar"
      intro="Approved and pending leave, holidays and joiners. Plan around busy days; clash warnings appear when you apply."
    />
  );
  if (query.isPending) return (<>{header}<PageLoader /></>);
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <>
        {header}
        {missing ? <EmptyState title="No employee record yet" /> : <ErrorNote>We could not load the calendar.</ErrorNote>}
      </>
    );
  }
  const cal = query.data;
  const holidays = cal.days.filter((d) => d.kind === 'holiday');
  return (
    <>
      {header}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
            ‹
          </Button>
          <h2 className="min-w-40 text-center font-display text-lg font-semibold text-ink" aria-live="polite">
            {monthLabel(cal.month)}
          </h2>
          <Button variant="secondary" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Next month">
            ›
          </Button>
        </div>
        {cal.has_reports && (
          <div role="group" aria-label="Whose calendar" className="flex gap-1 rounded-xl bg-white/70 p-1">
            {(['team', 'reports'] as const).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={`min-h-11 rounded-lg px-3 text-sm font-semibold ${view === v ? 'bg-primary text-white' : 'text-ink-soft'}`}
              >
                {v === 'team' ? 'My team' : 'My reports'}
              </button>
            ))}
          </div>
        )}
      </div>
      <p className="mb-2 text-sm text-ink-soft">
        {cal.team.name} · {cal.team.members.length} people · warn below {cal.threshold_pct}% available
      </p>

      <div className="glass overflow-x-auto rounded-xl2 p-2" tabIndex={0} role="region" aria-label="Calendar grid (scrolls sideways)">
        <table className="border-separate border-spacing-0.5 text-xs">
          <caption className="sr-only">
            Leave by person and day for {monthLabel(cal.month)}. A means approved, P means pending, H means holiday.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="sticky left-0 z-10 bg-canvas px-2 text-left font-semibold text-ink">
                Person
              </th>
              {cal.days.map((d) => (
                <th key={d.date} scope="col" className={`w-7 text-center font-medium ${d.kind !== 'working' ? 'text-muted' : 'text-ink'}`} title={d.holiday || undefined}>
                  {Number(d.date.slice(8))}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cal.team.members.map((m) => (
              <tr key={m.id}>
                <th scope="row" className="sticky left-0 z-10 whitespace-nowrap bg-canvas px-2 text-left font-medium text-ink">
                  {m.name}
                  {m.id === cal.me && <span className="text-muted"> (you)</span>}
                </th>
                {cal.days.map((d) => {
                  const c = cellFor(cal, m.id, d.date);
                  const label = c ? (c.status === 'approved' ? 'A' : 'P') : d.kind === 'holiday' ? 'H' : '';
                  const style = c
                    ? c.status === 'approved'
                      ? 'bg-accent text-white'
                      : 'bg-warning-soft text-warning border border-warning/40'
                    : d.kind === 'holiday'
                      ? 'bg-primary-soft text-primary-strong'
                      : d.kind === 'weekly_off'
                        ? 'bg-canvas-deep'
                        : 'bg-white/80';
                  return (
                    <td key={d.date} className={`h-7 w-7 rounded text-center font-semibold ${style}`}>
                      {label}
                      {c?.half && '½'}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 flex flex-wrap gap-3 text-xs text-ink-soft">
        <span><span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded bg-accent align-middle" />A approved</span>
        <span><span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded border border-warning/40 bg-warning-soft align-middle" />P pending</span>
        <span><span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded bg-primary-soft align-middle" />H holiday</span>
        <span><span aria-hidden="true" className="mr-1 inline-block h-3 w-3 rounded bg-canvas-deep align-middle" />weekly off</span>
      </p>

      <div className="mt-6 grid gap-6 md:grid-cols-2">
        <section className="glass rounded-xl2 p-5" aria-labelledby="off-heading">
          <h2 id="off-heading" className="font-display text-lg font-semibold text-ink">
            Who is off
          </h2>
          {cal.entries.length ? (
            <ul className="mt-2 space-y-2 text-sm">
              {cal.entries.map((e) => (
                <li key={e.id}>
                  <span className="font-semibold text-ink">{e.name}</span>: {dateRange(e.start, e.end, e.half)} ({e.status})
                  {e.type && <span className="block text-xs text-muted">{e.type}{e.reason ? `: ${e.reason}` : ''}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-2 text-sm text-muted">Nobody is off this month.</p>
          )}
          {!cal.sees_reasons && <p className="mt-3 text-xs text-muted">Leave types and reasons are visible only to the team’s manager and HR.</p>}
        </section>
        <section className="glass rounded-xl2 p-5" aria-labelledby="hol-heading">
          <h2 id="hol-heading" className="font-display text-lg font-semibold text-ink">
            Holidays and joiners
          </h2>
          <ul className="mt-2 space-y-1 text-sm">
            {holidays.map((h) => (
              <li key={h.date}>
                {day(h.date, false)}: {h.holiday}
              </li>
            ))}
            {cal.joiners.map((j) => (
              <li key={j.name}>
                {day(j.joined_on, false)}: <span className="font-semibold">{j.name}</span> joins as {j.designation}
              </li>
            ))}
            {!holidays.length && !cal.joiners.length && <li className="text-muted">None this month.</li>}
          </ul>
        </section>
      </div>
    </>
  );
}
