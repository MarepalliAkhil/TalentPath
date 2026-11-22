import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link, useParams, useSearchParams } from 'react-router-dom';
import { ApplicationDrawer } from '@/components/ApplicationDrawer';
import { CandidateName, FitBadge, ReasonChips } from '@/components/fit';
import { Icon } from '@/components/Icon';
import { STAGE_LABELS } from '@/lib/pipeline';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, Pager, SelectField, StatusBadge, TextField, buttonClass } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { BoardJob, Paginated, StaffApplication } from '@/lib/types';

type Ranked = Paginated<StaffApplication> & { job: BoardJob };

export function JobViewTabs({ jobId, current }: { jobId: string; current: 'list' | 'board' | 'plan' }) {
  const tab = (active: boolean) =>
    `inline-flex min-h-10 items-center gap-2 rounded-full px-4 text-sm font-semibold ${active ? 'bg-ink text-white' : 'bg-white/70 text-ink-soft hover:text-ink'}`;
  return (
    <nav aria-label="Job views" className="mb-4 flex flex-wrap gap-2">
      <Link to={`/recruiter/jobs/${jobId}/applications`} className={tab(current === 'list')} aria-current={current === 'list' ? 'page' : undefined}>
        <Icon name="layers" className="h-4 w-4" /> Ranked list
      </Link>
      <Link to={`/recruiter/jobs/${jobId}/board`} className={tab(current === 'board')} aria-current={current === 'board' ? 'page' : undefined}>
        <Icon name="columns" className="h-4 w-4" /> Pipeline board
      </Link>
      <Link to={`/recruiter/jobs/${jobId}/interview-plan`} className={tab(current === 'plan')} aria-current={current === 'plan' ? 'page' : undefined}>
        <Icon name="calendar" className="h-4 w-4" /> Interview plan
      </Link>
    </nav>
  );
}

export function JobApplicationsPage() {
  const { id = '' } = useParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState({ band: '', skill: '', status: '' });
  const [draftSkill, setDraftSkill] = useState('');
  const [params] = useSearchParams();
  // HIRA's links open a candidate's drawer directly: ?open=<application id>.
  const [openId, setOpenId] = useState<string | null>(() => params.get('open'));
  const apps = useQuery({
    queryKey: ['job-applications', id, page, filters],
    queryFn: () => api<Ranked>(`/jobs/${id}/applications${qs({ page, ...filters })}`),
    placeholderData: keepPreviousData,
    refetchInterval: 30_000,
  });
  useDocumentTitle(apps.data ? `Candidates · ${apps.data.job.title}` : 'Candidates');
  const set = (key: keyof typeof filters, value: string) => {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  };

  if (apps.isPending) return <PageLoader />;
  if (apps.isError || !apps.data) return <ErrorNote>We could not load candidates for this job.</ErrorNote>;
  const { job } = apps.data;
  const offset = (page - 1) * 20;

  return (
    <>
      <PageHeader
        title={`Candidates · ${job.title}`}
        intro={
          job.blind_screening
            ? `Ranked by fit score. Blind screening is on: identities appear at the ${job.reveal_stage === 'offer' ? 'Offer' : 'Interview'} stage.`
            : 'Ranked by fit score. Blind screening is off for this job.'
        }
      />
      <JobViewTabs jobId={id} current="list" />
      <form
        aria-label="Candidate filters"
        className="glass mb-4 grid gap-3 rounded-xl2 p-4 sm:grid-cols-4"
        onSubmit={(e) => {
          e.preventDefault();
          set('skill', draftSkill.trim());
        }}
      >
        <SelectField label="Fit band" value={filters.band} onChange={(e) => set('band', e.target.value)}>
          <option value="">All bands</option>
          <option value="strong">Strong (80+)</option>
          <option value="good">Good (60-79)</option>
          <option value="partial">Partial (40-59)</option>
          <option value="low">Low (below 40)</option>
        </SelectField>
        <SelectField label="Stage" value={filters.status} onChange={(e) => set('status', e.target.value)}>
          <option value="">All stages</option>
          {Object.entries(STAGE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <TextField label="Has skill" placeholder="e.g. Python or JS" value={draftSkill} onChange={(e) => setDraftSkill(e.target.value)} />
        <div className="flex items-end gap-2">
          <Button type="submit">Filter</Button>
          <Button
            variant="ghost"
            onClick={() => {
              setDraftSkill('');
              setFilters({ band: '', skill: '', status: '' });
            }}
          >
            Clear
          </Button>
        </div>
      </form>
      <p className="mb-3 text-sm font-medium text-ink-soft" role="status" aria-live="polite">
        {apps.data.count} {apps.data.count === 1 ? 'candidate' : 'candidates'}
      </p>
      {apps.data.results.length === 0 && <EmptyState title="No candidates match these filters" />}
      <ol className="flex flex-col gap-3">
        {apps.data.results.map((app, index) => (
          <li key={app.id} className="glass rounded-xl2 p-4">
            <div className="flex flex-col gap-3 md:flex-row md:items-start">
              <span className="font-display text-2xl font-semibold text-ink/30 tabular-nums" aria-hidden="true">
                {offset + index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-semibold text-ink">
                    <span className="sr-only">Rank {offset + index + 1}: </span>
                    <CandidateName app={app} />
                  </h2>
                  <FitBadge fit={app.fit} size="sm" />
                  <StatusBadge status={app.status} label={app.status_label} />
                </div>
                <p className="mt-0.5 text-xs text-muted">Applied {formatDate(app.created_at)}</p>
                {app.fit && (
                  <div className="mt-2">
                    <ReasonChips chips={app.fit.explanation.chips} limit={4} />
                  </div>
                )}
              </div>
              <Button variant="secondary" onClick={() => setOpenId(app.id)}>
                Explain<span className="sr-only"> score for {app.blind ? app.candidate.code : app.candidate.full_name}</span>
              </Button>
            </div>
          </li>
        ))}
      </ol>
      <Pager page={page} hasNext={Boolean(apps.data.next)} hasPrevious={Boolean(apps.data.previous)} onChange={setPage} />
      {openId && <ApplicationDrawer id={openId} jobId={id} onClose={() => setOpenId(null)} />}
      <p className="mt-6 text-sm">
        <Link to={`/recruiter/jobs/${id}/board`} className={buttonClass('ghost', 'px-0 underline')}>
          Open the pipeline board
        </Link>
      </p>
    </>
  );
}
