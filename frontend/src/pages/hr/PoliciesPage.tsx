import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation } from 'react-router-dom';
import { ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { day, WEEKDAY_NAMES, type Policies } from '@/lib/hr';

/** Handbook, my location's leave rules, shift and holidays. Ask HIRA links here with #anchors. */
export function PoliciesPage() {
  useDocumentTitle('Policies and holidays');
  const { hash } = useLocation();
  const query = useQuery({ queryKey: ['hr-policies'], queryFn: () => api<Policies>('/hr/policies') });

  useEffect(() => {
    if (!hash || !query.data) return;
    const target = document.getElementById(hash.slice(1));
    if (target) {
      target.scrollIntoView?.({ block: 'start' });
      target.focus({ preventScroll: true });
    }
  }, [hash, query.data]);

  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not load the policies.</ErrorNote>;
  const data = query.data;
  const wp = data.work_policy;
  return (
    <>
      <PageHeader
        title="Policies and holidays"
        intro={data.location ? `Rules for ${data.location.name}. HR keeps them up to date in HR settings.` : 'The employee handbook.'}
      />
      <nav aria-label="On this page" className="mb-6 flex flex-wrap gap-2 text-sm">
        {data.leave_types.length > 0 && (
          <a href="#leave-rules" className="rounded-full bg-white/70 px-3 py-1.5 font-semibold text-primary-strong underline">
            Leave rules
          </a>
        )}
        {data.holidays.length > 0 && (
          <a href="#holidays" className="rounded-full bg-white/70 px-3 py-1.5 font-semibold text-primary-strong underline">
            Holidays
          </a>
        )}
        <a href="#handbook" className="rounded-full bg-white/70 px-3 py-1.5 font-semibold text-primary-strong underline">
          Handbook
        </a>
      </nav>

      {data.leave_types.length > 0 && (
        <section id="leave-rules" tabIndex={-1} className="mb-8 scroll-mt-20" aria-labelledby="leave-rules-heading">
          <h2 id="leave-rules-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            Leave rules
          </h2>
          <ul className="grid gap-3 md:grid-cols-2">
            {data.leave_types.map((lt) => (
              <li key={lt.id} id={`leave-${lt.code}`} tabIndex={-1} className="glass scroll-mt-20 rounded-xl2 p-4">
                <h3 className="font-semibold text-ink">{lt.name}</h3>
                <p className="mt-1 text-sm text-ink-soft">{lt.summary}</p>
              </li>
            ))}
          </ul>
          {wp && (
            <p className="mt-3 text-sm text-ink-soft">
              General shift {wp.shift_start} to {wp.shift_end}, {wp.late_grace_minutes} minutes grace. Weekly off:{' '}
              {wp.weekly_off.map((d) => WEEKDAY_NAMES[d - 1]).join(' and ')}. Leave longer than {wp.hr_approval_over_days} days also needs
              HR. Requests waiting more than {wp.escalate_after_hours} hours go to the approver’s manager.
            </p>
          )}
        </section>
      )}

      {data.holidays.length > 0 && (
        <section id="holidays" tabIndex={-1} className="mb-8 scroll-mt-20" aria-labelledby="holidays-heading">
          <h2 id="holidays-heading" className="font-display text-xl font-semibold text-ink">
            Holidays
          </h2>
          <p className="mb-3 text-sm text-warning">
            Demo calendar: verify every date against the official government list before relying on it.
          </p>
          <ul className="glass divide-y divide-ink/10 rounded-xl2 px-4 text-sm">
            {data.holidays.map((h) => (
              <li key={h.id} className="flex justify-between gap-3 py-2">
                <span className="text-ink">
                  {h.name}
                  {h.regional && (
                    <span className="ml-2 rounded-full bg-primary-soft px-2 py-0.5 text-xs font-semibold text-primary-strong">State</span>
                  )}
                </span>
                <span className="shrink-0 text-ink-soft">{day(h.date)}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section id="handbook" aria-labelledby="handbook-heading">
        <h2 id="handbook-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Handbook
        </h2>
        <div className="space-y-3">
          {data.handbook.map((s) => (
            <article key={s.slug} id={s.slug} tabIndex={-1} className="glass scroll-mt-20 rounded-xl2 p-5">
              <h3 className="font-semibold text-ink">{s.title}</h3>
              <p className="mt-1 text-sm leading-relaxed text-ink-soft">{s.body}</p>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}
