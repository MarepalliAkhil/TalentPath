import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, Pager, StatusBadge } from '@/components/ui';
import { api, ApiError, qs } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Paginated, StaffApplication } from '@/lib/types';

const LABELS: Record<string, string> = {
  screening: 'Move to screening',
  interview: 'Move to interview',
  offer: 'Move to offer',
  rejected: 'Not selected',
};

function Detail({ id }: { id: string }) {
  const detail = useQuery({ queryKey: ['application', id], queryFn: () => api<StaffApplication>(`/applications/${id}`) });
  if (detail.isPending) return <PageLoader label="Loading resume" />;
  if (!detail.data) return <ErrorNote>Could not load this application.</ErrorNote>;
  const d = detail.data;
  return (
    <div className="mt-4 grid gap-4 border-t border-ink/10 pt-4 lg:grid-cols-[1fr_16rem]">
      <div>
        <h3 className="text-sm font-semibold text-ink">Resume text (extracted on the server)</h3>
        <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-canvas p-3 font-sans text-sm text-ink-soft" tabIndex={0}>
          {d.resume_text || 'No readable text in this file.'}
        </pre>
      </div>
      <div className="space-y-3 text-sm">
        {d.cover_note && (
          <div>
            <h3 className="font-semibold text-ink">Note from the candidate</h3>
            <p className="mt-1 text-ink-soft">{d.cover_note}</p>
          </div>
        )}
        <a href={`/api/applications/${d.id}/resume`} className="inline-flex font-semibold text-primary-strong underline" download>
          Download original ({d.resume_filename})
        </a>
        <ol className="space-y-1 text-muted" aria-label="Status history">
          {d.events?.map((e) => (
            <li key={e.at}>
              {e.label} · {formatDate(e.at)}
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

export function JobApplicationsPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const canMove = user?.role === 'recruiter' || user?.role === 'hr_admin';
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const apps = useQuery({
    queryKey: ['job-applications', id, page],
    queryFn: () => api<Paginated<StaffApplication> & { job: { id: string; title: string; status: string } }>(`/jobs/${id}/applications${qs({ page })}`),
  });
  useDocumentTitle(apps.data ? `Applicants · ${apps.data.job.title}` : 'Applicants');
  const move = useMutation({
    mutationFn: ({ appId, status }: { appId: string; status: string }) =>
      api(`/applications/${appId}/status`, { method: 'POST', body: { status } }),
    onSuccess: () => {
      setError('');
      void client.invalidateQueries({ queryKey: ['job-applications', id] });
    },
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Could not update the application.'),
  });

  if (apps.isPending) return <PageLoader />;
  if (apps.isError || !apps.data) return <ErrorNote>We could not load applicants for this job.</ErrorNote>;

  return (
    <>
      <PageHeader title={`Applicants · ${apps.data.job.title}`} intro={`${apps.data.count} ${apps.data.count === 1 ? "application" : "applications"}. Open one to read the extracted resume.`} />
      {error && <ErrorNote>{error}</ErrorNote>}
      {apps.data.results.length === 0 && <EmptyState title="No applications yet" />}
      <ul className="flex flex-col gap-3">
        {apps.data.results.map((app) => (
          <li key={app.id} className="glass rounded-xl2 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
              <div className="flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-ink">{app.candidate.full_name}</h2>
                  <StatusBadge status={app.status} label={app.status_label} />
                </div>
                <p className="text-sm text-muted">
                  {app.candidate.headline || 'Candidate'} · {app.candidate.location || 'Location not shared'} · Applied {formatDate(app.created_at)}
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" aria-expanded={openId === app.id} onClick={() => setOpenId(openId === app.id ? null : app.id)}>
                  {openId === app.id ? 'Hide' : 'View'}
                  <span className="sr-only"> application from {app.candidate.full_name}</span>
                </Button>
                {canMove &&
                  app.allowed_transitions.map((status) => (
                    <Button
                      key={status}
                      variant={status === 'rejected' ? 'ghost' : 'primary'}
                      disabled={move.isPending}
                      onClick={() => move.mutate({ appId: app.id, status })}
                    >
                      {LABELS[status] ?? status}
                      <span className="sr-only"> for {app.candidate.full_name}</span>
                    </Button>
                  ))}
              </div>
            </div>
            {openId === app.id && <Detail id={app.id} />}
          </li>
        ))}
      </ul>
      <Pager page={page} hasNext={Boolean(apps.data.next)} hasPrevious={Boolean(apps.data.previous)} onChange={setPage} />
    </>
  );
}
