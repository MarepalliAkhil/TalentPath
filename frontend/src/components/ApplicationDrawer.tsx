import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import type { NoteItem, StaffApplication } from '@/lib/types';
import { Dialog } from './Dialog';
import { CandidateName, FitBadge, FitBreakdown, ReasonChips } from './fit';
import { Icon } from './Icon';
import { InterviewPanel } from './InterviewPanel';
import { errorText, STAGE_LABELS, useMoveMutation } from '@/lib/pipeline';
import { MoveTo, RejectDialog } from './pipeline';
import { Button, ErrorNote, PageLoader, StatusBadge, SuccessNote, TextAreaField } from './ui';

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="border-t border-ink/10 py-4" aria-label={title}>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-ink-soft">{title}</h3>
      {children}
    </section>
  );
}

function Notes({ app, canVote }: { app: StaffApplication; canVote: boolean }) {
  const client = useQueryClient();
  const [body, setBody] = useState('');
  const [error, setError] = useState('');
  const add = useMutation({
    mutationFn: (payload: { body?: string; vote?: string }) =>
      api<NoteItem>(`/applications/${app.id}/notes`, { method: 'POST', body: payload }),
    onSuccess: () => {
      setBody('');
      setError('');
      void client.invalidateQueries({ queryKey: ['application', app.id] });
    },
    onError: (e) => setError(errorText(e)),
  });
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (body.trim()) add.mutate({ body });
  };
  return (
    <>
      {app.notes?.length ? (
        <ul className="mb-3 space-y-2">
          {app.notes.map((n) => (
            <li key={n.id} className="rounded-xl bg-canvas p-3 text-sm">
              <p className="flex flex-wrap items-center gap-2 text-xs text-muted">
                <span className="font-semibold text-ink">{n.author}</span>
                {n.kind === 'candidate_message' && <span className="rounded-full bg-accent-soft px-2 text-accent">Message from candidate</span>}
                {n.vote && (
                  <span className={n.vote === 'up' ? 'text-success' : 'text-danger'}>
                    <Icon name={n.vote === 'up' ? 'thumbUp' : 'thumbDown'} className="inline h-4 w-4" /> {n.vote === 'up' ? 'Thumbs up' : 'Thumbs down'}
                  </span>
                )}
                <span>
                  {STAGE_LABELS[n.stage] ?? n.stage} · {formatDate(n.created_at)}
                </span>
              </p>
              {n.body && <p className="mt-1 whitespace-pre-wrap text-ink-soft">{n.body}</p>}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mb-3 text-sm text-muted">No notes yet.</p>
      )}
      {error && <ErrorNote>{error}</ErrorNote>}
      <form onSubmit={submit} className="flex flex-col gap-2">
        <TextAreaField label="Add a note" rows={2} maxLength={2000} value={body} onChange={(e) => setBody(e.target.value)} />
        <div className="flex flex-wrap gap-2">
          <Button type="submit" variant="secondary" disabled={!body.trim() || add.isPending}>
            Save note
          </Button>
          {canVote && (
            <>
              <Button variant="ghost" onClick={() => add.mutate({ vote: 'up', body })} disabled={add.isPending}>
                <Icon name="thumbUp" className="h-4 w-4" /> Thumbs up
              </Button>
              <Button variant="ghost" onClick={() => add.mutate({ vote: 'down', body })} disabled={add.isPending}>
                <Icon name="thumbDown" className="h-4 w-4" /> Thumbs down
              </Button>
            </>
          )}
        </div>
      </form>
    </>
  );
}

function Reveal({ app }: { app: StaffApplication }) {
  const client = useQueryClient();
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const reveal = useMutation({
    mutationFn: () => api<StaffApplication>(`/applications/${app.id}/reveal`, { method: 'POST', body: { reason } }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['application', app.id] });
      void client.invalidateQueries({ queryKey: ['board', app.job.id] });
      void client.invalidateQueries({ queryKey: ['job-applications', app.job.id] });
    },
    onError: (e) => setError(errorText(e)),
  });
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        reveal.mutate();
      }}
      className="flex flex-col gap-2"
    >
      <p className="text-sm text-muted">Identity is revealed automatically at the {app.reveal_stage === 'offer' ? 'Offer' : 'Interview'} stage. An early reveal is recorded in the audit log.</p>
      {error && <ErrorNote>{error}</ErrorNote>}
      <TextAreaField label="Reason for revealing early" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} hint="At least 10 characters." />
      <Button type="submit" variant="secondary" className="self-start" disabled={reveal.isPending}>
        Reveal identity
      </Button>
    </form>
  );
}

export function ApplicationDrawer({ id, jobId, onClose }: { id: string; jobId: string; onClose: () => void }) {
  const { user } = useAuth();
  const detail = useQuery({ queryKey: ['application', id], queryFn: () => api<StaffApplication>(`/applications/${id}`) });
  const move = useMoveMutation(jobId);
  const [rejecting, setRejecting] = useState(false);
  const app = detail.data;
  const isManager = user?.role === 'hiring_manager';
  const canVote = isManager && !!app && ['screening', 'interview'].includes(app.status);

  return (
    <Dialog title="Application details" variant="drawer" onClose={onClose}>
      {detail.isPending && <PageLoader />}
      {detail.isError && <ErrorNote>Could not load this application.</ErrorNote>}
      {app && (
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-display text-lg font-semibold text-ink">
              <CandidateName app={app} />
            </p>
            <StatusBadge status={app.status} label={app.status_label} />
            <FitBadge fit={app.fit} />
          </div>
          {app.blind ? (
            <p className="mt-2 rounded-xl bg-primary-soft px-3 py-2 text-sm text-primary-strong">
              Blind screening: name, contact details, address and education institutions are hidden until the{' '}
              {app.reveal_stage === 'offer' ? 'Offer' : 'Interview'} stage.
            </p>
          ) : (
            app.candidate.email && <p className="mt-1 text-sm text-muted">{app.candidate.email}</p>
          )}
          {app.rejection_reason && <p className="mt-2 text-sm text-ink-soft">Not selected: {app.rejection_reason}</p>}

          {move.isError && <ErrorNote>{errorText(move.error)}</ErrorNote>}
          {move.isSuccess && <SuccessNote>Moved.</SuccessNote>}
          <div className="mt-3 max-w-xs">
            <MoveTo
              app={app}
              disabled={move.isPending}
              onMove={(status) => (status === 'rejected' ? setRejecting(true) : move.mutate({ id: app.id, status }))}
            />
          </div>

          {['interview', 'offer', 'hired'].includes(app.status) && (
            <Section title="Interviews">
              <InterviewPanel appId={app.id} jobTitle={app.job.title} />
            </Section>
          )}

          {app.fit && (
            <Section title={`Why ${app.fit.score} (${app.fit.band_label})`}>
              <ReasonChips chips={app.fit.explanation.chips} />
              {app.fit.explanation.raise_score.length > 0 && (
                <div className="mt-3">
                  <p className="text-sm font-semibold text-ink">What would raise this score</p>
                  <ul className="mt-1 list-disc pl-5 text-sm text-ink-soft">
                    {app.fit.explanation.raise_score.map((r) => (
                      <li key={r}>{r}</li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mt-4">
                <FitBreakdown fit={app.fit} />
              </div>
              <p className="mt-3 text-xs text-muted">
                The score reads only skills, where they appear and years of experience. It never uses name, gender, age,
                photo, address, city or college. Scorer v{app.fit.version}.
              </p>
            </Section>
          )}

          {app.evidence && app.evidence.length > 0 && (
            <Section title="Skill evidence">
              <ul className="space-y-1.5 text-sm">
                {app.evidence.map((e) => (
                  <li key={e.slug}>
                    <span className="font-semibold text-ink">{e.name}</span>{' '}
                    <span className="text-muted">({e.section})</span>
                    <span className="block text-ink-soft">“{e.snippet}”</span>
                  </li>
                ))}
              </ul>
            </Section>
          )}

          <Section title={app.blind ? 'Resume (redacted)' : 'Resume'}>
            <pre tabIndex={0} className="max-h-80 overflow-auto whitespace-pre-wrap rounded-xl bg-canvas p-3 font-sans text-sm text-ink-soft">
              {app.resume_text || 'No readable text in this file.'}
            </pre>
            {!app.blind && app.resume_filename && (
              <a href={`/api/applications/${app.id}/resume`} download className="mt-2 inline-flex text-sm font-semibold text-primary-strong underline">
                Download original ({app.resume_filename})
              </a>
            )}
            {app.cover_note && <p className="mt-3 text-sm text-ink-soft">Note from the candidate: {app.cover_note}</p>}
          </Section>

          <Section title="Notes">
            <Notes app={app} canVote={canVote} />
            {isManager && !canVote && <p className="mt-2 text-xs text-muted">Hiring managers add notes and votes at Screening and Interview.</p>}
          </Section>

          {user?.role === 'hr_admin' && app.blind && (
            <Section title="Reveal identity">
              <Reveal app={app} />
            </Section>
          )}

          <Section title="History">
            <ol className="space-y-1 text-sm text-muted">
              {app.events?.map((e) => (
                <li key={e.at}>
                  {e.label}
                  {e.reason ? ` (${e.reason})` : ''} · {formatDate(e.at)}
                </li>
              ))}
            </ol>
          </Section>
        </div>
      )}
      {rejecting && app && (
        <RejectDialog
          count={1}
          busy={move.isPending}
          onClose={() => setRejecting(false)}
          onConfirm={(reason, note) =>
            move.mutate({ id: app.id, status: 'rejected', reason, note }, { onSuccess: () => setRejecting(false) })
          }
        />
      )}
    </Dialog>
  );
}
