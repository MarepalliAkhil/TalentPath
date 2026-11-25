import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Dialog } from '@/components/Dialog';
import { BandPill, ResumeCard } from '@/components/growth';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, SuccessNote } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import type { InternalJobs } from '@/lib/growth';
import { useDocumentTitle } from '@/lib/hooks';
import { errorText } from '@/lib/pipeline';

type Job = InternalJobs['jobs'][number];

/** Internal jobs with my match; one-click apply with my profile resume. The manager-notice rule is shown first. */
export function InternalJobsPage() {
  useDocumentTitle('Internal jobs');
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['internal-jobs'], queryFn: () => api<InternalJobs>('/internal/jobs'), retry: false });
  const [confirm, setConfirm] = useState<Job | null>(null);
  const [message, setMessage] = useState('');
  const apply = useMutation({
    mutationFn: (job: Job) => api<{ id: string; job: string }>(`/internal/jobs/${job.id}/apply`, { method: 'POST', body: {} }),
    onSuccess: (data) => {
      setConfirm(null);
      setMessage(`Application sent for ${data.job}.`);
      void client.invalidateQueries({ queryKey: ['internal-jobs'] });
    },
  });
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>{errorText(query.error)}</ErrorNote>;
  const data = query.data;
  return (
    <>
      <PageHeader title="Internal jobs" intro="Open roles you can move into, with your match from the same scorer recruiters use." />
      <section
        className="mb-6 rounded-xl2 border border-primary/20 bg-primary-soft/60 p-4 text-sm text-primary-strong"
        aria-labelledby="rule-heading"
      >
        <h2 id="rule-heading" className="font-semibold">
          Before you apply
        </h2>
        <p className="mt-1">{data.rule.text}</p>
        {data.rule.manager && <p className="mt-1">Your reporting manager is {data.rule.manager}.</p>}
      </section>
      {message && <SuccessNote>{message}</SuccessNote>}
      {!data.has_resume && (
        <div className="mb-6">
          <ResumeCard compact />
        </div>
      )}
      {data.applications.length > 0 && (
        <section className="glass mb-6 rounded-xl2 p-5" aria-labelledby="mine-heading">
          <h2 id="mine-heading" className="font-display text-lg font-semibold text-ink">
            My internal applications
          </h2>
          <ul className="mt-2 space-y-1 text-sm">
            {data.applications.map((a) => (
              <li key={a.id} className="flex justify-between gap-2">
                <span className="text-ink">{a.job}</span>
                <span className="text-ink-soft">
                  {a.status_label} · {formatDate(a.applied_at)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      {data.jobs.length === 0 ? (
        <EmptyState title="No internal jobs are open right now" />
      ) : (
        <ul className="grid gap-3 md:grid-cols-2">
          {data.jobs.map((job) => (
            <li key={job.id} className="glass flex flex-col gap-2 rounded-xl2 p-4">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-display text-lg font-semibold text-ink">{job.title}</h2>
                <BandPill band={job.band} label={job.band_label} score={job.score} />
              </div>
              <p className="text-sm text-ink-soft">
                {job.department} · {job.location} · {job.level}
                {job.audience === 'internal' && ' · internal only'}
              </p>
              <div className="mt-auto flex flex-wrap items-center gap-3">
                <Link to={`/career/jobs/${job.id}`} className="text-sm font-semibold text-primary-strong underline">
                  Skill map<span className="sr-only"> for {job.title}</span>
                </Link>
                {job.applied ? (
                  <span className="text-sm font-semibold text-success">Applied</span>
                ) : (
                  <Button variant="secondary" onClick={() => setConfirm(job)} disabled={!data.has_resume}>
                    Apply<span className="sr-only"> for {job.title}</span>
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
      {confirm && (
        <Dialog title={`Apply for ${confirm.title}?`} onClose={() => setConfirm(null)}>
          <p className="text-sm text-ink-soft">
            We send the resume on your profile. It goes through the same screening as every application.
          </p>
          <p className="mt-2 text-sm font-semibold text-ink">{data.rule.text}</p>
          {apply.isError && <ErrorNote>{errorText(apply.error)}</ErrorNote>}
          <div className="mt-4 flex gap-2">
            <Button onClick={() => apply.mutate(confirm)} disabled={apply.isPending}>
              {apply.isPending ? 'Sending…' : 'Send application'}
            </Button>
            <Button variant="ghost" onClick={() => setConfirm(null)}>
              Cancel
            </Button>
          </div>
        </Dialog>
      )}
    </>
  );
}
