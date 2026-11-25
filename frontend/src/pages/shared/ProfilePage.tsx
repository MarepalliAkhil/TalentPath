import { useId, useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { ResumeCard } from '@/components/growth';
import { Icon } from '@/components/Icon';
import { Button, Card, ErrorNote, PageHeader, PageLoader, SuccessNote, TextAreaField, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import { errorText } from '@/lib/pipeline';
import { profileSchema, validate, type Errors } from '@/lib/schemas';
import type { EducationRow, ExperienceRow, ProfileData } from '@/lib/types';

const EMPTY_EDU: EducationRow = { qualification: '', college: '', branch: '', year: '', score: '' };
const EMPTY_EXP: ExperienceRow = { company: '', title: '', start: '', end: '', responsibilities: '' };

function Locked({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div>
      <dt className="flex items-center gap-1 text-sm text-muted">
        <Icon name="lock" className="h-3.5 w-3.5" />
        {label}
      </dt>
      <dd className="font-medium text-ink">{value || '—'}</dd>
      {hint && <dd className="text-xs text-muted">{hint}</dd>}
    </div>
  );
}

/** Identity: locked after registration or creation; only an admin can change it, with an audited reason. */
function IdentityCard({ p, onSaved }: { p: ProfileData; onSaved: (data: ProfileData) => void }) {
  const [dob, setDob] = useState('');
  const save = useMutation({
    mutationFn: () => api<ProfileData>('/profile', { method: 'PATCH', body: { date_of_birth: dob } }),
    onSuccess: onSaved,
  });
  const adminOnly = 'Only an admin can change this.';
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">Your details</h2>
      <dl className="mt-3 grid gap-4 sm:grid-cols-2">
        <Locked label="Full legal name" value={p.full_name} hint={adminOnly} />
        <Locked label="Email" value={p.email} hint={adminOnly} />
        <Locked label="Role" value={p.role_label} />
        {p.locked.date_of_birth && (
          <Locked label="Date of birth" value={p.date_of_birth ? formatDate(p.date_of_birth) : ''} hint={adminOnly} />
        )}
        {p.employee && (
          <>
            <Locked label="Employee ID" value={p.employee.code} />
            <Locked label="Joining date" value={formatDate(p.employee.joined_on)} />
            <Locked label="Reporting manager" value={p.employee.manager?.name ?? 'Not assigned'} />
            <Locked label="Company" value={p.employee.company?.name ?? ''} />
          </>
        )}
      </dl>
      {!p.locked.date_of_birth && (
        <form
          className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <TextField
            label="Date of birth"
            type="date"
            value={dob}
            hint="You can set this once. After that only an admin can correct it."
            onChange={(e) => setDob(e.target.value)}
          />
          <Button type="submit" variant="secondary" disabled={!dob || save.isPending}>
            Save date of birth
          </Button>
        </form>
      )}
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
    </Card>
  );
}

function PhotoCard({ hasPhoto, onChanged }: { hasPhoto: boolean; onChanged: (data?: ProfileData) => void }) {
  const inputId = useId();
  const [version, setVersion] = useState(0);
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.set('photo', file);
      return api<ProfileData>('/profile/photo', { method: 'POST', form });
    },
    onSuccess: (data) => {
      setVersion((v) => v + 1);
      onChanged(data);
    },
  });
  const remove = useMutation({
    mutationFn: () => api('/profile/photo', { method: 'DELETE' }),
    onSuccess: () => onChanged(),
  });
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">Profile photo</h2>
      <div className="mt-3 flex items-center gap-4">
        {hasPhoto ? (
          <img
            src={`/api/profile/photo?v=${version}`}
            alt="Your profile photo"
            width={80}
            height={80}
            className="h-20 w-20 rounded-full object-cover"
          />
        ) : (
          <span className="flex h-20 w-20 items-center justify-center rounded-full bg-primary-soft text-primary-strong" aria-hidden="true">
            <Icon name="user" className="h-8 w-8" />
          </span>
        )}
        <div className="flex flex-col gap-2">
          <label htmlFor={inputId} className="text-sm font-medium text-ink">
            Upload a photo (PNG, JPEG or WebP, up to 2 MB)
          </label>
          <input
            id={inputId}
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) upload.mutate(file);
            }}
            className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:font-semibold file:text-white"
          />
          {hasPhoto && (
            <Button variant="ghost" className="self-start" onClick={() => remove.mutate()} disabled={remove.isPending}>
              Remove photo
            </Button>
          )}
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">Your photo is never used for screening and is not shown on applications.</p>
      {(upload.isError || remove.isError) && <ErrorNote>{errorText(upload.error ?? remove.error)}</ErrorNote>}
    </Card>
  );
}

function RowsEditor<T extends object>({
  legend,
  rows,
  empty,
  fields,
  onChange,
}: {
  legend: string;
  rows: T[];
  empty: T;
  fields: { key: keyof T & string; label: string; wide?: boolean; multiline?: boolean; placeholder?: string }[];
  onChange: (rows: T[]) => void;
}) {
  const set = (index: number, key: keyof T, value: string) =>
    onChange(rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)));
  return (
    <fieldset className="flex flex-col gap-3 md:col-span-2">
      <legend className="font-display text-base font-semibold text-ink">{legend}</legend>
      {rows.length === 0 && <p className="text-sm text-muted">Nothing added yet.</p>}
      {rows.map((row, index) => (
        <div key={index} className="grid gap-3 rounded-xl border border-ink/10 bg-white/60 p-3 sm:grid-cols-2">
          {fields.map((f) =>
            f.multiline ? (
              <div key={f.key} className="sm:col-span-2">
                <TextAreaField
                  label={`${f.label} (${legend.toLowerCase()} ${index + 1})`}
                  rows={3}
                  value={String(row[f.key] ?? '')}
                  onChange={(e) => set(index, f.key, e.target.value)}
                />
              </div>
            ) : (
              <div key={f.key} className={f.wide ? 'sm:col-span-2' : ''}>
                <TextField
                  label={`${f.label} (${legend.toLowerCase()} ${index + 1})`}
                  value={String(row[f.key] ?? '')}
                  placeholder={f.placeholder}
                  onChange={(e) => set(index, f.key, e.target.value)}
                />
              </div>
            ),
          )}
          <Button variant="ghost" className="self-start sm:col-span-2" onClick={() => onChange(rows.filter((_, i) => i !== index))}>
            Remove {legend.toLowerCase()} {index + 1}
          </Button>
        </div>
      ))}
      <Button variant="secondary" className="self-start" onClick={() => onChange([...rows, { ...empty }])}>
        Add {legend.toLowerCase()}
      </Button>
    </fieldset>
  );
}

function DetailsForm({ p, onSaved }: { p: ProfileData; onSaved: (data: ProfileData) => void }) {
  const [values, setValues] = useState({
    headline: p.headline,
    location_text: p.location_text,
    phone: p.phone,
    address: p.address,
    linkedin_url: p.linkedin_url,
    github_url: p.github_url,
    portfolio_url: p.portfolio_url,
  });
  const [skills, setSkills] = useState(p.skills.join(', '));
  const [education, setEducation] = useState<EducationRow[]>(p.education.map((r) => ({ ...EMPTY_EDU, ...r })));
  const [experience, setExperience] = useState<ExperienceRow[]>(p.experience.map((r) => ({ ...EMPTY_EXP, ...r })));
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [saved, setSaved] = useState(false);
  const field = (key: keyof typeof values) => ({
    value: values[key],
    error: errors[key],
    onChange: (e: { target: { value: string } }) => setValues({ ...values, [key]: e.target.value }),
  });

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setSaved(false);
    setFormError('');
    const { data, errors: found } = validate(profileSchema, values);
    setErrors(found);
    if (!data) return;
    try {
      const updated = await api<ProfileData>('/profile', {
        method: 'PATCH',
        body: {
          ...values,
          skills: skills
            .split(',')
            .map((s) => s.trim())
            .filter(Boolean),
          education: education.filter((r) => r.qualification.trim()),
          experience: experience.filter((r) => r.title.trim()),
        },
      });
      onSaved(updated);
      setSaved(true);
    } catch (e) {
      if (e instanceof ApiError) {
        setErrors(e.fieldErrors);
        setFormError(e.message);
      } else {
        setFormError('Could not save. Please try again.');
      }
    }
  };

  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">Contact, links and background</h2>
      <p className="mt-1 text-sm text-muted">Phone, address, education and experience are encrypted before they are stored.</p>
      <form onSubmit={onSubmit} noValidate className="mt-4 grid gap-4 md:grid-cols-2">
        {formError && (
          <div className="md:col-span-2">
            <ErrorNote>{formError}</ErrorNote>
          </div>
        )}
        <TextField label="Headline" {...field('headline')} />
        <TextField label="Current city" autoComplete="address-level2" {...field('location_text')} />
        <TextField label="Phone" type="tel" autoComplete="tel" {...field('phone')} />
        <TextField label="LinkedIn" placeholder="https://linkedin.com/in/you" {...field('linkedin_url')} />
        <TextField label="GitHub" placeholder="https://github.com/you" {...field('github_url')} />
        <TextField label="Portfolio" placeholder="https://your-site.example" {...field('portfolio_url')} />
        <div className="md:col-span-2">
          <TextAreaField label="Address" autoComplete="street-address" rows={2} {...field('address')} />
        </div>
        <div className="md:col-span-2">
          <TextField
            label="Skills"
            hint="Separate skills with commas."
            value={skills}
            error={errors.skills}
            onChange={(e) => setSkills(e.target.value)}
          />
        </div>
        <RowsEditor
          legend="Education"
          rows={education}
          empty={EMPTY_EDU}
          onChange={setEducation}
          fields={[
            { key: 'qualification', label: 'Qualification', wide: true },
            { key: 'college', label: 'College' },
            { key: 'branch', label: 'Branch' },
            { key: 'year', label: 'Year' },
            { key: 'score', label: 'CGPA or percentage' },
          ]}
        />
        <RowsEditor
          legend="Experience"
          rows={experience}
          empty={EMPTY_EXP}
          onChange={setExperience}
          fields={[
            { key: 'title', label: 'Title' },
            { key: 'company', label: 'Company' },
            { key: 'start', label: 'Start', placeholder: '2024-07' },
            { key: 'end', label: 'End', placeholder: 'present' },
            { key: 'responsibilities', label: 'Responsibilities', multiline: true },
          ]}
        />
        <div className="flex flex-col gap-3 md:col-span-2">
          <Button type="submit" className="self-start">
            Save profile
          </Button>
          {saved && <SuccessNote>Profile saved.</SuccessNote>}
        </div>
      </form>
    </Card>
  );
}

function PasswordCard() {
  const client = useQueryClient();
  const [values, setValues] = useState({ current_password: '', new_password: '' });
  const change = useMutation({
    mutationFn: () => api('/profile/password', { method: 'POST', body: values }),
    onSuccess: () => {
      setValues({ current_password: '', new_password: '' });
      void client.invalidateQueries({ queryKey: ['me'] });
    },
  });
  const fieldErrors = change.error instanceof ApiError ? change.error.fieldErrors : {};
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">Change password</h2>
      <form
        className="mt-3 grid gap-4 md:grid-cols-2"
        onSubmit={(e) => {
          e.preventDefault();
          change.mutate();
        }}
      >
        <TextField
          label="Current password"
          type="password"
          autoComplete="current-password"
          value={values.current_password}
          error={fieldErrors.current_password}
          onChange={(e) => setValues({ ...values, current_password: e.target.value })}
        />
        <TextField
          label="New password"
          type="password"
          autoComplete="new-password"
          hint="At least 10 characters. Other devices are signed out."
          value={values.new_password}
          error={fieldErrors.new_password}
          onChange={(e) => setValues({ ...values, new_password: e.target.value })}
        />
        <div className="flex flex-col gap-2 md:col-span-2">
          <Button type="submit" className="self-start" disabled={change.isPending || !values.current_password || !values.new_password}>
            Change password
          </Button>
          {change.isSuccess && <SuccessNote>Password changed. Other devices were signed out.</SuccessNote>}
          {change.isError && !Object.keys(fieldErrors).length && <ErrorNote>{errorText(change.error)}</ErrorNote>}
        </div>
      </form>
    </Card>
  );
}

function NotificationsCard({ p, onSaved }: { p: ProfileData; onSaved: (data: ProfileData) => void }) {
  const save = useMutation({
    mutationFn: (prefs: Record<string, boolean>) => api<ProfileData>('/profile/notifications', { method: 'PUT', body: { prefs } }),
    onSuccess: onSaved,
  });
  return (
    <Card>
      <h2 className="font-display text-lg font-semibold text-ink">Email notifications</h2>
      <p className="mt-1 text-sm text-muted">
        Everything still appears under the bell. Account emails (password and invitations) always go.
      </p>
      <fieldset className="mt-3 flex flex-col gap-2">
        <legend className="sr-only">Email categories</legend>
        {p.notification_categories.map((c) => (
          <label key={c.key} className="flex items-center gap-2 text-sm text-ink">
            <input
              type="checkbox"
              className="h-4 w-4"
              checked={p.notification_prefs[c.key] !== false}
              disabled={save.isPending}
              onChange={(e) => save.mutate({ [c.key]: e.target.checked })}
            />
            {c.label}
          </label>
        ))}
      </fieldset>
      {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
    </Card>
  );
}

export function ProfilePage() {
  useDocumentTitle('Your profile');
  const { user } = useAuth();
  const client = useQueryClient();
  const [params] = useSearchParams();
  const profile = useQuery({ queryKey: ['profile'], queryFn: () => api<ProfileData>('/profile') });
  const store = (data?: ProfileData) => {
    if (data) client.setQueryData(['profile'], data);
    else void client.invalidateQueries({ queryKey: ['profile'] });
  };

  if (profile.isPending) return <PageLoader />;
  const p = profile.data;
  if (!p) return <ErrorNote>Could not load your profile.</ErrorNote>;
  const hasResume = user?.role === 'candidate' || user?.role === 'employee';

  return (
    <>
      <PageHeader title="Your profile" intro="Keep your details current. Identity fields are locked; an admin can correct them." />
      {params.get('welcome') === '1' && (
        <div className="mb-4">
          <SuccessNote>
            Welcome! We read your resume and filled in your profile. Check your phone, links, skills, education and experience, then save.
          </SuccessNote>
        </div>
      )}
      <div className="flex flex-col gap-6">
        <IdentityCard p={p} onSaved={store} />
        <PhotoCard hasPhoto={p.has_photo} onChanged={store} />
        <DetailsForm key={p.id} p={p} onSaved={store} />
        {hasResume && (
          <div className="flex flex-col gap-3">
            <ResumeCard />
            {p.resume_versions.length > 1 && (
              <Card>
                <h2 className="font-display text-lg font-semibold text-ink">Resume history</h2>
                <ul className="mt-2 flex flex-col gap-1 text-sm">
                  {p.resume_versions.map((v) => (
                    <li key={v.id}>
                      {v.filename} · {formatDate(v.uploaded_at)} {v.current ? '(current)' : '(earlier version)'}
                    </li>
                  ))}
                </ul>
                <p className="mt-2 text-xs text-muted">Deleting your resume removes every version.</p>
              </Card>
            )}
          </div>
        )}
        <PasswordCard />
        <NotificationsCard p={p} onSaved={store} />
      </div>
    </>
  );
}
