import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Button, ErrorNote, TextField } from '@/components/ui';
import { ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { registerSchema, validate, type Errors } from '@/lib/schemas';
import { AuthCard } from './AuthCard';

export function RegisterPage() {
  useDocumentTitle('Create your account');
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const nextParam = params.get('next');
  const next = nextParam && nextParam.startsWith('/') && !nextParam.startsWith('//') ? nextParam : null;
  const [values, setValues] = useState({ full_name: '', email: '', password: '' });
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user && !busy) return <Navigate to={user.dashboard} replace />;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const { data, errors: found } = validate(registerSchema, values);
    setErrors(found);
    if (!data) return;
    setBusy(true);
    try {
      const created = await register(data.full_name, data.email, data.password);
      navigate(next ?? created.dashboard, { replace: true });
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
      intro="Apply to roles and follow every application in one place."
      footer={
        <>
          Already registered? <Link to="/login" className="font-semibold text-primary-strong underline-offset-2 hover:underline">Sign in</Link>
        </>
      }
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {formError && <ErrorNote>{formError}</ErrorNote>}
        <TextField label="Full name" name="full_name" autoComplete="name" value={values.full_name} error={errors.full_name} onChange={(e) => setValues({ ...values, full_name: e.target.value })} required />
        <TextField label="Email" type="email" name="email" autoComplete="email" value={values.email} error={errors.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required />
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
        <Button type="submit" disabled={busy}>
          {busy ? 'Creating account…' : 'Create account'}
        </Button>
        <p className="text-xs text-muted">Staff accounts are created by your HR admin.</p>
      </form>
    </AuthCard>
  );
}
