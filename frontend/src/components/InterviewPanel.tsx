import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { api } from '@/lib/api';
import { istInputToIso, istRange } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { ApplicationInterviews, Interviewer, StaffOffer } from '@/lib/types';
import { Dialog } from './Dialog';
import { OfferBadge } from './OfferBadge';
import { OfferForm } from './OfferForm';
import { draftBody, draftFrom, type OfferDraft } from '@/lib/offers';
import { SummaryView } from './scorecards';
import { Button, ErrorNote, SelectField, SuccessNote, TextField } from './ui';

const OUTCOME: Record<string, string> = { passed: 'Passed', not_passed: 'Not recommended' };

function ManualDialog({ data, appId, onClose }: { data: ApplicationInterviews; appId: string; onClose: () => void }) {
  const client = useQueryClient();
  const people = useQuery({ queryKey: ['interviewers'], queryFn: () => api<{ results: Interviewer[] }>('/interviewers') });
  const first = data.rounds.find((r) => r.outcome !== 'passed') ?? data.rounds[0];
  const [round, setRound] = useState(first?.round.id ?? '');
  const [when, setWhen] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const save = useMutation({
    mutationFn: () =>
      api(`/applications/${appId}/interviews/manual`, {
        method: 'POST',
        body: { round_id: round, starts_at: istInputToIso(when), interviewer_ids: chosen },
      }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['application-interviews', appId] });
      onClose();
    },
  });
  const pool = data.rounds.find((r) => r.round.id === round)?.round.pool ?? [];
  const poolIds = new Set(pool.map((p) => p.id));
  const options = [...(people.data?.results ?? [])].sort((a, b) => Number(poolIds.has(b.id)) - Number(poolIds.has(a.id)));
  return (
    <Dialog title="Schedule by hand" description="Same clash checks as HIRA: nobody can be double booked." onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        className="flex flex-col gap-3"
      >
        <SelectField label="Round" value={round} onChange={(e) => setRound(e.target.value)}>
          {data.rounds.map((r) => (
            <option key={r.round.id} value={r.round.id}>
              {r.round.name} ({r.round.duration_minutes} min)
            </option>
          ))}
        </SelectField>
        <TextField label="Start (IST)" type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} required />
        <fieldset>
          <legend className="mb-1 text-sm font-medium text-ink">Interviewers (pool members first)</legend>
          <div className="grid max-h-48 gap-1 overflow-y-auto rounded-xl bg-canvas p-2" role="group" aria-label="Interviewers" tabIndex={0}>
            {options.map((p) => (
              <label key={p.id} className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm hover:bg-white">
                <input
                  type="checkbox"
                  className="h-4 w-4 accent-primary"
                  checked={chosen.includes(p.id)}
                  onChange={(e) => setChosen(e.target.checked ? [...chosen, p.id] : chosen.filter((x) => x !== p.id))}
                />
                {p.name}
                {poolIds.has(p.id) && <span className="text-xs text-muted">in pool</span>}
                <span className="ml-auto text-xs text-muted">{p.interviews_this_week} this week</span>
              </label>
            ))}
          </div>
        </fieldset>
        {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
        <Button type="submit" className="self-start" disabled={!when || !chosen.length || save.isPending}>
          Book it
        </Button>
      </form>
    </Dialog>
  );
}

function DraftOffer({ appId, designation, onClose }: { appId: string; designation: string; onClose: () => void }) {
  const navigate = useNavigate();
  const create = useMutation({
    mutationFn: (draft: OfferDraft) => api<StaffOffer>(`/applications/${appId}/offers`, { method: 'POST', body: draftBody(draft) }),
    onSuccess: (offer) => navigate(`/offers/${offer.id}`),
  });
  return (
    <Dialog title="Draft an offer" description="It goes to the hiring manager, then HR, before you can send it." onClose={onClose}>
      <OfferForm
        initial={draftFrom(undefined, undefined, designation)}
        submitLabel="Save draft"
        busy={create.isPending}
        error={create.error}
        onSubmit={(d) => create.mutate(d)}
        onCancel={onClose}
      />
    </Dialog>
  );
}

/** Rounds, interviews and scorecard summaries for one application (inside the application drawer). */
export function InterviewPanel({ appId, jobTitle }: { appId: string; jobTitle: string }) {
  const { user } = useAuth();
  const client = useQueryClient();
  const [manual, setManual] = useState(false);
  const [drafting, setDrafting] = useState(false);
  const data = useQuery({
    queryKey: ['application-interviews', appId],
    queryFn: () => api<ApplicationInterviews>(`/applications/${appId}/interviews`),
  });
  const propose = useMutation({
    mutationFn: () => api(`/applications/${appId}/interviews/propose`, { method: 'POST' }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['application-interviews', appId] }),
  });
  if (data.isPending) return <p className="text-sm text-muted">Loading interviews…</p>;
  if (data.isError || !data.data) return <ErrorNote>Could not load interviews.</ErrorNote>;
  const d = data.data;
  const canOffer =
    (user?.role === 'recruiter' || user?.role === 'hr') &&
    d.final_round_passed &&
    ['interview', 'offer'].includes(d.status) &&
    (!d.offer || ['revoked', 'declined', 'expired'].includes(d.offer.status));

  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-muted">
        {d.hira_enabled ? 'HIRA schedules this job.' : 'Let HIRA schedule is off for this job: schedule by hand.'}
      </p>
      <ol className="space-y-3">
        {d.rounds.map(({ round, interview, outcome, summary }) => (
          <li key={round.id} className="rounded-xl bg-canvas p-3 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="font-semibold text-ink">
                {round.order}. {round.name}{' '}
                <span className="font-normal text-muted">
                  · {round.mode_label}, {round.duration_minutes} min
                </span>
              </p>
              <span className="text-xs font-semibold text-ink-soft">
                {outcome ? OUTCOME[outcome] : interview ? interview.status_label : 'Not started'}
              </span>
            </div>
            {interview?.starts_at && <p className="text-ink-soft">{istRange(interview.starts_at, interview.ends_at)}</p>}
            {interview && interview.interviewers.length > 0 && (
              <p className="text-muted">
                With{' '}
                {interview.interviewers
                  .filter((i) => i.status === 'assigned')
                  .map((i) => i.name)
                  .join(', ')}
                {interview.scheduled_by === 'manual' && ' (scheduled by hand)'}
              </p>
            )}
            {interview?.status === 'pending' && <p className="text-muted">{interview.slots.length} slots offered to the candidate.</p>}
            {interview?.attention_label && (
              <p className="mt-1 rounded-lg bg-accent-soft px-2 py-1 text-xs font-semibold text-accent">
                Needs you: {interview.attention_label}
              </p>
            )}
            {summary && interview && ['completed', 'scheduled'].includes(interview.status) && (
              <div className="mt-2">
                <SummaryView summary={summary} />
                {summary.submitted > 0 && (
                  <Link to={`/interviews/${interview.id}/scorecard`} className="text-xs font-semibold text-primary-strong underline">
                    Read the scorecards<span className="sr-only"> for {round.name}</span>
                  </Link>
                )}
              </div>
            )}
          </li>
        ))}
      </ol>
      {propose.isError && <ErrorNote>{errorText(propose.error)}</ErrorNote>}
      {propose.isSuccess && <SuccessNote>HIRA has offered the candidate new times.</SuccessNote>}
      <div className="flex flex-wrap gap-2">
        {d.can_schedule && (
          <>
            <Button variant="secondary" onClick={() => propose.mutate()} disabled={propose.isPending}>
              Ask HIRA for slots
            </Button>
            <Button variant="ghost" onClick={() => setManual(true)}>
              Schedule by hand
            </Button>
          </>
        )}
        {d.offer && (
          <span className="flex items-center gap-2 text-sm">
            <OfferBadge offer={d.offer} />
            <Link to={`/offers/${d.offer.id}`} className="font-semibold text-primary-strong underline">
              Open offer
            </Link>
          </span>
        )}
        {canOffer && <Button onClick={() => setDrafting(true)}>Draft offer</Button>}
      </div>
      {manual && <ManualDialog data={d} appId={appId} onClose={() => setManual(false)} />}
      {drafting && <DraftOffer appId={appId} designation={jobTitle.split(' (')[0]} onClose={() => setDrafting(false)} />}
    </div>
  );
}
