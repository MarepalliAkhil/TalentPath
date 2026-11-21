import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, PageHeader, PageLoader, Pager } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { EmailItem, Paginated } from '@/lib/types';

export function OutboxPage() {
  useDocumentTitle('Simulated emails');
  const [page, setPage] = useState(1);
  const mail = useQuery({ queryKey: ['outbox', page], queryFn: () => api<Paginated<EmailItem>>(`/outbox${qs({ page })}`) });
  return (
    <>
      <PageHeader title="Simulated emails" intro="Nothing leaves the system. Every email the platform would send is stored here." />
      {mail.isPending && <PageLoader />}
      <ul className="flex flex-col gap-3">
        {mail.data?.results.map((m) => (
          <Card key={m.id} as="li">
            <div className="flex flex-col gap-1 sm:flex-row sm:justify-between">
              <h2 className="font-semibold text-ink">{m.subject}</h2>
              <span className="text-xs text-muted">{new Date(m.created_at).toLocaleString('en-IN')}</span>
            </div>
            <p className="text-sm text-muted">To {m.to_email}</p>
            <p className="mt-2 whitespace-pre-wrap break-words text-sm text-ink-soft">{m.body}</p>
          </Card>
        ))}
      </ul>
      <Pager page={page} hasNext={Boolean(mail.data?.next)} hasPrevious={Boolean(mail.data?.previous)} onChange={setPage} />
    </>
  );
}
