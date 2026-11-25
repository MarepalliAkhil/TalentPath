import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, Pager, StatusBadge, buttonClass } from '@/components/ui';
import { api, ApiError, qs } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Paginated, StaffJob } from '@/lib/types';

const TABS = [
  { value: '', label: 'All' },
  { value: 'open', label: 'Open' },
  { value: 'draft', label: 'Drafts' },
  { value: 'closed', label: 'Closed' },
];

const NEXT_ACTION: Record<StaffJob['status'], { to: string; label: string }> = {
  draft: { to: 'open', label: 'Publish' },
  open: { to: 'closed', label: 'Close' },
  closed: { to: 'open', label: 'Reopen' },
};

export function JobsManagePage({ scope }: { scope: 'mine' | 'all' }) {
  const title = scope === 'mine' ? 'My jobs' : 'All jobs';
  useDocumentTitle(title);
  const client = useQueryClient();
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [error, setError] = useState('');
  const jobs = useQuery({
    queryKey: ['jobs', status, page],
    queryFn: () => api<Paginated<StaffJob>>(`/jobs${qs({ status, page })}`),
  });
  const move = useMutation({
    mutationFn: ({ id, to }: { id: string; to: string }) => api<StaffJob>(`/jobs/${id}/status`, { method: 'POST', body: { status: to } }),
    onSuccess: () => {
      setError('');
      void client.invalidateQueries({ queryKey: ['jobs'] });
    },
    onError: (e) => setError(e instanceof ApiError ? (Object.values(e.fieldErrors)[0] ?? e.message) : 'Could not update the job.'),
  });

  return (
    <>
      <PageHeader
        title={title}
        intro={scope === 'mine' ? 'Jobs you created. Publish when a hiring manager and skills are set.' : 'Every job in the organisation.'}
        actions={
          <Link to="/recruiter/jobs/new" className={buttonClass('primary')}>
            Post a job
          </Link>
        }
      />
      <div role="group" aria-label="Filter by status" className="mb-4 flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            aria-pressed={status === tab.value}
            onClick={() => {
              setStatus(tab.value);
              setPage(1);
            }}
            className={`min-h-10 rounded-full px-4 text-sm font-semibold ${status === tab.value ? 'bg-ink text-white' : 'bg-white/70 text-ink-soft hover:text-ink'}`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {jobs.isPending && <PageLoader />}
      {jobs.data?.results.length === 0 && <EmptyState title="No jobs here yet" />}
      <ul className="flex flex-col gap-3">
        {jobs.data?.results.map((job) => {
          const action = NEXT_ACTION[job.status];
          return (
            <li key={job.id} className="glass flex flex-col gap-3 rounded-xl2 p-4 md:flex-row md:items-center">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-ink">{job.title}</h2>
                  <StatusBadge status={job.status} label={job.status_label} />
                </div>
                <p className="text-sm text-muted">
                  {job.department.name} · {job.location.name} · {job.application_count ?? 0} applicants · Manager:{' '}
                  {job.hiring_manager?.name ?? 'not assigned'} · Updated {formatDate(job.updated_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link to={`/recruiter/jobs/${job.id}/applications`} className={buttonClass('secondary')}>
                  Candidates<span className="sr-only"> for {job.title}</span>
                </Link>
                <Link to={`/recruiter/jobs/${job.id}/board`} className={buttonClass('secondary')}>
                  Board<span className="sr-only"> for {job.title}</span>
                </Link>
                {job.status !== 'closed' && (
                  <Link to={`/recruiter/jobs/${job.id}/edit`} className={buttonClass('secondary')}>
                    Edit<span className="sr-only"> {job.title}</span>
                  </Link>
                )}
                <Button variant="ghost" disabled={move.isPending} onClick={() => move.mutate({ id: job.id, to: action.to })}>
                  {action.label}
                  <span className="sr-only"> {job.title}</span>
                </Button>
              </div>
            </li>
          );
        })}
      </ul>
      <Pager page={page} hasNext={Boolean(jobs.data?.next)} hasPrevious={Boolean(jobs.data?.previous)} onChange={setPage} />
    </>
  );
}
