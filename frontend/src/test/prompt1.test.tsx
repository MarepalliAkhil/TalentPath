import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flattenErrors } from '@/lib/applyForm';
import { job, page, publicApi, signedInApi } from './fixtures';
import { axeViolations, mockApi, renderApp, setViewport } from './utils';

type Calls = [string, RequestInit | undefined][];
const callsOf = (mock: ReturnType<typeof mockApi>) => mock.mock.calls as unknown as Calls;

const PROFILE = {
  id: 'u1',
  email: 'employee@demo.example',
  full_name: 'Divya Pillai',
  role: 'employee',
  role_label: 'Employee',
  dashboard: '/employee',
  is_active: true,
  headline: 'Engineering Lead',
  location_text: 'Hyderabad',
  phone: '+91 90000 11111',
  address: '',
  linkedin_url: '',
  github_url: 'https://github.com/divya',
  portfolio_url: '',
  skills: ['Python', 'Django'],
  education: [{ qualification: 'B.Tech', college: 'Lakeview University', branch: 'CSE', year: '2016', score: '8.1' }],
  experience: [],
  date_of_birth: '1992-03-09',
  has_photo: false,
  employee: {
    id: 'e1',
    code: 'LW1009',
    designation: 'Engineering Lead',
    department: 'Engineering',
    location: 'Hyderabad',
    joined_on: '2023-01-15',
    manager: { id: 'e0', name: 'Vikram Natarajan' },
    company: { id: 'c1', name: 'Lumina Works Pvt. Ltd.' },
  },
  locked: { email: true, full_name: true, role: true, date_of_birth: true, employee_code: true, joined_on: true },
  notification_prefs: { applications: true, leave: false },
  notification_categories: [
    { key: 'applications', label: 'Applications and stage changes' },
    { key: 'leave', label: 'Leave and attendance' },
  ],
  resume_versions: [],
};

const fullJob = {
  ...job,
  company: {
    ...job.company!,
    tagline: 'Software that helps people find work they love.',
    about: 'Lumina Works builds hiring software.',
    size: '1,000 to 5,000 employees',
    founded: 2012,
    offices: ['Hyderabad (HITEC City)', 'Bengaluru (Koramangala)'],
    culture: 'Small squads own a problem end to end.',
    benefits: ['Health insurance'],
    hiring_process: [],
    website: 'https://lumina-works.example',
  },
  about_team: 'The search squad is eight engineers.',
  responsibilities: ['Build APIs', 'Review code'],
  required_qualifications: ['Experience: 5 to 8 years.'],
  preferred_qualifications: ['Hands-on time with Redis.'],
  benefits: ['Health insurance for your family'],
  hiring_process: [
    { step: 'Shortlist', detail: 'A recruiter reviews your application.' },
    { step: 'Assignment', detail: 'A short online assignment.' },
    { step: 'Technical interview', detail: 'A video interview.' },
    { step: 'HR round', detail: 'A conversation with HR.' },
    { step: 'Offer', detail: 'A written offer.' },
    { step: 'Onboarding', detail: 'Documents and a buddy.' },
  ],
  screening_question_count: 1,
};

describe('profile for every role', () => {
  beforeEach(() => setViewport(1280));

  it('shows locked identity fields read-only and saves the editable ones', async () => {
    const fetchMock = mockApi({
      ...signedInApi,
      '/api/profile': PROFILE,
      '/api/career/profile': { has_resume: false, filename: '', updated_at: null, source: 'none', skills: [], experience_years: null },
    });
    renderApp('/profile', 'employee');
    expect(await screen.findByRole('heading', { level: 1, name: 'Your profile' })).toBeInTheDocument();
    expect(screen.getByText('Full legal name')).toBeInTheDocument();
    expect(screen.getByText('LW1009')).toBeInTheDocument();
    expect(screen.getByText('Vikram Natarajan')).toBeInTheDocument();
    expect(screen.queryByLabelText(/^Full legal name/)).not.toBeInTheDocument(); // not an input
    expect(screen.queryByLabelText(/^Date of birth/)).not.toBeInTheDocument(); // already locked
    expect(screen.getByRole('checkbox', { name: 'Leave and attendance' })).not.toBeChecked();
    await userEvent.click(screen.getByRole('button', { name: 'Save profile' }));
    const isPatch = ([u, init]: Calls[number]) => String(u) === '/api/profile' && init?.method === 'PATCH';
    await waitFor(() => expect(callsOf(fetchMock).some(isPatch)).toBe(true));
    const body = JSON.parse(String(callsOf(fetchMock).find(isPatch)![1]!.body));
    expect(body).not.toHaveProperty('full_name');
    expect(body).not.toHaveProperty('email');
    expect(body.skills).toEqual(['Python', 'Django']);
    expect(await axeViolations()).toEqual([]);
  });

  it('is in the sidebar for the admin too', async () => {
    mockApi({
      ...signedInApi,
      '/api/dashboard/summary': { role: 'admin', users_by_role: { hr: 1 }, inactive_users: 2, emails_by_status: { sent: 4 } },
    });
    renderApp('/admin', 'admin');
    const nav = await screen.findByRole('navigation', { name: 'Main' });
    expect(within(nav).getByRole('link', { name: 'Profile' })).toHaveAttribute('href', '/profile');
    expect(await screen.findByRole('heading', { level: 1, name: 'Organisation overview' })).toBeInTheDocument();
    expect(screen.getByText(/2 deactivated accounts/)).toBeInTheDocument();
  });
});

describe('admin people page', () => {
  beforeEach(() => setViewport(1280));

  it('needs a reason for locked fields and never offers delete', async () => {
    const person = { ...PROFILE, created_at: '2026-01-01T00:00:00Z', employee: PROFILE.employee };
    const fetchMock = mockApi({
      ...signedInApi,
      '/api/users': page([person]),
      [`/api/users/${person.id}`]: person,
      '/api/companies': [],
    });
    renderApp('/admin/staff', 'admin');
    await userEvent.click(await screen.findByRole('button', { name: /Edit Divya Pillai/ }));
    expect(await screen.findByRole('heading', { name: 'Edit Divya Pillai' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Reason/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /delete/i })).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText(/^New employee ID/), 'LW2001');
    await userEvent.type(screen.getByLabelText(/^Reason/), 'Corrected after the audit');
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }));
    const isPatch = ([, init]: Calls[number]) => init?.method === 'PATCH';
    await waitFor(() => expect(callsOf(fetchMock).some(isPatch)).toBe(true));
    expect(JSON.parse(String(callsOf(fetchMock).find(isPatch)![1]!.body))).toEqual({
      employee_code: 'LW2001',
      reason: 'Corrected after the audit',
    });
  });
});

describe('job pages that look real', () => {
  beforeEach(() => setViewport(1280));

  it('show the company, the team, qualifications, CTC and the hiring steps', async () => {
    mockApi({ ...publicApi, '/api/public/jobs/backend-engineer-hyderabad': fullJob });
    renderApp('/jobs/backend-engineer-hyderabad');
    expect(await screen.findByRole('heading', { level: 1, name: 'Backend Engineer' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'About Lumina Works Pvt. Ltd.' })).toBeInTheDocument();
    for (const heading of [
      'About the team',
      'Responsibilities',
      'Required qualifications',
      'Preferred qualifications',
      'Benefits',
      'Hiring process',
      'Location and work mode',
    ]) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }
    expect(screen.getAllByText('₹20–30 LPA').length).toBeGreaterThan(0);
    expect(screen.getByText('Technical interview')).toBeInTheDocument();
    expect(screen.getByText('Companies and jobs on this site are fictional, for demonstration.')).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });

  it('terms and privacy pages explain the data plainly', async () => {
    mockApi(publicApi);
    renderApp('/privacy');
    expect(await screen.findByRole('heading', { level: 1, name: 'Privacy Policy' })).toBeInTheDocument();
    for (const heading of ['What we store', 'Why', 'How it is protected', 'How long we keep it', 'How to delete it']) {
      expect(screen.getByRole('heading', { name: heading })).toBeInTheDocument();
    }
    expect(screen.getByText(/encrypted in the database/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
  });
});

describe('server errors on the application form', () => {
  it('flatten to section.field keys', () => {
    expect(
      flattenErrors({
        compensation: { current_ctc_lpa: ['Too low.'] },
        answers: { q2: 'Enter a number.' },
        experience: { roles: [{ end: ['Bad.'] }] },
      }),
    ).toEqual({ 'compensation.current_ctc_lpa': 'Too low.', 'answers.q2': 'Enter a number.', 'experience.roles.0.end': 'Bad.' });
  });
});

vi.mock('@/lib/brand', async (orig) => orig());
