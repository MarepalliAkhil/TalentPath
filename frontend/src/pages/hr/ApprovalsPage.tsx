import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ClashWarnings, LeaveStatus } from '@/components/hr';
import { Dialog } from '@/components/Dialog';
import { Button, EmptyState, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { dateRange, day, type Approvals, type LeaveRequest, type Regularisation } from '@/lib/hr';
import { errorText } from '@/lib/pipeline';

type Decision = { kind: 'leave' | 'reg'; id: string; name: string; approve: boolean };

function DecisionDialog({ decision, onClose }: { decision: Decision; onClose: (message?: string) => void }) {
  const client = useQueryClient();
  const [note, setNote] = useState('');
  const act = useMutation({
    mutationFn: () =>
      decision.kind === 'leave'
        ? api(`/leave/requests/${decision.id}/${decision.approve ? 'approve' : 'reject'}`, { method: 'POST', body: { note } })
        : api(`/attendance/regularisations/${decision.id}/decide`, {
            method: 'POST',
            body: { decision: decision.approve ? 'approve' : 'reject', note },
          }),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['approvals'] });
      onClose(`${decision.approve ? 'Approved' : 'Not approved'}: ${decision.name}.`);
    },
  });
  const needsNote = !decision.approve;
  return (
    <Dialog title={decision.approve ? `Approve for ${decision.name}?` : `Do not approve for ${decision.name}?`} onClose={() => onClose()}>
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          act.mutate();
        }}
      >
        <TextAreaField
          label={needsNote ? 'Reason (shared with the employee)' : 'Note (optional)'}
          rows={3}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          hint={needsNote ? 'At least 5 characters.' : undefined}
          required={needsNote}
        />
        {act.isError && <ErrorNote>{errorText(act.error)}</ErrorNote>}
        <div className="flex gap-2">
          <Button
            type="submit"
            variant={decision.approve ? 'primary' : 'danger'}
            disabled={act.isPending || (needsNote && note.trim().length < 5)}
          >
            {decision.approve ? 'Approve' : 'Do not approve'}
          </Button>
          <Button variant="ghost" onClick={() => onClose()}>
            Cancel
          </Button>
        </div>
      </form>
    </Dialog>
  );
}

function LeaveCard({ r, onDecide }: { r: LeaveRequest; onDecide: (d: Decision) => void }) {
  return (
    <li className="glass rounded-xl2 p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-display text-lg font-semibold text-ink">{r.employee.name}</p>
          <p className="text-sm text-ink-soft">
            {r.leave_type_name}: {dateRange(r.start, r.end, r.half)} · <strong>{r.days_label}</strong>
          </p>
          {r.reason && <p className="mt-1 text-sm text-ink">“{r.reason}”</p>}
          <p className="mt-1 text-xs text-muted">
            {r.stage === 'hr' ? 'HR step' : 'Reporting manager step'}
            {r.delegated && ' · delegated to you'}
            {r.escalated && ' · escalated'}
            {r.has_document && (
              <>
                {' · '}
                <a href={`/api/leave/requests/${r.id}/document`} className="font-semibold text-primary-strong underline">
                  document
                </a>
              </>
            )}
          </p>
        </div>
        <LeaveStatus status={r.status} label={r.status_label} />
      </div>
      {r.warnings && r.warnings.length > 0 && (
        <div className="mt-3">
          <ClashWarnings warnings={r.warnings} />
        </div>
      )}
      {r.can_act && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => onDecide({ kind: 'leave', id: r.id, name: r.employee.name, approve: true })}>
            Approve<span className="sr-only"> leave for {r.employee.name}</span>
          </Button>
          <Button variant="secondary" onClick={() => onDecide({ kind: 'leave', id: r.id, name: r.employee.name, approve: false })}>
            Do not approve<span className="sr-only"> leave for {r.employee.name}</span>
          </Button>
        </div>
      )}
    </li>
  );
}

function RegCard({ r, onDecide }: { r: Regularisation; onDecide: (d: Decision) => void }) {
  return (
    <li className="glass rounded-xl2 p-4">
      <p className="font-display text-lg font-semibold text-ink">{r.employee.name}</p>
      <p className="text-sm text-ink-soft">
        Attendance correction for {day(r.date)}: {r.check_in} to {r.check_out} ({r.mode})
      </p>
      {r.reason && <p className="mt-1 text-sm text-ink">“{r.reason}”</p>}
      {r.can_decide && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button onClick={() => onDecide({ kind: 'reg', id: r.id, name: r.employee.name, approve: true })}>
            Approve<span className="sr-only"> correction for {r.employee.name}</span>
          </Button>
          <Button variant="secondary" onClick={() => onDecide({ kind: 'reg', id: r.id, name: r.employee.name, approve: false })}>
            Do not approve<span className="sr-only"> correction for {r.employee.name}</span>
          </Button>
        </div>
      )}
    </li>
  );
}

export function ApprovalsPage() {
  useDocumentTitle('Approvals');
  const query = useQuery({ queryKey: ['approvals'], queryFn: () => api<Approvals>('/leave/approvals'), refetchInterval: 60_000 });
  const [decision, setDecision] = useState<Decision | null>(null);
  const [message, setMessage] = useState('');
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not load your approvals.</ErrorNote>;
  const { leave, regularisations, needs_attention: attention } = query.data;
  const attentionOnly = attention.filter((a) => !leave.some((l) => l.id === a.id));
  return (
    <>
      <PageHeader
        title="Approvals"
        intro="Leave and attendance corrections waiting for you. The reporting line decides who approves; nobody approves their own."
      />
      {message && <SuccessNote>{message}</SuccessNote>}
      {attentionOnly.length > 0 && (
        <section className="mb-6" aria-labelledby="attention-heading">
          <h2 id="attention-heading" className="mb-2 font-display text-xl font-semibold text-ink">
            Needs attention ({attentionOnly.length})
          </h2>
          <p className="mb-2 text-sm text-muted">Escalated after 48 hours, or nobody left in the reporting line. HR can step in.</p>
          <ul className="space-y-3">
            {attentionOnly.map((r) => (
              <LeaveCard key={r.id} r={r} onDecide={setDecision} />
            ))}
          </ul>
        </section>
      )}
      <section className="mb-6" aria-labelledby="leave-heading">
        <h2 id="leave-heading" className="mb-2 font-display text-xl font-semibold text-ink">
          Leave ({leave.length})
        </h2>
        {leave.length ? (
          <ul className="space-y-3">
            {leave.map((r) => (
              <LeaveCard key={r.id} r={r} onDecide={setDecision} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No leave waiting for you" />
        )}
      </section>
      <section aria-labelledby="reg-heading">
        <h2 id="reg-heading" className="mb-2 font-display text-xl font-semibold text-ink">
          Attendance corrections ({regularisations.length})
        </h2>
        {regularisations.length ? (
          <ul className="space-y-3">
            {regularisations.map((r) => (
              <RegCard key={r.id} r={r} onDecide={setDecision} />
            ))}
          </ul>
        ) : (
          <EmptyState title="No corrections waiting for you" />
        )}
      </section>
      {decision && (
        <DecisionDialog
          decision={decision}
          onClose={(text) => {
            setDecision(null);
            if (text) setMessage(text);
          }}
        />
      )}
    </>
  );
}
