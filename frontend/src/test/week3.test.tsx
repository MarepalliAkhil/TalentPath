import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { HiraAvatar } from '@/components/HiraAvatar';
import type {
  ApplicationInterviews,
  AssignedInterviews,
  CandidateOffer,
  HiraBriefing,
  HiraItem,
  HiraSummary,
  Interview,
  ScorecardPage,
  StaffOffer,
} from '@/lib/types';
import { page, signedInApi } from './fixtures';
import { axeViolations, fakeUser, renderApp, setViewport } from './utils';

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
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
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

/** Pretend HIRA's popup was already shown this session (for tests about other screens). */
function briefingAlreadyShown(role: 'recruiter' | 'hr_admin') {
  window.sessionStorage.setItem(`hira-briefing-shown:${fakeUser(role).id}`, '1');
}

const needsItem: HiraItem = {
  id: 'h1',
  action: 'no_slots',
  label: 'Could not find free slots',
  reason_code: 'no_common_free_time',
  job: { id: 'j1', title: 'Backend Engineer' },
  application: 'a1',
  candidate: 'Ravi Kumar',
  interview: 'i1',
  round: 'Technical 1',
  created_at: '2026-11-21T10:00:00Z',
  link: '/recruiter/jobs/j1/applications?open=a1',
};

const briefingText =
  'While you were away, HIRA scheduled 5 interviews, handled 2 reschedules and chased 3 overdue scorecards; 1 item needs you.';

const briefing: HiraBriefing = {
  since: '2026-11-14T10:00:00Z',
  counts: { interview_scheduled: 5, reschedule_handled: 2, interviewer_replaced: 0, scorecard_chased: 3, reminder_sent: 0 },
  needs_you_count: 1,
  needs_you: [needsItem],
  message: briefingText,
  spoken: briefingText,
};

const staffApi = {
  ...signedInApi,
  '/api/auth/csrf': {},
  'GET /api/hira/briefing': briefing,
  'POST /api/hira/briefing': { ok: true },
};

const days = Array.from({ length: 14 }, (_, i) => ({
  date: `2026-11-${String(8 + i).padStart(2, '0')}`,
  scheduled: i % 3,
  rescheduled: i % 2,
  chased: 0,
  reminders: 1,
  needs_you: 0,
}));

const summary: HiraSummary = {
  days: 14,
  kpis: { actions: 40, scheduled: 13, reschedules: 5, replacements: 1, chased: 3, reminders: 14, needs_you: 1 },
  by_day: days,
  needs_you: [needsItem],
  actions: [
    { value: 'interview_scheduled', label: 'Scheduled an interview' },
    { value: 'no_slots', label: 'Could not find free slots' },
  ],
};

const slots = [
  { id: 's1', starts_at: '2026-11-24T04:30:00Z', ends_at: '2026-11-24T05:30:00Z', label: 'Tue', status: 'open' as const, held_until: null },
  { id: 's2', starts_at: '2026-11-24T06:30:00Z', ends_at: '2026-11-24T07:30:00Z', label: 'Tue', status: 'open' as const, held_until: null },
  { id: 's3', starts_at: '2026-11-25T04:30:00Z', ends_at: '2026-11-25T05:30:00Z', label: 'Wed', status: 'open' as const, held_until: null },
];

const round = {
  id: 'r1',
  order: 1,
  name: 'Technical 1',
  duration_minutes: 60,
  mode: 'video' as const,
  mode_label: 'Video call',
  interviewers_needed: 1,
};

const pendingInterview: Interview = {
  id: 'i1',
  application: 'a1',
  job: { id: 'j1', title: 'Backend Engineer' },
  round,
  status: 'pending',
  status_label: 'Waiting for the candidate to pick a slot',
  starts_at: null,
  ends_at: null,
  when: '',
  mode: 'video',
  mode_label: 'Video call',
  meeting_link: '',
  location: '',
  meeting_note: '',
  simulated: true,
  reschedule_count: 0,
  interviewers: [],
  slots,
  reschedules_left: 2,
  can_reschedule: false,
};

const scheduledInterview: Interview = {
  ...pendingInterview,
  status: 'scheduled',
  status_label: 'Scheduled',
  starts_at: slots[0].starts_at,
  ends_at: slots[0].ends_at,
  meeting_link: 'https://meet.example/simulated/abc',
  meeting_note: 'Video call. Simulated meeting link for this demo; nobody will be there.',
  interviewers: [{ id: 'e1', name: 'Divya Pillai', status: 'assigned' }],
  slots: [],
  can_reschedule: true,
};

beforeEach(() => {
  setViewport(1280);
  window.sessionStorage.clear();
});

describe('HIRA login briefing', () => {
  it('pops up once per session with counts from the log and the Needs you list', async () => {
    const fetchMock = mockRoutes(staffApi);
    const first = renderApp('/recruiter', 'recruiter');
    const dialog = await screen.findByRole('dialog', { name: 'HIRA briefing' });
    expect(within(dialog).getByTestId('hira-message')).toHaveTextContent('scheduled 5 interviews');
    expect(within(dialog).getByText('Could not find free slots')).toBeInTheDocument();
    expect(within(dialog).getByRole('link', { name: 'Open HIRA activity' })).toHaveAttribute('href', '/hira');
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(within(dialog).getByRole('button', { name: 'Close' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/hira/briefing')).toHaveLength(1));
    first.unmount();
    // Same browser session: no second popup.
    renderApp('/recruiter', 'recruiter');
    await screen.findByRole('heading', { level: 1, name: 'Hiring overview' });
    expect(screen.queryByRole('dialog', { name: 'HIRA briefing' })).not.toBeInTheDocument();
    expect(calls(fetchMock, 'GET', '/api/hira/briefing')).toHaveLength(1);
  });

  it('reads counts aloud, never names, and can be muted', async () => {
    mockRoutes(staffApi);
    const speakMock = window.speechSynthesis.speak as unknown as ReturnType<typeof vi.fn>;
    speakMock.mockClear();
    renderApp('/recruiter', 'recruiter');
    const dialog = await screen.findByRole('dialog', { name: 'HIRA briefing' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Play spoken briefing' }));
    expect(speakMock).toHaveBeenCalledTimes(1);
    const spoken = (speakMock.mock.calls[0][0] as { text: string }).text;
    expect(spoken).toBe(briefing.spoken);
    expect(spoken).not.toContain('Ravi');
    await userEvent.click(within(dialog).getByRole('button', { name: /Mute voice/ }));
    expect(within(dialog).getByRole('button', { name: 'Play spoken briefing' })).toBeDisabled();
  });

  it('is not shown to hiring managers', async () => {
    const fetchMock = mockRoutes(staffApi);
    renderApp('/manager', 'hiring_manager');
    await screen.findByRole('heading', { level: 1, name: 'Your hiring' });
    expect(screen.queryByRole('dialog', { name: 'HIRA briefing' })).not.toBeInTheDocument();
    expect(calls(fetchMock, 'GET', '/api/hira/briefing')).toHaveLength(0);
  });
});

describe('HIRA avatar', () => {
  it('falls back to a clean initials avatar when the image files are missing', () => {
    const { container } = render(<HiraAvatar pose="welcome" />);
    const img = container.querySelector('img');
    expect(img).toHaveAttribute('src', '/hira/hira-welcome.webp');
    fireEvent.error(img as HTMLImageElement);
    expect(container.querySelector('img')).toHaveAttribute('src', '/hira/hira.webp');
    fireEvent.error(container.querySelector('img') as HTMLImageElement);
    expect(container.querySelector('img')).toBeNull();
    expect(container).toHaveTextContent('HI');
  });
});

describe('HIRA activity page', () => {
  it('shows KPIs, Needs you, a chart with a table view and the log', async () => {
    briefingAlreadyShown('recruiter');
    const log = page([
      { ...needsItem, needs_you: true },
      { ...needsItem, id: 'h2', action: 'interview_scheduled', label: 'Scheduled an interview' },
    ]);
    mockRoutes({ ...staffApi, '/api/hira/activity/summary': summary, '/api/hira/activity': log });
    renderApp('/hira', 'recruiter');
    expect(await screen.findByRole('heading', { level: 1, name: 'HIRA activity' })).toBeInTheDocument();
    expect(await screen.findByText('Interviews scheduled')).toBeInTheDocument();
    const needs = screen.getByRole('region', { name: /Needs you/ });
    expect(within(needs).getByText('Could not find free slots')).toBeInTheDocument();
    expect(screen.getByRole('img', { name: /Stacked bar chart/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Table' }));
    const table = screen.getByRole('table', { name: 'HIRA actions per day' });
    expect(within(table).getAllByRole('row')).toHaveLength(15); // header + 14 days
    expect(await screen.findByRole('table', { name: /activity log/ })).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });
});

describe('candidate scheduling picker', () => {
  it('holds a slot when chosen and books it on confirm', async () => {
    const held = { ...slots[1], status: 'held', held_until: '2026-11-22T06:00:00Z' };
    const fetchMock = mockRoutes({
      ...signedInApi,
      '/api/auth/csrf': {},
      '/api/my/interviews': { results: [pendingInterview] },
      '/api/my/offers': { results: [] },
      'POST /api/interviews/i1/hold': { slot: held, held_minutes: 30 },
      'POST /api/interviews/i1/confirm': scheduledInterview,
    });
    renderApp('/candidate', 'candidate');
    const group = await screen.findByRole('group', { name: /Times when your interviewers are free/ });
    const radios = within(group).getAllByRole('radio');
    expect(radios).toHaveLength(3);
    await userEvent.click(radios[1]);
    expect(await screen.findByText(/Held for you until/)).toBeInTheDocument();
    expect(calls(fetchMock, 'POST', '/api/interviews/i1/hold')).toHaveLength(1);
    await userEvent.click(screen.getByRole('button', { name: 'Confirm this time' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/interviews/i1/confirm')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'POST', '/api/interviews/i1/confirm')).toEqual({ slot: 's2' });
    expect(await axeViolations()).toEqual([]);
  });

  it('shows a scheduled interview with a simulated link, the .ics and reschedule', async () => {
    mockRoutes({ ...signedInApi, '/api/my/interviews': { results: [scheduledInterview] }, '/api/my/offers': { results: [] } });
    renderApp('/candidate', 'candidate');
    expect(await screen.findByText(/meet\.example\/simulated/)).toBeInTheDocument();
    expect(screen.getAllByText('Simulated').length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /Add to calendar/ })).toHaveAttribute('href', '/api/interviews/i1/calendar.ics');
    await userEvent.click(screen.getByRole('button', { name: 'Reschedule' }));
    expect(screen.getByText(/2 left/)).toBeInTheDocument();
  });

  it('works from the email link without signing in', async () => {
    mockRoutes({
      '/api/auth/csrf': {},
      '/api/schedule/tok': {
        job: { title: 'Backend Engineer' },
        round,
        status: 'pending',
        slots,
        expires_at: '2026-11-25T00:00:00Z',
        hold_minutes: 30,
        simulated: true,
      },
      'POST /api/schedule/tok/hold': { slot: { ...slots[0], status: 'held', held_until: '2026-11-22T06:00:00Z' } },
      'POST /api/schedule/tok/confirm': { status: 'scheduled', when: 'Tue 24 Nov 2026, 10:00 IST', mode: 'Video call' },
    });
    renderApp('/schedule/tok', null);
    expect(await screen.findByRole('heading', { level: 1, name: 'Pick your interview time' })).toBeInTheDocument();
    await userEvent.click((await screen.findAllByRole('radio'))[0]);
    await userEvent.click(await screen.findByRole('button', { name: 'Confirm this time' }));
    expect(await screen.findByText(/You are booked for Tue 24 Nov 2026/)).toBeInTheDocument();
  });
});

const scorecardPage: ScorecardPage = {
  interview: {
    ...scheduledInterview,
    status: 'completed',
    candidate: { code: 'Candidate #7F3A', full_name: 'Ravi Kumar' },
    can_submit_scorecard: true,
    my_scorecard_submitted: false,
    scorecard_due_at: '2026-11-25T05:30:00Z',
  },
  template: [
    { key: 'skill:python', label: 'Python', kind: 'skill' },
    { key: 'communication', label: 'Communication', kind: 'general' },
  ],
  comment_required_for: [1, 2, 5],
  mine: null,
  others: [],
  others_hidden: true,
  summary: { submitted: 1, expected: 2, hidden: true, criteria: [], recommendations: { strong_no: 0, no: 0, yes: 1, strong_yes: 0 } },
};

describe('scorecard form', () => {
  it('requires a comment for extreme ratings and keeps others hidden until you submit', async () => {
    const fetchMock = mockRoutes({
      ...signedInApi,
      '/api/auth/csrf': {},
      'GET /api/interviews/i1/scorecards': scorecardPage,
      'POST /api/interviews/i1/scorecards': {},
    });
    renderApp('/interviews/i1/scorecard', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'Scorecard: Ravi Kumar' })).toBeInTheDocument();
    expect(screen.getByText(/Hidden until you submit your own scorecard/)).toBeInTheDocument();
    const python = screen.getByRole('group', { name: /Python/ });
    await userEvent.click(within(python).getByRole('radio', { name: /5: Exceptional/ }));
    expect(within(python).getByLabelText(/Comment for Python \(required/)).toBeRequired();
    await userEvent.type(within(python).getByLabelText(/Comment for Python/), 'Great design.');
    const comms = screen.getByRole('group', { name: /^Communication/ });
    await userEvent.click(within(comms).getByRole('radio', { name: /4: Strong/ }));
    expect(within(comms).getByLabelText(/Comment for Communication \(optional\)/)).not.toBeRequired();
    await userEvent.click(screen.getByRole('radio', { name: 'Strong yes' }));
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Submit scorecard' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/interviews/i1/scorecards')).toHaveLength(1));
    const body = bodyOf(fetchMock, 'POST', '/api/interviews/i1/scorecards');
    expect(body.ratings).toEqual({ 'skill:python': 5, communication: 4 });
    expect(body.comments).toEqual({ 'skill:python': 'Great design.' });
    expect(body.recommendation).toBe('strong_yes');
  });
});

const terms = {
  designation: 'Senior Backend Engineer',
  department: 'Engineering',
  location: 'Hyderabad',
  reporting_manager_id: 'm1',
  reporting_manager_name: 'Vikram Natarajan',
  joining_date: '2027-01-04',
  fixed_pay: 2400000,
  variable_pay: 240000,
  joining_bonus: 0,
  total: 2640000,
  display: { fixed_pay: 'INR 24,00,000', variable_pay: 'INR 2,40,000', joining_bonus: 'INR 0', total: 'INR 26,40,000' },
  currency: 'INR' as const,
};

const candidateOffer: CandidateOffer = {
  id: 'o1',
  status: 'sent',
  status_label: 'Sent to candidate',
  approval_step: '',
  approval_step_label: '',
  expires_on: '2026-12-01',
  created_at: '2026-11-20T10:00:00Z',
  job: { title: 'Senior Backend Engineer (Python)' },
  terms,
  sent_at: '2026-11-21T10:00:00Z',
  responded_at: null,
  can_respond: true,
  has_letter: true,
  acknowledgement: 'Typing your full name records that you accept this offer. It is not a legal electronic signature.',
  demo: true,
};

const staffOffer: StaffOffer = {
  id: 'o1',
  status: 'pending_approval',
  status_label: 'Pending approval',
  approval_step: 'hiring_manager',
  approval_step_label: 'Hiring manager',
  expires_on: '2026-12-01',
  created_at: '2026-11-20T10:00:00Z',
  application: 'a1',
  job: { id: 'j1', title: 'Senior Backend Engineer (Python)' },
  candidate: { code: 'Candidate #7F3A', full_name: 'Asha Verma' },
  terms,
  created_by: 'Meera Iyer',
  approvals: { hiring_manager: { name: null, at: null }, hr_admin: { name: null, at: null } },
  rejected: null,
  sent_at: null,
  responded_at: null,
  decline_reason: '',
  revoke_reason: '',
  has_letter: false,
  actions: { edit: false, submit: false, approve: true, reject: true, send: false, revoke: false },
};

describe('offers', () => {
  it('candidate accepts by typing their name (not a legal e-signature)', async () => {
    const fetchMock = mockRoutes({
      ...signedInApi,
      '/api/auth/csrf': {},
      'GET /api/offers/o1': candidateOffer,
      'POST /api/offers/o1/accept': { ...candidateOffer, status: 'accepted', status_label: 'Accepted', can_respond: false },
    });
    renderApp('/candidate/offers/o1', 'candidate');
    expect(await screen.findByRole('heading', { level: 1, name: /Your offer/ })).toBeInTheDocument();
    expect(screen.getByText(/fictional offer from a fictional company/)).toBeInTheDocument();
    expect(screen.getByText('INR 26,40,000')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /offer letter/ })).toHaveAttribute('href', '/api/offers/o1/letter');
    expect(screen.getByText(/not a legal electronic signature/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/Type your full name to accept/), 'Asha Verma');
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Accept offer' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/offers/o1/accept')).toHaveLength(1));
    expect(bodyOf(fetchMock, 'POST', '/api/offers/o1/accept')).toEqual({ typed_name: 'Asha Verma' });
    expect(await screen.findByText(/You accepted the offer/)).toBeInTheDocument();
  });

  it('hiring manager approves at their step', async () => {
    const fetchMock = mockRoutes({
      ...signedInApi,
      '/api/auth/csrf': {},
      'GET /api/offers/o1': staffOffer,
      'POST /api/offers/o1/approve': {
        ...staffOffer,
        approval_step: 'hr_admin',
        approval_step_label: 'HR admin',
        actions: { ...staffOffer.actions, approve: false, reject: false },
      },
    });
    renderApp('/offers/o1', 'hiring_manager');
    expect(await screen.findByRole('heading', { level: 1, name: 'Offer: Asha Verma' })).toBeInTheDocument();
    expect(screen.getByText('Waiting for Hiring manager')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Send to candidate' })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/offers/o1/approve')).toHaveLength(1));
    expect(await screen.findByText('Waiting for HR admin')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Approve' })).not.toBeInTheDocument();
  });

  it('a rejection needs a reason of at least 10 characters', async () => {
    mockRoutes({ ...signedInApi, '/api/auth/csrf': {}, 'GET /api/offers/o1': staffOffer });
    renderApp('/offers/o1', 'hiring_manager');
    await userEvent.click(await screen.findByRole('button', { name: 'Request changes' }));
    const dialog = screen.getByRole('dialog', { name: 'Request changes' });
    const submit = within(dialog).getByRole('button', { name: 'Request changes' });
    expect(submit).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Reason/), 'Pay is above band.');
    expect(submit).toBeEnabled();
  });
});

const appInterviews: ApplicationInterviews = {
  application: 'a2',
  status: 'interview',
  hira_enabled: true,
  rounds: [
    {
      round: { ...round, pool: [{ id: 'e1', name: 'Divya Pillai' }] },
      interview: {
        ...scheduledInterview,
        status: 'completed',
        status_label: 'Completed',
        candidate: { code: 'Candidate #9A11', full_name: 'Ravi Kumar' },
        attention: '',
        attention_label: '',
        scheduled_by: 'hira',
      },
      outcome: 'passed',
      summary: {
        submitted: 2,
        expected: 2,
        hidden: false,
        criteria: [{ key: 'communication', label: 'Communication', average: 4.5, count: 2 }],
        recommendations: { strong_no: 0, no: 0, yes: 1, strong_yes: 1 },
      },
    },
  ],
  final_round_passed: true,
  can_schedule: true,
  offer: null,
};

describe('interview panel in the application drawer', () => {
  it('shows each round with averages and recommendations, and lets the recruiter draft an offer', async () => {
    briefingAlreadyShown('recruiter');
    mockRoutes({
      ...signedInApi,
      '/api/jobs/j1/applications': {
        ...page([]),
        job: { id: 'j1', title: 'Backend Engineer', status: 'open', blind_screening: true, reveal_stage: 'interview' },
      },
      '/api/applications/a2': {
        id: 'a2',
        status: 'interview',
        status_label: 'Interview',
        created_at: '2026-11-20T10:00:00Z',
        updated_at: '2026-11-20T10:00:00Z',
        resume_filename: 'ravi.pdf',
        blind: false,
        candidate: { id: 'u2', code: 'Candidate #9A11', full_name: 'Ravi Kumar', email: 'ravi@candidates.example', headline: '', location: '' },
        job: { id: 'j1', title: 'Backend Engineer', slug: 'backend' },
        allowed_transitions: ['offer', 'rejected'],
        fit: null,
        skills: [],
        resume_text: 'Resume',
        evidence: [],
        notes: [],
        events: [],
        revealed: null,
        reveal_stage: 'interview',
      },
      '/api/applications/a2/interviews': appInterviews,
      '/api/hiring-managers': [{ id: 'm1', full_name: 'Vikram Natarajan' }],
    });
    renderApp('/recruiter/jobs/j1/applications?open=a2', 'recruiter');
    const drawer = await screen.findByRole('dialog', { name: 'Application details' });
    const section = await within(drawer).findByRole('region', { name: 'Interviews' });
    expect(await within(section).findByText('Passed')).toBeInTheDocument();
    expect(within(section).getByText('4.5')).toBeInTheDocument();
    expect(within(section).getByText(/Strong yes 1/)).toBeInTheDocument();
    await userEvent.click(within(section).getByRole('button', { name: 'Draft offer' }));
    const form = await screen.findByRole('form', { name: 'Offer terms' });
    expect(within(form).getByLabelText(/Designation/)).toHaveValue('Backend Engineer');
    expect(await axeViolations()).toEqual([]);
  });
});

describe('mobile 390 px', () => {
  const assigned: AssignedInterviews = {
    upcoming: [
      {
        ...scheduledInterview,
        candidate: { code: 'Candidate #9A11', full_name: null },
        can_decline: true,
        can_submit_scorecard: false,
        my_scorecard_submitted: false,
      },
    ],
    needs_feedback: [
      { ...scheduledInterview, id: 'i2', status: 'completed', candidate: { code: 'Candidate #1B22', full_name: 'Neha Shah' }, can_submit_scorecard: true },
    ],
    past: [],
  };

  it('my interviews page is accessible and blind-aware', async () => {
    setViewport(390);
    mockRoutes({ ...signedInApi, '/api/interviews/assigned': assigned });
    renderApp('/interviews', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'My interviews' })).toBeInTheDocument();
    expect((await screen.findAllByText(/Candidate #9A11/)).length).toBeGreaterThan(0);
    expect(screen.getByRole('link', { name: /Fill in scorecard/ })).toHaveAttribute('href', '/interviews/i2/scorecard');
    expect(await axeViolations()).toEqual([]);
  });

  it('offers list is accessible', async () => {
    setViewport(390);
    mockRoutes({ ...signedInApi, '/api/offers': page([staffOffer]) });
    renderApp('/offers', 'hiring_manager');
    expect(await screen.findByRole('heading', { level: 1, name: 'Offers' })).toBeInTheDocument();
    expect(await screen.findByText('Waiting for Hiring manager')).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('availability page lists every weekday with time inputs', async () => {
    setViewport(390);
    mockRoutes({
      ...signedInApi,
      '/api/availability': { timezone: 'Asia/Kolkata', working_hours: { '1': ['10:00', '18:00'] }, skills: ['Python'], blocked: [] },
    });
    renderApp('/interviews/availability', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'My availability' })).toBeInTheDocument();
    expect(screen.getByRole('checkbox', { name: 'Monday' })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: 'Sunday' })).not.toBeChecked();
    expect(screen.getByLabelText('Sunday start')).toBeDisabled();
    expect(await axeViolations()).toEqual([]);
  });
});
