import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { PageHeader, PageLoader, Pager } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { AuditEntry, Paginated } from '@/lib/types';

export function AuditPage() {
  useDocumentTitle('Audit log');
  const [page, setPage] = useState(1);
  const log = useQuery({ queryKey: ['audit', page], queryFn: () => api<Paginated<AuditEntry>>(`/audit${qs({ page })}`) });
  return (
    <>
      <PageHeader title="Audit log" intro="Sensitive actions: sign-ins, account changes, resume views and downloads, status changes." />
      {log.isPending && <PageLoader />}
      <div className="glass overflow-x-auto rounded-xl2">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <caption className="sr-only">Audit events, newest first</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                When
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Action
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Actor
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Target
              </th>
            </tr>
          </thead>
          <tbody>
            {log.data?.results.map((e) => (
              <tr key={e.id} className="border-t border-ink/10">
                <td className="whitespace-nowrap px-4 py-3 text-ink-soft">{new Date(e.created_at).toLocaleString('en-IN')}</td>
                <td className="px-4 py-3 font-mono text-xs text-ink">{e.action}</td>
                <td className="px-4 py-3 text-ink-soft">{e.actor ?? '—'}</td>
                <td className="px-4 py-3 text-ink-soft">{e.target_type ? `${e.target_type} ${e.target_id.slice(0, 8)}` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} hasNext={Boolean(log.data?.next)} hasPrevious={Boolean(log.data?.previous)} onChange={setPage} />
    </>
  );
}
