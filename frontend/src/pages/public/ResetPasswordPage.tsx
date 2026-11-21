import { useState, type FormEvent } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Button, ErrorNote, SuccessNote, TextField, buttonClass } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { resetSchema, validate, type Errors } from '@/lib/schemas';
import { AuthCard } from './AuthCard';

export function ResetPasswordPage() {
  useDocumentTitle('Choose a new password');
  const [params] = useSearchParams();
  const uid = params.get('uid') ?? '';
  const token = params.get('token') ?? '';
  const [values, setValues] = useState({ password: '', confirm: '' });
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [done, setDone] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const { data, errors: found } = validate(resetSchema, values);
    setErrors(found);
    if (!data) return;
    try {
      await api('/auth/password-reset/confirm', { method: 'POST', body: { uid, token, password: data.password } });
      setDone(true);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(error.fieldErrors);
        setFormError(error.message);
      }
    }
  };

  return (
    <AuthCard title="Choose a new password">
      {!uid || !token ? (
        <ErrorNote>This link is incomplete. Request a new reset email.</ErrorNote>
      ) : done ? (
        <div className="flex flex-col gap-4">
          <SuccessNote>Password updated. Other sessions were signed out.</SuccessNote>
          <Link to="/login" className={buttonClass('primary')}>
            Sign in
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {formError && <ErrorNote>{formError}</ErrorNote>}
          <TextField label="New password" type="password" autoComplete="new-password" value={values.password} error={errors.password} onChange={(e) => setValues({ ...values, password: e.target.value })} required />
          <TextField label="Confirm new password" type="password" autoComplete="new-password" value={values.confirm} error={errors.confirm} onChange={(e) => setValues({ ...values, confirm: e.target.value })} required />
          <Button type="submit">Update password</Button>
        </form>
      )}
    </AuthCard>
  );
}
