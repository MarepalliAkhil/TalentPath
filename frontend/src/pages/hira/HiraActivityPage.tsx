import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { HiraAvatar } from '@/components/HiraAvatar';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, Pager, SelectField, StatTile, TextField } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { assistant, brand } from '@/lib/brand';
import { formatDate } from '@/lib/format';
import { useDocumentTitle, useMediaQuery } from '@/lib/hooks';
import { ist } from '@/lib/interviews';
import type { HiraItem, HiraSummary, Paginated } from '@/lib/types';

const SERIES = [
  { key: 'scheduled', label: 'Scheduled', color: brand.colors.primary },
  { key: 'rescheduled', label: 'Reschedules and replacements', color: brand.colors.accent },
  { key: 'reminders', label: 'Reminders', color: brand.colors.inkSoft },
  { key: 'chased', label: 'Scorecards chased', color: brand.colors.warning },
  { key: 'needs_you', label: 'Flagged for you', color: brand.colors.danger },
] as const;

function dayLabel(iso: string) {
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-IN', { day: 'numeric', month: 'short' });
}

function ActionsByDay({ summary }: { summary: HiraSummary }) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)');
  const rows = summary.by_day.map((d) => ({ ...d, day: dayLabel(d.date) }));
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby="by-day-heading">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h2 id="by-day-heading" className="font-display text-xl font-semibold text-ink">
          Actions by day (last {summary.days} days)
        </h2>
        <div role="group" aria-label="Chart or table" className="flex gap-1">
          <Button variant={view === 'chart' ? 'primary' : 'ghost'} aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
            Chart
          </Button>
          <Button variant={view === 'table' ? 'primary' : 'ghost'} aria-pressed={view === 'table'} onClick={() => setView('table')}>
            Table
          </Button>
        </div>
      </div>
      {view === 'chart' ? (
        <figure>
          <div
            className="h-72 w-full"
            role="img"
            aria-label="Stacked bar chart of HIRA actions per day. Switch to the table for the exact numbers."
          >
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={brand.colors.canvasDeep} />
                <XAxis dataKey="day" tick={{ fontSize: 11, fill: brand.colors.muted }} interval="preserveStartEnd" />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: brand.colors.muted }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {SERIES.map((s) => (
                  <Bar key={s.key} dataKey={s.key} name={s.label} stackId="day" fill={s.color} isAnimationActive={!reduced} />
                ))}
              </BarChart>
            </ResponsiveContainer>
          </div>
          <figcaption className="mt-2 text-xs text-muted">
            Each bar is one IST calendar day. Counts come from HIRA's activity log.
          </figcaption>
        </figure>
      ) : (
        <div className="overflow-x-auto" role="region" aria-label="Actions by day table" tabIndex={0}>
          <table className="w-full min-w-[36rem] text-left text-sm">
            <caption className="sr-only">HIRA actions per day</caption>
            <thead>
              <tr className="border-b border-ink/10 text-muted">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Day
                </th>
                {SERIES.map((s) => (
                  <th key={s.key} scope="col" className="py-2 pr-3 font-semibold">
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {summary.by_day.map((d) => (
                <tr key={d.date} className="border-b border-ink/5">
                  <th scope="row" className="py-1.5 pr-3 font-medium text-ink">
                    {formatDate(d.date)}
                  </th>
                  {SERIES.map((s) => (
                    <td key={s.key} className="py-1.5 pr-3 tabular-nums">
                      {d[s.key]}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function NeedsYou({ items }: { items: HiraItem[] }) {
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby="needs-heading">
      <h2 id="needs-heading" className="mb-3 font-display text-xl font-semibold text-ink">
        Needs you <span className="text-base font-normal text-muted">({items.length})</span>
      </h2>
      {items.length ? (
        <ul className="space-y-2">
          {items.map((item) => (
            <li key={item.id} className="rounded-xl border border-accent/30 bg-accent-soft/60 p-3 text-sm">
              <p className="font-semibold text-ink">{item.label}</p>
              <p className="text-ink-soft">
                {item.candidate} · {item.job?.title}
                {item.round && ` · ${item.round}`} · {ist(item.created_at)}
              </p>
              {item.link && (
                <Link to={item.link} className="font-semibold text-primary-strong underline">
                  Open
                  <span className="sr-only">
                    {' '}
                    {item.label} for {item.candidate}
                  </span>
                </Link>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">Nothing needs you right now. HIRA will flag anything it cannot solve.</p>
      )}
    </section>
  );
}

export function HiraActivityPage() {
  useDocumentTitle('HIRA activity');
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ action: '', from: '', to: '', needs_you: '' });
  const summary = useQuery({ queryKey: ['hira-summary'], queryFn: () => api<HiraSummary>('/hira/activity/summary') });
  const rows = useQuery({
    queryKey: ['hira-activity', page, filters],
    queryFn: () => api<Paginated<HiraItem>>(`/hira/activity${qs({ page, ...filters })}`),
    placeholderData: keepPreviousData,
  });
  const set = (key: keyof typeof filters, value: string) => {
    setFilters({ ...filters, [key]: value });
    setPage(1);
  };
  const k = summary.data?.kpis;

  return (
    <>
      <PageHeader
        title="HIRA activity"
        intro={`What ${assistant.display} did for you: every action is logged, and anything it could not solve is listed under Needs you.`}
        actions={<HiraAvatar pose="explain" size={56} />}
      />
      {summary.isPending && <PageLoader />}
      {summary.isError && <ErrorNote>We could not load HIRA's activity.</ErrorNote>}
      {k && summary.data && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatTile label="Interviews scheduled" value={k.scheduled} />
            <StatTile label="Reschedules handled" value={k.reschedules} />
            <StatTile label="Scorecards chased" value={k.chased} />
            <StatTile label="Needs you" value={k.needs_you} />
          </div>
          <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
            <ActionsByDay summary={summary.data} />
            <NeedsYou items={summary.data.needs_you} />
          </div>
        </>
      )}
      <section className="mt-8" aria-labelledby="log-heading">
        <h2 id="log-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Activity log
        </h2>
        <form
          aria-label="Activity filters"
          className="glass mb-4 grid gap-3 rounded-xl2 p-4 sm:grid-cols-4"
          onSubmit={(e) => e.preventDefault()}
        >
          <SelectField label="Action" value={filters.action} onChange={(e) => set('action', e.target.value)}>
            <option value="">All actions</option>
            {summary.data?.actions.map((a) => (
              <option key={a.value} value={a.value}>
                {a.label}
              </option>
            ))}
          </SelectField>
          <TextField label="From" type="date" value={filters.from} onChange={(e) => set('from', e.target.value)} />
          <TextField label="To" type="date" value={filters.to} onChange={(e) => set('to', e.target.value)} />
          <SelectField label="Show" value={filters.needs_you} onChange={(e) => set('needs_you', e.target.value)}>
            <option value="">Everything</option>
            <option value="1">Flagged for a person</option>
          </SelectField>
        </form>
        {rows.data && rows.data.results.length === 0 && <EmptyState title="No activity matches these filters" />}
        {rows.data && rows.data.results.length > 0 && (
          <div className="glass overflow-x-auto rounded-xl2" role="region" aria-label="Activity log table" tabIndex={0}>
            <table className="w-full min-w-[40rem] text-left text-sm">
              <caption className="sr-only">HIRA activity log, newest first</caption>
              <thead>
                <tr className="border-b border-ink/10 text-muted">
                  <th scope="col" className="px-4 py-2 font-semibold">
                    When (IST)
                  </th>
                  <th scope="col" className="px-4 py-2 font-semibold">
                    Action
                  </th>
                  <th scope="col" className="px-4 py-2 font-semibold">
                    Job
                  </th>
                  <th scope="col" className="px-4 py-2 font-semibold">
                    Candidate
                  </th>
                  <th scope="col" className="px-4 py-2 font-semibold">
                    Reason
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.data.results.map((r) => (
                  <tr key={r.id} className="border-b border-ink/5">
                    <td className="whitespace-nowrap px-4 py-2 text-ink-soft">{ist(r.created_at)}</td>
                    <td className="px-4 py-2 font-medium text-ink">
                      {r.label}
                      {r.needs_you && <span className="ml-2 rounded-full bg-accent-soft px-2 text-xs text-accent">Flagged</span>}
                    </td>
                    <td className="px-4 py-2 text-ink-soft">{r.job?.title}</td>
                    <td className="px-4 py-2 text-ink-soft">{r.candidate}</td>
                    <td className="px-4 py-2 text-muted">{r.reason_code.replace(/_/g, ' ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager page={page} hasNext={Boolean(rows.data?.next)} hasPrevious={Boolean(rows.data?.previous)} onChange={setPage} />
      </section>
    </>
  );
}
