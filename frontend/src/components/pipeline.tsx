import { useId, useState, type FormEvent } from 'react';
import { DEFAULT_REASONS, STAGE_LABELS } from '@/lib/pipeline';
import type { StaffApplication } from '@/lib/types';
import { Dialog } from './Dialog';
import { Button, ErrorNote, SelectField, TextAreaField } from './ui';

/** Reason is required; the note stays internal and is never shown to the candidate. */
export function RejectDialog({
  count,
  reasons = DEFAULT_REASONS,
  onConfirm,
  onClose,
  busy,
  error,
}: {
  count: number;
  reasons?: { value: string; label: string }[];
  onConfirm: (reason: string, note: string) => void;
  onClose: () => void;
  busy?: boolean;
  error?: string;
}) {
  const [reason, setReason] = useState('');
  const [note, setNote] = useState('');
  const [problem, setProblem] = useState('');
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!reason) {
      setProblem('Choose a reason.');
      return;
    }
    onConfirm(reason, note);
  };
  return (
    <Dialog
      title={count === 1 ? 'Mark as not selected' : `Mark ${count} candidates as not selected`}
      description="The candidate gets a short, kind message with other matching jobs. They never see the reason or your note."
      onClose={onClose}
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        {error && <ErrorNote>{error}</ErrorNote>}
        <SelectField label="Reason" value={reason} error={problem} onChange={(e) => setReason(e.target.value)} required>
          <option value="">Choose a reason…</option>
          {reasons.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </SelectField>
        <TextAreaField label="Internal note (optional)" rows={3} maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
        <div className="flex gap-2">
          <Button type="submit" variant="danger" disabled={busy}>
            {busy ? 'Saving…' : 'Confirm'}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

/** Keyboard-friendly alternative to drag and drop. */
export function MoveTo({
  app,
  onMove,
  disabled,
}: {
  app: StaffApplication;
  onMove: (status: string) => void;
  disabled?: boolean;
}) {
  const id = useId();
  const [target, setTarget] = useState('');
  if (!app.allowed_transitions.length) return null;
  const who = app.blind || !app.candidate.full_name ? app.candidate.code : app.candidate.full_name;
  return (
    <div className="flex items-center gap-1.5">
      <label htmlFor={id} className="sr-only">
        Move {who} to
      </label>
      <select
        id={id}
        value={target}
        onChange={(e) => setTarget(e.target.value)}
        className="min-h-9 flex-1 rounded-lg border border-ink/15 bg-white px-2 text-sm"
      >
        <option value="">Move to…</option>
        {app.allowed_transitions.map((s) => (
          <option key={s} value={s}>
            {STAGE_LABELS[s] ?? s}
          </option>
        ))}
      </select>
      <Button
        variant="secondary"
        className="min-h-9 px-3"
        disabled={!target || disabled}
        onClick={() => {
          onMove(target);
          setTarget('');
        }}
      >
        Move<span className="sr-only"> {who}</span>
      </Button>
    </div>
  );
}
