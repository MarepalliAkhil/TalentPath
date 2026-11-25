import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ApplyContext } from '@/lib/applyForm';
import { ApplicationWizard } from '@/pages/candidate/ApplyPage';
import { job, publicApi } from './fixtures';
import { mockApi, renderApp, renderWith, setViewport } from './utils';

describe('form validation', () => {
  beforeEach(() => {
    mockApi(publicApi);
    setViewport(1280);
  });

  it('login shows field errors and does not call the API', async () => {
    const login = vi.fn();
    renderApp('/login', null, { login });
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter your email address.')).toBeInTheDocument();
    expect(screen.getByText('Enter your password.')).toBeInTheDocument();
    expect(screen.getByLabelText(/^Email/)).toHaveAttribute('aria-invalid', 'true');
    expect(login).not.toHaveBeenCalled();
  });

  it('login rejects a malformed email', async () => {
    renderApp('/login', null);
    await userEvent.type(screen.getByLabelText(/^Email/), 'not-an-email');
    await userEvent.type(screen.getByLabelText(/^Password/), 'whatever');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument();
  });

  it('login calls auth with valid input', async () => {
    const login = vi.fn(async () => ({
      id: '1',
      email: 'a@demo.example',
      full_name: 'A B',
      role: 'candidate' as const,
      role_label: 'Candidate',
      dashboard: '/candidate',
      is_active: true,
    }));
    renderApp('/login', null, { login });
    await userEvent.type(screen.getByLabelText(/^Email/), 'a@demo.example');
    await userEvent.type(screen.getByLabelText(/^Password/), 'Secret-pass-1');
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }));
    expect(login).toHaveBeenCalledWith('a@demo.example', 'Secret-pass-1');
  });

  it('registration enforces password length', async () => {
    renderApp('/register', null);
    await userEvent.type(screen.getByLabelText(/^Full legal name/), 'Asha Verma');
    await userEvent.type(screen.getByLabelText(/^Email/), 'asha@example.test');
    await userEvent.type(screen.getByLabelText(/^Password/), 'short');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByText('Use at least 10 characters.')).toBeInTheDocument();
  });

  it('registration requires a resume and the terms', async () => {
    const register = vi.fn();
    renderApp('/register', null, { register });
    await userEvent.type(screen.getByLabelText(/^Full legal name/), 'Asha Verma');
    await userEvent.type(screen.getByLabelText(/^Email/), 'asha@example.test');
    await userEvent.type(screen.getByLabelText(/^Password/), 'Sturdy-Pass-2026');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByText('Attach your resume (PDF or DOCX).')).toBeInTheDocument();
    expect(screen.getByText('Accept the Terms and the Privacy Policy to continue.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Terms and Conditions' })).toHaveAttribute('href', '/terms');
    expect(register).not.toHaveBeenCalled();
  });

  it('registration sends the resume as multipart form data', async () => {
    const register = vi.fn(async () => ({
      id: '1',
      email: 'asha@example.test',
      full_name: 'Asha Verma',
      role: 'candidate' as const,
      role_label: 'Candidate',
      dashboard: '/candidate',
      is_active: true,
    }));
    renderApp('/register', null, { register });
    await userEvent.type(screen.getByLabelText(/^Full legal name/), 'Asha Verma');
    await userEvent.type(screen.getByLabelText(/^Email/), 'asha@example.test');
    await userEvent.type(screen.getByLabelText(/^Password/), 'Sturdy-Pass-2026');
    await userEvent.upload(screen.getByLabelText(/^Resume/), new File(['%PDF-1.4'], 'cv.pdf', { type: 'application/pdf' }));
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    await vi.waitFor(() => expect(register).toHaveBeenCalled());
    const form = (register.mock.calls[0] as unknown as [FormData])[0];
    expect(form.get('accept_terms')).toBe('true');
    expect((form.get('resume') as File).name).toBe('cv.pdf');
  });
});

const FULL_FORM = {
  personal: { phone: '+91 90000 12345', current_city: 'Hyderabad', willing_to_relocate: 'yes' as const, date_of_birth: '1999-04-12' },
  education: {
    highest_qualification: "Bachelor's degree",
    college: 'Lakeview University',
    branch: 'Computer Science',
    graduation_year: '2021',
    score_type: 'cgpa' as const,
    score: '8.4',
    tenth_percentage: '91',
    twelfth_percentage: '88',
  },
  experience: { status: 'fresher' as const, roles: [], total_years: '0' },
  compensation: { current_ctc_lpa: '0', expected_ctc_lpa: '6.5', notice_period: 'immediate', earliest_joining: '2030-01-01' },
  links: { linkedin_url: '', github_url: '', portfolio_url: '' },
  answers: { q1: 'yes' },
  use_profile_resume: false,
  cover_letter: '',
};

function context(step: number, extra: Partial<ApplyContext> = {}): ApplyContext {
  return {
    job: {
      slug: job.slug,
      title: job.title,
      company: null,
      screening_questions: [{ id: 'q1', text: 'Comfortable with shifts?', kind: 'yes_no', required: true }],
    },
    already_applied: false,
    draft: { data: FULL_FORM, step, saved_at: '2026-11-25T10:00:00Z' },
    prefill: {
      personal: { full_name: 'Asha Verma', email: 'asha@demo.example', phone: '', current_city: '', date_of_birth: null },
      education: { college: '', branch: '', graduation_year: '', score: '' },
      experience: { status: 'fresher', roles: [] },
      links: { linkedin_url: '', github_url: '', portfolio_url: '' },
    },
    locked: { date_of_birth: false },
    profile_resume: null,
    notice_periods: [{ value: 'immediate', label: 'Immediate' }],
    qualifications: ["Bachelor's degree"],
    terms_version: '2026-11',
    ...extra,
  };
}

describe('apply form', () => {
  const setup = (ctx: ApplyContext) => {
    const onDone = vi.fn();
    renderWith(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ApplicationWizard job={job} ctx={ctx} onDone={onDone} />
      </MemoryRouter>,
    );
    return onDone;
  };

  it('shows progress and checks each step before moving on', async () => {
    setup(context(0, { draft: null }));
    expect(screen.getByText('Step 1 of 7: Personal')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Next: Education' }));
    expect(screen.getByText('Enter your phone number.')).toBeInTheDocument();
    expect(screen.getByText('Choose yes or no.')).toBeInTheDocument();
    expect(screen.getByText('Step 1 of 7: Personal')).toBeInTheDocument();
  });

  it('requires a resume', async () => {
    setup(context(5));
    await userEvent.click(screen.getByRole('button', { name: 'Next: Review and submit' }));
    expect(screen.getByText('Attach your resume (PDF or DOCX).')).toBeInTheDocument();
  });

  it('rejects other file types', async () => {
    setup(context(5));
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(screen.getByLabelText(/^Upload a resume/), new File(['MZ'], 'setup.exe', { type: 'application/octet-stream' }));
    await user.click(screen.getByRole('button', { name: 'Next: Review and submit' }));
    expect(screen.getByText('Upload a PDF or DOCX file.')).toBeInTheDocument();
  });

  it('rejects files over 5 MB', async () => {
    setup(context(5));
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'cv.pdf', { type: 'application/pdf' });
    await userEvent.upload(screen.getByLabelText(/^Upload a resume/), big);
    await userEvent.click(screen.getByRole('button', { name: 'Next: Review and submit' }));
    expect(screen.getByText('Resumes must be 5 MB or smaller.')).toBeInTheDocument();
  });

  it('requires the declarations and the Terms', async () => {
    setup(
      context(6, {
        profile_resume: { filename: 'mine.pdf' },
        draft: { data: { ...FULL_FORM, use_profile_resume: true }, step: 6, saved_at: '2026-11-25T10:00:00Z' },
      }),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Submit application' }));
    expect(screen.getByText('Confirm that the information is true.')).toBeInTheDocument();
    expect(screen.getByText('Accept the Terms and Conditions and the Privacy Policy.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Privacy Policy' })).toHaveAttribute('href', '/privacy');
  });

  it('submits the whole form as multipart form data', async () => {
    const fetchMock = mockApi({ '/api/applications': { id: 'x' } });
    document.cookie = 'csrftoken=test-token';
    const onDone = setup(
      context(6, {
        profile_resume: { filename: 'mine.pdf' },
        draft: { data: { ...FULL_FORM, use_profile_resume: true }, step: 6, saved_at: '2026-11-25T10:00:00Z' },
      }),
    );
    await userEvent.click(screen.getByRole('checkbox', { name: /information is true/ }));
    await userEvent.click(screen.getByRole('checkbox', { name: /I accept the/ }));
    await userEvent.click(screen.getByRole('button', { name: 'Submit application' }));
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
    expect(url).toBe('/api/applications');
    const body = init.body as FormData;
    const form = JSON.parse(String(body.get('form')));
    expect(form.personal.willing_to_relocate).toBe(true);
    expect(form.compensation.expected_ctc_lpa).toBe('6.5');
    expect(form.declarations).toEqual({ info_true: true, accept_terms: true });
    expect(body.get('resume')).toBeNull();
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('test-token');
  });

  it('saves a draft', async () => {
    const fetchMock = mockApi({ [`/api/applications/drafts/${job.slug}`]: { saved_at: '2026-11-25T11:00:00Z', step: 2 } });
    setup(context(2));
    await userEvent.click(screen.getByRole('button', { name: 'Save as draft' }));
    await vi.waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
    expect(url).toBe(`/api/applications/drafts/${job.slug}`);
    expect(init.method).toBe('PUT');
    expect(JSON.parse(String(init.body)).step).toBe(2);
  });
});
