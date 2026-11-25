import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import facts from 'virtual:repo-facts';
import { describe, expect, it, vi } from 'vitest';
import { boldScore } from '../../build/repoFacts';
import type { AnalyticsReport, InternalJobs, JobMap, MapJob, NextRole } from '@/lib/growth';
import { signedInApi } from './fixtures';
import { axeViolations, renderApp, setViewport } from './utils';

type Value = unknown | ((body: unknown) => unknown);

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
const calls = (mock: FetchMock, method: string, path: string) =>
  mock.mock.calls.filter(
    ([input, init]) => String(input).split('?')[0] === path && ((init as RequestInit | undefined)?.method ?? 'GET') === method,
  );

const demoOff = { demo_mode: false, accounts: [], upload_limit_bytes: null };
const demoOn = {
  demo_mode: true,
  accounts: [
    { role: 'candidate', label: 'Candidate' },
    { role: 'recruiter', label: 'Recruiter' },
    { role: 'manager', label: 'Manager' },
    { role: 'employee', label: 'Employee' },
    { role: 'hr', label: 'HR' },
    { role: 'admin', label: 'Admin' },
  ],
  upload_limit_bytes: 1048576,
};
const api = { ...signedInApi, '/api/auth/csrf': {}, '/api/demo/config': demoOff };
const PROFILE = {
  id: 'u',
  email: 'candidate@demo.example',
  full_name: 'Asha Verma',
  role: 'candidate',
  role_label: 'Candidate',
  dashboard: '/candidate',
  is_active: true,
  headline: '',
  location_text: '',
  phone: '',
  address: '',
  linkedin_url: '',
  github_url: '',
  portfolio_url: '',
  skills: [],
  education: [],
  experience: [],
  date_of_birth: null,
  has_photo: false,
  employee: null,
  locked: { email: true, full_name: true, role: true, date_of_birth: false, employee_code: false, joined_on: false },
  notification_prefs: { applications: true },
  notification_categories: [{ key: 'applications', label: 'Applications and stage changes' }],
  resume_versions: [],
};

const mapJob: MapJob = {
  id: 'j1',
  slug: 'platform-engineer-hyderabad',
  title: 'Platform Engineer',
  department: 'Engineering',
  location: 'Hyderabad',
  level: 'Senior',
  audience: 'both',
  score: 64,
  band: 'good',
  band_label: 'Good',
};

const jobMap: JobMap = {
  job: mapJob,
  source: 'profile',
  have: [{ slug: 'python', name: 'Python', effort: 'medium', section: 'experience', evidence: 'Built Django services in Python.' }],
  missing_required: [{ slug: 'kubernetes', name: 'Kubernetes', effort: 'large' }],
  missing_nice: [{ slug: 'stakeholder-management', name: 'Stakeholder Management', effort: null }],
  path: [
    {
      slug: 'linux',
      name: 'Linux',
      kind: 'prerequisite',
      effort: 'medium',
      effort_label: 'Medium',
      prerequisites: [],
      unlocks: ['Docker', 'Kubernetes'],
      link: null,
    },
    {
      slug: 'docker',
      name: 'Docker',
      kind: 'prerequisite',
      effort: 'medium',
      effort_label: 'Medium',
      prerequisites: ['Linux'],
      unlocks: ['Kubernetes'],
      link: { title: 'Docker documentation', url: 'https://docs.docker.com/' },
    },
    {
      slug: 'kubernetes',
      name: 'Kubernetes',
      kind: 'required',
      effort: 'large',
      effort_label: 'Large',
      prerequisites: ['Docker', 'Linux'],
      unlocks: [],
      link: { title: 'Kubernetes documentation', url: 'https://kubernetes.io/docs/home/' },
    },
    {
      slug: 'stakeholder-management',
      name: 'Stakeholder Management',
      kind: 'nice',
      effort: null,
      effort_label: 'Not rated',
      prerequisites: [],
      unlocks: [],
      link: null,
    },
  ],
  applied: false,
  can_apply_internally: false,
};

const profile = {
  has_resume: true,
  filename: 'asha.pdf',
  updated_at: '2026-11-22T10:00:00Z',
  source: 'profile',
  skills: ['Django', 'Python'],
  experience_years: 4,
};

describe('career map', () => {
  it('lists the jobs you are closest to with the same band labels recruiters see', async () => {
    mockRoutes({ ...api, '/api/career/profile': profile, '/api/career/map': { source: 'profile', jobs: [mapJob] } });
    renderApp('/career', 'candidate');
    expect(await screen.findByRole('heading', { level: 1, name: 'Your career map' })).toBeInTheDocument();
    expect(await screen.findByText('Good · 64')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the skill map for Platform Engineer' })).toHaveAttribute('href', '/career/jobs/j1');
    expect(screen.getByText(/Using/)).toHaveTextContent('asha.pdf');
    expect(await axeViolations()).toEqual([]);
  });

  it('shows have, missing and an ordered path where only curated links appear', async () => {
    mockRoutes({ ...api, '/api/career/map/j1': jobMap });
    renderApp('/career/jobs/j1', 'candidate');
    expect(await screen.findByRole('heading', { level: 1, name: 'Skill map: Platform Engineer' })).toBeInTheDocument();
    expect(screen.getByText('“Built Django services in Python.”')).toBeInTheDocument();
    const path = document.querySelector('main ol') as HTMLOListElement;
    const names = within(path)
      .getAllByRole('listitem')
      .map((li) => li.querySelector('p')?.firstChild?.textContent);
    expect(names).toEqual(['Linux', 'Docker', 'Kubernetes', 'Stakeholder Management']); // prerequisites first
    const links = screen.getAllByRole('link').filter((a) => a.getAttribute('href')?.startsWith('https://'));
    expect(links.map((a) => a.getAttribute('href'))).toEqual(['https://docs.docker.com/', 'https://kubernetes.io/docs/home/']);
    expect(screen.getAllByText('No curated link yet.')).toHaveLength(2);
    expect(screen.getByRole('link', { name: 'Apply for this job' })).toHaveAttribute('href', '/jobs/platform-engineer-hyderabad/apply');
    expect(await axeViolations()).toEqual([]);
  });

  it('employees also see their next role', async () => {
    const next: NextRole = {
      current_level: 'Lead',
      department: 'Engineering',
      source: 'profile',
      levels: [
        {
          level: 'Manager',
          rank: 60,
          titles: ['Engineering Manager, Platform Services'],
          skills_needed: [{ slug: 'kubernetes', name: 'Kubernetes', jobs: 1, effort: 'large' }],
          have: [],
          missing: [{ slug: 'kubernetes', name: 'Kubernetes', effort: 'large' }],
          path: [jobMap.path[2]],
        },
      ],
    };
    mockRoutes({
      ...api,
      '/api/career/profile': profile,
      '/api/career/map': { source: 'profile', jobs: [mapJob] },
      '/api/career/next-role': next,
    });
    renderApp('/career', 'employee');
    expect(await screen.findByRole('heading', { name: 'Your next role' })).toBeInTheDocument();
    expect(screen.getByText('Manager: Engineering Manager, Platform Services')).toBeInTheDocument();
    expect(screen.getByText(/still to learn: Kubernetes/)).toBeInTheDocument();
  });

  it('the profile resume can be uploaded and deleted', async () => {
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/career/profile': profile,
      'DELETE /api/career/profile': {},
      '/api/profile': PROFILE,
    });
    renderApp('/profile', 'candidate');
    await userEvent.click(await screen.findByRole('button', { name: 'Delete my resume' }));
    await waitFor(() => expect(calls(fetchMock, 'DELETE', '/api/career/profile')).toHaveLength(1));
  });
});

describe('internal jobs', () => {
  const internal: InternalJobs = {
    jobs: [{ ...mapJob, audience: 'internal', applied: false, own_department: true }],
    applications: [],
    rule: {
      stage: 'interview',
      text: 'Your reporting manager is told only if your application reaches the Interview stage. Nobody is told when you apply, and your application is screened like any other.',
      manager: 'Vikram Natarajan',
    },
    has_resume: true,
  };

  it('shows the manager rule before applying and applies in one click', async () => {
    const fetchMock = mockRoutes({
      ...api,
      'GET /api/internal/jobs': internal,
      'POST /api/internal/jobs/j1/apply': { id: 'a1', job: 'Platform Engineer', status: 'applied' },
    });
    renderApp('/internal-jobs', 'employee');
    const rule = await screen.findByRole('heading', { name: 'Before you apply' });
    expect(rule.parentElement).toHaveTextContent('reaches the Interview stage');
    expect(screen.getByText(/Your reporting manager is Vikram Natarajan/)).toBeInTheDocument();
    expect(await axeViolations()).toEqual([]);
    await userEvent.click(screen.getByRole('button', { name: 'Apply for Platform Engineer' }));
    const dialog = screen.getByRole('dialog', { name: 'Apply for Platform Engineer?' });
    expect(dialog).toHaveTextContent('Nobody is told when you apply');
    await userEvent.click(within(dialog).getByRole('button', { name: 'Send application' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/internal/jobs/j1/apply')).toHaveLength(1));
    expect(await screen.findByText('Application sent for Platform Engineer.')).toBeInTheDocument();
  });

  it('is not open to candidates', async () => {
    mockRoutes({ ...api });
    renderApp('/internal-jobs', 'candidate');
    expect(await screen.findByRole('heading', { level: 1 })).not.toHaveTextContent('Internal jobs');
  });
});

describe('analytics', () => {
  const report: AnalyticsReport = {
    report: 'hiring',
    from: '2026-05-26',
    to: '2026-11-22',
    department: '',
    scope: 'own',
    departments: [{ id: 'd1', name: 'Engineering' }],
    sections: [
      {
        key: 'funnel',
        title: 'Funnel conversion',
        summary: '5 applications: 60% reached Interview and 40% were hired.',
        chart: { type: 'bar', x: 'stage', series: [{ key: 'reached', label: 'Applications' }] },
        columns: [
          { key: 'stage', label: 'Stage' },
          { key: 'reached', label: 'Applications reaching it' },
          { key: 'conversion', label: '% of previous stage' },
        ],
        rows: [
          { stage: 'Applied', reached: 5, conversion: null },
          { stage: 'Screening', reached: 4, conversion: 80 },
        ],
        note: '',
      },
    ],
  };

  it('every chart has a summary, a table view and a CSV export', async () => {
    mockRoutes({ ...api, '/api/analytics/hiring': report });
    renderApp('/analytics', 'recruiter');
    expect(await screen.findByTestId('summary-funnel')).toHaveTextContent('60% reached Interview');
    await userEvent.click(screen.getByRole('button', { name: 'Table' }));
    const table = screen.getByRole('table', { name: 'Funnel conversion' });
    expect(within(table).getByRole('rowheader', { name: 'Screening' })).toBeInTheDocument();
    expect(within(table).getByText('–')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'CSV of Funnel conversion' })).toHaveAttribute('href', '/api/analytics/hiring/funnel.csv');
    expect(screen.queryByRole('button', { name: 'People' })).not.toBeInTheDocument(); // HR only
    expect(await axeViolations()).toEqual([]);
  });

  it('hr_admin can switch to people analytics and filter by department', async () => {
    const fetchMock = mockRoutes({
      ...api,
      '/api/analytics/hiring': { ...report, scope: 'all' },
      '/api/analytics/people': {
        ...report,
        report: 'people',
        scope: 'all',
        sections: [{ ...report.sections[0], key: 'onboarding', title: 'Onboarding completion', chart: null }],
      },
    });
    renderApp('/analytics', 'hr');
    await userEvent.click(await screen.findByRole('button', { name: 'People' }));
    expect(await screen.findByRole('heading', { name: 'Onboarding completion' })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText('Department'), 'd1');
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes('/api/analytics/people?department=d1'))).toBe(true));
  });

  it('employees cannot open analytics', async () => {
    mockRoutes({ ...api });
    renderApp('/analytics', 'employee');
    await waitFor(() => expect(screen.queryByRole('heading', { level: 1, name: 'Analytics' })).not.toBeInTheDocument());
  });
});

describe('for recruiters', () => {
  it('has one h1, no logos, plain company names and numbers from the repository', async () => {
    mockRoutes({ ...api });
    renderApp('/for-recruiters');
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1);
    expect(document.querySelectorAll('main img')).toHaveLength(0);
    for (const name of ['Phenom', 'TurboHire', 'Darwinbox', 'Keka']) {
      expect(screen.getByRole('heading', { level: 2, name })).toBeInTheDocument();
    }
    expect(screen.getByText(/not affiliated with, endorsed by or connected to/)).toBeInTheDocument();
    expect(screen.getByTestId('fact-Backend test functions')).toHaveTextContent(String(facts.tests.backend));
    expect(screen.getByTestId('fact-Permission actions')).toHaveTextContent(String(facts.policy.actions));
    const matching = facts.evaluations.matching.holdout;
    expect(matching).not.toBeNull();
    expect(screen.getByRole('rowheader', { name: 'Matching (fit band)' }).parentElement).toHaveTextContent(
      `${matching!.correct} / ${matching!.total}`,
    );
    expect(screen.getByRole('link', { name: /GitHub/ })).toHaveAttribute('href', 'https://github.com/MarepalliAkhil');
    expect(document.body.textContent).not.toMatch(/\+91|phone/i);
    expect(await axeViolations()).toEqual([]);
  });

  it('is linked from the career site header and footer and fits 390 px', async () => {
    setViewport(390);
    mockRoutes({ ...api });
    renderApp('/for-recruiters');
    expect(screen.getAllByRole('link', { name: 'For recruiters' })).toHaveLength(2);
    expect(await axeViolations()).toEqual([]);
  });

  it('the repo facts parser reads bold figures only', () => {
    const doc =
      '| Split | x |\n| --- | --- |\n| Tune (44), first run | 41 / 44 |\n| Tune (44), after | **44 / 44 (100%)** |\n| Holdout (44) | **35 / 44** |';
    expect(boldScore(doc, /^Tune/)).toEqual({ correct: 44, total: 44 });
    expect(boldScore(doc, /^Holdout/)).toEqual({ correct: 35, total: 44 });
    expect(boldScore(null, /^Tune/)).toBeNull();
  });
});

describe('demo mode', () => {
  it('never shows a banner or Try-as buttons on the login page', async () => {
    mockRoutes({ ...api, '/api/demo/config': demoOn });
    renderApp('/login');
    expect(await screen.findByRole('heading', { level: 1, name: 'Sign in' })).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('button', { name: /Try as/ })).not.toBeInTheDocument());
    expect(screen.queryByText(/resets nightly/)).not.toBeInTheDocument();
    expect(screen.queryByRole('note')).not.toBeInTheDocument();
  });

  it('keeps the Try-as buttons on For recruiters when it is on', async () => {
    const fetchMock = mockRoutes({
      ...api,
      '/api/demo/config': demoOn,
      'POST /api/auth/demo-login': {
        user: {
          id: 'u',
          email: 'hr@demo.example',
          full_name: 'Anita',
          role: 'hr',
          role_label: 'HR',
          dashboard: '/hr',
          is_active: true,
        },
      },
    });
    renderApp('/for-recruiters');
    const labels = (await screen.findAllByRole('button', { name: /^Try as/ })).map((b) => b.textContent);
    expect(labels).toEqual(['Try as candidate', 'Try as recruiter', 'Try as manager', 'Try as employee', 'Try as HR', 'Try as admin']);
    expect(screen.queryByText(/resets nightly/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Try as HR' }));
    await waitFor(() => expect(calls(fetchMock, 'POST', '/api/auth/demo-login')).toHaveLength(1));
  });
});
