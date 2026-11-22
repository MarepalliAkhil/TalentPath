import { useEffect, useId, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api, ApiError } from '@/lib/api';
import {
  dateRange,
  day,
  LEAVE_STATUS_STYLE,
  type Balances,
  type HrCard,
  type LeaveCheck,
  type LeaveRequest,
  type Onboarding,
  type OnboardingTask,
} from '@/lib/hr';
import { errorText } from '@/lib/pipeline';
import { Icon } from './Icon';
import { Button, ErrorNote, SelectField, SuccessNote, TextAreaField, TextField } from './ui';

export function LeaveStatus({ status, label }: { status: string; label: string }) {
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${LEAVE_STATUS_STYLE[status] ?? 'bg-canvas-deep text-ink'}`}>
      {label}
    </span>
  );
}

export function ProgressBar({ percent, label }: { percent: number; label: string }) {
  return (
    <div>
      <div className="flex justify-between text-sm">
        <span className="font-medium text-ink">{label}</span>
        <span className="text-muted">{percent}%</span>
      </div>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={percent}
        className="mt-1 h-2.5 overflow-hidden rounded-full bg-canvas-deep"
      >
        <div className="h-full rounded-full bg-primary" style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

/** Clash warnings: they inform, they never block. */
export function ClashWarnings({ warnings }: { warnings: string[] }) {
  if (!warnings.length) return null;
  return (
    <div className="rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning" role="status">
      <p className="font-semibold">Team availability</p>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {warnings.map((w) => (
          <li key={w}>{w}</li>
        ))}
      </ul>
      <p className="mt-1 text-xs">This is a heads-up; you can still go ahead.</p>
    </div>
  );
}

function DayBreakdown({ check }: { check: LeaveCheck }) {
  const skipped = check.breakdown.filter((r) => r.counted === 0);
  const sandwich = check.breakdown.filter((r) => r.kind === 'sandwich');
  return (
    <div className="rounded-xl border border-primary/20 bg-primary-soft/60 px-4 py-3 text-sm" aria-live="polite">
      <p className="font-semibold text-primary-strong">
        Days counted: <span data-testid="days-counted">{check.days_label}</span>
      </p>
      {skipped.length > 0 && (
        <p className="mt-1 text-ink-soft">
          Not counted: {skipped.map((r) => `${day(r.date, false)}${r.label ? ` (${r.label})` : r.kind === 'weekly_off' ? ' (weekly off)' : ''}`).join(', ')}.
        </p>
      )}
      {sandwich.length > 0 && (
        <p className="mt-1 text-ink-soft">
          Sandwich rule: {sandwich.map((r) => day(r.date, false)).join(', ')} {sandwich.length === 1 ? 'is' : 'are'} counted because leave sits on both sides.
        </p>
      )}
      {check.available !== null && <p className="mt-1 text-ink-soft">Available for these dates: {check.available} days.</p>}
      {check.needs_hr_approval && <p className="mt-1 text-ink-soft">Longer than the HR threshold: your manager, then HR, will approve it.</p>}
    </div>
  );
}

const FIELD_ORDER = ['leave_type', 'start', 'end', 'half', 'document'];

/** Apply for leave. The engine's preview shows the days counted, rule errors and team warnings before submitting. */
export function LeaveForm({ balances, onDone }: { balances: Balances; onDone?: (leave: LeaveRequest) => void }) {
  const client = useQueryClient();
  const [type, setType] = useState(balances.types.find((t) => !t.unpaid)?.code ?? '');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [half, setHalf] = useState('');
  const [reason, setReason] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const fileId = useId();
  const info = balances.types.find((t) => t.code === type);
  const single = !end || end === start;
  const halfAllowed = Boolean(info?.half_day_allowed && single);
  const effectiveHalf = halfAllowed ? half : '';
  const effectiveEnd = end || start;

  const preview = useQuery({
    queryKey: ['leave-preview', type, start, effectiveEnd, effectiveHalf, Boolean(file)],
    queryFn: () =>
      api<LeaveCheck>('/leave/preview', {
        method: 'POST',
        body: { leave_type: type, start, end: effectiveEnd, half: effectiveHalf, has_document: Boolean(file) },
      }),
    enabled: Boolean(type && start),
    staleTime: 10_000,
  });

  const submit = useMutation({
    mutationFn: () => {
      if (file) {
        const form = new FormData();
        form.set('leave_type', type);
        form.set('start', start);
        form.set('end', effectiveEnd);
        form.set('half', effectiveHalf);
        form.set('reason', reason);
        form.set('document', file);
        return api<LeaveRequest>('/leave/requests', { method: 'POST', form });
      }
      return api<LeaveRequest>('/leave/requests', {
        method: 'POST',
        body: { leave_type: type, start, end: effectiveEnd, half: effectiveHalf, reason },
      });
    },
    onSuccess: (leave) => {
      void client.invalidateQueries({ queryKey: ['leave-balances'] });
      void client.invalidateQueries({ queryKey: ['leave-requests'] });
      setStart('');
      setEnd('');
      setHalf('');
      setReason('');
      setFile(null);
      onDone?.(leave);
    },
  });

  useEffect(() => {
    if (!halfAllowed) setHalf('');
  }, [halfAllowed]);

  const check = preview.data;
  const serverErrors = submit.error instanceof ApiError ? submit.error.fieldErrors : {};
  const errors = { ...(check?.errors ?? {}), ...serverErrors };
  const firstError = FIELD_ORDER.map((k) => errors[k]).find(Boolean);
  const canSubmit = Boolean(check?.ok) && !submit.isPending && !preview.isFetching;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (canSubmit) submit.mutate();
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" aria-label="Apply for leave" noValidate>
      <SelectField label="Leave type" value={type} onChange={(e) => setType(e.target.value)} error={errors.leave_type} required>
        {balances.types.map((t) => {
          const b = balances.balances.find((x) => x.type === t.code);
          return (
            <option key={t.code} value={t.code}>
              {t.name}
              {b && !b.unpaid ? ` (${b.available} available)` : t.unpaid ? ' (unpaid)' : ''}
            </option>
          );
        })}
      </SelectField>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField label="From" type="date" value={start} onChange={(e) => setStart(e.target.value)} error={errors.start} required />
        <TextField label="To" type="date" value={end} min={start || undefined} onChange={(e) => setEnd(e.target.value)} error={errors.end} hint="Leave empty for a single day." />
      </div>
      {halfAllowed && (
        <SelectField label="Duration" value={half} onChange={(e) => setHalf(e.target.value)} error={errors.half}>
          <option value="">Full day</option>
          <option value="first">First half</option>
          <option value="second">Second half</option>
        </SelectField>
      )}
      {info && info.min_notice_days > 0 && (
        <p className="-mt-2 text-xs text-muted">
          {info.name} needs {info.min_notice_days} {info.min_notice_days === 1 ? "day's" : "days'"} notice.
        </p>
      )}
      {(check?.needs_document || file) && (
        <div className="flex flex-col gap-1.5">
          <label htmlFor={fileId} className="text-sm font-medium text-ink">
            Supporting document (PDF, PNG or JPEG, up to 5 MB)
          </label>
          <input
            id={fileId}
            type="file"
            accept="application/pdf,image/png,image/jpeg"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            aria-invalid={Boolean(errors.document) || undefined}
            className="text-sm"
          />
          {errors.document && <p className="text-sm font-medium text-danger">{errors.document}</p>}
        </div>
      )}
      <TextAreaField label="Reason (optional)" rows={2} maxLength={1000} value={reason} onChange={(e) => setReason(e.target.value)} hint="Only you, your approvers and HR can read it." />

      {check && check.days > 0 && <DayBreakdown check={check} />}
      {check && <ClashWarnings warnings={check.warnings} />}
      {firstError && !preview.isFetching && <ErrorNote>{firstError}</ErrorNote>}
      {submit.isError && !Object.keys(serverErrors).length && <ErrorNote>{errorText(submit.error)}</ErrorNote>}
      {submit.isSuccess && (
        <SuccessNote>
          Sent for approval: {submit.data.days_label} of {submit.data.leave_type_name.toLowerCase()}, waiting for {submit.data.approver}.
        </SuccessNote>
      )}
      <div>
        <Button type="submit" disabled={!canSubmit}>
          {submit.isPending ? 'Sending…' : check?.ok ? `Apply for ${check.days_label}` : 'Apply'}
        </Button>
      </div>
    </form>
  );
}

function TaskRow({ task, onChanged }: { task: OnboardingTask; onChanged: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const fileId = useId();
  const complete = useMutation({
    mutationFn: () => {
      if (task.kind === 'upload') {
        const form = new FormData();
        if (file) form.set('document', file);
        return api(`/onboarding/tasks/${task.id}/complete`, { method: 'POST', form });
      }
      return api(`/onboarding/tasks/${task.id}/complete`, { method: 'POST', body: {} });
    },
    onSuccess: onChanged,
  });
  const action = task.kind === 'acknowledge' ? 'I have read and accept' : task.kind === 'upload' ? 'Upload and mark done' : 'Mark done';
  return (
    <li className="flex flex-col gap-2 rounded-xl border border-ink/10 bg-white/70 p-3 sm:flex-row sm:items-start sm:justify-between">
      <div className="flex gap-3">
        <span
          aria-hidden="true"
          className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full ${task.done ? 'bg-success text-white' : 'border-2 border-ink/25'}`}
        >
          {task.done && <Icon name="check" className="h-4 w-4" />}
        </span>
        <div>
          <p className={`font-semibold ${task.done ? 'text-muted line-through' : 'text-ink'}`}>
            {task.title}
            <span className="sr-only">{task.done ? ' (done)' : ' (to do)'}</span>
          </p>
          {task.description && <p className="text-sm text-muted">{task.description}</p>}
          <p className="mt-0.5 text-xs text-ink-soft">
            {task.category_label} · {task.owner_label}: {task.owner_name} · due {day(task.due_on)}
            {task.overdue && <span className="ml-1 font-semibold text-danger">Overdue</span>}
            {task.done && task.done_by && ` · done by ${task.done_by}`}
          </p>
        </div>
      </div>
      {task.can_complete && (
        <div className="flex flex-col gap-2 sm:items-end">
          {task.kind === 'upload' && (
            <>
              <label htmlFor={fileId} className="sr-only">
                Document for {task.title}
              </label>
              <input id={fileId} type="file" accept="application/pdf,image/png,image/jpeg" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="max-w-56 text-xs" />
            </>
          )}
          <Button
            variant="secondary"
            aria-label={`${action}: ${task.title}`}
            onClick={() => complete.mutate()}
            disabled={complete.isPending || (task.kind === 'upload' && !file)}
          >
            {action}
          </Button>
          {complete.isError && <p className="text-sm text-danger">{errorText(complete.error)}</p>}
        </div>
      )}
    </li>
  );
}

export function Checklist({ data, queryKey }: { data: Onboarding; queryKey: unknown[] }) {
  const client = useQueryClient();
  const refresh = () => {
    void client.invalidateQueries({ queryKey });
    void client.invalidateQueries({ queryKey: ['onboarding'] });
  };
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby="checklist-heading">
      <h2 id="checklist-heading" className="font-display text-xl font-semibold text-ink">
        Onboarding checklist
      </h2>
      <div className="mt-3">
        <ProgressBar percent={data.progress.percent} label={`${data.progress.done} of ${data.progress.total} done`} />
      </div>
      <ul className="mt-4 space-y-2">
        {data.tasks.map((t) => (
          <TaskRow key={t.id} task={t} onChanged={refresh} />
        ))}
      </ul>
    </section>
  );
}

export function PersonCard({ role, person }: { role: string; person: Onboarding['manager'] }) {
  return (
    <div className="glass rounded-xl2 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">{role}</p>
      {person ? (
        <>
          <p className="mt-1 font-display text-lg font-semibold text-ink">{person.name}</p>
          <p className="text-sm text-ink-soft">
            {person.designation} · {person.department}
          </p>
          <a href={`mailto:${person.email}`} className="mt-1 inline-block text-sm font-semibold text-primary-strong underline">
            {person.email}
          </a>
        </>
      ) : (
        <p className="mt-1 text-sm text-muted">Not assigned yet. HR will set this up.</p>
      )}
    </div>
  );
}

export function FirstWeek({ plan }: { plan: Onboarding['first_week'] }) {
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby="first-week-heading">
      <h2 id="first-week-heading" className="font-display text-xl font-semibold text-ink">
        Your first week
      </h2>
      <ol className="mt-3 space-y-2 text-sm">
        {plan.map((s) => (
          <li key={`${s.day}-${s.starts}`} className="flex gap-3">
            <span className="w-28 shrink-0 font-semibold text-ink">
              {day(s.day, false)}, {s.starts}
            </span>
            <span className="text-ink-soft">
              {s.title}
              {s.host && <span className="block text-xs text-muted">with {s.host}</span>}
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

// ---------------------------------------------------------------- Ask HIRA cards
/** The assistant never submits leave: the employee checks the engine's result and presses Confirm. */
function LeaveConfirm({ card, onSent }: { card: Extract<HrCard, { kind: 'leave_confirm' }>; onSent: (text: string) => void }) {
  const client = useQueryClient();
  const confirm = useMutation({
    mutationFn: () => api<LeaveRequest>('/leave/requests', { method: 'POST', body: card.payload }),
    onSuccess: (leave) => {
      void client.invalidateQueries({ queryKey: ['leave-balances'] });
      void client.invalidateQueries({ queryKey: ['leave-requests'] });
      onSent(`Done. ${leave.days_label} of ${leave.leave_type_name.toLowerCase()} sent to ${leave.approver} for approval.`);
    },
  });
  const { check, payload } = card;
  const errors = Object.values(check.errors);
  return (
    <div className="mt-2 rounded-lg bg-white p-3 text-sm" aria-label="Leave request to confirm" role="group">
      <p className="font-semibold text-ink">{card.type_name || payload.leave_type}</p>
      <p className="text-ink-soft">{dateRange(payload.start, payload.end, payload.half)}</p>
      {check.ok && <p className="mt-1 text-ink">Days counted: {check.days_label}</p>}
      {errors.length > 0 && (
        <ul className="mt-1 list-disc pl-5 text-danger">
          {errors.map((e) => (
            <li key={e}>{e}</li>
          ))}
        </ul>
      )}
      {check.warnings.map((w) => (
        <p key={w} className="mt-1 text-warning">
          {w}
        </p>
      ))}
      {confirm.isSuccess ? (
        <p className="mt-2 font-semibold text-success">Sent for approval.</p>
      ) : check.ok ? (
        <div className="mt-2 flex flex-wrap gap-2">
          <Button onClick={() => confirm.mutate()} disabled={confirm.isPending}>
            Confirm
          </Button>
          <Link to="/leave" className="inline-flex min-h-11 items-center text-sm font-semibold text-primary-strong underline">
            Change on the leave page
          </Link>
        </div>
      ) : (
        <Link to="/leave" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
          Open the leave page
        </Link>
      )}
      {confirm.isError && <p className="mt-1 text-danger">{errorText(confirm.error)}</p>}
    </div>
  );
}

export function HrCardView({ card, onSent }: { card: HrCard; onSent: (text: string) => void }) {
  switch (card.kind) {
    case 'balances':
      return (
        <table className="mt-2 w-full rounded-lg bg-white text-sm">
          <caption className="sr-only">Your leave balances</caption>
          <thead>
            <tr className="text-left text-xs text-muted">
              <th scope="col" className="px-2 py-1">Type</th>
              <th scope="col" className="px-2 py-1 text-right">Available</th>
            </tr>
          </thead>
          <tbody>
            {card.rows.map((r) => (
              <tr key={r.type}>
                <td className="px-2 py-1 text-ink">{r.name}</td>
                <td className="px-2 py-1 text-right font-semibold text-ink">{r.unpaid ? 'Unpaid' : r.available}</td>
              </tr>
            ))}
          </tbody>
        </table>
      );
    case 'leave_confirm':
      return <LeaveConfirm card={card} onSent={onSent} />;
    case 'holidays':
      return (
        <div className="mt-2 rounded-lg bg-white p-2 text-sm">
          <ul className="space-y-0.5">
            {card.rows.map((h) => (
              <li key={h.date} className="flex justify-between gap-2">
                <span className="text-ink">{h.name}</span>
                <span className="text-muted">{day(h.date, false)}</span>
              </li>
            ))}
          </ul>
          <p className="mt-1 text-xs text-muted">{card.note}</p>
        </div>
      );
    case 'person':
      return (
        <p className="mt-2 rounded-lg bg-white p-2 text-sm">
          <span className="block text-xs text-muted">{card.role}</span>
          <span className="font-semibold text-ink">{card.name}</span>, {card.designation}
        </p>
      );
    case 'checklist':
      return (
        <div className="mt-2 rounded-lg bg-white p-2 text-sm">
          <ProgressBar percent={card.progress.percent} label={`${card.progress.done} of ${card.progress.total} done`} />
          <ul className="mt-1 space-y-0.5">
            {card.rows.map((r) => (
              <li key={r.title} className="text-ink-soft">
                {r.title} <span className="text-xs text-muted">(due {day(r.due_on, false)})</span>
              </li>
            ))}
          </ul>
        </div>
      );
    case 'attendance':
      return (
        <dl className="mt-2 grid grid-cols-3 gap-1 rounded-lg bg-white p-2 text-center text-xs">
          {(['present', 'late', 'missing_checkout'] as const).map((k) => (
            <div key={k}>
              <dt className="text-muted">{k === 'missing_checkout' ? 'No check-out' : k === 'late' ? 'Late' : 'Present'}</dt>
              <dd className="text-base font-semibold text-ink">{card.counts[k] ?? 0}</dd>
            </div>
          ))}
        </dl>
      );
    case 'pending':
      return (
        <ul className="mt-2 space-y-1 text-sm">
          {card.rows.map((r) => (
            <li key={`${r.kind}-${r.name}-${r.detail}`} className="rounded-lg bg-white px-3 py-1.5">
              <span className="font-semibold text-ink">{r.name}</span>
              <span className="block text-xs text-muted">
                {r.detail}
                {r.escalated && ' · escalated'}
              </span>
            </li>
          ))}
        </ul>
      );
    case 'source':
      return (
        <p className="mt-2 text-xs text-muted">
          Source:{' '}
          <Link to={card.link} className="font-semibold text-primary-strong underline">
            {card.title}
          </Link>
        </p>
      );
    default:
      return null;
  }
}
