import { useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import { rupees } from '@/lib/interviews';
import type { OfferDraft } from '@/lib/offers';
import { Button, ErrorNote, SelectField, TextField } from './ui';

/** Offer terms (INR per year). Used to draft a new offer and to edit a draft. */
export function OfferForm({
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  onCancel,
}: {
  initial: OfferDraft;
  submitLabel: string;
  busy: boolean;
  error: unknown;
  onSubmit: (draft: OfferDraft) => void;
  onCancel?: () => void;
}) {
  const [draft, setDraft] = useState(initial);
  const managers = useQuery({
    queryKey: ['hiring-managers'],
    queryFn: () => api<{ id: string; full_name: string }[]>('/hiring-managers'),
  });
  const fields = error instanceof ApiError ? error.fieldErrors : {};
  const set = (key: keyof OfferDraft) => (e: { target: { value: string } }) => setDraft({ ...draft, [key]: e.target.value });
  const total = Number(draft.fixed_pay || 0) + Number(draft.variable_pay || 0);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    onSubmit(draft);
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Offer terms">
      <TextField
        label="Designation"
        value={draft.designation}
        onChange={set('designation')}
        error={fields.designation}
        required
        maxLength={120}
      />
      <SelectField
        label="Reporting manager"
        value={draft.reporting_manager_id}
        onChange={set('reporting_manager_id')}
        error={fields.reporting_manager_id}
        hint="Defaults to the job's hiring manager."
      >
        <option value="">Job's hiring manager</option>
        {managers.data?.map((m) => (
          <option key={m.id} value={m.id}>
            {m.full_name}
          </option>
        ))}
      </SelectField>
      <div className="grid gap-3 sm:grid-cols-2">
        <TextField
          label="Joining date"
          type="date"
          value={draft.joining_date}
          onChange={set('joining_date')}
          error={fields.joining_date}
          required
        />
        <TextField
          label="Offer expires on"
          type="date"
          value={draft.expires_on}
          onChange={set('expires_on')}
          error={fields.expires_on}
          required
        />
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        <TextField
          label="Fixed pay (₹ per year)"
          inputMode="numeric"
          value={draft.fixed_pay}
          onChange={set('fixed_pay')}
          error={fields.fixed_pay}
          required
        />
        <TextField
          label="Variable pay (₹ per year)"
          inputMode="numeric"
          value={draft.variable_pay}
          onChange={set('variable_pay')}
          error={fields.variable_pay}
        />
        <TextField
          label="Joining bonus (₹, optional)"
          inputMode="numeric"
          value={draft.joining_bonus}
          onChange={set('joining_bonus')}
          error={fields.joining_bonus}
        />
      </div>
      <p className="text-sm text-ink-soft" aria-live="polite">
        Total annual compensation: <span className="font-semibold text-ink">{Number.isFinite(total) ? rupees(total) : '-'}</span>
      </p>
      {error != null && !Object.keys(fields).length && <ErrorNote>{error instanceof Error ? error.message : 'Could not save.'}</ErrorNote>}
      <div className="flex gap-2">
        <Button type="submit" disabled={busy}>
          {submitLabel}
        </Button>
        {onCancel && (
          <Button variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}
