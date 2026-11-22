import { useEffect, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { SkillPicker } from '@/components/SkillPicker';
import { Button, Card, ErrorNote, PageHeader, PageLoader, SelectField, TextAreaField, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { jobSchema, validate, type Errors } from '@/lib/schemas';
import type { Department, Level, Location, Skill, StaffJob } from '@/lib/types';
import { useAuth } from '@/auth/AuthContext';

type Values = {
  title: string;
  department: string;
  location: string;
  level: string;
  work_mode: string;
  employment_type: string;
  openings: string;
  hiring_manager: string;
  description: string;
  required_skills: string[];
  nice_to_have_skills: string[];
  blind_screening: boolean;
  reveal_stage: 'interview' | 'offer';
};

const EMPTY: Values = {
  title: '',
  department: '',
  location: '',
  level: '',
  work_mode: 'hybrid',
  employment_type: 'full_time',
  openings: '1',
  hiring_manager: '',
  description: '',
  required_skills: [],
  nice_to_have_skills: [],
  blind_screening: true,
  reveal_stage: 'interview',
};

export function JobFormPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  useDocumentTitle(editing ? 'Edit job' : 'Post a job');
  const navigate = useNavigate();
  const client = useQueryClient();
  const { user } = useAuth();
  const [values, setValues] = useState<Values>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [busy, setBusy] = useState(false);

  const departments = useQuery({ queryKey: ['departments'], queryFn: () => api<Department[]>('/departments') });
  const locations = useQuery({ queryKey: ['locations'], queryFn: () => api<Location[]>('/locations') });
  const levels = useQuery({ queryKey: ['levels'], queryFn: () => api<Level[]>('/job-levels') });
  const skills = useQuery({ queryKey: ['skills'], queryFn: () => api<Skill[]>('/skills'), staleTime: 300_000 });
  const managers = useQuery({
    queryKey: ['hiring-managers'],
    queryFn: () => api<{ id: string; full_name: string }[]>('/hiring-managers'),
  });
  const existing = useQuery({
    queryKey: ['job', id],
    queryFn: () => api<StaffJob>(`/jobs/${id}`),
    enabled: editing,
  });

  useEffect(() => {
    const job = existing.data;
    if (!job) return;
    setValues({
      title: job.title,
      department: job.department.id,
      location: job.location.id,
      level: job.level.id,
      work_mode: job.work_mode,
      employment_type: job.employment_type,
      openings: String(job.openings),
      hiring_manager: job.hiring_manager?.id ?? '',
      description: job.description,
      required_skills: job.required_skills.map((s) => s.id),
      nice_to_have_skills: job.nice_to_have_skills.map((s) => s.id),
      blind_screening: job.blind_screening,
      reveal_stage: job.reveal_stage,
    });
  }, [existing.data]);

  const set = <K extends keyof Values>(key: K, value: Values[K]) => setValues((v) => ({ ...v, [key]: value }));
  const back = user?.role === 'hr_admin' ? '/admin/jobs' : '/recruiter/jobs';

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const { data, errors: found } = validate(jobSchema, values);
    setErrors(found);
    if (!data) {
      setFormError('Please fix the highlighted fields.');
      return;
    }
    setBusy(true);
    const body = { ...data, hiring_manager: data.hiring_manager || null };
    try {
      if (editing) await api(`/jobs/${id}`, { method: 'PATCH', body });
      else await api('/jobs', { method: 'POST', body });
      void client.invalidateQueries({ queryKey: ['jobs'] });
      navigate(back);
    } catch (error) {
      if (error instanceof ApiError) {
        setErrors(error.fieldErrors);
        setFormError(error.message);
      }
      setBusy(false);
    }
  };

  if (editing && existing.isPending) return <PageLoader />;

  return (
    <>
      <PageHeader title={editing ? 'Edit job' : 'Post a job'} intro="New jobs start as drafts. Publish from your job list once everything looks right." />
      <Card>
        <form onSubmit={onSubmit} noValidate className="grid gap-5 md:grid-cols-2">
          {formError && (
            <div className="md:col-span-2">
              <ErrorNote>{formError}</ErrorNote>
            </div>
          )}
          <div className="md:col-span-2">
            <TextField label="Job title" value={values.title} error={errors.title} onChange={(e) => set('title', e.target.value)} required />
          </div>
          <SelectField label="Department" value={values.department} error={errors.department} onChange={(e) => set('department', e.target.value)} required>
            <option value="">Choose…</option>
            {departments.data?.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </SelectField>
          <SelectField label="Location" value={values.location} error={errors.location} onChange={(e) => set('location', e.target.value)} required>
            <option value="">Choose…</option>
            {locations.data?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </SelectField>
          <SelectField label="Level" value={values.level} error={errors.level} onChange={(e) => set('level', e.target.value)} required>
            <option value="">Choose…</option>
            {levels.data?.map((l) => (
              <option key={l.id} value={l.id}>
                {l.name}
              </option>
            ))}
          </SelectField>
          <SelectField label="Hiring manager" value={values.hiring_manager} error={errors.hiring_manager} onChange={(e) => set('hiring_manager', e.target.value)} hint="Required before publishing.">
            <option value="">Not assigned yet</option>
            {managers.data?.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name}
              </option>
            ))}
          </SelectField>
          <SelectField label="Work mode" value={values.work_mode} onChange={(e) => set('work_mode', e.target.value)}>
            <option value="onsite">On-site</option>
            <option value="hybrid">Hybrid</option>
            <option value="remote">Remote</option>
          </SelectField>
          <SelectField label="Employment type" value={values.employment_type} onChange={(e) => set('employment_type', e.target.value)}>
            <option value="full_time">Full-time</option>
            <option value="part_time">Part-time</option>
            <option value="contract">Contract</option>
            <option value="internship">Internship</option>
          </SelectField>
          <TextField label="Openings" type="number" min={1} max={500} inputMode="numeric" value={values.openings} error={errors.openings} onChange={(e) => set('openings', e.target.value)} />
          <div className="md:col-span-2">
            <TextAreaField
              label="Description"
              rows={10}
              value={values.description}
              error={errors.description}
              hint="Plain text. Separate sections with a blank line; start bullet lines with “- ”."
              onChange={(e) => set('description', e.target.value)}
              required
            />
          </div>
          <SkillPicker
            label="Required skills"
            skills={skills.data ?? []}
            value={values.required_skills}
            exclude={values.nice_to_have_skills}
            error={errors.required_skills}
            onChange={(ids) => set('required_skills', ids)}
          />
          <SkillPicker
            label="Nice-to-have skills"
            skills={skills.data ?? []}
            value={values.nice_to_have_skills}
            exclude={values.required_skills}
            error={errors.nice_to_have_skills}
            onChange={(ids) => set('nice_to_have_skills', ids)}
          />
          <fieldset className="rounded-xl border border-ink/15 p-4 md:col-span-2">
            <legend className="px-1 text-sm font-semibold text-ink">Blind screening</legend>
            <label className="flex min-h-11 items-center gap-3 text-sm text-ink">
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={values.blind_screening}
                onChange={(e) => set('blind_screening', e.target.checked)}
              />
              Hide name, contact details, address and college while screening
            </label>
            <div className="mt-2 max-w-xs">
              <SelectField
                label="Reveal identity at"
                value={values.reveal_stage}
                disabled={!values.blind_screening}
                onChange={(e) => set('reveal_stage', e.target.value as Values['reveal_stage'])}
              >
                <option value="interview">Interview</option>
                <option value="offer">Offer</option>
              </SelectField>
            </div>
          </fieldset>
          <div className="flex gap-2 md:col-span-2">
            <Button type="submit" disabled={busy}>
              {busy ? 'Saving…' : editing ? 'Save changes' : 'Save draft'}
            </Button>
            <Button variant="ghost" onClick={() => navigate(back)}>
              Cancel
            </Button>
          </div>
        </form>
      </Card>
    </>
  );
}
