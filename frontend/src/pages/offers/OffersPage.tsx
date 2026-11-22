import { useState } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { OfferBadge } from '@/components/OfferBadge';
import { EmptyState, ErrorNote, PageHeader, PageLoader, Pager } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Paginated, StaffOffer } from '@/lib/types';

export function OffersPage() {
  useDocumentTitle('Offers');
  const { user } = useAuth();
  const [tab, setTab] = useState<'me' | 'all'>(user?.role === 'recruiter' ? 'all' : 'me');
  const [page, setPage] = useState(1);
  const offers = useQuery({
    queryKey: ['offers', tab, page],
    queryFn: () => api<Paginated<StaffOffer>>(`/offers${qs({ page, awaiting: tab === 'me' ? 'me' : '' })}`),
    placeholderData: keepPreviousData,
  });
  const meLabel = user?.role === 'recruiter' ? 'Ready for you' : 'Awaiting my approval';
  const tabClass = (active: boolean) =>
    `min-h-10 rounded-full px-4 text-sm font-semibold ${active ? 'bg-ink text-white' : 'bg-white/70 text-ink-soft hover:text-ink'}`;

  return (
    <>
      <PageHeader title="Offers" intro="Drafted by recruiters, approved by the hiring manager and then HR, and sent with a PDF letter." />
      <div role="group" aria-label="Which offers" className="mb-4 flex flex-wrap gap-2">
        <button type="button" className={tabClass(tab === 'me')} aria-pressed={tab === 'me'} onClick={() => { setTab('me'); setPage(1); }}>
          {meLabel}
        </button>
        <button type="button" className={tabClass(tab === 'all')} aria-pressed={tab === 'all'} onClick={() => { setTab('all'); setPage(1); }}>
          All offers
        </button>
      </div>
      {offers.isPending && <PageLoader />}
      {offers.isError && <ErrorNote>We could not load offers.</ErrorNote>}
      {offers.data?.results.length === 0 && <EmptyState title="No offers here" />}
      <ul className="flex flex-col gap-3">
        {offers.data?.results.map((offer) => {
          const who = offer.candidate.full_name ?? offer.candidate.code;
          return (
            <li key={offer.id} className="glass flex flex-col gap-2 rounded-xl2 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-semibold text-ink">
                  {who} · {offer.job.title}
                </p>
                <p className="text-sm text-muted">
                  {offer.terms.designation} · {offer.terms.display.total} a year · expires {formatDate(offer.expires_on)}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <OfferBadge offer={offer} />
                <Link to={`/offers/${offer.id}`} className="font-semibold text-primary-strong underline">
                  Open<span className="sr-only"> offer for {who}</span>
                </Link>
              </div>
            </li>
          );
        })}
      </ul>
      <Pager page={page} hasNext={Boolean(offers.data?.next)} hasPrevious={Boolean(offers.data?.previous)} onChange={setPage} />
    </>
  );
}
