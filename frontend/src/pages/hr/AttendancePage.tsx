import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';
import { LeaveStatus } from '@/components/hr';
import {
  Button,
  EmptyState,
  ErrorNote,
  PageHeader,
  PageLoader,
  SelectField,
  StatTile,
  SuccessNote,
  TextAreaField,
  TextField,
} from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { day, monthLabel, shiftMonth, thisMonth, todayIso, type AttendanceDay, type AttendanceMe, type AttendanceTeam } from '@/lib/hr';
import { errorText } from '@/lib/pipeline';

const STATUS_LABEL: Record<AttendanceDay['status'], string> = {
  present: 'Present',
  leave: 'On leave',
  absent: 'No record',
  today: 'Today',
  weekly_off: 'Weekly off',
  holiday: 'Holiday',
  working: 'Working day',
};

function TodayCard({ data }: { data: AttendanceMe }) {
  const client = useQueryClient();
  const [mode, setMode] = useState('office');
  const done = () => void client.invalidateQueries({ queryKey: ['attendance-me'] });
  const checkIn = useMutation({ mutationFn: () => api('/attendance/check-in', { method: 'POST', body: { mode } }), onSuccess: done });
  const checkOut = useMutation({ mutationFn: () => api('/attendance/check-out', { method: 'POST', body: {} }), onSuccess: done });
  const today = data.today;
  const error = checkIn.error ?? checkOut.error;
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby="today-heading">
      <h2 id="today-heading" className="font-display text-xl font-semibold text-ink">
        Today
      </h2>
      <p className="text-sm text-muted">
        General shift {data.shift.start} to {data.shift.end} ({data.shift.location}), {data.shift.late_grace_minutes} minutes grace. No
        location is recorded.
      </p>
      {today?.check_in ? (
        <p className="mt-3 text-sm text-ink">
          Checked in {today.check_in} ({today.mode}){today.late && <strong className="text-warning"> · late</strong>}
          {today.check_out ? (
            <>
              {' '}
              · checked out {today.check_out}
              {today.early && <strong className="text-warning"> · early</strong>}
            </>
          ) : null}
        </p>
      ) : (
        <fieldset className="mt-3">
          <legend className="text-sm font-medium text-ink">Where are you working today?</legend>
          <div className="mt-1 flex gap-4">
            {(['office', 'remote'] as const).map((m) => (
              <label key={m} className="inline-flex min-h-11 items-center gap-2 text-sm capitalize">
                <input type="radio" name="work-mode" value={m} checked={mode === m} onChange={() => setMode(m)} className="h-4 w-4" />
                {m}
              </label>
            ))}
          </div>
        </fieldset>
      )}
      <div className="mt-3 flex gap-2">
        {!today?.check_in && (
          <Button onClick={() => checkIn.mutate()} disabled={checkIn.isPending}>
            Check in
          </Button>
        )}
        {today?.check_in && !today.check_out && (
          <Button onClick={() => checkOut.mutate()} disabled={checkOut.isPending}>
            Check out
          </Button>
        )}
      </div>
      {error && <ErrorNote>{errorText(error)}</ErrorNote>}
    </section>
  );
}

function RegulariseForm() {
  const client = useQueryClient();
  const [date, setDate] = useState('');
  const [checkIn, setCheckIn] = useState('09:30');
  const [checkOut, setCheckOut] = useState('18:30');
  const [mode, setMode] = useState('office');
  const [reason, setReason] = useState('');
  const send = useMutation({
    mutationFn: () =>
      api('/attendance/regularisations', { method: 'POST', body: { date, check_in: checkIn, check_out: checkOut, mode, reason } }),
    onSuccess: () => {
      setDate('');
      setReason('');
      void client.invalidateQueries({ queryKey: ['attendance-me'] });
    },
  });
  const fields = send.error instanceof ApiError ? send.error.fieldErrors : {};
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    send.mutate();
  };
  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-3" aria-label="Request an attendance correction">
      <TextField
        label="Date"
        type="date"
        max={todayIso()}
        value={date}
        onChange={(e) => setDate(e.target.value)}
        error={fields.date}
        required
      />
      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Check-in"
          type="time"
          value={checkIn}
          onChange={(e) => setCheckIn(e.target.value)}
          error={fields.check_in}
          required
        />
        <TextField
          label="Check-out"
          type="time"
          value={checkOut}
          onChange={(e) => setCheckOut(e.target.value)}
          error={fields.check_out}
          required
        />
      </div>
      <SelectField label="Work mode" value={mode} onChange={(e) => setMode(e.target.value)}>
        <option value="office">Office</option>
        <option value="remote">Remote</option>
      </SelectField>
      <TextAreaField
        label="What happened?"
        rows={2}
        maxLength={500}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        error={fields.reason}
        required
      />
      {send.isError && !Object.keys(fields).length && <ErrorNote>{errorText(send.error)}</ErrorNote>}
      {send.isSuccess && <SuccessNote>Sent to your reporting manager.</SuccessNote>}
      <div>
        <Button type="submit" disabled={send.isPending || !date || reason.trim().length < 5}>
          Send for approval
        </Button>
      </div>
    </form>
  );
}

function TeamSummary({ month }: { month: string }) {
  const query = useQuery({ queryKey: ['attendance-team', month], queryFn: () => api<AttendanceTeam>(`/attendance/team?month=${month}`) });
  if (!query.data || query.data.rows.length === 0) return null;
  return (
    <section className="glass mt-6 rounded-xl2 p-5" aria-labelledby="team-att-heading">
      <h2 id="team-att-heading" className="font-display text-xl font-semibold text-ink">
        {query.data.scope === 'all' ? 'Everyone' : 'My reports'}: {monthLabel(month)}
      </h2>
      <div className="mt-3 overflow-x-auto" tabIndex={0} role="region" aria-label="Team attendance table (scrolls sideways)">
        <table className="w-full text-sm">
          <caption className="sr-only">Monthly attendance summary</caption>
          <thead>
            <tr className="text-left text-xs text-muted">
              <th scope="col" className="py-1 pr-3">
                Person
              </th>
              <th scope="col" className="px-2 text-right">
                Present
              </th>
              <th scope="col" className="px-2 text-right">
                Remote
              </th>
              <th scope="col" className="px-2 text-right">
                Late
              </th>
              <th scope="col" className="px-2 text-right">
                Early
              </th>
              <th scope="col" className="px-2 text-right">
                No check-out
              </th>
              <th scope="col" className="px-2 text-right">
                Leave
              </th>
              <th scope="col" className="px-2 text-right">
                No record
              </th>
            </tr>
          </thead>
          <tbody>
            {query.data.rows.map((r) => (
              <tr key={r.employee} className="border-t border-ink/10">
                <th scope="row" className="py-1.5 pr-3 text-left font-medium text-ink">
                  {r.name} <span className="text-xs text-muted">{r.department}</span>
                </th>
                <td className="px-2 text-right">{r.present}</td>
                <td className="px-2 text-right">{r.remote}</td>
                <td className="px-2 text-right">{r.late}</td>
                <td className="px-2 text-right">{r.early}</td>
                <td className="px-2 text-right">{r.missing_checkout}</td>
                <td className="px-2 text-right">{r.on_leave}</td>
                <td className="px-2 text-right">{r.absent}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export function AttendancePage() {
  useDocumentTitle('Attendance');
  const { user } = useAuth();
  const [month, setMonth] = useState(thisMonth());
  const query = useQuery({
    queryKey: ['attendance-me', month],
    queryFn: () => api<AttendanceMe>(`/attendance/me?month=${month}`),
    retry: false,
  });
  if (query.isPending) return <PageLoader />;
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <>
        <PageHeader title="Attendance" />
        {missing ? <EmptyState title="No employee record yet" /> : <ErrorNote>We could not load attendance.</ErrorNote>}
        {user?.role === 'hr' && <TeamSummary month={month} />}
      </>
    );
  }
  const data = query.data;
  const c = data.summary.counts;
  const flagged = data.summary.days
    .filter((d) => d.status !== 'weekly_off')
    .slice()
    .reverse();
  return (
    <>
      <PageHeader
        title="Attendance"
        intro="Web check-in and check-out. Missed a check-out? Request a correction for your manager to approve."
      />
      <div className="grid gap-6 lg:grid-cols-2">
        <TodayCard data={data} />
        <section className="glass rounded-xl2 p-5" aria-labelledby="reg-heading">
          <h2 id="reg-heading" className="mb-3 font-display text-xl font-semibold text-ink">
            Request a correction
          </h2>
          <RegulariseForm />
          {data.regularisations.length > 0 && (
            <ul className="mt-4 space-y-1 text-sm">
              {data.regularisations.map((r) => (
                <li key={r.id} className="flex items-center justify-between gap-2">
                  <span>
                    {day(r.date)}: {r.check_in} to {r.check_out}
                  </span>
                  <LeaveStatus status={r.status} label={r.status_label} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="mb-3 mt-8 flex items-center gap-2">
        <Button variant="secondary" onClick={() => setMonth(shiftMonth(month, -1))} aria-label="Previous month">
          ‹
        </Button>
        <h2 className="min-w-40 text-center font-display text-lg font-semibold text-ink">{monthLabel(data.summary.month)}</h2>
        <Button variant="secondary" onClick={() => setMonth(shiftMonth(month, 1))} aria-label="Next month" disabled={month >= thisMonth()}>
          ›
        </Button>
      </div>
      <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
        <StatTile label="Present" value={c.present} />
        <StatTile label="Office / remote" value={`${c.office} / ${c.remote}`} />
        <StatTile label="Late" value={c.late} />
        <StatTile label="Left early" value={c.early} />
        <StatTile label="No check-out" value={c.missing_checkout} />
        <StatTile label="On leave" value={c.on_leave} />
      </div>
      <div
        className="glass mt-4 overflow-x-auto rounded-xl2 p-4"
        tabIndex={0}
        role="region"
        aria-label="Daily attendance (scrolls sideways)"
      >
        <table className="w-full text-sm">
          <caption className="sr-only">Daily attendance for {monthLabel(data.summary.month)}</caption>
          <thead>
            <tr className="text-left text-xs text-muted">
              <th scope="col" className="py-1 pr-3">
                Day
              </th>
              <th scope="col" className="pr-3">
                Status
              </th>
              <th scope="col" className="pr-3">
                In
              </th>
              <th scope="col" className="pr-3">
                Out
              </th>
              <th scope="col">Flags</th>
            </tr>
          </thead>
          <tbody>
            {flagged.map((d) => (
              <tr key={d.date} className="border-t border-ink/10">
                <th scope="row" className="py-1.5 pr-3 text-left font-medium text-ink">
                  {day(d.date, false)}
                </th>
                <td className="pr-3">
                  {d.holiday || STATUS_LABEL[d.status]}
                  {d.mode ? ` (${d.mode})` : ''}
                </td>
                <td className="pr-3">{d.check_in ?? '–'}</td>
                <td className="pr-3">{d.check_out ?? '–'}</td>
                <td className="text-xs">
                  {[d.late && 'Late', d.early && 'Early', d.missing_checkout && 'No check-out', d.regularised && 'Corrected']
                    .filter(Boolean)
                    .join(', ')}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <TeamSummary month={month} />
    </>
  );
}
