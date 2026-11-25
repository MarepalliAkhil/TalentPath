import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, ErrorNote, PageHeader, PageLoader, SelectField, SuccessNote, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { day, WEEKDAY_NAMES, type HrConfig, type LeaveTypeConfig, type WorkPolicy } from '@/lib/hr';
import { errorText } from '@/lib/pipeline';

const KEY = ['hr-config'];

function Check({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label className="inline-flex min-h-11 items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4" />
      {label}
    </label>
  );
}

const nullableInt = (v: string) => (v.trim() === '' ? null : Number(v));

/** Leave rules are data: hr_admin edits them here, the engine applies them. */
function LeaveTypeEditor({ lt }: { lt: LeaveTypeConfig }) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    yearly_quota: String(lt.yearly_quota),
    monthly_accrual: lt.monthly_accrual,
    prorate_joiners: lt.prorate_joiners,
    carry_forward_cap: String(lt.carry_forward_cap),
    min_notice_days: String(lt.min_notice_days),
    max_consecutive_days: lt.max_consecutive_days === null ? '' : String(lt.max_consecutive_days),
    half_day_allowed: lt.half_day_allowed,
    document_after_days: lt.document_after_days === null ? '' : String(lt.document_after_days),
    sandwich_rule: lt.sandwich_rule,
    active: lt.active,
  });
  const save = useMutation({
    mutationFn: () =>
      api<LeaveTypeConfig>(`/hr/config/leave-types/${lt.id}`, {
        method: 'PATCH',
        body: {
          ...form,
          yearly_quota: Number(form.yearly_quota),
          carry_forward_cap: Number(form.carry_forward_cap),
          min_notice_days: Number(form.min_notice_days),
          max_consecutive_days: nullableInt(form.max_consecutive_days),
          document_after_days: nullableInt(form.document_after_days),
        },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const fields = save.error instanceof ApiError ? save.error.fieldErrors : {};
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) => setForm((f) => ({ ...f, [key]: value }));
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    save.mutate();
  };
  return (
    <li className="rounded-xl border border-ink/10 bg-white/70 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="font-semibold text-ink">
            {lt.name}
            {!lt.active && <span className="ml-2 text-xs text-muted">(inactive)</span>}
          </h3>
          <p className="text-sm text-ink-soft">{lt.summary}</p>
        </div>
        <Button variant="secondary" onClick={() => setOpen((v) => !v)} aria-expanded={open}>
          {open ? 'Close' : 'Edit'}
          <span className="sr-only"> {lt.name}</span>
        </Button>
      </div>
      {open && (
        <form onSubmit={onSubmit} className="mt-4 grid gap-3 sm:grid-cols-3" aria-label={`Edit ${lt.name}`}>
          {!lt.unpaid && (
            <>
              <TextField
                label="Yearly quota (days)"
                type="number"
                step="0.5"
                min="0"
                value={form.yearly_quota}
                onChange={(e) => set('yearly_quota', e.target.value)}
                error={fields.yearly_quota}
              />
              <TextField
                label="Carry-forward cap"
                type="number"
                step="0.5"
                min="0"
                value={form.carry_forward_cap}
                onChange={(e) => set('carry_forward_cap', e.target.value)}
                error={fields.carry_forward_cap}
              />
            </>
          )}
          <TextField
            label="Minimum notice (days)"
            type="number"
            min="0"
            value={form.min_notice_days}
            onChange={(e) => set('min_notice_days', e.target.value)}
            error={fields.min_notice_days}
          />
          <TextField
            label="Maximum in one request"
            type="number"
            min="0"
            value={form.max_consecutive_days}
            onChange={(e) => set('max_consecutive_days', e.target.value)}
            hint="Empty: no limit"
            error={fields.max_consecutive_days}
          />
          <TextField
            label="Document required after (days)"
            type="number"
            min="0"
            value={form.document_after_days}
            onChange={(e) => set('document_after_days', e.target.value)}
            hint="Empty: never"
            error={fields.document_after_days}
          />
          <div className="flex flex-col sm:col-span-3 sm:flex-row sm:flex-wrap sm:gap-x-6">
            {!lt.unpaid && <Check label="Credited monthly" checked={form.monthly_accrual} onChange={(v) => set('monthly_accrual', v)} />}
            {!lt.unpaid && <Check label="Prorate for joiners" checked={form.prorate_joiners} onChange={(v) => set('prorate_joiners', v)} />}
            <Check label="Half days allowed" checked={form.half_day_allowed} onChange={(v) => set('half_day_allowed', v)} />
            <Check
              label="Sandwich rule (count weekends and holidays between leave days)"
              checked={form.sandwich_rule}
              onChange={(v) => set('sandwich_rule', v)}
            />
            <Check label="Active" checked={form.active} onChange={(v) => set('active', v)} />
          </div>
          {save.isError && !Object.keys(fields).length && <ErrorNote>{errorText(save.error)}</ErrorNote>}
          {save.isSuccess && <SuccessNote>Saved. New requests use these rules straight away.</SuccessNote>}
          <div className="sm:col-span-3">
            <Button type="submit" disabled={save.isPending}>
              Save {lt.name.toLowerCase()}
            </Button>
          </div>
        </form>
      )}
    </li>
  );
}

function WorkPolicyForm({ wp }: { wp: WorkPolicy }) {
  const client = useQueryClient();
  const [form, setForm] = useState({
    shift_start: wp.shift_start,
    shift_end: wp.shift_end,
    late_grace_minutes: String(wp.late_grace_minutes),
    hr_approval_over_days: String(wp.hr_approval_over_days),
    min_team_available_pct: String(wp.min_team_available_pct),
    escalate_after_hours: String(wp.escalate_after_hours),
    internal_manager_notice: wp.internal_manager_notice ?? 'interview',
    weekly_off: wp.weekly_off,
  });
  const save = useMutation({
    mutationFn: () =>
      api<WorkPolicy>(`/hr/config/work-policy/${wp.location}`, {
        method: 'PATCH',
        body: {
          ...form,
          late_grace_minutes: Number(form.late_grace_minutes),
          early_grace_minutes: Number(form.late_grace_minutes),
          hr_approval_over_days: Number(form.hr_approval_over_days),
          min_team_available_pct: Number(form.min_team_available_pct),
          escalate_after_hours: Number(form.escalate_after_hours),
        },
      }),
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const fields = save.error instanceof ApiError ? save.error.fieldErrors : {};
  const set = (key: string, value: string) => setForm((f) => ({ ...f, [key]: value }));
  const toggleDay = (d: number) =>
    setForm((f) => ({ ...f, weekly_off: f.weekly_off.includes(d) ? f.weekly_off.filter((x) => x !== d) : [...f.weekly_off, d].sort() }));
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
      className="grid gap-3 sm:grid-cols-3"
      aria-label={`Work policy for ${wp.location_name}`}
    >
      <TextField
        label="Shift starts"
        type="time"
        value={form.shift_start}
        onChange={(e) => set('shift_start', e.target.value)}
        error={fields.shift_start}
      />
      <TextField
        label="Shift ends"
        type="time"
        value={form.shift_end}
        onChange={(e) => set('shift_end', e.target.value)}
        error={fields.shift_end}
      />
      <TextField
        label="Grace (minutes)"
        type="number"
        min="0"
        value={form.late_grace_minutes}
        onChange={(e) => set('late_grace_minutes', e.target.value)}
        error={fields.late_grace_minutes}
      />
      <TextField
        label="HR approval above (days)"
        type="number"
        step="0.5"
        min="0"
        value={form.hr_approval_over_days}
        onChange={(e) => set('hr_approval_over_days', e.target.value)}
        error={fields.hr_approval_over_days}
      />
      <TextField
        label="Warn below team availability (%)"
        type="number"
        min="0"
        max="100"
        value={form.min_team_available_pct}
        onChange={(e) => set('min_team_available_pct', e.target.value)}
        error={fields.min_team_available_pct}
      />
      <TextField
        label="Escalate after (hours)"
        type="number"
        min="1"
        value={form.escalate_after_hours}
        onChange={(e) => set('escalate_after_hours', e.target.value)}
        error={fields.escalate_after_hours}
      />
      <SelectField
        label="Tell the manager about an internal application at"
        value={form.internal_manager_notice}
        onChange={(e) => set('internal_manager_notice', e.target.value)}
        error={fields.internal_manager_notice}
        hint="Never at application time."
      >
        <option value="interview">Interview</option>
        <option value="offer">Offer</option>
      </SelectField>
      <fieldset className="sm:col-span-3">
        <legend className="text-sm font-medium text-ink">Weekly off</legend>
        <div className="flex flex-wrap gap-x-4">
          {WEEKDAY_NAMES.map((name, i) => (
            <Check key={name} label={name} checked={form.weekly_off.includes(i + 1)} onChange={() => toggleDay(i + 1)} />
          ))}
        </div>
        {fields.weekly_off && <p className="text-sm text-danger">{fields.weekly_off}</p>}
      </fieldset>
      {save.isError && !Object.keys(fields).length && <ErrorNote>{errorText(save.error)}</ErrorNote>}
      {save.isSuccess && <SuccessNote>Work policy saved.</SuccessNote>}
      <div className="sm:col-span-3">
        <Button type="submit" disabled={save.isPending}>
          Save work policy
        </Button>
      </div>
    </form>
  );
}

function Holidays({ config, location }: { config: HrConfig; location: string }) {
  const client = useQueryClient();
  const [date, setDate] = useState('');
  const [name, setName] = useState('');
  const [regional, setRegional] = useState(false);
  const add = useMutation({
    mutationFn: () => api('/hr/config/holidays', { method: 'POST', body: { location, date, name, regional } }),
    onSuccess: () => {
      setDate('');
      setName('');
      void client.invalidateQueries({ queryKey: KEY });
    },
  });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/hr/config/holidays/${id}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: KEY }),
  });
  const fields = add.error instanceof ApiError ? add.error.fieldErrors : {};
  const rows = config.holidays.filter((h) => h.location === location);
  return (
    <>
      <p className="mb-2 text-sm text-warning">Seeded holidays are demo data: verify them against the official list.</p>
      <ul className="divide-y divide-ink/10 text-sm">
        {rows.map((h) => (
          <li key={h.id} className="flex items-center justify-between gap-2 py-1.5">
            <span>
              {day(h.date)}: {h.name}
              {h.regional && <span className="ml-1 text-xs text-muted">(state)</span>}
            </span>
            <Button variant="ghost" onClick={() => remove.mutate(h.id)} disabled={remove.isPending}>
              Remove<span className="sr-only"> {h.name}</span>
            </Button>
          </li>
        ))}
      </ul>
      <form
        className="mt-4 grid gap-3 sm:grid-cols-[1fr_2fr_auto] sm:items-end"
        onSubmit={(e) => {
          e.preventDefault();
          add.mutate();
        }}
        aria-label="Add a holiday"
      >
        <TextField label="Date" type="date" value={date} onChange={(e) => setDate(e.target.value)} error={fields.date} required />
        <TextField
          label="Holiday name"
          value={name}
          maxLength={120}
          onChange={(e) => setName(e.target.value)}
          error={fields.name}
          required
        />
        <Button type="submit" disabled={add.isPending || !date || name.trim().length < 2}>
          Add holiday
        </Button>
        <div className="sm:col-span-3">
          <Check label="State (regional) holiday" checked={regional} onChange={setRegional} />
        </div>
      </form>
    </>
  );
}

export function HrSettingsPage() {
  useDocumentTitle('HR settings');
  const query = useQuery({ queryKey: KEY, queryFn: () => api<HrConfig>('/hr/config') });
  const [picked, setPicked] = useState('');
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not load HR settings.</ErrorNote>;
  const config = query.data;
  const location =
    picked || config.locations.find((l) => config.leave_types.some((t) => t.location === l.id))?.id || config.locations[0]?.id || '';
  const types = config.leave_types.filter((t) => t.location === location);
  const wp = config.work_policies.find((p) => p.location === location);
  return (
    <>
      <PageHeader
        title="HR settings"
        intro="Leave types, holiday calendars and the work policy for each location. Changes apply to new requests at once and are audited."
      />
      <div className="mb-6 max-w-sm">
        <SelectField label="Location" value={location} onChange={(e) => setPicked(e.target.value)}>
          {config.locations.map((l) => (
            <option key={l.id} value={l.id}>
              {l.name}
            </option>
          ))}
        </SelectField>
      </div>
      <section className="glass mb-6 rounded-xl2 p-5" aria-labelledby="types-heading">
        <h2 id="types-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Leave types
        </h2>
        {types.length ? (
          <ul className="space-y-3">
            {types.map((lt) => (
              <LeaveTypeEditor key={lt.id} lt={lt} />
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted">No leave types at this location yet. Run the seed or add them through the API.</p>
        )}
      </section>
      {wp && (
        <section className="glass mb-6 rounded-xl2 p-5" aria-labelledby="wp-heading">
          <h2 id="wp-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            Work policy
          </h2>
          <WorkPolicyForm key={wp.location} wp={wp} />
        </section>
      )}
      <section className="glass rounded-xl2 p-5" aria-labelledby="hol-heading">
        <h2 id="hol-heading" className="mb-3 font-display text-xl font-semibold text-ink">
          Holiday calendar
        </h2>
        <Holidays config={config} location={location} />
      </section>
    </>
  );
}
