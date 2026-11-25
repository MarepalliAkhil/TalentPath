import { useRef, useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, ErrorNote, TextField } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { registerSchema, validate, type Errors } from '@/lib/schemas';
import { AuthCard } from './AuthCard';

/** Candidate registration (D-81): a resume is required; we read it to fill in the profile for review. */
export function RegisterPage() {
  useDocumentTitle('Create your account');
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [values, setValues] = useState({ full_name: '', email: '', password: '' });
  const [resume, setResume] = useState<File | null>(null);
  const [accepted, setAccepted] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  if (user && !busy) return <Navigate to={user.dashboard} replace />;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const { data, errors: found } = validate(registerSchema, { ...values, resume: resume ?? undefined, accept_terms: accepted });
    setErrors(found);
    if (!data) {
      if (found.resume) fileInput.current?.focus();
      return;
    }
    const form = new FormData();
    form.append('full_name', data.full_name);
    form.append('email', data.email);
    form.append('password', data.password);
    form.append('accept_terms', 'true');
    form.append('resume', data.resume);
    setBusy(true);
    try {
      await register(form);
      navigate('/profile?welcome=1', { replace: true });
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError('Could not create your account. Please try again.');
      }
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Create your candidate account"
      intro="Upload your resume and we fill in your profile for you to check."
      footer={
        <>
          Already registered?{' '}
          <Link to="/login" className="font-semibold text-primary-strong underline-offset-2 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError && <ErrorNote>{formError}</ErrorNote>}
        <TextField
          label="Full legal name"
          name="full_name"
          autoComplete="name"
          hint="As on your ID. Only an admin can change it later."
          value={values.full_name}
          error={errors.full_name}
          onChange={(e) => setValues({ ...values, full_name: e.target.value })}
          required
        />
        <TextField
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          value={values.email}
          error={errors.email}
          onChange={(e) => setValues({ ...values, email: e.target.value })}
          required
        />
        <TextField
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          hint="At least 10 characters. Avoid common passwords."
          value={values.password}
          error={errors.password}
          onChange={(e) => setValues({ ...values, password: e.target.value })}
          required
        />
        <div className="flex flex-col gap-1.5">
          <label htmlFor="register-resume" className="text-sm font-medium text-ink">
            Resume{' '}
            <span className="text-danger" aria-hidden="true">
              *
            </span>
          </label>
          <input
            ref={fileInput}
            id="register-resume"
            name="resume"
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            aria-describedby={`register-resume-hint${errors.resume ? ' register-resume-error' : ''}`}
            aria-invalid={errors.resume ? true : undefined}
            required
            onChange={(e) => setResume(e.target.files?.[0] ?? null)}
            className="block w-full rounded-xl border border-dashed border-ink/25 bg-white/80 p-3 text-sm text-ink file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:font-semibold file:text-white"
          />
          <p id="register-resume-hint" className="text-xs text-muted">
            PDF or DOCX, up to 5 MB. We read it on our server, store it encrypted and pre-fill your phone, links, skills,
            education and experience.
          </p>
          {errors.resume && (
            <p id="register-resume-error" className="text-sm font-medium text-danger">
              {errors.resume}
            </p>
          )}
        </div>
        <div className="flex flex-col gap-1">
          <label className="flex items-start gap-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => setAccepted(e.target.checked)}
              aria-invalid={errors.accept_terms ? true : undefined}
              aria-describedby={errors.accept_terms ? 'register-terms-error' : undefined}
              className="mt-1 h-4 w-4"
            />
            <span>
              I accept the{' '}
              <Link to="/terms" target="_blank" className="font-semibold text-primary-strong underline">
                Terms and Conditions
              </Link>{' '}
              and the{' '}
              <Link to="/privacy" target="_blank" className="font-semibold text-primary-strong underline">
                Privacy Policy
              </Link>
              .
            </span>
          </label>
          {errors.accept_terms && (
            <p id="register-terms-error" className="text-sm font-medium text-danger">
              {errors.accept_terms}
            </p>
          )}
        </div>
        <Button type="submit" disabled={busy}>
          {busy ? 'Reading your resume…' : 'Create account'}
        </Button>
        <p className="text-xs text-muted">Staff accounts are created by your admin.</p>
      </form>
    </AuthCard>
  );
}
