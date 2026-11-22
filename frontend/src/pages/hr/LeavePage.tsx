import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { LeaveForm, LeaveStatus } from '@/components/hr';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { dateRange, type Balances, type LeaveRequest } from '@/lib/hr';
import { errorText } from '@/lib/pipeline';

function BalanceTiles({ data }: { data: Balances }) {
  return (
    <ul className="grid grid-cols-2 gap-3 md:grid-cols-5" aria-label={`Leave balances for ${data.year}`}>
      {data.balances.map((b) => (
        <li key={b.type} className="glass rounded-xl2 p-4">
          <p className="text-sm text-muted">{b.name}</p>
          <p className="mt-1 font-display text-2xl font-semibold text-ink">{b.unpaid ? 'Unpaid' : b.available}</p>
          <p className="text-xs text-ink-soft">
            {b.unpaid ? `${b.taken} taken` : `available · ${b.taken} taken`}
            {b.pending > 0 && ` · ${b.pending} pending`}
            {(b.booked_ahead ?? 0) > 0 && ` · ${b.booked_ahead} booked ahead of accrual`}
          </p>
        </li>
      ))}
    </ul>
  );
}

function MyRequests() {
  const client = useQueryClient();
  const query = useQuery({ queryKey: ['leave-requests'], queryFn: () => api<{ results: LeaveRequest[] }>('/leave/requests') });
  const cancel = useMutation({
    mutationFn: (id: string) => api<LeaveRequest>(`/leave/requests/${id}/cancel`, { method: 'POST', body: {} }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['leave-requests'] });
      void client.invalidateQueries({ queryKey: ['leave-balances'] });
    },
  });
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not load your requests.</ErrorNote>;
  const rows = query.data.results;
  if (!rows.length) return <EmptyState title="No leave requests yet" />;
  return (
    <>
      {cancel.isError && <ErrorNote>{errorText(cancel.error)}</ErrorNote>}
      <ul className="space-y-2">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-col gap-2 rounded-xl border border-ink/10 bg-white/70 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-semibold text-ink">
                {r.leave_type_name}: {dateRange(r.start, r.end, r.half)}
              </p>
              <p className="text-sm text-ink-soft">
                {r.days_label}
                {r.status === 'pending' && r.approver && ` · waiting for ${r.approver}`}
                {r.escalated && ' · escalated'}
                {r.delegated && ' · delegated'}
              </p>
              {r.decision_note && <p className="text-sm text-muted">Note: {r.decision_note}</p>}
            </div>
            <div className="flex items-center gap-2">
              <LeaveStatus status={r.status} label={r.status_label} />
              {r.can_cancel && (
                <Button variant="ghost" onClick={() => cancel.mutate(r.id)} disabled={cancel.isPending}>
                  Cancel<span className="sr-only"> {r.leave_type_name} from {r.start}</span>
                </Button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

export function LeavePage() {
  useDocumentTitle('Leave');
  const balances = useQuery({ queryKey: ['leave-balances'], queryFn: () => api<Balances>('/leave/balances'), retry: false });
  if (balances.isPending) return <PageLoader />;
  if (balances.isError) {
    const missing = balances.error instanceof ApiError && balances.error.status === 404;
    return (
      <>
        <PageHeader title="Leave" />
        <EmptyState title={missing ? 'No employee record yet' : 'We could not load your leave'}>
          {missing ? 'Leave opens once HR creates your employee record.' : 'Please refresh the page.'}
        </EmptyState>
      </>
    );
  }
  return (
    <>
      <PageHeader
        title="Leave"
        intro="Every rule is checked as you type: you see the days counted and any team clash before you apply."
        actions={
          <>
            <Link to="/team-calendar" className="inline-flex min-h-11 items-center text-sm font-semibold text-primary-strong underline">
              Team calendar
            </Link>
            <Link to="/hr/policies" className="inline-flex min-h-11 items-center text-sm font-semibold text-primary-strong underline">
              Leave rules
            </Link>
          </>
        }
      />
      <BalanceTiles data={balances.data} />
      <div className="mt-6 grid gap-6 lg:grid-cols-2">
        <section className="glass rounded-xl2 p-5" aria-labelledby="apply-heading">
          <h2 id="apply-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            Apply for leave
          </h2>
          <LeaveForm balances={balances.data} />
        </section>
        <section className="glass rounded-xl2 p-5" aria-labelledby="mine-heading">
          <h2 id="mine-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            My requests
          </h2>
          <MyRequests />
        </section>
      </div>
    </>
  );
}
