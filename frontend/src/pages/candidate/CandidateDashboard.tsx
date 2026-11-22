import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, StatusBadge, SuccessNote, buttonClass } from '@/components/ui';
import { api } from '@/lib/api';
import { firstName, formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { CandidateApplication, Paginated } from '@/lib/types';
import { MyInterviews, MyOffers } from './CandidateHiring';

const STEPS = ['applied', 'screening', 'interview', 'offer', 'hired'];

function Progress({ status }: { status: string }) {
  const index = STEPS.indexOf(status);
  if (index < 0) return null;
  return (
    <ol className="mt-4 grid grid-cols-5 gap-1" aria-label="Application progress">
      {STEPS.map((step, i) => (
        <li key={step} className="flex flex-col gap-1">
          <span className={`h-1.5 rounded-full ${i <= index ? 'bg-primary' : 'bg-ink/10'}`} aria-hidden="true" />
          <span className={`text-[11px] capitalize ${i === index ? 'font-semibold text-ink' : 'text-muted'}`}>
            {step}
            {i === index && <span className="sr-only"> (current step)</span>}
          </span>
        </li>
      ))}
    </ol>
  );
}

function ApplicationRow({ app }: { app: CandidateApplication }) {
  const client = useQueryClient();
  const [confirming, setConfirming] = useState(false);
  const withdraw = useMutation({
    mutationFn: () => api(`/applications/${app.id}/withdraw`, { method: 'POST' }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['my-applications'] }),
  });
  return (
    <li className="glass rounded-xl2 p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="font-display text-lg font-semibold text-ink">
            {app.job.is_open ? (
              <Link to={`/jobs/${app.job.slug}`} className="hover:text-primary-strong">
                {app.job.title}
              </Link>
            ) : (
              app.job.title
            )}
          </h2>
          <p className="text-sm text-muted">
            {app.job.department} · {app.job.location} · Applied {formatDate(app.created_at)}
          </p>
        </div>
        <StatusBadge status={app.status} label={app.status_label} />
      </div>
      <Progress status={app.status} />
      {app.can_withdraw && (
        <div className="mt-4 flex flex-wrap items-center gap-2">
          {confirming ? (
            <>
              <span className="text-sm text-ink-soft">Withdraw this application?</span>
              <Button variant="danger" onClick={() => withdraw.mutate()} disabled={withdraw.isPending}>
                Yes, withdraw
              </Button>
              <Button variant="ghost" onClick={() => setConfirming(false)}>
                Keep it
              </Button>
            </>
          ) : (
            <Button variant="ghost" onClick={() => setConfirming(true)}>
              Withdraw
            </Button>
          )}
        </div>
      )}
      {withdraw.isError && <ErrorNote>Could not withdraw. Please try again.</ErrorNote>}
    </li>
  );
}

export function CandidateDashboard() {
  useDocumentTitle('My applications');
  const { user } = useAuth();
  const location = useLocation();
  const flash = (location.state as { flash?: string } | null)?.flash;
  const apps = useQuery({
    queryKey: ['my-applications'],
    queryFn: () => api<Paginated<CandidateApplication>>('/applications?page_size=50'),
  });

  return (
    <>
      <PageHeader
        title="My applications"
        intro={user ? `Hi ${firstName(user.full_name)}, here is where every application stands.` : undefined}
        actions={
          <Link to="/jobs" className={buttonClass('primary')}>
            Find more jobs
          </Link>
        }
      />
      {flash && <div className="mb-4"><SuccessNote>{flash}</SuccessNote></div>}
      <MyOffers />
      <MyInterviews />
      {apps.isPending && <PageLoader />}
      {apps.isError && <ErrorNote>We could not load your applications.</ErrorNote>}
      {apps.data && apps.data.results.length === 0 && (
        <EmptyState title="No applications yet">
          <Link to="/jobs" className="font-semibold text-primary-strong underline">
            Browse open roles
          </Link>{' '}
          and apply with your resume.
        </EmptyState>
      )}
      {apps.data && apps.data.results.length > 0 && (
        <ul className="flex flex-col gap-4">
          {apps.data.results.map((app) => (
            <ApplicationRow key={app.id} app={app} />
          ))}
        </ul>
      )}
    </>
  );
}
