import { useEffect, useState } from 'react';
import { onWakeChange } from '@/lib/api';

/** Shown while a request waits for the free-tier server to wake up (the API client retries by itself). */
export function WakeNotice() {
  const [waking, setWaking] = useState(false);
  useEffect(() => onWakeChange(setWaking), []);
  return (
    <div role="status" aria-live="polite" className="pointer-events-none fixed inset-x-0 top-3 z-[60] flex justify-center px-4">
      {waking && (
        <p className="pointer-events-auto flex items-center gap-3 rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-white shadow-lift">
          <span
            className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent motion-reduce:animate-none"
            aria-hidden="true"
          />
          Waking up the server, this can take up to a minute…
        </p>
      )}
    </div>
  );
}
