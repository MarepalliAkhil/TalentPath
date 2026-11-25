import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, ErrorNote, TextField } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { safeNext } from '@/lib/redirect';
import { loginSchema, validate, type Errors } from '@/lib/schemas';
import { AuthCard } from './AuthCard';

export function LoginPage() {
  useDocumentTitle('Sign in');
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const next = safeNext(params.get('next'));
  const [values, setValues] = useState({ email: '', password: '' });
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user && !busy) return <Navigate to={next ?? user.dashboard} replace />;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const { data, errors: found } = validate(loginSchema, values);
    setErrors(found);
    if (!data) return;
    setBusy(true);
    try {
      const signedIn = await login(data.email, data.password);
      navigate(next ?? signedIn.dashboard, { replace: true });
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : 'Could not sign in. Please try again.');
      setBusy(false);
    }
  };

  return (
    <AuthCard
      title="Sign in"
      intro="Candidates, recruiters, managers, employees and HR all sign in here."
      footer={
        <>
          New here? <Link to="/register" className="font-semibold text-primary-strong underline-offset-2 hover:underline">Create a candidate account</Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError && <ErrorNote>{formError}</ErrorNote>}
        <TextField label="Email" type="email" name="email" autoComplete="email" value={values.email} error={errors.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required />
        <TextField label="Password" type="password" name="password" autoComplete="current-password" value={values.password} error={errors.password} onChange={(e) => setValues({ ...values, password: e.target.value })} required />
        <Button type="submit" disabled={busy}>
          {busy ? 'Signing in…' : 'Sign in'}
        </Button>
        <Link to="/forgot-password" className="text-center text-sm font-medium text-primary-strong underline-offset-2 hover:underline">
          Forgot your password?
        </Link>
      </form>
    </AuthCard>
  );
}
