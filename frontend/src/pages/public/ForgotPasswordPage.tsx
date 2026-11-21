import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Button, ErrorNote, SuccessNote, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { forgotSchema, validate, type Errors } from '@/lib/schemas';
import { AuthCard } from './AuthCard';

const DEMO_MODE = import.meta.env.VITE_DEMO_MODE === 'true';

export function ForgotPasswordPage() {
  useDocumentTitle('Reset your password');
  const [email, setEmail] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [sent, setSent] = useState(false);
  const [formError, setFormError] = useState('');

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    const { data, errors: found } = validate(forgotSchema, { email });
    setErrors(found);
    if (!data) return;
    try {
      await api('/auth/password-reset', { method: 'POST', body: data });
      setSent(true);
    } catch (error) {
      setFormError(error instanceof ApiError ? error.message : 'Please try again.');
    }
  };

  return (
    <AuthCard title="Reset your password" intro="We will email you a link that works for one hour.">
      {sent ? (
        <div className="flex flex-col gap-3">
          <SuccessNote>If an account exists for {email}, a reset link is on its way.</SuccessNote>
          {DEMO_MODE && email.endsWith('.example') && (
            <Link to={`/demo-inbox?email=${encodeURIComponent(email)}`} className="font-semibold text-primary-strong underline">
              Open the demo inbox
            </Link>
          )}
        </div>
      ) : (
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {formError && <ErrorNote>{formError}</ErrorNote>}
          <TextField label="Email" type="email" autoComplete="email" value={email} error={errors.email} onChange={(e) => setEmail(e.target.value)} required />
          <Button type="submit">Send reset link</Button>
        </form>
      )}
    </AuthCard>
  );
}
