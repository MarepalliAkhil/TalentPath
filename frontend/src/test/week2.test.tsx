import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import type { Board, FairnessResult, Fit, HiraReply, StaffApplication } from '@/lib/types';
import { job, page, publicApi, signedInApi } from './fixtures';
import { axeViolations, mockApi, renderApp, setViewport } from './utils';

const fit: Fit = {
  score: 82,
  band: 'strong',
  band_label: 'Strong',
  version: 1,
  computed_at: '2026-11-21T10:00:00Z',
  explanation: {
    chips: [
      { kind: 'positive', label: 'Has Python (projects)' },
      { kind: 'gap', label: 'Missing required: SQL' },
    ],
    raise_score: ['Add evidence of SQL'],
    breakdown: [
      { component: 'required', weight: 50, points: 33.3 },
      { component: 'experience', weight: 15, points: 15 },
    ],
    matched_required: 2,
    required_total: 3,
    matched_nice: 0,
    nice_total: 0,
    strong_evidence: 1,
    experience_years: 3,
    min_years: 2,
  },
};

const blindApp: StaffApplication = {
  id: 'a1',
  status: 'applied',
  status_label: 'Applied',
  created_at: '2026-11-20T10:00:00Z',
  updated_at: '2026-11-20T10:00:00Z',
  resume_filename: null,
  blind: true,
  candidate: { id: null, code: 'Candidate #7F3A', full_name: null, email: null, headline: null, location: null },
  job: { id: 'j1', title: 'Backend Engineer', slug: 'backend-engineer-hyderabad' },
  allowed_transitions: ['rejected', 'screening'],
  fit,
  skills: [{ slug: 'python', name: 'Python', section: 'projects' }],
};

const openApp: StaffApplication = {
  ...blindApp,
  id: 'a2',
  status: 'interview',
  status_label: 'Interview',
  blind: false,
  resume_filename: 'ravi.pdf',
  candidate: { id: 'u2', code: 'Candidate #9A11', full_name: 'Ravi Kumar', email: 'ravi@candidates.example', headline: '', location: '' },
  allowed_transitions: ['offer', 'rejected'],
  fit: { ...fit, score: 55, band: 'partial', band_label: 'Partial' },
};

const blindDetail: StaffApplication = {
  ...blindApp,
  resume_text: '[hidden]\nEmail: [hidden]\nSKILLS\nPython, Django\nEDUCATION\nB.Tech, [hidden]',
  evidence: [{ slug: 'python', name: 'Python', section: 'projects', snippet: 'Chat app in Python' }],
  notes: [],
  events: [{ to_status: 'applied', label: 'Applied', at: '2026-11-20T10:00:00Z' }],
  revealed: null,
  reveal_stage: 'interview',
};

type FetchMock = ReturnType<typeof mockApi>;
function callTo(mock: FetchMock, url: string): [string, RequestInit] | undefined {
  return mock.mock.calls.find(([input]) => input === url) as unknown as [string, RequestInit] | undefined;
}

const boardJob = { id: 'j1', title: 'Backend Engineer', status: 'open', blind_screening: true, reveal_stage: 'interview' };

function board(canMove: boolean): Board {
  const columns = ['applied', 'screening', 'interview', 'offer', 'hired', 'rejected', 'withdrawn'].map((status) => ({
    status,
    label: status === 'rejected' ? 'Not selected' : status[0].toUpperCase() + status.slice(1),
    drop_target: !['hired', 'withdrawn'].includes(status),
    note: status === 'hired' ? 'One-click hire arrives in week 3' : '',
    cards: [blindApp, openApp]
      .filter((a) => a.status === status)
      .map((a) => ({ ...a, allowed_transitions: canMove ? a.allowed_transitions : [] })),
  }));
  return {
    job: boardJob,
    can_move: canMove,
    can_note: true,
    transitions: { applied: ['rejected', 'screening'] },
    rejection_reasons: [{ value: 'skills_gap', label: 'Required skills not shown' }],
    columns,
  };
}

const staffApi = {
  ...signedInApi,
  '/api/jobs/j1/applications': { ...page([blindApp, openApp]), job: boardJob },
  '/api/applications/a1': blindDetail,
  '/api/applications/a1/status': { ...blindApp, status: 'screening' },
};

describe('ranked list with explanations', () => {
  beforeEach(() => setViewport(1280));

  it('ranks candidates, hides identity while blind and explains the score', async () => {
    mockApi(staffApi);
    renderApp('/recruiter/jobs/j1/applications', 'recruiter');
    expect(await screen.findByText('Candidate #7F3A')).toBeInTheDocument();
    expect(screen.getByText('Ravi Kumar')).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(screen.getAllByText('Has Python (projects)').length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole('button', { name: /Explain score for Candidate #7F3A/ }));
    const drawer = await screen.findByRole('dialog', { name: 'Application details' });
    expect(await within(drawer).findByText('Add evidence of SQL')).toBeInTheDocument();
    expect(within(drawer).getByText(/Blind screening: name, contact details/)).toBeInTheDocument();
    expect(within(drawer).getByText(/\[hidden\]/, { selector: 'pre' })).toBeInTheDocument();
    expect(within(drawer).queryByText(/Download original/)).not.toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });
});

describe('pipeline board', () => {
  beforeEach(() => setViewport(1280));

  it('moves a card with the keyboard-friendly Move to menu', async () => {
    const fetchMock = mockApi({ ...staffApi, '/api/jobs/j1/board': board(true) });
    renderApp('/recruiter/jobs/j1/board', 'recruiter');
    expect(await screen.findByRole('heading', { level: 2, name: /Applied/ })).toBeInTheDocument();
    expect(screen.getByText('One-click hire arrives in week 3')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Drag Candidate #7F3A' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Move Candidate #7F3A to'), 'screening');
    await userEvent.click(screen.getByRole('button', { name: 'Move Candidate #7F3A' }));
    await waitFor(() => {
      const init = callTo(fetchMock, '/api/applications/a1/status')?.[1];
      expect(init?.method).toBe('POST');
      expect(JSON.parse(String(init?.body)).status).toBe('screening');
    });
    expect(await screen.findByText('Candidate #7F3A moved to Screening.')).toBeInTheDocument();
  });

  it('asks for a reason before rejecting', async () => {
    const fetchMock = mockApi({ ...staffApi, '/api/jobs/j1/board': board(true) });
    renderApp('/recruiter/jobs/j1/board', 'recruiter');
    await userEvent.selectOptions(await screen.findByLabelText('Move Candidate #7F3A to'), 'rejected');
    await userEvent.click(screen.getByRole('button', { name: 'Move Candidate #7F3A' }));
    const dialog = await screen.findByRole('dialog', { name: 'Mark as not selected' });
    await userEvent.click(within(dialog).getByRole('button', { name: 'Confirm' }));
    expect(within(dialog).getByText('Choose a reason.')).toBeInTheDocument();
    expect(callTo(fetchMock, '/api/applications/a1/status')).toBeUndefined();
  });

  it('hiring managers read the board without move controls and it is axe clean at 390 px', async () => {
    setViewport(390);
    mockApi({ ...staffApi, '/api/jobs/j1/board': board(false) });
    renderApp('/recruiter/jobs/j1/board', 'manager');
    expect(await screen.findByText('Candidate #7F3A')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^Drag/ })).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/^Move .* to$/)).not.toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });
});

const searchReply: HiraReply = {
  intent: 'job_search',
  answer: 'I found 1 open job for React in Hyderabad.',
  chips: ['How does matching work?'],
  jobs: [job],
  applications: [],
  action: null,
  link: '/jobs',
  needs_sign_in: false,
};

describe('Ask HIRA', () => {
  it('answers a visitor on the career site with job cards', async () => {
    setViewport(390);
    const fetchMock = mockApi({ ...publicApi, '/api/hira/ask': searchReply });
    renderApp('/');
    await userEvent.click(screen.getByRole('button', { name: /Ask HIRA/ }));
    const panel = screen.getByRole('dialog', { name: 'Ask HIRA' });
    expect(within(panel).getByText('Hiring Intelligence & Recruiting Assistant')).toBeInTheDocument();
    expect(panel.className).toContain('inset-x-0'); // bottom sheet on mobile
    await userEvent.type(within(panel).getByLabelText('Your question'), 'find react jobs in hyd');
    await userEvent.click(within(panel).getByRole('button', { name: 'Send' }));
    expect(await within(panel).findByText('I found 1 open job for React in Hyderabad.')).toBeInTheDocument();
    expect(within(panel).getByRole('link', { name: /Backend Engineer/ })).toHaveAttribute('href', `/jobs/${job.slug}`);
    expect(JSON.parse(String(callTo(fetchMock, '/api/hira/ask')?.[1].body))).toEqual({ message: 'find react jobs in hyd' });
    expect(await axeViolations()).toEqual([]);
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'Ask HIRA' })).not.toBeInTheDocument();
  });

  it('shows a candidate their own status and the recruiter message form', async () => {
    setViewport(1280);
    const status: HiraReply = {
      ...searchReply,
      intent: 'talk_to_recruiter',
      answer: 'Choose the application and write your message.',
      jobs: [],
      link: null,
      applications: [{ id: 'a9', title: 'Data Engineer', status: 'screening', status_label: 'Under review' }],
      action: { type: 'message_recruiter' },
    };
    mockApi({ ...signedInApi, '/api/hira/ask': status, '/api/hira/message': { detail: 'Sent.' } });
    renderApp('/candidate', 'candidate');
    await userEvent.click(await screen.findByRole('button', { name: /Ask HIRA/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Talk to a recruiter' }));
    expect(await screen.findByText('Choose the application and write your message.')).toBeInTheDocument();
    expect(screen.getByRole('option', { name: 'Data Engineer (Under review)' })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText('Message for the recruiter'), 'Is the role hybrid?');
    await userEvent.click(screen.getByRole('button', { name: 'Send to recruiter' }));
    expect(await screen.findByText('Sent.')).toBeInTheDocument();
  });
});

describe('fairness check page', () => {
  it('runs the counterfactual check and states the result plainly', async () => {
    setViewport(1280);
    const result: FairnessResult = {
      applications: 40,
      variants: 120,
      changes: 0,
      passed: true,
      summary: '120 variants tested, 0 score changes.',
      examples: [],
      changed_fields: ['name', 'gender words and pronouns', 'college or university', 'city'],
    };
    mockApi({ ...signedInApi, '/api/fairness/check': result });
    renderApp('/hr/fairness', 'hr');
    await userEvent.click(await screen.findByRole('button', { name: 'Run the check' }));
    expect(await screen.findByRole('heading', { level: 2, name: '120 variants tested, 0 score changes.' })).toBeInTheDocument();
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(await axeViolations()).toEqual([]);
  });
});
