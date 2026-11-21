import { useRef, useState, type FormEvent } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Button, Card, ErrorNote, PageLoader, TextAreaField, buttonClass } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { applySchema, validate, type Errors } from '@/lib/schemas';
import type { PublicJob } from '@/lib/types';
import { NotFoundPage } from '../public/NotFoundPage';

export function ApplyForm({ job, onDone }: { job: PublicJob; onDone: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [note, setNote] = useState('');
  const [errors, setErrors] = useState<Errors>({});
  const [formError, setFormError] = useState('');
  const [duplicate, setDuplicate] = useState(false);
  const [busy, setBusy] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const fileError = errors.resume;

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setFormError('');
    const { data, errors: found } = validate(applySchema, { cover_note: note, resume: file ?? undefined });
    setErrors(found);
    if (!data) {
      if (found.resume) fileInput.current?.focus();
      return;
    }
    const form = new FormData();
    form.append('job', job.slug);
    form.append('cover_note', data.cover_note);
    form.append('resume', data.resume);
    setBusy(true);
    try {
      await api('/applications', { method: 'POST', form });
      onDone();
    } catch (error) {
      if (error instanceof ApiError) {
        setDuplicate(error.status === 409);
        setErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError('Upload failed. Please try again.');
      }
      setBusy(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5">
      {formError && (
        <ErrorNote>
          {formError}{' '}
          {duplicate && (
            <Link to="/candidate" className="font-semibold underline">
              See my applications
            </Link>
          )}
        </ErrorNote>
      )}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="resume" className="text-sm font-medium text-ink">
          Resume <span className="text-danger" aria-hidden="true">*</span>
        </label>
        <input
          ref={fileInput}
          id="resume"
          name="resume"
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          aria-describedby={`resume-hint${fileError ? ' resume-error' : ''}`}
          aria-invalid={fileError ? true : undefined}
          required
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="block w-full rounded-xl border border-dashed border-ink/25 bg-white/80 p-3 text-sm text-ink file:mr-3 file:rounded-lg file:border-0 file:bg-primary file:px-3 file:py-2 file:font-semibold file:text-white"
        />
        <p id="resume-hint" className="text-xs text-muted">
          PDF or DOCX, up to 5 MB. We check the file itself, read the text on our server and store it encrypted.
        </p>
        {fileError && (
          <p id="resume-error" className="text-sm font-medium text-danger">
            {fileError}
          </p>
        )}
      </div>
      <TextAreaField
        label="Note to the hiring team (optional)"
        value={note}
        maxLength={2000}
        hint={`${note.length}/2000 characters`}
        error={errors.cover_note}
        onChange={(e) => setNote(e.target.value)}
      />
      <Button type="submit" disabled={busy}>
        {busy ? 'Sending application…' : 'Submit application'}
      </Button>
    </form>
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
  useDocumentTitle(job.data ? `Apply: ${job.data.title}` : 'Apply');

  if (job.isPending) return <PageLoader />;
  if (!job.data) return <NotFoundPage />;
  const data = job.data;

  const done = () => {
    void client.invalidateQueries({ queryKey: ['my-applications'] });
    navigate('/candidate', { state: { flash: `Application sent for ${data.title}.` } });
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Link to={`/jobs/${slug}`} className="text-sm font-medium text-primary-strong hover:underline">
        ← Back to job
      </Link>
      <h1 className="mt-3 font-display text-3xl font-semibold text-ink">Apply: {data.title}</h1>
      <p className="mt-1 text-muted">
        {data.department.name} · {data.location.name} · {data.work_mode_label}
      </p>
      <Card className="mt-6">
        <ApplyForm job={data} onDone={done} />
      </Card>
      <p className="mt-4 text-sm text-muted">
        Changed your mind? <Link to="/jobs" className={buttonClass('ghost', 'min-h-0 px-1 py-0 underline')}>Keep browsing</Link>
      </p>
    </div>
  );
}
