import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, ErrorNote, PageHeader, PageLoader, SelectField, SuccessNote, TextField } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { MODES } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { Interviewer, InterviewMode, InterviewPlan } from '@/lib/types';
import { JobViewTabs } from './JobApplicationsPage';

interface RoundDraft {
  id?: string;
  name: string;
  duration_minutes: number;
  mode: InterviewMode;
  interviewers_needed: number;
  pool: string[];
}

const DURATIONS = [15, 30, 45, 60, 75, 90, 120, 150, 180];

export function InterviewPlanPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const client = useQueryClient();
  const canEdit = user?.role === 'recruiter' || user?.role === 'hr';
  const plan = useQuery({ queryKey: ['interview-plan', id], queryFn: () => api<InterviewPlan>(`/jobs/${id}/interview-plan`) });
  const people = useQuery({
    queryKey: ['interviewers'],
    queryFn: () => api<{ results: Interviewer[] }>('/interviewers'),
    enabled: canEdit,
  });
  useDocumentTitle(plan.data ? `Interview plan · ${plan.data.job.title}` : 'Interview plan');
  const [rounds, setRounds] = useState<RoundDraft[] | null>(null);
  const [hira, setHira] = useState(true);
  useEffect(() => {
    if (plan.data && rounds === null) {
      setHira(plan.data.hira_enabled);
      setRounds(
        plan.data.rounds.map((r) => ({
          id: r.id,
          name: r.name,
          duration_minutes: r.duration_minutes,
          mode: r.mode,
          interviewers_needed: r.interviewers_needed,
          pool: (r.pool ?? []).map((p) => p.id),
        })),
      );
    }
  }, [plan.data, rounds]);
  const save = useMutation({
    mutationFn: () => api<InterviewPlan>(`/jobs/${id}/interview-plan`, { method: 'PUT', body: { hira_enabled: hira, rounds } }),
    onSuccess: (data) => client.setQueryData(['interview-plan', id], data),
  });

  if (plan.isPending || !rounds) return <PageLoader />;
  if (plan.isError || !plan.data) return <ErrorNote>We could not load the interview plan.</ErrorNote>;
  const set = (index: number, patch: Partial<RoundDraft>) => setRounds(rounds.map((r, i) => (i === index ? { ...r, ...patch } : r)));
  const move = (index: number, delta: number) => {
    const next = [...rounds];
    const [item] = next.splice(index, 1);
    next.splice(index + delta, 0, item);
    setRounds(next);
  };
  const names = new Map(plan.data.rounds.flatMap((r) => r.pool ?? []).map((p) => [p.id, p.name]));
  people.data?.results.forEach((p) => names.set(p.id, p.name));

  return (
    <>
      <PageHeader
        title={`Interview plan · ${plan.data.job.title}`}
        intro="Rounds run in order. HIRA picks interviewers from each round's pool by free time and weekly load."
      />
      <JobViewTabs jobId={id} current="plan" />
      <form
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
        aria-label="Interview plan"
      >
        <label className="glass mb-4 flex min-h-11 items-center gap-3 rounded-xl2 p-4 text-sm font-semibold text-ink">
          <input
            type="checkbox"
            checked={hira}
            disabled={!canEdit}
            onChange={(e) => setHira(e.target.checked)}
            className="h-5 w-5 accent-primary"
          />
          Let HIRA schedule
          <span className="font-normal text-muted">
            {hira
              ? 'HIRA offers slots as soon as a candidate reaches Interview.'
              : 'Off: you schedule each interview by hand (with the same clash checks).'}
          </span>
        </label>
        <ol className="flex flex-col gap-4">
          {rounds.map((round, index) => (
            <li key={round.id ?? `new-${index}`} className="glass rounded-xl2 p-4">
              <fieldset disabled={!canEdit} className="flex flex-col gap-3">
                <legend className="font-display text-lg font-semibold text-ink">
                  Round {index + 1}: {round.name || 'New round'}
                </legend>
                <div className="grid gap-3 sm:grid-cols-4">
                  <TextField
                    label="Name"
                    value={round.name}
                    maxLength={60}
                    onChange={(e) => set(index, { name: e.target.value })}
                    required
                  />
                  <SelectField
                    label="Duration"
                    value={round.duration_minutes}
                    onChange={(e) => set(index, { duration_minutes: Number(e.target.value) })}
                  >
                    {DURATIONS.map((d) => (
                      <option key={d} value={d}>
                        {d} minutes
                      </option>
                    ))}
                  </SelectField>
                  <SelectField label="Mode" value={round.mode} onChange={(e) => set(index, { mode: e.target.value as InterviewMode })}>
                    {MODES.map((m) => (
                      <option key={m.value} value={m.value}>
                        {m.label}
                      </option>
                    ))}
                  </SelectField>
                  <SelectField
                    label="Interviewers"
                    value={round.interviewers_needed}
                    onChange={(e) => set(index, { interviewers_needed: Number(e.target.value) })}
                  >
                    {[1, 2, 3, 4].map((n) => (
                      <option key={n} value={n}>
                        {n === 1 ? '1 interviewer' : `Panel of ${n}`}
                      </option>
                    ))}
                  </SelectField>
                </div>
                <fieldset>
                  <legend className="mb-1 text-sm font-medium text-ink">Pool ({round.pool.length} people)</legend>
                  {canEdit && people.data ? (
                    <div
                      className="grid max-h-48 gap-1 overflow-y-auto rounded-xl bg-canvas p-2 sm:grid-cols-2"
                      tabIndex={0}
                      role="group"
                      aria-label={`Pool for ${round.name}`}
                    >
                      {people.data.results.map((p) => (
                        <label key={p.id} className="flex min-h-11 items-center gap-2 rounded-lg px-2 text-sm hover:bg-white">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-primary"
                            checked={round.pool.includes(p.id)}
                            onChange={(e) =>
                              set(index, { pool: e.target.checked ? [...round.pool, p.id] : round.pool.filter((x) => x !== p.id) })
                            }
                          />
                          <span>
                            {p.name}
                            <span className="block text-xs text-muted">
                              {p.skills
                                .slice(0, 3)
                                .map((s) => s.name)
                                .join(', ') || p.role}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                  ) : (
                    <p className="text-sm text-ink-soft">{round.pool.map((p) => names.get(p) ?? p).join(', ') || 'Nobody yet'}</p>
                  )}
                </fieldset>
                {canEdit && (
                  <div className="flex flex-wrap gap-2">
                    <Button variant="ghost" onClick={() => move(index, -1)} disabled={index === 0}>
                      Move up<span className="sr-only"> {round.name}</span>
                    </Button>
                    <Button variant="ghost" onClick={() => move(index, 1)} disabled={index === rounds.length - 1}>
                      Move down<span className="sr-only"> {round.name}</span>
                    </Button>
                    <Button variant="ghost" onClick={() => setRounds(rounds.filter((_, i) => i !== index))} disabled={rounds.length === 1}>
                      Remove<span className="sr-only"> {round.name}</span>
                    </Button>
                  </div>
                )}
              </fieldset>
            </li>
          ))}
        </ol>
        {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
        {save.isSuccess && <SuccessNote>Plan saved.</SuccessNote>}
        {canEdit && (
          <div className="mt-4 flex flex-wrap gap-2">
            <Button
              variant="secondary"
              onClick={() => setRounds([...rounds, { name: '', duration_minutes: 45, mode: 'video', interviewers_needed: 1, pool: [] }])}
              disabled={rounds.length >= 6}
            >
              Add a round
            </Button>
            <Button type="submit" disabled={save.isPending}>
              Save plan
            </Button>
          </div>
        )}
      </form>
    </>
  );
}
