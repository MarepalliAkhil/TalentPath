import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, PageHeader, PageLoader, Pager, SelectField } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { EmailItem, Paginated } from '@/lib/types';

interface EmailLog extends Paginated<EmailItem> {
  provider: string;
  counts: Record<string, number>;
}

const PROVIDERS: Record<string, string> = {
  console: 'Console: nothing is sent, each email is logged and kept here.',
  smtp: 'SMTP (Gmail App Password): real emails, within the allowlist and limits.',
  api: 'Email API (Brevo or Resend): real emails, within the allowlist and limits.',
};

const STATUS_STYLE: Record<string, string> = {
  sent: 'bg-success-soft text-success',
  queued: 'bg-warning-soft text-warning',
  held: 'bg-canvas-deep text-ink-soft',
  failed: 'bg-danger-soft text-danger',
};

/** The email log (D-86): every email, its delivery status and why anything was held or failed. */
export function OutboxPage() {
  useDocumentTitle('Email log');
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState('');
  const mail = useQuery({
    queryKey: ['outbox', status, page],
    queryFn: () => api<EmailLog>(`/outbox${qs({ page, status })}`),
  });
  const data = mail.data;
  return (
    <>
      <PageHeader
        title="Email log"
        intro={data ? (PROVIDERS[data.provider] ?? data.provider) : 'Every email the platform writes, and what happened to it.'}
      />
      {data && (
        <p className="mb-3 text-sm text-muted">
          {['sent', 'queued', 'held', 'failed'].map((key) => `${data.counts[key] ?? 0} ${key}`).join(' · ')}
        </p>
      )}
      <div className="mb-4 max-w-xs">
        <SelectField
          label="Show"
          value={status}
          onChange={(e) => {
            setStatus(e.target.value);
            setPage(1);
          }}
        >
          <option value="">All emails</option>
          <option value="sent">Sent</option>
          <option value="queued">Queued</option>
          <option value="held">Held (not sent)</option>
          <option value="failed">Failed</option>
        </SelectField>
      </div>
      {mail.isPending && <PageLoader />}
      <ul className="flex flex-col gap-3">
        {data?.results.map((m) => (
          <Card key={m.id} as="li">
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
              <h2 className="font-semibold text-ink">{m.subject}</h2>
              <span className="flex items-center gap-2 text-xs text-muted">
                {m.status && (
                  <span className={`rounded-full px-2 py-0.5 font-semibold ${STATUS_STYLE[m.status] ?? ''}`}>{m.status_label}</span>
                )}
                {new Date(m.created_at).toLocaleString('en-IN')}
              </span>
            </div>
            <p className="text-sm text-muted">
              To {m.to_email}
              {m.provider ? ` · via ${m.provider}` : ''}
              {m.attempts ? ` · ${m.attempts} ${m.attempts === 1 ? 'attempt' : 'attempts'}` : ''}
            </p>
            {m.hold_reason && <p className="mt-1 text-sm text-ink-soft">Held: {m.hold_reason}</p>}
            {m.last_error && <p className="mt-1 text-sm text-danger">Last error: {m.last_error}</p>}
            <details className="mt-2 text-sm">
              <summary className="cursor-pointer font-semibold text-primary-strong">Show the text</summary>
              <p className="mt-2 whitespace-pre-wrap break-words text-ink-soft">{m.body}</p>
            </details>
            {m.attachment && (
              <details className="mt-2 text-sm">
                <summary className="cursor-pointer font-semibold text-primary-strong">Attachment: {m.attachment.name}</summary>
                <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all rounded-xl bg-canvas p-2 text-xs text-ink-soft">
                  {m.attachment.content}
                </pre>
              </details>
            )}
          </Card>
        ))}
      </ul>
      <Pager page={page} hasNext={Boolean(data?.next)} hasPrevious={Boolean(data?.previous)} onChange={setPage} />
    </>
  );
}
