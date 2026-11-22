import { useQuery } from '@tanstack/react-query';
import { Link, Navigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Card, PageHeader } from '@/components/ui';
import { api } from '@/lib/api';
import { firstName } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import type { Balances, Onboarding } from '@/lib/hr';

export function EmployeeDashboard() {
  useDocumentTitle('Overview');
  const { user } = useAuth();
  const onboarding = useQuery({ queryKey: ['onboarding-me'], queryFn: () => api<Onboarding>('/onboarding/me'), retry: false });
  const balances = useQuery({ queryKey: ['leave-balances'], queryFn: () => api<Balances>('/leave/balances'), retry: false });

  // First sign-in after the one-click hire: show the Welcome page once.
  if (onboarding.data?.welcome_pending) return <Navigate to="/welcome" replace />;

  const paid = balances.data?.balances.filter((b) => !b.unpaid) ?? [];
  const progress = onboarding.data && onboarding.data.tasks.length > 0 ? onboarding.data.progress : null;
  return (
    <>
      <PageHeader title={user ? `Hello, ${firstName(user.full_name)}` : 'Hello'} intro="Your space for everyday work life." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h2 className="font-display text-lg font-semibold">Leave and time off</h2>
          {paid.length ? (
            <ul className="mt-2 space-y-0.5 text-sm">
              {paid.map((b) => (
                <li key={b.type} className="flex justify-between">
                  <span className="text-ink-soft">{b.name}</span>
                  <span className="font-semibold text-ink">{b.available}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="mt-1 text-sm text-muted">Balances appear once HR creates your employee record.</p>
          )}
          <Link to="/leave" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
            Apply for leave
          </Link>
        </Card>
        <Card>
          <h2 className="font-display text-lg font-semibold">Team calendar</h2>
          <p className="mt-1 text-sm text-muted">See who is away and spot clashes before you plan.</p>
          <Link to="/team-calendar" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
            Open the team calendar
          </Link>
        </Card>
        <Card>
          <h2 className="font-display text-lg font-semibold">{progress ? 'Onboarding' : 'Attendance'}</h2>
          {progress ? (
            <>
              <p className="mt-1 text-sm text-muted">
                {progress.done} of {progress.total} checklist items done.
              </p>
              <Link to="/welcome" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
                Open your checklist
              </Link>
            </>
          ) : (
            <>
              <p className="mt-1 text-sm text-muted">Check in and out, and fix a missed check-out.</p>
              <Link to="/attendance" className="mt-2 inline-block text-sm font-semibold text-primary-strong underline">
                Open attendance
              </Link>
            </>
          )}
        </Card>
      </div>
    </>
  );
}
