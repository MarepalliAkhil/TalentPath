import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApplyForm } from '@/pages/candidate/ApplyPage';
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
    await userEvent.type(screen.getByLabelText(/^Full name/), 'Asha Verma');
    await userEvent.type(screen.getByLabelText(/^Email/), 'asha@example.test');
    await userEvent.type(screen.getByLabelText(/^Password/), 'short');
    await userEvent.click(screen.getByRole('button', { name: 'Create account' }));
    expect(screen.getByText('Use at least 10 characters.')).toBeInTheDocument();
  });
});

describe('apply form', () => {
  const setup = () => {
    const onDone = vi.fn();
    renderWith(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ApplyForm job={job} onDone={onDone} />
      </MemoryRouter>,
    );
    return onDone;
  };

  it('requires a resume', async () => {
    setup();
    await userEvent.click(screen.getByRole('button', { name: 'Submit application' }));
    expect(screen.getByText('Attach your resume (PDF or DOCX).')).toBeInTheDocument();
  });

  it('rejects other file types', async () => {
    setup();
    const user = userEvent.setup({ applyAccept: false });
    await user.upload(screen.getByLabelText(/^Resume/), new File(['MZ'], 'setup.exe', { type: 'application/octet-stream' }));
    await user.click(screen.getByRole('button', { name: 'Submit application' }));
    expect(screen.getByText('Upload a PDF or DOCX file.')).toBeInTheDocument();
  });

  it('rejects files over 5 MB', async () => {
    setup();
    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'cv.pdf', { type: 'application/pdf' });
    await userEvent.upload(screen.getByLabelText(/^Resume/), big);
    await userEvent.click(screen.getByRole('button', { name: 'Submit application' }));
    expect(screen.getByText('Resumes must be 5 MB or smaller.')).toBeInTheDocument();
  });

  it('submits a valid PDF as multipart form data', async () => {
    const fetchMock = mockApi({ '/api/applications': { id: 'x' } });
    document.cookie = 'csrftoken=test-token';
    const onDone = setup();
    await userEvent.upload(screen.getByLabelText(/^Resume/), new File(['%PDF-1.4'], 'cv.pdf', { type: 'application/pdf' }));
    await userEvent.click(screen.getByRole('button', { name: 'Submit application' }));
    await vi.waitFor(() => expect(onDone).toHaveBeenCalled());
    const [url, init] = fetchMock.mock.calls.at(-1) as unknown as [string, RequestInit];
    expect(url).toBe('/api/applications');
    expect(init.body).toBeInstanceOf(FormData);
    expect((init.headers as Record<string, string>)['X-CSRFToken']).toBe('test-token');
  });
});
