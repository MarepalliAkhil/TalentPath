import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Icon } from '@/components/Icon';
import { SlotPicker } from '@/components/SlotPicker';
import { Button, ErrorNote, StatusBadge } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { istRange } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { CandidateOffer, Interview, Slot } from '@/lib/types';

function Meeting({ interview }: { interview: Interview }) {
  return (
    <div className="mt-2 space-y-1 text-sm text-ink-soft">
      <p className="font-semibold text-ink">{istRange(interview.starts_at, interview.ends_at)}</p>
      <p>
        {interview.mode_label} · {interview.round.duration_minutes} minutes
        {interview.interviewers.length > 0 && ` · with ${interview.interviewers.map((i) => i.name).join(', ')}`}
      </p>
      {interview.mode === 'video' && interview.meeting_link ? (
        <p>
          Meeting link: <span className="break-all font-mono text-xs">{interview.meeting_link}</span>{' '}
          <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning">Simulated</span>
        </p>
      ) : (
        <p>
          {interview.location} <span className="rounded-full bg-warning-soft px-2 py-0.5 text-xs font-semibold text-warning">Simulated</span>
        </p>
      )}
      <p className="text-xs text-muted">{interview.meeting_note}</p>
    </div>
  );
}

function InterviewCard({ interview }: { interview: Interview }) {
  const client = useQueryClient();
  const [asking, setAsking] = useState(false);
  const refresh = () => client.invalidateQueries({ queryKey: ['my-interviews'] });
  const reschedule = useMutation({
    mutationFn: () => api<Interview>(`/interviews/${interview.id}/reschedule`, { method: 'POST' }),
    onSuccess: () => {
      setAsking(false);
      void refresh();
    },
  });
  const hold = async (slot: string) => {
    try {
      return await api<{ slot: Slot }>(`/interviews/${interview.id}/hold`, { method: 'POST', body: { slot } });
    } catch (e) {
      void refresh(); // HIRA may have offered fresh times
      throw e;
    }
  };
  const confirm = async (slot: string) => {
    try {
      await api(`/interviews/${interview.id}/confirm`, { method: 'POST', body: { slot } });
    } finally {
      void refresh();
    }
  };

  return (
    <li className="glass rounded-xl2 p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-display text-lg font-semibold text-ink">{interview.job.title}</h3>
          <p className="text-sm text-muted">
            {interview.round.name} · {interview.round.mode_label} · {interview.round.duration_minutes} minutes
          </p>
        </div>
        <span className="rounded-full bg-accent-soft px-2.5 py-0.5 text-xs font-semibold text-accent">
          {interview.status === 'pending' ? 'Pick a time' : interview.status_label}
        </span>
      </div>
      {interview.status === 'pending' && (
        <div className="mt-4">
          <SlotPicker
            key={interview.slots.map((s) => s.id).join()}
            slots={interview.slots}
            legend="Times when your interviewers are free (IST)"
            onHold={hold}
            onConfirm={confirm}
          />
        </div>
      )}
      {interview.status === 'scheduled' && (
        <>
          <Meeting interview={interview} />
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <a href={`/api/interviews/${interview.id}/calendar.ics`} download className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary-strong underline">
              <Icon name="download" className="h-4 w-4" /> Add to calendar (.ics)
            </a>
            {interview.can_reschedule ? (
              asking ? (
                <>
                  <span className="text-sm text-ink-soft">Ask HIRA for other times? ({interview.reschedules_left} left)</span>
                  <Button variant="secondary" onClick={() => reschedule.mutate()} disabled={reschedule.isPending}>
                    Yes, reschedule
                  </Button>
                  <Button variant="ghost" onClick={() => setAsking(false)}>
                    Keep this time
                  </Button>
                </>
              ) : (
                <Button variant="ghost" onClick={() => setAsking(true)}>
                  Reschedule
                </Button>
              )
            ) : (
              <p className="text-xs text-muted">
                {interview.reschedules_left === 0
                  ? 'You have used both reschedules. Message the recruiter through Ask HIRA if you need help.'
                  : 'Rescheduling closes 12 hours before the interview.'}
              </p>
            )}
          </div>
          {reschedule.isError && <ErrorNote>{errorText(reschedule.error)}</ErrorNote>}
        </>
      )}
      {(interview.status === 'completed' || interview.status === 'no_show') && (
        <p className="mt-2 text-sm text-muted">{istRange(interview.starts_at, interview.ends_at)} · {interview.status_label}</p>
      )}
    </li>
  );
}

export function MyInterviews() {
  const interviews = useQuery({ queryKey: ['my-interviews'], queryFn: () => api<{ results: Interview[] }>('/my/interviews') });
  const active = (interviews.data?.results ?? []).filter((i) => i.status === 'pending' || i.status === 'scheduled');
  if (!active.length) return null;
  return (
    <section className="mb-8" aria-labelledby="interviews-heading">
      <h2 id="interviews-heading" className="mb-3 font-display text-xl font-semibold text-ink">
        Your interviews
      </h2>
      <ul className="flex flex-col gap-4">
        {active.map((i) => (
          <InterviewCard key={i.id} interview={i} />
        ))}
      </ul>
    </section>
  );
}

export function MyOffers() {
  const offers = useQuery({ queryKey: ['my-offers'], queryFn: () => api<{ results: CandidateOffer[] }>('/my/offers') });
  const rows = offers.data?.results ?? [];
  if (!rows.length) return null;
  return (
    <section className="mb-8" aria-labelledby="offers-heading">
      <h2 id="offers-heading" className="mb-3 font-display text-xl font-semibold text-ink">
        Your offers
      </h2>
      <ul className="flex flex-col gap-3">
        {rows.map((offer) => (
          <li key={offer.id} className="glass flex flex-col gap-2 rounded-xl2 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-ink">{offer.job.title}</p>
              <p className="text-sm text-muted">
                {offer.terms.designation} · valid until {formatDate(offer.expires_on)}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <StatusBadge status={offer.status === 'accepted' ? 'offer' : 'interview'} label={offer.status_label} />
              <Link to={`/candidate/offers/${offer.id}`} className="font-semibold text-primary-strong underline">
                {offer.can_respond ? 'View and respond' : 'View offer'}
                <span className="sr-only"> for {offer.job.title}</span>
              </Link>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
