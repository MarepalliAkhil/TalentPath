import { useId, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { api } from '@/lib/api';
import { SOURCE_LABEL, type DemoConfig, type PathStep, type ProfileResume } from '@/lib/growth';
import type { User } from '@/lib/types';
import { errorText } from '@/lib/pipeline';
import { Button, ErrorNote, SuccessNote } from './ui';

// eslint-disable-next-line react-refresh/only-export-components -- small hook shared by layouts and the login page
export function useDemoConfig() {
  return useQuery({
    queryKey: ['demo-config'],
    queryFn: () => api<DemoConfig>('/demo/config'),
    staleTime: 10 * 60_000,
    retry: false,
  });
}

/** Slim banner on every page while demo mode is on. */
export function DemoBanner() {
  const config = useDemoConfig();
  if (!config.data?.demo_mode) return null;
  return (
    <p role="note" className="bg-ink px-4 py-1.5 text-center text-xs font-semibold text-white">
      {config.data.banner}
    </p>
  );
}

/** "Try as …" buttons: sign in to a seeded demo account. Shown only when demo mode is on. */
export function DemoButtons({ heading = 'Try it as' }: { heading?: string }) {
  const config = useDemoConfig();
  const client = useQueryClient();
  const navigate = useNavigate();
  const signIn = useMutation({
    mutationFn: (role: string) => api<{ user: User }>('/auth/demo-login', { method: 'POST', body: { role } }),
    onSuccess: ({ user }) => {
      client.setQueryData(['me'], user);
      navigate(user.dashboard, { replace: true });
    },
  });
  if (!config.data?.demo_mode) return null;
  return (
    <div role="group" aria-label="Try the demo" className="flex flex-col gap-2">
      <p className="text-sm font-semibold text-ink">{heading}</p>
      <div className="flex flex-wrap gap-2">
        {config.data.accounts.map((a) => (
          <Button key={a.role} variant="secondary" onClick={() => signIn.mutate(a.role)} disabled={signIn.isPending}>
            Try as {a.role === 'hr_admin' ? a.label : a.label.toLowerCase()}
          </Button>
        ))}
      </div>
      <p className="text-xs text-muted">Signs you in to a seeded demo account. Demo data resets nightly.</p>
      {signIn.isError && <ErrorNote>{errorText(signIn.error)}</ErrorNote>}
    </div>
  );
}

/** The person's own resume for the career map (and one-click internal applications). */
export function ResumeCard({ compact = false }: { compact?: boolean }) {
  const client = useQueryClient();
  const inputId = useId();
  const [file, setFile] = useState<File | null>(null);
  const profile = useQuery({ queryKey: ['career-profile'], queryFn: () => api<ProfileResume>('/career/profile') });
  const refresh = () => {
    void client.invalidateQueries({ queryKey: ['career-profile'] });
    void client.invalidateQueries({ queryKey: ['career-map'] });
    void client.invalidateQueries({ queryKey: ['internal-jobs'] });
  };
  const upload = useMutation({
    mutationFn: () => {
      const form = new FormData();
      if (file) form.set('resume', file);
      return api<ProfileResume>('/career/profile', { method: 'POST', form });
    },
    onSuccess: () => {
      setFile(null);
      refresh();
    },
  });
  const remove = useMutation({ mutationFn: () => api('/career/profile', { method: 'DELETE' }), onSuccess: refresh });
  const data = profile.data;
  return (
    <section className="glass rounded-xl2 p-5" aria-labelledby={`${inputId}-heading`}>
      <h2 id={`${inputId}-heading`} className="font-display text-xl font-semibold text-ink">
        Your resume for the career map
      </h2>
      {data && (
        <p className="mt-1 text-sm text-ink-soft">
          {data.has_resume ? (
            <>
              Using <strong>{data.filename}</strong>. {data.skills.length} skills found.
            </>
          ) : (
            <>Your map uses {SOURCE_LABEL[data.source]}. Add a resume to see it before you apply.</>
          )}
        </p>
      )}
      {!compact && data && data.skills.length > 0 && (
        <p className="mt-2 text-sm text-muted">Skills: {data.skills.join(', ')}</p>
      )}
      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end">
        <div className="flex flex-col gap-1">
          <label htmlFor={inputId} className="text-sm font-medium text-ink">
            {data?.has_resume ? 'Replace resume' : 'Add resume'} (PDF or DOCX, up to 5 MB)
          </label>
          <input
            id={inputId}
            type="file"
            accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="text-sm"
          />
        </div>
        <Button onClick={() => upload.mutate()} disabled={!file || upload.isPending}>
          {upload.isPending ? 'Reading…' : 'Upload'}
        </Button>
        {data?.has_resume && (
          <Button variant="ghost" onClick={() => remove.mutate()} disabled={remove.isPending}>
            Delete my resume
          </Button>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">
        Read on our server with the same rules as applications and stored encrypted. Only you see it; delete it at any time.
      </p>
      {upload.isError && <ErrorNote>{errorText(upload.error)}</ErrorNote>}
      {upload.isSuccess && <SuccessNote>Resume saved. Your map is up to date.</SuccessNote>}
      {remove.isSuccess && !data?.has_resume && <SuccessNote>Resume deleted.</SuccessNote>}
    </section>
  );
}

const KIND_LABEL: Record<NonNullable<PathStep['kind']>, string> = {
  required: 'Required',
  nice: 'Nice to have',
  prerequisite: 'Needed first',
};

/** Ordered learning path. Links only come from shared/learning_links.json; otherwise text only. */
export function LearningPath({ steps }: { steps: PathStep[] }) {
  if (!steps.length) return <p className="text-sm text-muted">Nothing to learn for this one: you have every listed skill.</p>;
  return (
    <ol className="space-y-2">
      {steps.map((step, i) => (
        <li key={step.slug} className="flex gap-3 rounded-xl border border-ink/10 bg-white/70 p-3">
          <span aria-hidden="true" className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-sm font-semibold text-white">
            {i + 1}
          </span>
          <div className="text-sm">
            <p className="font-semibold text-ink">
              {step.name}
              {step.kind && <span className="ml-2 rounded-full bg-canvas-deep px-2 py-0.5 text-xs font-medium text-ink-soft">{KIND_LABEL[step.kind]}</span>}
            </p>
            <p className="text-ink-soft">
              Effort: {step.effort_label}
              {step.prerequisites.length > 0 && ` · after ${step.prerequisites.join(', ')}`}
              {step.unlocks.length > 0 && ` · needed for ${step.unlocks.join(', ')}`}
            </p>
            {step.link ? (
              <a href={step.link.url} target="_blank" rel="noopener noreferrer" className="font-semibold text-primary-strong underline">
                {step.link.title}
                <span className="sr-only"> (official documentation, opens in a new tab)</span>
              </a>
            ) : (
              <p className="text-xs text-muted">No curated link yet.</p>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function BandPill({ band, label, score }: { band: string; label: string; score: number }) {
  const style: Record<string, string> = {
    strong: 'bg-success-soft text-success',
    good: 'bg-primary-soft text-primary-strong',
    partial: 'bg-warning-soft text-warning',
    low: 'bg-canvas-deep text-ink-soft',
  };
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold ${style[band] ?? 'bg-canvas-deep text-ink'}`}>
      {label} · {score}
    </span>
  );
}
