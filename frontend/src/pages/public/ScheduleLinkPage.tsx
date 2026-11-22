import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { HiraAvatar } from '@/components/HiraAvatar';
import { SlotPicker } from '@/components/SlotPicker';
import { ErrorNote, PageLoader, SuccessNote } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { assistant } from '@/lib/brand';
import { useDocumentTitle, useNoIndex } from '@/lib/hooks';
import type { ScheduleLink, Slot } from '@/lib/types';

/** Pick an interview slot from the email link, without signing in (single use, expires). */
export function ScheduleLinkPage() {
  const { token = '' } = useParams();
  useDocumentTitle('Pick your interview time');
  useNoIndex();
  const [booked, setBooked] = useState<{ when: string; mode: string } | null>(null);
  const link = useQuery({
    queryKey: ['schedule-link', token],
    queryFn: () => api<ScheduleLink>(`/schedule/${encodeURIComponent(token)}`),
    retry: false,
    enabled: !booked,
  });
  const path = `/schedule/${encodeURIComponent(token)}`;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <div className="mb-6 flex items-center gap-4">
        <HiraAvatar pose="welcome" size={56} />
        <div>
          <h1 className="font-display text-2xl font-semibold text-ink sm:text-3xl">Pick your interview time</h1>
          <p className="text-sm text-muted">{assistant.display}</p>
        </div>
      </div>
      {booked ? (
        <SuccessNote>
          You are booked for {booked.when} ({booked.mode}). A calendar invite is on its way. Sign in to see the details or to
          reschedule.
        </SuccessNote>
      ) : link.isPending ? (
        <PageLoader />
      ) : link.isError ? (
        <ErrorNote>
          {link.error instanceof ApiError && link.error.status === 410
            ? 'This link has expired or was already used.'
            : 'This scheduling link is not valid.'}{' '}
          <Link to="/login" className="font-semibold underline">
            Sign in
          </Link>{' '}
          to see your interviews.
        </ErrorNote>
      ) : (
        <section className="glass rounded-xl2 p-5" aria-labelledby="link-heading">
          <h2 id="link-heading" className="font-display text-xl font-semibold text-ink">
            {link.data.job.title}
          </h2>
          <p className="mb-4 text-sm text-muted">
            {link.data.round.name} · {link.data.round.mode_label} · {link.data.round.duration_minutes} minutes. Meeting links in
            this demo are simulated.
          </p>
          {link.data.status === 'pending' ? (
            <SlotPicker
              slots={link.data.slots}
              holdMinutes={link.data.hold_minutes}
              legend="Times when your interviewers are free (IST)"
              onHold={async (slot) => {
                try {
                  return await api<{ slot: Slot }>(`${path}/hold`, { method: 'POST', body: { slot } });
                } catch (e) {
                  void link.refetch();
                  throw e;
                }
              }}
              onConfirm={async (slot) => {
                const result = await api<{ when: string; mode: string }>(`${path}/confirm`, { method: 'POST', body: { slot } });
                setBooked(result);
              }}
            />
          ) : (
            <p className="text-sm text-ink-soft">This interview is already arranged. Sign in to see the details.</p>
          )}
        </section>
      )}
    </div>
  );
}
