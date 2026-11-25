import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { ProgressBar } from '@/components/hr';
import { EmptyState, ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { day, type Attention, type OnboardingRow } from '@/lib/hr';

const REL: Record<OnboardingRow['relationship'], string> = { hr: 'HR', manager: 'Your report', buddy: 'You are the buddy' };

function AttentionPanel() {
  const query = useQuery({ queryKey: ['hr-attention'], queryFn: () => api<Attention>('/hr/attention') });
  if (!query.data) return null;
  const { overdue_tasks: overdue, no_buddy: noBuddy } = query.data;
  if (!overdue.length && !noBuddy.length) return null;
  return (
    <section className="mb-6 rounded-xl2 border border-warning/30 bg-warning-soft p-5" aria-labelledby="attention-heading">
      <h2 id="attention-heading" className="font-display text-lg font-semibold text-warning">
        Needs attention
      </h2>
      <ul className="mt-2 space-y-1 text-sm text-ink">
        {overdue.map((t) => (
          <li key={`${t.employee}-${t.title}`}>
            <Link to={`/onboarding/${t.employee}`} className="font-semibold underline">
              {t.name}
            </Link>
            : “{t.title}” was due {day(t.due_on)}
          </li>
        ))}
        {noBuddy.map((e) => (
          <li key={e.employee}>
            <Link to={`/onboarding/${e.employee}`} className="font-semibold underline">
              {e.name}
            </Link>{' '}
            has no buddy yet
          </li>
        ))}
      </ul>
    </section>
  );
}

export function OnboardingPage() {
  useDocumentTitle('Onboarding');
  const { user } = useAuth();
  const [all, setAll] = useState(false);
  const query = useQuery({
    queryKey: ['onboarding', all],
    queryFn: () => api<{ results: OnboardingRow[] }>(`/onboarding${all ? '?all=1' : ''}`),
  });
  return (
    <>
      <PageHeader
        title="Onboarding"
        intro={
          user?.role === 'hr'
            ? 'Every new joiner and their checklist progress.'
            : 'New joiners who report to you or who you are a buddy for.'
        }
        actions={
          <label className="inline-flex min-h-11 items-center gap-2 text-sm">
            <input type="checkbox" checked={all} onChange={(e) => setAll(e.target.checked)} className="h-4 w-4" />
            Include finished
          </label>
        }
      />
      {user?.role === 'hr' && <AttentionPanel />}
      {query.isPending && <PageLoader />}
      {query.isError && <ErrorNote>We could not load onboarding.</ErrorNote>}
      {query.data && query.data.results.length === 0 && <EmptyState title="Nobody is onboarding right now" />}
      {query.data && query.data.results.length > 0 && (
        <ul className="grid gap-4 md:grid-cols-2">
          {query.data.results.map((row) => (
            <li key={row.id} className="glass rounded-xl2 p-5">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <Link
                    to={`/onboarding/${row.id}`}
                    className="font-display text-lg font-semibold text-ink underline-offset-2 hover:underline"
                  >
                    {row.name}
                  </Link>
                  <p className="text-sm text-ink-soft">
                    {row.designation}, {row.department} · {row.code}
                  </p>
                </div>
                <span className="rounded-full bg-primary-soft px-2.5 py-0.5 text-xs font-semibold text-primary-strong">
                  {REL[row.relationship]}
                </span>
              </div>
              <p className="mt-2 text-sm text-muted">
                Joins {day(row.joined_on)} · manager {row.manager ?? 'not set'} · buddy {row.buddy ?? 'not set'}
              </p>
              <div className="mt-3">
                <ProgressBar percent={row.progress.percent} label={`${row.progress.done} of ${row.progress.total} tasks done`} />
              </div>
              {row.overdue > 0 && <p className="mt-2 text-sm font-semibold text-danger">{row.overdue} overdue</p>}
            </li>
          ))}
        </ul>
      )}
    </>
  );
}
