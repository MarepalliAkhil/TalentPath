import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { api } from '@/lib/api';
import type { NotificationItem, Paginated } from '@/lib/types';
import { Icon } from './Icon';

export function NotificationBell() {
  const { data } = useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: () => api<Paginated<NotificationItem> & { unread_count: number }>('/notifications?unread=1&page_size=1'),
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
  });
  const count = data?.unread_count ?? 0;
  const label = count ? `Notifications, ${count} unread` : 'Notifications';
  return (
    <Link
      to="/notifications"
      aria-label={label}
      className="relative flex h-11 w-11 items-center justify-center rounded-full border border-ink/10 bg-white/80 text-ink hover:border-primary hover:text-primary-strong"
    >
      <Icon name="bell" />
      {count > 0 && (
        <span
          aria-hidden="true"
          className="absolute -right-0.5 -top-0.5 min-w-5 rounded-full bg-accent px-1.5 text-center text-[11px] font-bold leading-5 text-white"
        >
          {count > 99 ? '99+' : count}
        </span>
      )}
    </Link>
  );
}
