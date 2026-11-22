import { useId, useState } from 'react';
import { errorText } from '@/lib/pipeline';
import { ist, istRange } from '@/lib/interviews';
import type { Slot } from '@/lib/types';
import { Button, ErrorNote } from './ui';

/**
 * Pick one of HIRA's slots. Choosing a slot holds it for a short while (so no one
 * else can take it); "Confirm" books it. Shared by the dashboard and the email link page.
 */
export function SlotPicker({
  slots,
  holdMinutes = 30,
  onHold,
  onConfirm,
  legend,
}: {
  slots: Slot[];
  holdMinutes?: number;
  onHold: (slotId: string) => Promise<{ slot: Slot }>;
  onConfirm: (slotId: string) => Promise<unknown>;
  legend: string;
}) {
  const name = useId();
  const [chosen, setChosen] = useState<string>(() => slots.find((s) => s.status === 'held')?.id ?? '');
  const [heldUntil, setHeldUntil] = useState<string | null>(() => slots.find((s) => s.status === 'held')?.held_until ?? null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const pick = async (slotId: string) => {
    setChosen(slotId);
    setError('');
    setBusy(true);
    try {
      const result = await onHold(slotId);
      setHeldUntil(result.slot.held_until);
    } catch (e) {
      setHeldUntil(null);
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  const confirm = async () => {
    setBusy(true);
    setError('');
    try {
      await onConfirm(chosen);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (slots.length === 0) {
    return <p className="text-sm text-muted">HIRA is looking for new times. You will get an email as soon as there are slots to pick.</p>;
  }
  return (
    <div className="flex flex-col gap-3">
      <fieldset>
        <legend className="mb-2 text-sm font-semibold text-ink">{legend}</legend>
        <div className="grid gap-2 sm:grid-cols-2">
          {slots.map((slot) => (
            <label
              key={slot.id}
              className={`flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm ${
                chosen === slot.id ? 'border-primary bg-primary-soft' : 'border-ink/15 bg-white/80 hover:border-primary'
              }`}
            >
              <input
                type="radio"
                name={name}
                value={slot.id}
                checked={chosen === slot.id}
                onChange={() => void pick(slot.id)}
                disabled={busy}
                className="h-4 w-4 accent-primary"
              />
              <span className="text-ink">{istRange(slot.starts_at, slot.ends_at)}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <p role="status" aria-live="polite" className="min-h-5 text-sm text-ink-soft">
        {chosen && heldUntil ? `Held for you until ${ist(heldUntil)}. Confirm within ${holdMinutes} minutes.` : ''}
      </p>
      {error && <ErrorNote>{error}</ErrorNote>}
      <Button className="self-start" onClick={() => void confirm()} disabled={!chosen || !heldUntil || busy}>
        Confirm this time
      </Button>
    </div>
  );
}
