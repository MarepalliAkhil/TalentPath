import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader, PageLoader, StatTile, buttonClass } from '@/components/ui';
import { api } from '@/lib/api';
import { firstName } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Summary } from '@/lib/types';

const ROLE_LABELS: Record<string, string> = {
  candidate: 'Candidates',
  recruiter: 'Recruiters',
  manager: 'Managers',
  employee: 'Employees',
  hr: 'HR',
  admin: 'Admins',
};

const EMAIL_LABELS: Record<string, string> = { sent: 'Sent', queued: 'Queued', held: 'Held', failed: 'Failed' };

/** The admin's home (D-80): accounts and the organisation. No hiring or candidate data here. */
export function AdminOverview() {
  useDocumentTitle('Organisation overview');
  const { user } = useAuth();
  const summary = useQuery({ queryKey: ['summary'], queryFn: () => api<Summary>('/dashboard/summary') });
  const s = summary.data;
  return (
    <>
      <PageHeader
        title="Organisation overview"
        intro={user ? `Welcome back, ${firstName(user.full_name)}. You manage accounts, roles and the organisation.` : undefined}
        actions={
          <Link to="/admin/staff" className={buttonClass('primary')}>
            Add a person
          </Link>
        }
      />
      {summary.isPending && <PageLoader />}
      {s && (
        <>
          <section aria-labelledby="accounts-heading">
            <h2 id="accounts-heading" className="font-display text-xl font-semibold text-ink">
              Active accounts
            </h2>
            <dl className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {Object.keys(ROLE_LABELS).map((role) => (
                <div key={role} className="glass rounded-xl2 p-4">
                  <dt className="text-sm text-muted">{ROLE_LABELS[role]}</dt>
                  <dd className="font-display text-2xl font-semibold">{s.users_by_role?.[role] ?? 0}</dd>
                </div>
              ))}
            </dl>
            <p className="mt-3 text-sm text-muted">
              {s.inactive_users ?? 0} deactivated {s.inactive_users === 1 ? 'account' : 'accounts'} (kept with their history, never
              deleted).
            </p>
          </section>
          <section aria-labelledby="email-heading" className="mt-8">
            <h2 id="email-heading" className="font-display text-xl font-semibold text-ink">
              Emails
            </h2>
            <div className="mt-3 grid grid-cols-2 gap-3 lg:grid-cols-4">
              {Object.keys(EMAIL_LABELS).map((key) => (
                <StatTile key={key} label={EMAIL_LABELS[key]} value={s.emails_by_status?.[key] ?? 0} />
              ))}
            </div>
            <p className="mt-3 text-sm">
              <Link to="/admin/outbox" className="font-semibold text-primary-strong underline">
                Open the email log
              </Link>
            </p>
          </section>
        </>
      )}
    </>
  );
}
