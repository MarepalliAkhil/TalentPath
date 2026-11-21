import { useEffect, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { profileSchema, validate, type Errors } from '@/lib/schemas';
import type { ProfileData } from '@/lib/types';

export function ProfilePage() {
  useDocumentTitle('Your profile');
  const client = useQueryClient();
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api<ProfileData>('/profile') });
  const [values, setValues] = useState({ full_name: '', headline: '', location_text: '', phone: '', address: '' });
  const [errors, setErrors] = useState<Errors>({});
  const [saved, setSaved] = useState(false);
  const [formError, setFormError] = useState('');

  useEffect(() => {
    const p = profile.data;
    if (p) setValues({ full_name: p.full_name, headline: p.headline, location_text: p.location_text, phone: p.phone, address: p.address });
  }, [profile.data]);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    setFormError('');
    const { data, errors: found } = validate(profileSchema, values);
    setErrors(found);
    if (!data) return;
    try {
      const updated = await api<ProfileData>('/profile', { method: 'PATCH', body: data });
      client.setQueryData(['profile'], updated);
      void client.invalidateQueries({ queryKey: ['me'] });
      setSaved(true);
    } catch (e) {
      if (e instanceof ApiError) {
        setErrors(e.fieldErrors);
        setFormError(e.message);
      }
    }
  };

  if (profile.isPending) return <PageLoader />;
  const p = profile.data;

  return (
    <>
      <PageHeader title="Your profile" intro="Phone number and address are encrypted before they are stored." />
      <Card>
        {p && (
          <dl className="mb-6 grid gap-3 text-sm sm:grid-cols-2">
            <div>
              <dt className="text-muted">Email</dt>
              <dd className="font-medium text-ink">{p.email}</dd>
            </div>
            <div>
              <dt className="text-muted">Role</dt>
              <dd className="font-medium text-ink">{p.role_label}</dd>
            </div>
          </dl>
        )}
        <form onSubmit={onSubmit} noValidate className="grid gap-4 md:grid-cols-2">
          {formError && (
            <div className="md:col-span-2">
              <ErrorNote>{formError}</ErrorNote>
            </div>
          )}
          <TextField label="Full name" autoComplete="name" value={values.full_name} error={errors.full_name} onChange={(e) => setValues({ ...values, full_name: e.target.value })} />
          <TextField label="Headline" value={values.headline} error={errors.headline} onChange={(e) => setValues({ ...values, headline: e.target.value })} />
          <TextField label="City" autoComplete="address-level2" value={values.location_text} error={errors.location_text} onChange={(e) => setValues({ ...values, location_text: e.target.value })} />
          <TextField label="Phone" type="tel" autoComplete="tel" value={values.phone} error={errors.phone} onChange={(e) => setValues({ ...values, phone: e.target.value })} />
          <div className="md:col-span-2">
            <TextAreaField label="Address" autoComplete="street-address" rows={3} value={values.address} error={errors.address} onChange={(e) => setValues({ ...values, address: e.target.value })} />
          </div>
          <div className="flex flex-col gap-3 md:col-span-2">
            <Button type="submit" className="self-start">
              Save profile
            </Button>
            {saved && <SuccessNote>Profile saved.</SuccessNote>}
          </div>
        </form>
      </Card>
    </>
  );
}
