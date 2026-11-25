import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Icon } from '@/components/Icon';
import { TermsList } from '@/components/TermsList';
import { Button, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField, TextField } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import { errorText } from '@/lib/pipeline';
import type { CandidateOffer } from '@/lib/types';

export function CandidateOfferPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const client = useQueryClient();
  const offer = useQuery({ queryKey: ['offer', id], queryFn: () => api<CandidateOffer>(`/offers/${id}`) });
  useDocumentTitle(offer.data ? `Offer: ${offer.data.job.title}` : 'Your offer');
  const [typed, setTyped] = useState('');
  const [declining, setDeclining] = useState(false);
  const [reason, setReason] = useState('');
  const done = () => {
    void client.invalidateQueries({ queryKey: ['offer', id] });
    void client.invalidateQueries({ queryKey: ['my-offers'] });
  };
  const accept = useMutation({
    mutationFn: () => api<CandidateOffer>(`/offers/${id}/accept`, { method: 'POST', body: { typed_name: typed } }),
    onSuccess: done,
  });
  const decline = useMutation({
    mutationFn: () => api<CandidateOffer>(`/offers/${id}/decline`, { method: 'POST', body: { reason } }),
    onSuccess: done,
  });

  if (offer.isPending) return <PageLoader />;
  if (offer.isError || !offer.data) return <ErrorNote>We could not find this offer.</ErrorNote>;
  const data = offer.data;
  const submitAccept = (event: FormEvent) => {
    event.preventDefault();
    accept.mutate();
  };

  return (
    <>
      <PageHeader
        title={`Your offer: ${data.job.title}`}
        intro={`Status: ${data.status_label}. Valid until ${formatDate(data.expires_on)}.`}
        actions={
          <Link to="/candidate" className="text-sm font-semibold text-primary-strong underline">
            Back to my applications
          </Link>
        }
      />
      <p className="mb-4 rounded-xl bg-warning-soft px-4 py-3 text-sm text-warning">
        Demo: this is a fictional offer from a fictional company. Nothing here is a real offer of employment.
      </p>
      {accept.isSuccess && <SuccessNote>Congratulations! You accepted the offer. The recruiter has been told.</SuccessNote>}
      {decline.isSuccess && <SuccessNote>You declined the offer. Thank you for letting us know.</SuccessNote>}
      <section className="glass mt-4 rounded-xl2 p-5" aria-labelledby="terms-heading">
        <h2 id="terms-heading" className="mb-2 font-display text-xl font-semibold text-ink">
          Terms
        </h2>
        <TermsList terms={data.terms} />
        {data.has_letter && (
          <a
            href={`/api/offers/${id}/letter`}
            target="_blank"
            rel="noreferrer"
            className="mt-4 inline-flex min-h-11 items-center gap-2 font-semibold text-primary-strong underline"
          >
            <Icon name="document" className="h-4 w-4" /> Open the offer letter (PDF)
          </a>
        )}
      </section>
      {data.can_respond && (
        <section className="glass mt-6 rounded-xl2 p-5" aria-labelledby="respond-heading">
          <h2 id="respond-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            Respond
          </h2>
          <form onSubmit={submitAccept} className="flex flex-col gap-3">
            <TextField
              label="Type your full name to accept"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="name"
              hint={`${data.acknowledgement} Your name on file: ${user?.full_name ?? ''}.`}
              error={accept.isError ? errorText(accept.error) : undefined}
              required
            />
            <Button type="submit" className="self-start" disabled={!typed.trim() || accept.isPending}>
              Accept offer
            </Button>
          </form>
          <div className="mt-6 border-t border-ink/10 pt-4">
            {declining ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  decline.mutate();
                }}
                className="flex flex-col gap-3"
              >
                <TextAreaField
                  label="Reason (optional)"
                  rows={2}
                  maxLength={500}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                />
                {decline.isError && <ErrorNote>{errorText(decline.error)}</ErrorNote>}
                <div className="flex gap-2">
                  <Button type="submit" variant="danger" disabled={decline.isPending}>
                    Decline offer
                  </Button>
                  <Button variant="ghost" onClick={() => setDeclining(false)}>
                    Cancel
                  </Button>
                </div>
              </form>
            ) : (
              <Button variant="ghost" onClick={() => setDeclining(true)}>
                Decline this offer
              </Button>
            )}
          </div>
        </section>
      )}
    </>
  );
}
