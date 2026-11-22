import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Dialog } from '@/components/Dialog';
import { Icon } from '@/components/Icon';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField, buttonClass } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { ist, istRange } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { AssignedInterviews, Interview } from '@/lib/types';

function who(interview: Interview) {
  return interview.candidate?.full_name ?? interview.candidate?.code ?? 'Candidate';
}

function Row({ interview, onDecline }: { interview: Interview; onDecline: (i: Interview) => void }) {
  const client = useQueryClient();
  const noShow = useMutation({
    mutationFn: () => api(`/interviews/${interview.id}/no-show`, { method: 'POST' }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['assigned-interviews'] }),
  });
  return (
    <li className="glass flex flex-col gap-3 rounded-xl2 p-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <p className="font-semibold text-ink">
          {who(interview)} · {interview.job.title}
        </p>
        <p className="text-sm text-muted">
          {interview.round.name} · {istRange(interview.starts_at, interview.ends_at)} · {interview.mode_label}
        </p>
        {interview.can_submit_scorecard && interview.scorecard_due_at && (
          <p className="text-xs font-semibold text-accent">Scorecard due {ist(interview.scorecard_due_at)}</p>
        )}
        {noShow.isError && <ErrorNote>{errorText(noShow.error)}</ErrorNote>}
      </div>
      <div className="flex flex-wrap gap-2">
        {interview.can_submit_scorecard && (
          <Link to={`/interviews/${interview.id}/scorecard`} className={buttonClass('primary')}>
            Fill in scorecard<span className="sr-only"> for {who(interview)}</span>
          </Link>
        )}
        {!interview.can_submit_scorecard && interview.my_scorecard_submitted && (
          <Link to={`/interviews/${interview.id}/scorecard`} className={buttonClass('secondary')}>
            View feedback<span className="sr-only"> for {who(interview)}</span>
          </Link>
        )}
        {interview.status === 'scheduled' && (
          <a href={`/api/interviews/${interview.id}/calendar.ics`} download className={buttonClass('ghost')}>
            <Icon name="download" className="h-4 w-4" /> .ics<span className="sr-only"> invite for {who(interview)}</span>
          </a>
        )}
        {interview.can_decline && (
          <Button variant="ghost" onClick={() => onDecline(interview)}>
            Can't make it<span className="sr-only"> ({who(interview)})</span>
          </Button>
        )}
        {interview.can_mark_no_show && (
          <Button variant="ghost" onClick={() => noShow.mutate()} disabled={noShow.isPending}>
            Mark no-show<span className="sr-only"> for {who(interview)}</span>
          </Button>
        )}
      </div>
    </li>
  );
}

function DeclineDialog({ interview, onClose }: { interview: Interview; onClose: () => void }) {
  const client = useQueryClient();
  const [reason, setReason] = useState('');
  const decline = useMutation({
    mutationFn: () => api<{ replaced: boolean; replacement?: string }>(`/interviews/${interview.id}/decline`, { method: 'POST', body: { reason } }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['assigned-interviews'] }),
  });
  return (
    <Dialog title="Decline this interview?" description={`${who(interview)} · ${ist(interview.starts_at)}`} onClose={onClose}>
      {decline.isSuccess ? (
        <div className="flex flex-col gap-3">
          <SuccessNote>
            {decline.data.replaced
              ? `HIRA found a replacement: ${decline.data.replacement}.`
              : 'Nobody else was free, so HIRA has offered the candidate new times and told the recruiter.'}
          </SuccessNote>
          <Button className="self-start" onClick={onClose}>
            Done
          </Button>
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            decline.mutate();
          }}
          className="flex flex-col gap-3"
        >
          <p className="text-sm text-ink-soft">HIRA will look for someone else from the same pool who is free at that time.</p>
          <TextAreaField label="Reason (optional)" rows={2} maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} />
          {decline.isError && <ErrorNote>{errorText(decline.error)}</ErrorNote>}
          <div className="flex gap-2">
            <Button type="submit" variant="danger" disabled={decline.isPending}>
              Decline
            </Button>
            <Button variant="ghost" onClick={onClose}>
              Keep it
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}

function Group({ title, rows, empty, onDecline }: { title: string; rows: Interview[]; empty: string; onDecline: (i: Interview) => void }) {
  const id = title.toLowerCase().replace(/\W+/g, '-');
  return (
    <section className="mb-8" aria-labelledby={id}>
      <h2 id={id} className="mb-3 font-display text-xl font-semibold text-ink">
        {title} <span className="text-base font-normal text-muted">({rows.length})</span>
      </h2>
      {rows.length ? (
        <ul className="flex flex-col gap-3">
          {rows.map((i) => (
            <Row key={i.id} interview={i} onDecline={onDecline} />
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted">{empty}</p>
      )}
    </section>
  );
}

export function MyInterviewsPage() {
  useDocumentTitle('My interviews');
  const [declining, setDeclining] = useState<Interview | null>(null);
  const data = useQuery({ queryKey: ['assigned-interviews'], queryFn: () => api<AssignedInterviews>('/interviews/assigned') });
  return (
    <>
      <PageHeader
        title="My interviews"
        intro="Interviews HIRA has booked with you. Times are in IST."
        actions={
          <Link to="/interviews/availability" className={buttonClass('secondary')}>
            <Icon name="clock" className="h-4 w-4" /> My availability
          </Link>
        }
      />
      {data.isPending && <PageLoader />}
      {data.isError && <ErrorNote>We could not load your interviews.</ErrorNote>}
      {data.data && (
        <>
          {data.data.needs_feedback.length + data.data.upcoming.length + data.data.past.length === 0 && (
            <EmptyState title="No interviews yet">HIRA picks interviewers by skills and free time. Keep your availability up to date.</EmptyState>
          )}
          <Group title="Needs your feedback" rows={data.data.needs_feedback} empty="Nothing to fill in." onDecline={setDeclining} />
          <Group title="Upcoming" rows={data.data.upcoming} empty="No upcoming interviews." onDecline={setDeclining} />
          <Group title="Past" rows={data.data.past} empty="No past interviews." onDecline={setDeclining} />
        </>
      )}
      {declining && <DeclineDialog interview={declining} onClose={() => setDeclining(null)} />}
    </>
  );
}
