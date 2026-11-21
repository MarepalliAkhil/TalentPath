import { useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { Button, Card, EmptyState, TextField } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle, useNoIndex } from '@/lib/hooks';
import type { EmailItem } from '@/lib/types';

function Linkified({ text }: { text: string }) {
  const parts = text.split(/(https?:\/\/\S+)/g);
  return (
    <p className="whitespace-pre-wrap break-words text-sm text-ink-soft">
      {parts.map((part, i) =>
        /^https?:\/\//.test(part) ? (
          <a key={i} href={part} className="font-semibold text-primary-strong underline">
            {part}
          </a>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </p>
  );
}

export function DemoInboxPage() {
  useDocumentTitle('Demo inbox');
  useNoIndex();
  const [params, setParams] = useSearchParams();
  const email = params.get('email') ?? '';
  const [draft, setDraft] = useState(email);
  const inbox = useQuery({
    queryKey: ['demo-inbox', email],
    queryFn: () => api<{ results: EmailItem[] }>(`/demo/inbox?email=${encodeURIComponent(email)}`),
    enabled: email.endsWith('.example'),
    retry: false,
  });

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    setParams(draft ? { email: draft.trim() } : {});
  };

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="font-display text-3xl font-semibold text-ink">Demo inbox</h1>
      <p className="mt-1 text-muted">Emails are simulated. In demo mode you can read messages sent to fictional *.example addresses.</p>
      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex-1">
          <TextField label="Demo email address" type="email" value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="candidate@demo.example" />
        </div>
        <Button type="submit">Open inbox</Button>
      </form>
      <div className="mt-6 flex flex-col gap-3">
        {inbox.isError && <EmptyState title="Inbox unavailable">Demo mode may be off, or the address is not a demo address.</EmptyState>}
        {inbox.data?.results.length === 0 && <EmptyState title="No messages yet" />}
        {inbox.data?.results.map((mail) => (
          <Card key={mail.id} as="article">
            <h2 className="font-semibold text-ink">{mail.subject}</h2>
            <p className="mb-2 text-xs text-muted">{formatDate(mail.created_at)}</p>
            <Linkified text={mail.body} />
          </Card>
        ))}
      </div>
    </div>
  );
}
