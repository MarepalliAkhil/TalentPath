import { useEffect, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Button, ErrorNote, PageHeader, PageLoader, SuccessNote, TextField } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { istInputToIso, WEEKDAYS } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { Availability, WorkingHours } from '@/lib/types';

type Row = { on: boolean; start: string; end: string };

function toRows(hours: WorkingHours): Record<string, Row> {
  return Object.fromEntries(
    WEEKDAYS.map(({ key }) => [
      key,
      hours[key] ? { on: true, start: hours[key][0], end: hours[key][1] } : { on: false, start: '10:00', end: '18:00' },
    ]),
  );
}

export function AvailabilityPage() {
  useDocumentTitle('My availability');
  const client = useQueryClient();
  const data = useQuery({ queryKey: ['availability'], queryFn: () => api<Availability>('/availability') });
  const [rows, setRows] = useState<Record<string, Row> | null>(null);
  const [block, setBlock] = useState({ starts_at: '', ends_at: '', reason: '' });
  useEffect(() => {
    if (data.data && rows === null) setRows(toRows(data.data.working_hours));
  }, [data.data, rows]);
  const refresh = (value: Availability) => client.setQueryData(['availability'], value);
  const save = useMutation({
    mutationFn: () => {
      const hours = Object.fromEntries(
        Object.entries(rows ?? {})
          .filter(([, r]) => r.on)
          .map(([k, r]) => [k, [r.start, r.end]]),
      );
      return api<Availability>('/availability', { method: 'PUT', body: { working_hours: hours } });
    },
    onSuccess: refresh,
  });
  const add = useMutation({
    mutationFn: () =>
      api<Availability>('/availability/blocks', {
        method: 'POST',
        body: { starts_at: istInputToIso(block.starts_at), ends_at: istInputToIso(block.ends_at), reason: block.reason },
      }),
    onSuccess: (value) => {
      refresh(value);
      setBlock({ starts_at: '', ends_at: '', reason: '' });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/availability/blocks/${id}`, { method: 'DELETE' }),
    onSuccess: () => client.invalidateQueries({ queryKey: ['availability'] }),
  });

  if (data.isPending || !rows) return <PageLoader />;
  if (data.isError || !data.data) return <ErrorNote>We could not load your availability.</ErrorNote>;
  const set = (key: string, patch: Partial<Row>) => setRows({ ...rows, [key]: { ...rows[key], ...patch } });
  const submitBlock = (event: FormEvent) => {
    event.preventDefault();
    add.mutate();
  };

  return (
    <>
      <PageHeader
        title="My availability"
        intro="HIRA only offers interview slots inside your working hours, outside blocked time and away from your other interviews. All times are IST (Asia/Kolkata)."
        actions={
          <Link to="/interviews" className="text-sm font-semibold text-primary-strong underline">
            Back to my interviews
          </Link>
        }
      />
      {data.data.skills.length > 0 && <p className="mb-4 text-sm text-muted">You interview for: {data.data.skills.join(', ')}.</p>}
      <form
        className="glass mb-8 rounded-xl2 p-5"
        aria-labelledby="hours-heading"
        onSubmit={(e) => {
          e.preventDefault();
          save.mutate();
        }}
      >
        <h2 id="hours-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Working hours
        </h2>
        <div className="flex flex-col divide-y divide-ink/10">
          {WEEKDAYS.map(({ key, label }) => (
            <fieldset key={key} className="grid grid-cols-1 items-center gap-2 py-2 sm:grid-cols-[10rem_1fr_1fr]">
              <legend className="sr-only">{label}</legend>
              <label className="flex min-h-11 items-center gap-2 text-sm font-medium text-ink">
                <input
                  type="checkbox"
                  checked={rows[key].on}
                  onChange={(e) => set(key, { on: e.target.checked })}
                  className="h-5 w-5 accent-primary"
                />
                {label}
              </label>
              <label className="flex items-center gap-2 text-sm text-ink-soft">
                From
                <input
                  type="time"
                  step={900}
                  value={rows[key].start}
                  disabled={!rows[key].on}
                  onChange={(e) => set(key, { start: e.target.value })}
                  className="min-h-11 rounded-xl border border-ink/15 bg-white px-2"
                  aria-label={`${label} start`}
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-ink-soft">
                To
                <input
                  type="time"
                  step={900}
                  value={rows[key].end}
                  disabled={!rows[key].on}
                  onChange={(e) => set(key, { end: e.target.value })}
                  className="min-h-11 rounded-xl border border-ink/15 bg-white px-2"
                  aria-label={`${label} end`}
                />
              </label>
            </fieldset>
          ))}
        </div>
        {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
        {save.isSuccess && <SuccessNote>Working hours saved.</SuccessNote>}
        <Button type="submit" className="mt-3" disabled={save.isPending}>
          Save working hours
        </Button>
      </form>

      <section className="glass rounded-xl2 p-5" aria-labelledby="blocked-heading">
        <h2 id="blocked-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Blocked time
        </h2>
        {data.data.blocked.length ? (
          <ul className="mb-4 space-y-2">
            {data.data.blocked.map((b) => (
              <li key={b.id} className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-canvas p-3 text-sm">
                <span>
                  {b.label}
                  {b.reason && ` · ${b.reason}`}
                </span>
                <Button variant="ghost" onClick={() => remove.mutate(b.id)} disabled={remove.isPending}>
                  Remove<span className="sr-only"> {b.label}</span>
                </Button>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-4 text-sm text-muted">No blocked time coming up.</p>
        )}
        <form onSubmit={submitBlock} className="grid gap-3 sm:grid-cols-3">
          <TextField
            label="From (IST)"
            type="datetime-local"
            value={block.starts_at}
            onChange={(e) => setBlock({ ...block, starts_at: e.target.value })}
            required
          />
          <TextField
            label="To (IST)"
            type="datetime-local"
            value={block.ends_at}
            onChange={(e) => setBlock({ ...block, ends_at: e.target.value })}
            required
          />
          <TextField
            label="Reason (optional)"
            value={block.reason}
            maxLength={120}
            onChange={(e) => setBlock({ ...block, reason: e.target.value })}
          />
          <div className="sm:col-span-3">
            {add.isError && <ErrorNote>{errorText(add.error)}</ErrorNote>}
            <Button type="submit" variant="secondary" disabled={add.isPending}>
              Block this time
            </Button>
          </div>
        </form>
      </section>
    </>
  );
}
