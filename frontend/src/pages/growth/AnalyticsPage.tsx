import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { useAuth } from '@/auth/AuthContext';
import { Button, ErrorNote, PageHeader, PageLoader, SelectField, TextField } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { brand } from '@/lib/brand';
import type { AnalyticsReport, Section } from '@/lib/growth';
import { useDocumentTitle, useMediaQuery } from '@/lib/hooks';

const COLORS = [brand.colors.primary, brand.colors.accent, brand.colors.inkSoft];

function cell(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === '') return '–';
  return String(value);
}

function ChartBlock({ section }: { section: Section }) {
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)');
  const chart = section.chart!;
  const data = section.rows.map((row) =>
    Object.fromEntries(Object.entries(row).map(([k, v]) => [k, typeof v === 'number' || v === null ? v : String(v)])),
  );
  const common = { data, margin: { top: 8, right: 8, bottom: 8, left: -16 } };
  return (
    <figure>
      <div className="h-64 w-full" role="img" aria-label={`${section.title}: ${section.summary} Switch to the table for exact numbers.`}>
        <ResponsiveContainer width="100%" height="100%">
          {chart.type === 'line' ? (
            <LineChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke={brand.colors.canvasDeep} />
              <XAxis dataKey={chart.x} tick={{ fontSize: 11, fill: brand.colors.muted }} />
              <YAxis tick={{ fontSize: 11, fill: brand.colors.muted }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {chart.series.map((s, i) => (
                <Line
                  key={s.key}
                  dataKey={s.key}
                  name={s.label}
                  stroke={COLORS[i % COLORS.length]}
                  strokeWidth={2}
                  isAnimationActive={!reduced}
                />
              ))}
            </LineChart>
          ) : (
            <BarChart {...common}>
              <CartesianGrid strokeDasharray="3 3" stroke={brand.colors.canvasDeep} />
              <XAxis dataKey={chart.x} tick={{ fontSize: 11, fill: brand.colors.muted }} interval={0} />
              <YAxis tick={{ fontSize: 11, fill: brand.colors.muted }} />
              <Tooltip />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              {chart.series.map((s, i) => (
                <Bar key={s.key} dataKey={s.key} name={s.label} fill={COLORS[i % COLORS.length]} isAnimationActive={!reduced} />
              ))}
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </figure>
  );
}

function TableBlock({ section }: { section: Section }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label={`${section.title} table`} tabIndex={0}>
      <table className="w-full text-left text-sm">
        <caption className="sr-only">{section.title}</caption>
        <thead>
          <tr className="border-b border-ink/10 text-muted">
            {section.columns.map((c) => (
              <th key={c.key} scope="col" className="py-2 pr-3 font-semibold">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {section.rows.map((row, i) => (
            <tr key={i} className="border-b border-ink/5">
              {section.columns.map((c, j) =>
                j === 0 ? (
                  <th key={c.key} scope="row" className="py-1.5 pr-3 font-medium text-ink">
                    {cell(row[c.key])}
                  </th>
                ) : (
                  <td key={c.key} className="py-1.5 pr-3 tabular-nums">
                    {cell(row[c.key])}
                  </td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function SectionCard({ section, report, filters }: { section: Section; report: string; filters: Record<string, string> }) {
  const [view, setView] = useState<'chart' | 'table'>(section.chart && section.rows.length ? 'chart' : 'table');
  const id = `section-${section.key}`;
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby={id}>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 id={id} className="font-display text-lg font-semibold text-ink">
          {section.title}
        </h2>
        <div className="flex flex-wrap items-center gap-1">
          {section.chart && section.rows.length > 0 && (
            <div role="group" aria-label={`${section.title}: chart or table`} className="flex gap-1">
              <Button variant={view === 'chart' ? 'primary' : 'ghost'} aria-pressed={view === 'chart'} onClick={() => setView('chart')}>
                Chart
              </Button>
              <Button variant={view === 'table' ? 'primary' : 'ghost'} aria-pressed={view === 'table'} onClick={() => setView('table')}>
                Table
              </Button>
            </div>
          )}
          <a
            href={`/api/analytics/${report}/${section.key}.csv${qs(filters)}`}
            className="inline-flex min-h-11 items-center px-2 text-sm font-semibold text-primary-strong underline"
            download
          >
            CSV<span className="sr-only"> of {section.title}</span>
          </a>
        </div>
      </div>
      <p className="mb-3 text-sm text-ink" data-testid={`summary-${section.key}`}>
        {section.summary}
      </p>
      {view === 'chart' && section.chart ? <ChartBlock section={section} /> : <TableBlock section={section} />}
      {section.note && <p className="mt-2 text-xs text-muted">{section.note}</p>}
    </section>
  );
}

export function AnalyticsPage() {
  useDocumentTitle('Analytics');
  const { user } = useAuth();
  const [report, setReport] = useState<'hiring' | 'people'>('hiring');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [department, setDepartment] = useState('');
  const filters: Record<string, string> = {};
  if (from) filters.from = from;
  if (to) filters.to = to;
  if (department) filters.department = department;
  const query = useQuery({
    queryKey: ['analytics', report, from, to, department],
    queryFn: () => api<AnalyticsReport>(`/analytics/${report}${qs(filters)}`),
  });
  const isAdmin = user?.role === 'hr';
  return (
    <>
      <PageHeader
        title="Analytics"
        intro={
          isAdmin
            ? 'Hiring and people metrics across the company, computed on the server from the records themselves.'
            : 'Hiring metrics for the jobs you own or are assigned to, computed on the server from the records themselves.'
        }
      />
      {isAdmin && (
        <div role="group" aria-label="Report" className="mb-4 flex gap-1">
          {(['hiring', 'people'] as const).map((r) => (
            <Button key={r} variant={report === r ? 'primary' : 'ghost'} aria-pressed={report === r} onClick={() => setReport(r)}>
              {r === 'hiring' ? 'Hiring' : 'People'}
            </Button>
          ))}
        </div>
      )}
      <form className="glass mb-6 grid gap-3 rounded-xl2 p-4 sm:grid-cols-3" aria-label="Filters" onSubmit={(e) => e.preventDefault()}>
        <TextField label="From" type="date" value={from || query.data?.from || ''} onChange={(e) => setFrom(e.target.value)} />
        <TextField label="To" type="date" value={to || query.data?.to || ''} onChange={(e) => setTo(e.target.value)} />
        <SelectField label="Department" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {query.data?.departments.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </SelectField>
      </form>
      {query.isPending && <PageLoader />}
      {query.isError && <ErrorNote>We could not load analytics. Check the dates.</ErrorNote>}
      {query.data && (
        <div className="grid gap-4 lg:grid-cols-2">
          {query.data.sections.map((s) => (
            <SectionCard key={`${report}-${s.key}`} section={s} report={report} filters={filters} />
          ))}
        </div>
      )}
    </>
  );
}
