import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { EmptyState, PageHeader, PageLoader, StatTile, StatusBadge, buttonClass } from '@/components/ui';
import { api } from '@/lib/api';
import { firstName } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Paginated, StaffJob, Summary } from '@/lib/types';

const TITLES = {
  recruiter: 'Hiring overview',
  manager: 'Your hiring',
  hr: 'HR overview',
} as const;

export function StaffOverview({ role }: { role: keyof typeof TITLES }) {
  const title = TITLES[role];
  useDocumentTitle(title);
  const { user } = useAuth();
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/dashboard/summary') });
  const jobs = useQuery({ queryKey: ['jobs', 'recent'], queryFn: () => api<Paginated<StaffJob>>('/jobs?page_size=6') });
  const s = summary.data;
  const jobsLink = role === 'hr' ? '/hr/jobs' : '/recruiter/jobs';

  return (
    <>
      <PageHeader
        title={title}
        intro={user ? `Welcome back, ${firstName(user.full_name)}.` : undefined}
        actions={
          role === 'recruiter' ? (
            <Link to="/recruiter/jobs/new" className={buttonClass('primary')}>
              Post a job
            </Link>
          ) : undefined
        }
      />
      {summary.isPending && <PageLoader />}
      {s && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatTile label="Open jobs" value={s.jobs_by_status?.open ?? 0} />
          <StatTile label="Applications" value={s.applications_total ?? 0} />
          <StatTile label="New (not yet screened)" value={s.applications_by_status?.applied ?? 0} />
          <StatTile label="In interviews" value={s.applications_by_status?.interview ?? 0} />
        </div>
      )}
      {s?.users_by_role && (
        <section className="mt-8" aria-labelledby="people-heading">
          <h2 id="people-heading" className="font-display text-xl font-semibold text-ink">
            Active accounts
          </h2>
          <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
            {Object.entries(s.users_by_role).map(([r, n]) => (
              <div key={r} className="glass rounded-xl2 p-4">
                <dt className="text-sm capitalize text-muted">{r.replace('_', ' ')}</dt>
                <dd className="font-display text-2xl font-semibold">{n}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}
      <section className="mt-10" aria-labelledby="jobs-heading">
        <div className="mb-3 flex items-end justify-between">
          <h2 id="jobs-heading" className="font-display text-xl font-semibold text-ink">
            {role === 'manager' ? 'Jobs assigned to you' : 'Recent jobs'}
          </h2>
          {role !== 'manager' && (
            <Link to={jobsLink} className="text-sm font-semibold text-primary-strong hover:underline">
              See all
            </Link>
          )}
        </div>
        {jobs.data?.results.length === 0 && <EmptyState title="No jobs yet" />}
        <ul className="grid gap-3 md:grid-cols-2">
          {jobs.data?.results.map((job) => (
            <li key={job.id} className="glass flex items-center justify-between gap-3 rounded-xl2 p-4">
              <div>
                <p className="font-semibold text-ink">{job.title}</p>
                <p className="text-sm text-muted">
                  {job.location.name} · {job.application_count ?? 0} applicants
                </p>
              </div>
              <div className="flex flex-col items-end gap-2">
                <StatusBadge status={job.status} label={job.status_label} />
                <span className="flex gap-3">
                  <Link to={`/recruiter/jobs/${job.id}/applications`} className="text-sm font-semibold text-primary-strong hover:underline">
                    Candidates<span className="sr-only"> for {job.title}</span>
                  </Link>
                  <Link to={`/recruiter/jobs/${job.id}/board`} className="text-sm font-semibold text-primary-strong hover:underline">
                    Board<span className="sr-only"> for {job.title}</span>
                  </Link>
                </span>
              </div>
            </li>
          ))}
        </ul>
      </section>
    </>
  );
}
