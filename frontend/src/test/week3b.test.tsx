import { fireEvent, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import type { Approvals, AttendanceMe, Balances, HrConfig, LeaveCheck, LeaveRequest, Onboarding, Policies, TeamCalendar } from '@/lib/hr';
import type { StaffOffer } from '@/lib/types';
import { signedInApi } from './fixtures';
import { axeViolations, renderApp, setViewport } from './utils';

type Value = unknown | ((body: unknown) => unknown);

/** fetch stub keyed by "METHOD /api/path" (or just "/api/path" for any method). */
function mockRoutes(routes: Record<string, Value>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname + input.search : input.url;
    const path = url.split('?')[0];
    const method = (init?.method ?? 'GET').toUpperCase();
    const key = [`${method} ${path}`, path].find((k) => k in routes);
    if (!key) {
      return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404, headers: { 'content-type': 'application/json' } });
    }
    const value = routes[key];
    const body = init?.body && typeof init.body === 'string' ? JSON.parse(init.body) : undefined;
    const data = typeof value === 'function' ? (value as (b: unknown) => unknown)(body) : value;
    return new Response(JSON.stringify(data ?? {}), { status: 200, headers: { 'content-type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

type FetchMock = ReturnType<typeof mockRoutes>;

function calls(mock: FetchMock, method: string, path: string) {
  return mock.mock.calls.filter(
    ([input, init]) => String(input).split('?')[0] === path && ((init as RequestInit | undefined)?.method ?? 'GET') === method,
  );
}

function bodyOf(mock: FetchMock, method: string, path: string) {
  const [, init] = calls(mock, method, path)[0];
  return JSON.parse(String((init as RequestInit).body));
}

const api = { ...signedInApi, '/api/auth/csrf': {} };

// ---------------------------------------------------------------- fixtures
const person = (name: string, designation: string) => ({
  id: name,
  name,
  designation,
  department: 'Engineering',
  email: `${name.split(' ')[0].toLowerCase()}@demo.example`,
});

const onboarding: Onboarding = {
  employee: {
    id: 'e1',
    code: 'LW1031',
    name: 'Asha Verma',
    designation: 'Frontend Engineer',
    department: 'Engineering',
    location: 'Hyderabad',
    joined_on: '2026-11-30',
    status: 'onboarding',
  },
  manager: person('Vikram Rao', 'Head of Engineering'),
  buddy: person('Rahul Verma', 'Backend Engineer'),
  progress: { done: 1, total: 3, percent: 33 },
  tasks: [
    {
      id: 't1',
      title: 'Upload ID and address proof',
      description: 'Synthetic in this demo.',
      category: 'documents',
      category_label: 'Documents',
      owner_kind: 'employee',
      owner_label: 'New joiner',
      owner_name: 'Asha Verma',
      kind: 'upload',
      due_on: '2026-11-26',
      done: false,
      done_at: null,
      done_by: null,
      has_document: false,
      can_complete: true,
      overdue: false,
    },
    {
      id: 't2',
      title: 'Read and acknowledge the code of conduct',
      description: '',
      category: 'policies',
      category_label: 'Policies',
      owner_kind: 'employee',
      owner_label: 'New joiner',
      owner_name: 'Asha Verma',
      kind: 'acknowledge',
      due_on: '2026-12-01',
      done: false,
      done_at: null,
      done_by: null,
      has_document: false,
      can_complete: true,
      overdue: false,
    },
    {
      id: 't3',
      title: 'Prepare laptop and accounts',
      description: '',
      category: 'it',
      category_label: 'IT setup',
      owner_kind: 'it',
      owner_label: 'IT desk',
      owner_name: 'IT desk',
      kind: 'task',
      due_on: '2026-11-27',
      done: true,
      done_at: '2026-11-22T10:00:00Z',
      done_by: 'Meera Iyer',
      has_document: false,
      can_complete: false,
      overdue: false,
    },
  ],
  first_week: [
    { day: '2026-11-30', starts: '10:00', title: 'Welcome, ID card and laptop handover', host: 'HR and IT desk' },
    { day: '2026-12-01', starts: '13:00', title: 'Lunch with your buddy', host: 'Rahul Verma' },
  ],
  welcome_pending: true,
};

const balances: Balances = {
  year: 2026,
  balances: [
    { type: 'casual', name: 'Casual leave', unpaid: false, balance: 11, pending: 0, taken: 1, available: 11 },
    { type: 'earned', name: 'Earned leave', unpaid: false, balance: 16.5, pending: 0, taken: 0, available: 16.5 },
    { type: 'lop', name: 'Loss of pay', unpaid: true, balance: null, pending: 0, taken: 0, available: null },
  ],
  types: [
    { code: 'casual', name: 'Casual leave', half_day_allowed: true, unpaid: false, min_notice_days: 1, document_after_days: null },
    { code: 'earned', name: 'Earned leave', half_day_allowed: false, unpaid: false, min_notice_days: 7, document_after_days: null },
    { code: 'lop', name: 'Loss of pay', half_day_allowed: true, unpaid: true, min_notice_days: 3, document_after_days: null },
  ],
  hr_approval_over_days: 5,
};

const warning = '2 of 4 people in Vikram Rao’s team are already off on Tue 8 Dec (1 would be available).';

const check: LeaveCheck = {
  days: 4,
  days_label: '4 days',
  breakdown: [
    { date: '2026-12-04', kind: 'working', counted: 1, label: '' },
    { date: '2026-12-05', kind: 'sandwich', counted: 1, label: '' },
    { date: '2026-12-06', kind: 'sandwich', counted: 1, label: '' },
    { date: '2026-12-07', kind: 'working', counted: 1, label: '' },
  ],
  errors: {},
  warnings: [warning],
  needs_document: false,
  needs_hr_approval: false,
  available: 16.5,
  ok: true,
};

const leave: LeaveRequest = {
  id: 'l1',
  employee: { id: 'e2', name: 'Rahul Verma', code: 'LW1020' },
  leave_type: 'earned',
  leave_type_name: 'Earned leave',
  start: '2026-12-04',
  end: '2026-12-07',
  half: '',
  days: 4,
  days_label: '4 days',
  status: 'pending',
  status_label: 'Pending',
  stage: 'manager',
  approver: 'Vikram Rao',
  delegated: false,
  escalated: false,
  reason: 'Sister’s wedding in Vizag',
  has_document: false,
  decision_note: null,
  created_at: '2026-11-22T10:00:00Z',
  can_cancel: false,
  can_act: true,
  warnings: [warning],
};

const calendar: TeamCalendar = {
  month: '2026-12',
  team: {
    name: 'Vikram Rao’s team',
    members: [
      { id: 'e1', name: 'Asha Verma', designation: 'Frontend Engineer' },
      { id: 'e2', name: 'Rahul Verma', designation: 'Backend Engineer' },
    ],
  },
  sees_reasons: false,
  threshold_pct: 50,
  days: Array.from({ length: 31 }, (_, i) => {
    const d = `2026-12-${String(i + 1).padStart(2, '0')}`;
    const dow = new Date(`${d}T00:00:00Z`).getUTCDay();
    return {
      date: d,
      kind: d === '2026-12-25' ? 'holiday' : dow === 0 || dow === 6 ? 'weekly_off' : 'working',
      holiday: d === '2026-12-25' ? 'Christmas' : '',
    };
  }),
  entries: [
    {
      id: 'l1',
      employee: 'e2',
      name: 'Rahul Verma',
      start: '2026-12-04',
      end: '2026-12-07',
      half: '',
      status: 'approved',
      type: null,
      reason: null,
    },
  ],
  joiners: [{ name: 'Asha Verma', joined_on: '2026-11-30', designation: 'Frontend Engineer' }],
  has_reports: false,
  me: 'e1',
};

const attendance: AttendanceMe = {
  today: null,
  shift: { start: '09:30', end: '18:30', late_grace_minutes: 15, early_grace_minutes: 15, location: 'Hyderabad' },
  summary: {
    month: '2026-11',
    counts: {
      working_days: 15,
      present: 12,
      office: 8,
      remote: 4,
      late: 2,
      early: 1,
      missing_checkout: 1,
      on_leave: 1,
      holidays: 0,
      absent: 2,
    },
    days: [
      {
        date: '2026-11-20',
        status: 'present',
        holiday: '',
        check_in: '09:52',
        check_out: null,
        mode: 'office',
        late: true,
        early: false,
        missing_checkout: true,
        regularised: false,
      },
      {
        date: '2026-11-21',
        status: 'weekly_off',
        holiday: '',
        check_in: null,
        check_out: null,
        mode: null,
        late: false,
        early: false,
        missing_checkout: false,
        regularised: false,
      },
    ],
  },
  regularisations: [],
};

const accepted: StaffOffer = {
  id: 'o1',
  status: 'accepted',
  status_label: 'Accepted',
  approval_step: '',
  approval_step_label: '',
  expires_on: '2026-12-01',
  created_at: '2026-11-10T10:00:00Z',
  application: 'a1',
  job: { id: 'j1', title: 'Frontend Engineer (React)' },
  candidate: { code: 'Candidate #7F3A', full_name: 'Ishaan Malhotra' },
  terms: {
    designation: 'Frontend Engineer',
    department: 'Engineering',
    location: 'Hyderabad',
    reporting_manager_id: 'u1',
    reporting_manager_name: 'Vikram Rao',
    joining_date: '2026-11-30',
    fixed_pay: 1800000,
    variable_pay: 0,
    joining_bonus: 0,
    total: 1800000,
    display: { fixed_pay: 'INR 18,00,000', variable_pay: 'INR 0', joining_bonus: 'INR 0', total: 'INR 18,00,000' },
    currency: 'INR',
  },
  created_by: 'Meera Iyer',
  approvals: {
    manager: { name: 'Vikram Rao', at: '2026-11-11T10:00:00Z' },
    hr: { name: 'Priya Nair', at: '2026-11-12T10:00:00Z' },
  },
  rejected: null,
  sent_at: '2026-11-12T11:00:00Z',
  responded_at: '2026-11-13T09:00:00Z',
  decline_reason: '',
  revoke_reason: '',
  has_letter: true,
  actions: { edit: false, submit: false, approve: false, reject: false, send: false, revoke: false, hire: true },
  hired: null,
};

// ---------------------------------------------------------------- tests
describe('one-click hire', () => {
  it('recruiter hires an accepted offer after seeing what will happen', async () => {
    let hired = false;
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/offers/o1': () =>
        hired
          ? {
              ...accepted,
              actions: { ...accepted.actions, hire: false },
              hired: { employee: 'e9', code: 'LW1031', joined_on: '2026-11-30' },
            }
          : accepted,
      'POST /api/offers/o1/hire': () => {
        hired = true;
        return onboarding;
      },
    });
    renderApp('/offers/o1', 'recruiter');
    await userEvent.click(await screen.findByRole('button', { name: 'Hire' }));
    const dialog = screen.getByRole('dialog', { name: 'Hire Ishaan Malhotra?' });
    expect(within(dialog).getByText(/switch the same login to the employee role/)).toBeInTheDocument();
    expect(within(dialog).getByText(/withdraw their other open applications/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Hire now' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/offers/o1/hire')).toHaveLength(1));
    expect(await screen.findByText(/Hired: employee LW1031/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See onboarding progress' })).toHaveAttribute('href', '/onboarding/e9');
    expect(screen.queryByRole('button', { name: 'Hire' })).not.toBeInTheDocument();
  });
});

describe('welcome page', () => {
  it('a new employee sees the checklist, buddy, manager and first week, and it is marked seen', async () => {
    const fetchMock = mockRoutes({ ...api, 'GET /api/onboarding/me': onboarding, 'POST /api/onboarding/me': { ok: true } });
    renderApp('/welcome', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'Welcome to Lumina Works, Asha' })).toBeInTheDocument();
    expect(screen.getByText('LW1031')).toBeInTheDocument();
    expect(screen.getByText('Vikram Rao')).toBeInTheDocument();
    expect(screen.getAllByText('Rahul Verma').length).toBeGreaterThan(0);
    expect(screen.getByRole('progressbar', { name: '1 of 3 done' })).toHaveAttribute('aria-valuenow', '33');
    expect(screen.getByRole('heading', { name: 'Your first week' })).toBeInTheDocument();
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/onboarding/me')).toHaveLength(1));
    expect(await axeViolations()).toEqual([]);
  });

  it('finishing a checklist item calls the API; uploads need a file first', async () => {
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/onboarding/me': { ...onboarding, welcome_pending: false },
      'POST /api/onboarding/tasks/t2/complete': { ...onboarding.tasks[1], done: true },
    });
    renderApp('/welcome', 'employee');
    const upload = await screen.findByRole('button', { name: /Upload and mark done: Upload ID/ });
    expect(upload).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: /I have read and accept: Read and acknowledge the code of conduct/ }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/onboarding/tasks/t2/complete')).toHaveLength(1));
    expect(screen.queryByRole('button', { name: /Prepare laptop/ })).not.toBeInTheDocument(); // IT's task, not mine
  });

  it('the employee dashboard sends a new joiner to the welcome page once', async () => {
    mockRoutes({ ...api, 'GET /api/onboarding/me': onboarding, 'POST /api/onboarding/me': { ok: true }, '/api/leave/balances': balances });
    renderApp('/employee', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: /Welcome to Lumina Works/ })).toBeInTheDocument();
  });
});

describe('leave', () => {
  it('shows the days counted, the sandwich days and a team warning before applying', async () => {
    const fetchMock = mockRoutes({
      ...api,
      '/api/leave/balances': balances,
      'GET /api/leave/requests': { results: [] },
      'POST /api/leave/preview': check,
      'POST /api/leave/requests': { ...leave, employee: { id: 'e1', name: 'Asha Verma', code: 'LW1031' }, can_act: false },
    });
    renderApp('/leave', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'Leave' })).toBeInTheDocument();
    expect(screen.getByRole('list', { name: 'Leave balances for 2026' })).toHaveTextContent('16.5');
    await userEvent.selectOptions(screen.getByLabelText(/Leave type/), 'earned');
    fireEvent.change(screen.getByLabelText(/From/), { target: { value: '2026-12-04' } });
    fireEvent.change(screen.getByLabelText(/^To/), { target: { value: '2026-12-07' } });
    expect(await screen.findByTestId('days-counted')).toHaveTextContent('4 days');
    expect(screen.getByText(/Sandwich rule/)).toBeInTheDocument();
    expect(screen.getByText(warning)).toBeInTheDocument();
    expect(screen.getByText(/you can still go ahead/)).toBeInTheDocument();
    expect(screen.queryByLabelText('Duration')).not.toBeInTheDocument(); // earned leave: no half days
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Apply for 4 days' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/leave/requests')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'POST', '/api/leave/requests')).toMatchObject({
      leave_type: 'earned',
      start: '2026-12-04',
      end: '2026-12-07',
    });
    expect(await screen.findByText(/Sent for approval/)).toBeInTheDocument();
  });

  it('rule errors block the button', async () => {
    mockRoutes({
      ...api,
      '/api/leave/balances': balances,
      'GET /api/leave/requests': { results: [] },
      'POST /api/leave/preview': { ...check, ok: false, warnings: [], errors: { start: 'Earned leave needs 7 days’ notice.' } },
    });
    renderApp('/leave', 'employee');
    await screen.findByRole('heading', { level: 1, name: 'Leave' });
    fireEvent.change(screen.getByLabelText(/From/), { target: { value: '2026-11-24' } });
    expect((await screen.findAllByText(/needs 7 days’ notice/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('button', { name: 'Apply' })).toBeDisabled();
  });
});

describe('approvals inbox', () => {
  const approvals: Approvals = { leave: [leave], regularisations: [], needs_attention: [] };

  it('the manager sees the reason and the clash warning, and approves', async () => {
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/leave/approvals': approvals,
      'POST /api/leave/requests/l1/approve': { ...leave, status: 'approved' },
    });
    renderApp('/leave/approvals', 'manager');
    expect(await screen.findByText('“Sister’s wedding in Vizag”')).toBeInTheDocument();
    expect(screen.getByText(warning)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Approve leave for Rahul Verma' }));
    await userEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/leave/requests/l1/approve')).toHaveLength(1));
    expect(await screen.findByText('Approved: Rahul Verma.')).toBeInTheDocument();
  });

  it('not approving needs a reason', async () => {
    mockRoutes({ ...api, 'GET /api/leave/approvals': approvals });
    renderApp('/leave/approvals', 'employee');
    await userEvent.click(await screen.findByRole('button', { name: 'Do not approve leave for Rahul Verma' }));
    const dialog = screen.getByRole('dialog');
    expect(within(dialog).getByRole('button', { name: 'Do not approve' })).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'Release week');
    expect(within(dialog).getByRole('button', { name: 'Do not approve' })).toBeEnabled();
  });
});

describe('team calendar', () => {
  it('shows who is off, holidays and joiners without reasons for peers', async () => {
    mockRoutes({ ...api, '/api/team-calendar': calendar });
    renderApp('/team-calendar', 'employee');
    expect(await screen.findByRole('heading', { level: 2, name: 'December 2026' })).toBeInTheDocument();
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByText(/Leave types and reasons are visible only/)).toBeInTheDocument();
    expect(screen.getByText(/Christmas/)).toBeInTheDocument();
    expect(screen.getByText(/joins as Frontend Engineer/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });
});

describe('attendance', () => {
  it('checks in with a work mode and shows the month', async () => {
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/attendance/me': attendance,
      'POST /api/attendance/check-in': {
        date: '2026-11-22',
        check_in: '09:31',
        check_out: null,
        mode: 'remote',
        late: false,
        early: false,
      },
      '/api/attendance/team': { month: '2026-11', scope: 'reports', rows: [] },
    });
    renderApp('/attendance', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'Attendance' })).toBeInTheDocument();
    expect(screen.getByText(/No location is recorded/)).toBeInTheDocument();
    expect(screen.getAllByText('No check-out').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('radio', { name: 'remote' }));
    await userEvent.click(screen.getByRole('button', { name: 'Check in' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/attendance/check-in')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'POST', '/api/attendance/check-in')).toEqual({ mode: 'remote' });
    expect(await axeViolations()).toEqual([]);
  });
});

describe('Ask HIRA for employees', () => {
  it('shows a confirmation card and only submits leave when the employee presses Confirm', async () => {
    const reply = {
      intent: 'apply_leave',
      answer: 'Here is casual leave for Fri 27 Nov 2026: 1 day. Press Confirm to send it to your manager.',
      chips: ['My leave balance'],
      jobs: [],
      applications: [],
      action: null,
      link: null,
      needs_sign_in: false,
      card: {
        kind: 'leave_confirm',
        payload: { leave_type: 'casual', start: '2026-11-27', end: '2026-11-27', half: '', reason: '' },
        check: { ...check, days: 1, days_label: '1 day', warnings: [], breakdown: [] },
        type_name: 'Casual leave',
      },
    };
    const fetchMock = mockRoutes({
      ...api,
      '/api/leave/balances': balances,
      'GET /api/onboarding/me': { ...onboarding, welcome_pending: false },
      'POST /api/hira/ask': reply,
      'POST /api/leave/requests': { ...leave, leave_type_name: 'Casual leave', days_label: '1 day' },
    });
    renderApp('/employee', 'employee');
    await userEvent.click(await screen.findByRole('button', { name: /Ask HIRA/ }));
    const panel = screen.getByRole('dialog', { name: 'Ask HIRA' });
    await userEvent.click(within(panel).getByRole('button', { name: 'Apply casual leave next Friday' }));
    const card = await within(panel).findByRole('group', { name: 'Leave request to confirm' });
    expect(within(card).getByText('Days counted: 1 day')).toBeInTheDocument();
    expect(calls(fetchMock, 'POST', '/api/leave/requests')).toHaveLength(0); // nothing submitted yet
    await userEvent.click(within(card).getByRole('button', { name: 'Confirm' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/leave/requests')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'POST', '/api/leave/requests')).toEqual(reply.card.payload);
    expect(await within(panel).findByText(/sent to Vikram Rao for approval/)).toBeInTheDocument();
  });

  it('shows balances as a table', async () => {
    mockRoutes({
      ...api,
      '/api/leave/balances': balances,
      'GET /api/onboarding/me': { ...onboarding, welcome_pending: false },
      'POST /api/hira/ask': {
        intent: 'leave_balance',
        answer: 'Available now: Casual leave: 11 days.',
        chips: [],
        jobs: [],
        applications: [],
        action: null,
        link: '/leave',
        needs_sign_in: false,
        card: { kind: 'balances', rows: balances.balances },
      },
    });
    renderApp('/employee', 'employee');
    await userEvent.click(await screen.findByRole('button', { name: /Ask HIRA/ }));
    await userEvent.click(screen.getByRole('button', { name: 'My leave balance' }));
    expect(await screen.findByRole('table', { name: 'Your leave balances' })).toHaveTextContent('Casual leave11');
  });
});

describe('policies and HR settings', () => {
  const policies: Policies = {
    handbook: [{ slug: 'leave-overview', title: 'Leave at Lumina Works', body: 'Every location sets its own leave types.' }],
    location: { id: 'loc1', name: 'Hyderabad' },
    leave_types: [],
    holidays: [{ id: 'h1', date: '2026-06-02', name: 'Telangana Formation Day', regional: true, note: 'Demo data' }],
    work_policy: null,
  };

  it('policies page marks holidays as demo data to verify', async () => {
    mockRoutes({ ...api, '/api/hr/policies': policies });
    renderApp('/hr/policies', 'employee');
    expect(await screen.findByText('Telangana Formation Day')).toBeInTheDocument();
    expect(screen.getByText(/verify every date/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('hr_admin edits a leave rule', async () => {
    const lt = {
      id: 'lt1',
      location: 'loc1',
      location_name: 'Hyderabad',
      code: 'casual',
      name: 'Casual leave',
      yearly_quota: 12,
      monthly_accrual: true,
      prorate_joiners: true,
      carry_forward_cap: 0,
      min_notice_days: 1,
      backdate_days: 0,
      max_consecutive_days: 3,
      half_day_allowed: true,
      document_after_days: null,
      sandwich_rule: false,
      unpaid: false,
      active: true,
      summary: 'Casual leave: 12 days a year, credited monthly.',
    };
    const config: HrConfig = {
      locations: [{ id: 'loc1', name: 'Hyderabad' }],
      leave_types: [lt],
      work_policies: [],
      holidays: [],
      codes: [],
    };
    const fetchMock = mockRoutes({
      ...api,
      '/api/hr/config': config,
      'PATCH /api/hr/config/leave-types/lt1': { ...lt, min_notice_days: 2 },
    });
    renderApp('/hr/settings', 'hr');
    await userEvent.click(await screen.findByRole('button', { name: 'Edit Casual leave' }));
    const notice = screen.getByLabelText('Minimum notice (days)');
    await userEvent.clear(notice);
    await userEvent.type(notice, '2');
    await userEvent.click(screen.getByRole('checkbox', { name: /Sandwich rule/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Save casual leave' }));
    await waitFor(() => expect(calls(fetchMock, 'PATCH', '/api/hr/config/leave-types/lt1')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'PATCH', '/api/hr/config/leave-types/lt1')).toMatchObject({ min_notice_days: 2, sandwich_rule: true });
    expect(await axeViolations()).toEqual([]);
  });
});

describe('mobile 390 px (week 3B)', () => {
  it('welcome page', async () => {
    setViewport(390);
    mockRoutes({ ...api, 'GET /api/onboarding/me': { ...onboarding, welcome_pending: false } });
    renderApp('/welcome', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: /Welcome/ })).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('leave page', async () => {
    setViewport(390);
    mockRoutes({ ...api, '/api/leave/balances': balances, 'GET /api/leave/requests': { results: [leave] } });
    renderApp('/leave', 'employee');
    expect(await screen.findByText(/Earned leave: Fri 4 Dec/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('team calendar grid scrolls inside a focusable region, not the page', async () => {
    setViewport(390);
    mockRoutes({ ...api, '/api/team-calendar': calendar });
    renderApp('/team-calendar', 'employee');
    const region = await screen.findByRole('region', { name: /Calendar grid/ });
    expect(region).toHaveAttribute('tabindex', '0');
    expect(await axeViolations()).toEqual([]);
  });
});
