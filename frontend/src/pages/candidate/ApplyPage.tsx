import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, Card, ErrorNote, PageLoader, SelectField, SuccessNote, TextAreaField, TextField, buttonClass } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import {
  EMPTY_ROLE,
  SECTION_STEP,
  STEPS,
  flattenErrors,
  initialState,
  stepErrors,
  type ApplyContext,
  type FormState,
} from '@/lib/applyForm';
import type { ExperienceRow, PublicJob } from '@/lib/types';
import { NotFoundPage } from '../public/NotFoundPage';

function Progress({ step }: { step: number }) {
  return (
    <nav aria-label="Application steps" className="mb-6">
      <p className="mb-2 text-sm font-semibold text-ink">
        Step {step + 1} of {STEPS.length}: {STEPS[step]}
      </p>
      <div className="h-2 overflow-hidden rounded-full bg-canvas-deep" aria-hidden="true">
        <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${((step + 1) / STEPS.length) * 100}%` }} />
      </div>
      <ol className="mt-3 hidden flex-wrap gap-x-4 gap-y-1 text-xs text-muted sm:flex">
        {STEPS.map((label, i) => (
          <li key={label} aria-current={i === step ? 'step' : undefined} className={i === step ? 'font-semibold text-primary-strong' : ''}>
            {i + 1}. {label}
          </li>
        ))}
      </ol>
    </nav>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <fieldset className="grid gap-4 md:grid-cols-2">
      <legend className="mb-2 font-display text-lg font-semibold text-ink">{title}</legend>
      {children}
    </fieldset>
  );
}

function YesNo({ label, value, error, onChange }: { label: string; value: string; error?: string; onChange: (v: 'yes' | 'no') => void }) {
  return (
    <fieldset className="flex flex-col gap-1.5">
      <legend className="text-sm font-medium text-ink">
        {label}{' '}
        <span className="text-danger" aria-hidden="true">
          *
        </span>
      </legend>
      <div className="flex gap-4">
        {(['yes', 'no'] as const).map((v) => (
          <label key={v} className="flex items-center gap-2 text-sm">
            <input type="radio" className="h-4 w-4" checked={value === v} onChange={() => onChange(v)} />
            {v === 'yes' ? 'Yes' : 'No'}
          </label>
        ))}
      </div>
      {error && <p className="text-sm font-medium text-danger">{error}</p>}
    </fieldset>
  );
}

export function ApplicationWizard({ job, ctx, onDone }: { job: PublicJob; ctx: ApplyContext; onDone: () => void }) {
  const [form, setForm] = useState<FormState>(() => initialState(ctx));
  const [step, setStep] = useState(() => Math.min(ctx.draft?.step ?? 0, STEPS.length - 1));
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState('career_site');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState('');
  const [savedAt, setSavedAt] = useState(ctx.draft?.saved_at ?? '');
  const [busy, setBusy] = useState(false);
  const top = useRef<HTMLDivElement>(null);
  const questions = ctx.job.screening_questions;

  useEffect(() => {
    top.current?.focus();
  }, [step]);

  const set = <K extends keyof FormState>(section: K, patch: Partial<FormState[K]>) =>
    setForm((f) => ({ ...f, [section]: { ...(f[section] as object), ...patch } }));
  const err = (key: string) => errors[key];

  const saveDraft = useMutation({
    mutationFn: () =>
      api<{ saved_at: string }>(`/applications/drafts/${encodeURIComponent(job.slug)}`, { method: 'PUT', body: { data: form, step } }),
    onSuccess: (data) => setSavedAt(data.saved_at),
  });

  const next = () => {
    const found = stepErrors(step, form, ctx, file);
    setErrors(found);
    if (Object.keys(found).length) return;
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const submit = async () => {
    setFormError('');
    const found = stepErrors(6, form, ctx, file);
    setErrors(found);
    if (Object.keys(found).length) return;
    const payload = {
      ...form,
      personal: { ...form.personal, willing_to_relocate: form.personal.willing_to_relocate === 'yes' },
      experience: { ...form.experience, roles: form.experience.status === 'fresher' ? [] : form.experience.roles },
    };
    const body = new FormData();
    body.append('job', job.slug);
    body.append('source', source);
    body.append('form', JSON.stringify(payload));
    if (!form.use_profile_resume && file) body.append('resume', file);
    setBusy(true);
    try {
      await api('/applications', { method: 'POST', form: body });
      onDone();
    } catch (error) {
      setBusy(false);
      if (error instanceof ApiError) {
        const flat = flattenErrors(error.data);
        setErrors(flat);
        setFormError(error.status === 409 ? 'You have already applied to this job.' : 'Please fix the highlighted answers.');
        const first = Object.keys(flat)[0]?.split('.')[0];
        if (first && first in SECTION_STEP) setStep(SECTION_STEP[first]);
      } else {
        setFormError('Could not send your application. Please try again.');
      }
    }
  };

  const errorList = Object.entries(errors);
  return (
    <div>
      <Progress step={step} />
      <div ref={top} tabIndex={-1} className="focus:outline-none">
        {formError && <ErrorNote>{formError}</ErrorNote>}
        {errorList.length > 0 && (
          <div role="alert" className="mb-4 rounded-xl border border-danger/30 bg-danger-soft p-3 text-sm text-danger">
            {errorList.length === 1 ? 'One answer needs attention.' : `${errorList.length} answers need attention.`}
          </div>
        )}
      </div>

      {step === 0 && (
        <Section title="Personal details">
          <TextField
            label="Full legal name"
            value={ctx.prefill.personal.full_name}
            readOnly
            hint="From your account. Only an admin can change it."
          />
          <TextField label="Email" value={ctx.prefill.personal.email} readOnly hint="From your account." />
          <TextField
            label="Phone"
            type="tel"
            autoComplete="tel"
            required
            value={form.personal.phone}
            error={err('personal.phone')}
            onChange={(e) => set('personal', { phone: e.target.value })}
          />
          <TextField
            label="Current city"
            autoComplete="address-level2"
            required
            value={form.personal.current_city}
            error={err('personal.current_city')}
            onChange={(e) => set('personal', { current_city: e.target.value })}
          />
          <TextField
            label="Date of birth"
            type="date"
            required
            readOnly={ctx.locked.date_of_birth}
            hint={ctx.locked.date_of_birth ? 'From your profile (locked).' : 'Saved to your profile and then locked.'}
            value={form.personal.date_of_birth}
            error={err('personal.date_of_birth')}
            onChange={(e) => set('personal', { date_of_birth: e.target.value })}
          />
          <YesNo
            label="Willing to relocate?"
            value={form.personal.willing_to_relocate}
            error={err('personal.willing_to_relocate')}
            onChange={(v) => set('personal', { willing_to_relocate: v })}
          />
        </Section>
      )}

      {step === 1 && (
        <Section title="Education">
          <SelectField
            label="Highest qualification"
            required
            value={form.education.highest_qualification}
            error={err('education.highest_qualification')}
            onChange={(e) => set('education', { highest_qualification: e.target.value })}
          >
            {ctx.qualifications.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </SelectField>
          <TextField
            label="College"
            required
            value={form.education.college}
            error={err('education.college')}
            onChange={(e) => set('education', { college: e.target.value })}
          />
          <TextField
            label="Branch or major"
            required
            value={form.education.branch}
            error={err('education.branch')}
            onChange={(e) => set('education', { branch: e.target.value })}
          />
          <TextField
            label="Graduation year"
            inputMode="numeric"
            required
            value={form.education.graduation_year}
            error={err('education.graduation_year')}
            onChange={(e) => set('education', { graduation_year: e.target.value })}
          />
          <SelectField
            label="Score type"
            value={form.education.score_type}
            onChange={(e) => set('education', { score_type: e.target.value as 'cgpa' | 'percentage' })}
          >
            <option value="cgpa">CGPA (out of 10)</option>
            <option value="percentage">Percentage</option>
          </SelectField>
          <TextField
            label={form.education.score_type === 'cgpa' ? 'CGPA' : 'Percentage'}
            inputMode="decimal"
            required
            value={form.education.score}
            error={err('education.score')}
            onChange={(e) => set('education', { score: e.target.value })}
          />
          <TextField
            label="10th percentage"
            inputMode="decimal"
            required
            value={form.education.tenth_percentage}
            error={err('education.tenth_percentage')}
            onChange={(e) => set('education', { tenth_percentage: e.target.value })}
          />
          <TextField
            label="12th percentage"
            inputMode="decimal"
            required
            value={form.education.twelfth_percentage}
            error={err('education.twelfth_percentage')}
            onChange={(e) => set('education', { twelfth_percentage: e.target.value })}
          />
          <p className="text-xs text-muted md:col-span-2">
            Your college and scores never change your fit score, and stay hidden from recruiters while screening is blind.
          </p>
        </Section>
      )}

      {step === 2 && (
        <Section title="Experience">
          <SelectField
            label="You are"
            value={form.experience.status}
            onChange={(e) => {
              const status = e.target.value as 'fresher' | 'experienced';
              set('experience', {
                status,
                roles: status === 'experienced' && form.experience.roles.length === 0 ? [{ ...EMPTY_ROLE }] : form.experience.roles,
              });
            }}
          >
            <option value="fresher">A fresher</option>
            <option value="experienced">Experienced</option>
          </SelectField>
          <TextField
            label="Total experience (years)"
            inputMode="decimal"
            required
            value={form.experience.total_years}
            error={err('experience.total_years')}
            onChange={(e) => set('experience', { total_years: e.target.value })}
          />
          {form.experience.status === 'experienced' && (
            <div className="flex flex-col gap-3 md:col-span-2">
              {err('experience.roles') && <p className="text-sm font-medium text-danger">{err('experience.roles')}</p>}
              {form.experience.roles.map((role, i) => {
                const setRole = (patch: Partial<ExperienceRow>) =>
                  set('experience', { roles: form.experience.roles.map((r, j) => (j === i ? { ...r, ...patch } : r)) });
                return (
                  <div key={i} className="grid gap-3 rounded-xl border border-ink/10 bg-white/60 p-3 sm:grid-cols-2">
                    <TextField
                      label={`Company (role ${i + 1})`}
                      value={role.company}
                      error={err(`experience.roles.${i}.company`)}
                      onChange={(e) => setRole({ company: e.target.value })}
                    />
                    <TextField
                      label={`Title (role ${i + 1})`}
                      value={role.title}
                      error={err(`experience.roles.${i}.title`)}
                      onChange={(e) => setRole({ title: e.target.value })}
                    />
                    <TextField
                      label={`Start month (role ${i + 1})`}
                      type="month"
                      value={role.start}
                      error={err(`experience.roles.${i}.start`)}
                      onChange={(e) => setRole({ start: e.target.value })}
                    />
                    <TextField
                      label={`End month (role ${i + 1})`}
                      type="month"
                      hint="Leave empty if you work there now."
                      value={role.end === 'present' ? '' : role.end}
                      error={err(`experience.roles.${i}.end`)}
                      onChange={(e) => setRole({ end: e.target.value || 'present' })}
                    />
                    <div className="sm:col-span-2">
                      <TextAreaField
                        label={`Responsibilities (role ${i + 1})`}
                        rows={3}
                        value={role.responsibilities}
                        onChange={(e) => setRole({ responsibilities: e.target.value })}
                      />
                    </div>
                    <Button
                      variant="ghost"
                      className="self-start"
                      onClick={() => set('experience', { roles: form.experience.roles.filter((_, j) => j !== i) })}
                    >
                      Remove role {i + 1}
                    </Button>
                  </div>
                );
              })}
              <Button
                variant="secondary"
                className="self-start"
                onClick={() => set('experience', { roles: [...form.experience.roles, { ...EMPTY_ROLE, end: 'present' }] })}
              >
                Add a role
              </Button>
            </div>
          )}
        </Section>
      )}

      {step === 3 && (
        <Section title="Compensation and joining">
          <TextField
            label="Current CTC (lakhs per annum)"
            inputMode="decimal"
            required
            hint="0 if you are a fresher."
            value={form.compensation.current_ctc_lpa}
            error={err('compensation.current_ctc_lpa')}
            onChange={(e) => set('compensation', { current_ctc_lpa: e.target.value })}
          />
          <TextField
            label="Expected CTC (lakhs per annum)"
            inputMode="decimal"
            required
            value={form.compensation.expected_ctc_lpa}
            error={err('compensation.expected_ctc_lpa')}
            onChange={(e) => set('compensation', { expected_ctc_lpa: e.target.value })}
          />
          <SelectField
            label="Notice period"
            required
            value={form.compensation.notice_period}
            error={err('compensation.notice_period')}
            onChange={(e) => set('compensation', { notice_period: e.target.value })}
          >
            <option value="">Choose…</option>
            {ctx.notice_periods.map((n) => (
              <option key={n.value} value={n.value}>
                {n.label}
              </option>
            ))}
          </SelectField>
          <TextField
            label="Earliest joining date"
            type="date"
            required
            value={form.compensation.earliest_joining}
            error={err('compensation.earliest_joining')}
            onChange={(e) => set('compensation', { earliest_joining: e.target.value })}
          />
          <p className="text-xs text-muted md:col-span-2">
            Recruiters see compensation next to your application, never inside the fit score.
          </p>
        </Section>
      )}

      {step === 4 && (
        <Section title="Links and questions">
          <TextField
            label="LinkedIn"
            value={form.links.linkedin_url}
            error={err('links.linkedin_url')}
            onChange={(e) => set('links', { linkedin_url: e.target.value })}
          />
          <TextField
            label="GitHub"
            value={form.links.github_url}
            error={err('links.github_url')}
            onChange={(e) => set('links', { github_url: e.target.value })}
          />
          <TextField
            label="Portfolio"
            value={form.links.portfolio_url}
            error={err('links.portfolio_url')}
            onChange={(e) => set('links', { portfolio_url: e.target.value })}
          />
          <SelectField label="How did you find this job?" value={source} onChange={(e) => setSource(e.target.value)}>
            <option value="career_site">Our career site</option>
            <option value="job_board">A job board</option>
            <option value="referral">Someone referred me</option>
          </SelectField>
          {questions.length > 0 && (
            <div className="flex flex-col gap-4 md:col-span-2">
              <h3 className="font-semibold text-ink">Questions from the hiring team</h3>
              {questions.map((q) =>
                q.kind === 'yes_no' ? (
                  <YesNo
                    key={q.id}
                    label={q.text}
                    value={form.answers[q.id] ?? ''}
                    error={err(`answers.${q.id}`)}
                    onChange={(v) => setForm((f) => ({ ...f, answers: { ...f.answers, [q.id]: v } }))}
                  />
                ) : (
                  <TextField
                    key={q.id}
                    label={q.text}
                    required={q.required}
                    inputMode={q.kind === 'number' ? 'decimal' : undefined}
                    value={form.answers[q.id] ?? ''}
                    error={err(`answers.${q.id}`)}
                    onChange={(e) => setForm((f) => ({ ...f, answers: { ...f.answers, [q.id]: e.target.value } }))}
                  />
                ),
              )}
            </div>
          )}
        </Section>
      )}

      {step === 5 && (
        <Section title="Resume and cover letter">
          {ctx.profile_resume && (
            <label className="flex items-center gap-2 text-sm text-ink md:col-span-2">
              <input
                type="checkbox"
                className="h-4 w-4"
                checked={form.use_profile_resume}
                onChange={(e) => setForm((f) => ({ ...f, use_profile_resume: e.target.checked }))}
              />
              Use the resume on my profile ({ctx.profile_resume.filename})
            </label>
          )}
          {!form.use_profile_resume && (
            <div className="flex flex-col gap-1.5 md:col-span-2">
              <label htmlFor="apply-resume" className="text-sm font-medium text-ink">
                Upload a resume{' '}
                <span className="text-danger" aria-hidden="true">
                  *
                </span>
              </label>
              <input
                id="apply-resume"
                type="file"
                accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                aria-invalid={err('resume') ? true : undefined}
                aria-describedby="apply-resume-hint"
                onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                className="block w-full rounded-xl border border-dashed border-ink/25 bg-white/80 p-3 text-sm text-ink file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:font-semibold file:text-white"
              />
              <p id="apply-resume-hint" className="text-xs text-muted">
                PDF or DOCX, up to 5 MB. We check the file itself and store it encrypted.
              </p>
              {err('resume') && <p className="text-sm font-medium text-danger">{err('resume')}</p>}
            </div>
          )}
          <div className="md:col-span-2">
            <TextAreaField
              label="Cover letter (optional)"
              maxLength={3000}
              hint={`${form.cover_letter.length}/3000 characters`}
              value={form.cover_letter}
              onChange={(e) => setForm((f) => ({ ...f, cover_letter: e.target.value }))}
            />
          </div>
        </Section>
      )}

      {step === 6 && (
        <Section title="Review and submit">
          <dl className="grid gap-3 text-sm md:col-span-2 md:grid-cols-2">
            <div>
              <dt className="text-muted">Phone and city</dt>
              <dd className="font-medium text-ink">
                {form.personal.phone} · {form.personal.current_city}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Education</dt>
              <dd className="font-medium text-ink">
                {form.education.highest_qualification}, {form.education.college} ({form.education.graduation_year})
              </dd>
            </div>
            <div>
              <dt className="text-muted">Experience</dt>
              <dd className="font-medium text-ink">
                {form.experience.status === 'fresher'
                  ? 'Fresher'
                  : `${form.experience.total_years} years, ${form.experience.roles.length} roles`}
              </dd>
            </div>
            <div>
              <dt className="text-muted">CTC and notice</dt>
              <dd className="font-medium text-ink">
                {form.compensation.current_ctc_lpa} → {form.compensation.expected_ctc_lpa} LPA ·{' '}
                {ctx.notice_periods.find((n) => n.value === form.compensation.notice_period)?.label ?? '—'} · joins{' '}
                {form.compensation.earliest_joining ? formatDate(form.compensation.earliest_joining) : '—'}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Resume</dt>
              <dd className="font-medium text-ink">
                {form.use_profile_resume ? ctx.profile_resume?.filename : (file?.name ?? 'Not chosen')}
              </dd>
            </div>
            <div>
              <dt className="text-muted">Questions answered</dt>
              <dd className="font-medium text-ink">
                {Object.values(form.answers).filter(Boolean).length} of {questions.length}
              </dd>
            </div>
          </dl>
          <div className="flex flex-col gap-3 md:col-span-2">
            <label className="flex items-start gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={form.declarations.info_true}
                onChange={(e) => set('declarations', { info_true: e.target.checked })}
              />
              I confirm the information is true.
            </label>
            {err('declarations.info_true') && <p className="text-sm font-medium text-danger">{err('declarations.info_true')}</p>}
            <label className="flex items-start gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="mt-1 h-4 w-4"
                checked={form.declarations.accept_terms}
                onChange={(e) => set('declarations', { accept_terms: e.target.checked })}
              />
              <span>
                I accept the{' '}
                <Link to="/terms" target="_blank" className="font-semibold text-primary-strong underline">
                  Terms and Conditions
                </Link>{' '}
                and the{' '}
                <Link to="/privacy" target="_blank" className="font-semibold text-primary-strong underline">
                  Privacy Policy
                </Link>{' '}
                (version {ctx.terms_version}).
              </span>
            </label>
            {err('declarations.accept_terms') && <p className="text-sm font-medium text-danger">{err('declarations.accept_terms')}</p>}
          </div>
        </Section>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-2 border-t border-ink/10 pt-4">
        {step > 0 && (
          <Button variant="secondary" onClick={() => setStep((s) => s - 1)}>
            Back
          </Button>
        )}
        {step < STEPS.length - 1 ? (
          <Button onClick={next}>Next: {STEPS[step + 1]}</Button>
        ) : (
          <Button onClick={() => void submit()} disabled={busy}>
            {busy ? 'Sending application…' : 'Submit application'}
          </Button>
        )}
        <Button variant="ghost" onClick={() => saveDraft.mutate()} disabled={saveDraft.isPending}>
          {saveDraft.isPending ? 'Saving…' : 'Save as draft'}
        </Button>
        {savedAt && !saveDraft.isPending && (
          <span className="text-xs text-muted">Draft saved {new Date(savedAt).toLocaleTimeString('en-IN')}</span>
        )}
      </div>
      {saveDraft.isError && <ErrorNote>Could not save the draft. Please try again.</ErrorNote>}
    </div>
  );
}

export function ApplyPage() {
  const { slug = '' } = useParams();
  const navigate = useNavigate();
  const client = useQueryClient();
  const job = useQuery({
    queryKey: ['public-job', slug],
    queryFn: () => api<PublicJob>(`/public/jobs/${encodeURIComponent(slug)}`),
    retry: false,
  });
  const ctx = useQuery({
    queryKey: ['apply-form', slug],
    queryFn: () => api<ApplyContext>(`/applications/drafts/${encodeURIComponent(slug)}`),
    retry: false,
  });
  useDocumentTitle(job.data ? `Apply: ${job.data.title}` : 'Apply');

  if (job.isPending || ctx.isPending) return <PageLoader />;
  if (!job.data || !ctx.data) return <NotFoundPage />;
  const data = job.data;

  const done = () => {
    void client.invalidateQueries({ queryKey: ['my-applications'] });
    navigate('/candidate', { state: { flash: `Application sent for ${data.title}.` } });
  };

  return (
    <div className="mx-auto max-w-3xl">
      <Link to={`/jobs/${slug}`} className="text-sm font-medium text-primary-strong hover:underline">
        ← Back to job
      </Link>
      <h1 className="mt-3 font-display text-3xl font-semibold text-ink">Apply: {data.title}</h1>
      <p className="mt-1 text-muted">
        {[data.company?.name, data.department.name, data.location.name, data.work_mode_label].filter(Boolean).join(' · ')}
      </p>
      <Card className="mt-6">
        {ctx.data.already_applied ? (
          <SuccessNote>
            You have already applied to this job.{' '}
            <Link to="/candidate" className="font-semibold underline">
              See my applications
            </Link>
          </SuccessNote>
        ) : (
          <ApplicationWizard job={data} ctx={ctx.data} onDone={done} />
        )}
      </Card>
      <p className="mt-4 text-sm text-muted">
        Not ready?{' '}
        <Link to="/jobs" className={buttonClass('ghost', 'min-h-0 px-1 py-0 underline')}>
          Keep browsing
        </Link>{' '}
        (save a draft first).
      </p>
    </div>
  );
}
