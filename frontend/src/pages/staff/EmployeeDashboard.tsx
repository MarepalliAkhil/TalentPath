import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Card, PageHeader } from '@/components/ui';
import { firstName } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';

export function EmployeeDashboard() {
  useDocumentTitle('Overview');
  const { user } = useAuth();
  return (
    <>
      <PageHeader title={user ? `Hello, ${firstName(user.full_name)}` : 'Hello'} intro="Your space for everyday work life." />
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <h2 className="font-display text-lg font-semibold">Leave and time off</h2>
          <p className="mt-1 text-sm text-muted">Leave requests, balances and approvals will appear here.</p>
        </Card>
        <Card>
          <h2 className="font-display text-lg font-semibold">Team calendar</h2>
          <p className="mt-1 text-sm text-muted">See who is away and spot clashes before you plan.</p>
        </Card>
        <Card>
          <h2 className="font-display text-lg font-semibold">Your profile</h2>
          <p className="mt-1 text-sm text-muted">
            Keep your contact details current. <Link to="/profile" className="font-semibold text-primary-strong underline">Edit profile</Link>
          </p>
        </Card>
      </div>
    </>
  );
}
