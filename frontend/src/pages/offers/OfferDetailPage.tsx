import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Dialog } from '@/components/Dialog';
import { Icon } from '@/components/Icon';
import { OfferBadge } from '@/components/OfferBadge';
import { OfferForm } from '@/components/OfferForm';
import { draftBody, draftFrom, type OfferDraft } from '@/lib/offers';
import { TermsList } from '@/components/TermsList';
import { Button, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import { ist } from '@/lib/interviews';
import { errorText } from '@/lib/pipeline';
import type { StaffOffer } from '@/lib/types';

function ReasonDialog({ title, action, busy, error, onConfirm, onClose }: { title: string; action: string; busy: boolean; error: unknown; onConfirm: (reason: string) => void; onClose: () => void }) {
  const [reason, setReason] = useState('');
  return (
    <Dialog title={title} onClose={onClose}>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          onConfirm(reason);
        }}
        className="flex flex-col gap-3"
      >
        <TextAreaField label="Reason" rows={3} maxLength={500} value={reason} onChange={(e) => setReason(e.target.value)} hint="At least 10 characters. Recorded in the audit log." required />
        {error != null && <ErrorNote>{errorText(error)}</ErrorNote>}
        <div className="flex gap-2">
          <Button type="submit" variant="danger" disabled={busy || reason.trim().length < 10}>
            {action}
          </Button>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

export function OfferDetailPage() {
  const { id = '' } = useParams();
  const client = useQueryClient();
  const offer = useQuery({ queryKey: ['offer', id], queryFn: () => api<StaffOffer>(`/offers/${id}`) });
  useDocumentTitle('Offer');
  const [editing, setEditing] = useState(false);
  const [asking, setAsking] = useState<'reject' | 'revoke' | null>(null);
  const update = (data: StaffOffer) => {
    client.setQueryData(['offer', id], data);
    void client.invalidateQueries({ queryKey: ['offers'] });
  };
  const act = useMutation({
    mutationFn: ({ name, reason }: { name: string; reason?: string }) =>
      api<StaffOffer>(`/offers/${id}/${name}`, { method: 'POST', body: reason ? { reason } : {} }),
    onSuccess: (data) => {
      update(data);
      setAsking(null);
    },
  });
  const [confirmHire, setConfirmHire] = useState(false);
  const hire = useMutation({
    mutationFn: () => api<{ employee: { id: string; code: string; name: string } }>(`/offers/${id}/hire`, { method: 'POST', body: {} }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['offer', id] });
      void client.invalidateQueries({ queryKey: ['offers'] });
      void client.invalidateQueries({ queryKey: ['onboarding'] });
      setConfirmHire(false);
    },
  });
  const edit = useMutation({
    mutationFn: (draft: OfferDraft) => api<StaffOffer>(`/offers/${id}`, { method: 'PATCH', body: draftBody(draft) }),
    onSuccess: (data) => {
      update(data);
      setEditing(false);
    },
  });

  if (offer.isPending) return <PageLoader />;
  if (offer.isError || !offer.data) return <ErrorNote>We could not find this offer.</ErrorNote>;
  const o = offer.data;
  const who = o.candidate.full_name ?? o.candidate.code;
  const steps = [
    { label: 'Drafted', who: o.created_by, at: o.created_at, done: true },
    { label: 'Hiring manager approval', who: o.approvals.hiring_manager.name, at: o.approvals.hiring_manager.at, done: !!o.approvals.hiring_manager.at },
    { label: 'HR approval', who: o.approvals.hr_admin.name, at: o.approvals.hr_admin.at, done: !!o.approvals.hr_admin.at },
    { label: 'Sent to the candidate', who: null, at: o.sent_at, done: !!o.sent_at },
    { label: o.status === 'declined' ? 'Declined' : 'Accepted', who: null, at: o.responded_at, done: !!o.responded_at },
  ];

  return (
    <>
      <PageHeader
        title={`Offer: ${who}`}
        intro={`${o.job.title} · expires ${formatDate(o.expires_on)}`}
        actions={
          <Link to="/offers" className="text-sm font-semibold text-primary-strong underline">
            All offers
          </Link>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <OfferBadge offer={o} />
        <a href={`/api/offers/${id}/letter`} target="_blank" rel="noreferrer" className="inline-flex min-h-11 items-center gap-2 text-sm font-semibold text-primary-strong underline">
          <Icon name="document" className="h-4 w-4" /> {o.has_letter ? 'Offer letter (PDF)' : 'Preview the letter (PDF)'}
        </a>
      </div>
      {o.hired && (
        <SuccessNote>
          Hired: employee {o.hired.code}, joining {formatDate(o.hired.joined_on)}.{' '}
          <Link to={`/onboarding/${o.hired.employee}`} className="font-semibold underline">
            See onboarding progress
          </Link>
        </SuccessNote>
      )}
      {act.isError && !asking && <ErrorNote>{errorText(act.error)}</ErrorNote>}
      {act.isSuccess && !asking && <SuccessNote>Done: {act.data.status_label}.</SuccessNote>}
      {o.rejected && (
        <p className="mb-4 rounded-xl border border-danger/30 bg-danger-soft px-4 py-3 text-sm text-danger">
          Changes requested on {formatDate(o.rejected.at)}: {o.rejected.reason}
        </p>
      )}
      {o.decline_reason && <p className="mb-4 text-sm text-ink-soft">Candidate's reason for declining: {o.decline_reason}</p>}
      {o.revoke_reason && <p className="mb-4 text-sm text-ink-soft">Revoked: {o.revoke_reason}</p>}

      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <section className="glass rounded-xl2 p-5" aria-labelledby="terms-heading">
          <h2 id="terms-heading" className="mb-2 font-display text-xl font-semibold text-ink">
            Terms
          </h2>
          {editing ? (
            <OfferForm
              initial={draftFrom(o.terms, o.expires_on)}
              submitLabel="Save changes"
              busy={edit.isPending}
              error={edit.error}
              onSubmit={(draft) => edit.mutate(draft)}
              onCancel={() => setEditing(false)}
            />
          ) : (
            <TermsList terms={o.terms} />
          )}
        </section>
        <section className="glass rounded-xl2 p-5" aria-labelledby="approvals-heading">
          <h2 id="approvals-heading" className="mb-2 font-display text-xl font-semibold text-ink">
            Approvals
          </h2>
          <ol className="space-y-2 text-sm">
            {steps.map((s) => (
              <li key={s.label} className="flex items-start gap-2">
                <span aria-hidden="true" className={`mt-1 h-3 w-3 shrink-0 rounded-full ${s.done ? 'bg-success' : 'border border-ink/30'}`} />
                <span>
                  <span className="font-semibold text-ink">{s.label}</span>
                  <span className="sr-only">{s.done ? ' (done)' : ' (not yet)'}</span>
                  {s.done && (
                    <span className="block text-muted">
                      {s.who ? `${s.who}, ` : ''}
                      {ist(s.at)}
                    </span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </section>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {o.actions.edit && !editing && (
          <Button variant="secondary" onClick={() => setEditing(true)}>
            Edit terms
          </Button>
        )}
        {o.actions.submit && (
          <Button onClick={() => act.mutate({ name: 'submit' })} disabled={act.isPending}>
            Send for approval
          </Button>
        )}
        {o.actions.approve && (
          <Button onClick={() => act.mutate({ name: 'approve' })} disabled={act.isPending}>
            Approve
          </Button>
        )}
        {o.actions.reject && (
          <Button variant="ghost" onClick={() => setAsking('reject')}>
            Request changes
          </Button>
        )}
        {o.actions.send && (
          <Button onClick={() => act.mutate({ name: 'send' })} disabled={act.isPending}>
            Send to candidate
          </Button>
        )}
        {o.actions.hire && (
          <Button onClick={() => setConfirmHire(true)} disabled={hire.isPending}>
            Hire
          </Button>
        )}
        {o.actions.revoke && (
          <Button variant="ghost" onClick={() => setAsking('revoke')}>
            Revoke offer
          </Button>
        )}
      </div>
      {confirmHire && (
        <Dialog title={`Hire ${who}?`} onClose={() => setConfirmHire(false)}>
          <p className="text-sm text-ink-soft">In one step TalentPath will:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-ink">
            <li>move the application to Hired and create the employee record with an employee ID;</li>
            <li>switch the same login to the employee role (audited);</li>
            <li>credit leave prorated from the joining date;</li>
            <li>build the onboarding checklist, pick a buddy and plan the first week;</li>
            <li>politely withdraw their other open applications and reduce this job’s openings (it closes when filled).</li>
          </ul>
          {hire.isError && <ErrorNote>{errorText(hire.error)}</ErrorNote>}
          <div className="mt-4 flex gap-2">
            <Button onClick={() => hire.mutate()} disabled={hire.isPending}>
              {hire.isPending ? 'Hiring…' : 'Hire now'}
            </Button>
            <Button variant="ghost" onClick={() => setConfirmHire(false)}>
              Cancel
            </Button>
          </div>
        </Dialog>
      )}
      {asking && (
        <ReasonDialog
          title={asking === 'reject' ? 'Request changes' : 'Revoke this offer?'}
          action={asking === 'reject' ? 'Request changes' : 'Revoke'}
          busy={act.isPending}
          error={act.error}
          onConfirm={(reason) => act.mutate({ name: asking, reason })}
          onClose={() => setAsking(null)}
        />
      )}
    </>
  );
}
