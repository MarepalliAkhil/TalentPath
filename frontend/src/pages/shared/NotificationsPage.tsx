import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Button, EmptyState, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { NotificationItem, Paginated } from '@/lib/types';

export function NotificationsPage() {
  useDocumentTitle('Notifications');
  const client = useQueryClient();
  const navigate = useNavigate();
  const list = useQuery({
    queryKey: ['notifications', 'list'],
    queryFn: () => api<Paginated<NotificationItem> & { unread_count: number }>('/notifications?page_size=50'),
  });
  const refresh = () => client.invalidateQueries({ queryKey: ['notifications'] });
  const readAll = useMutation({ mutationFn: () => api('/notifications/read-all', { method: 'POST' }), onSuccess: refresh });
  const open = async (n: NotificationItem) => {
    if (!n.read) await api(`/notifications/${n.id}/read`, { method: 'POST' });
    await refresh();
    if (n.link) navigate(n.link);
  };

  return (
    <>
      <PageHeader
        title="Notifications"
        intro={list.data ? `${list.data.unread_count} unread` : undefined}
        actions={
          <Button variant="secondary" onClick={() => readAll.mutate()} disabled={!list.data?.unread_count}>
            Mark all as read
          </Button>
        }
      />
      {list.isPending && <PageLoader />}
      {list.data?.results.length === 0 && <EmptyState title="You are all caught up" />}
      <ul className="flex flex-col gap-2">
        {list.data?.results.map((n) => (
          <li key={n.id}>
            <button
              type="button"
              onClick={() => void open(n)}
              className={`glass flex w-full flex-col gap-1 rounded-xl2 p-4 text-left hover:shadow-lift ${n.read ? 'opacity-80' : ''}`}
            >
              <span className="flex items-center gap-2 font-semibold text-ink">
                {!n.read && <span className="h-2 w-2 rounded-full bg-accent" aria-hidden="true" />}
                {n.title}
                {!n.read && <span className="sr-only">(unread)</span>}
              </span>
              <span className="text-sm text-ink-soft">{n.body}</span>
              <span className="text-xs text-muted">{formatDate(n.created_at)}</span>
            </button>
          </li>
        ))}
      </ul>
    </>
  );
}
