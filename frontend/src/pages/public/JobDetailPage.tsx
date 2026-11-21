import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { Icon } from '@/components/Icon';
import { buttonClass, Chip, PageLoader } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { useSeo } from '@/lib/hooks';
import type { PublicJob } from '@/lib/types';
import { NotFoundPage } from './NotFoundPage';

function Description({ text }: { text: string }) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="space-y-5 text-ink-soft">
      {blocks.map((block, i) => {
        const lines = block.split('\n');
        const [first, ...rest] = lines;
        const isSection = rest.length > 0 && !first.startsWith('- ') && first.length < 40;
        const body = isSection ? rest : lines;
        const bullets = body.every((l) => l.startsWith('- '));
        return (
          <div key={i}>
            {isSection && <h2 className="mb-2 font-display text-lg font-semibold text-ink">{first}</h2>}
            {bullets ? (
              <ul className="list-disc space-y-1 pl-5">
                {body.map((l) => (
                  <li key={l}>{l.slice(2)}</li>
                ))}
              </ul>
            ) : (
              <p>{body.join(' ')}</p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function JobDetailPage() {
  const { slug = '' } = useParams();
  const { user } = useAuth();
  const job = useQuery({
    queryKey: ['public-job', slug],
    queryFn: () => api<PublicJob>(`/public/jobs/${encodeURIComponent(slug)}`),
    retry: false,
  });
  const seo = useMemo(
    () =>
      job.data?.seo
        ? {
            title: job.data.seo.title,
            description: job.data.seo.description,
            canonical: job.data.seo.canonical,
            jsonLd: job.data.seo.json_ld,
          }
        : null,
    [job.data],
  );
  useSeo(seo);

  if (job.isPending) return <PageLoader />;
  if (job.error instanceof ApiError && job.error.status === 404) return <NotFoundPage />;
  if (!job.data) return <p role="alert">We could not load this job. Please refresh.</p>;
  const j = job.data;

  let cta = (
    <Link to={`/jobs/${j.slug}/apply`} className={buttonClass('primary', 'w-full sm:w-auto')}>
      Apply now <Icon name="arrow" className="h-4 w-4" />
    </Link>
  );
  if (user && user.role !== 'candidate') {
    cta = <p className="text-sm text-muted">You are signed in as {user.role_label}. Candidates apply from their own account.</p>;
  }

  return (
    <article className="grid gap-8 lg:grid-cols-[1fr_20rem]">
      <div>
        <nav aria-label="Breadcrumb" className="text-sm text-muted">
          <Link to="/jobs" className="hover:text-primary-strong">
            Jobs
          </Link>{' '}
          / <span aria-current="page">{j.department.name}</span>
        </nav>
        <h1 className="mt-3 font-display text-3xl font-semibold tracking-tight text-ink sm:text-4xl">{j.title}</h1>
        <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-muted">
          <span className="inline-flex items-center gap-1">
            <Icon name="pin" className="h-4 w-4" /> {j.location.name}
          </span>
          <span>{j.work_mode_label}</span>
          <span>{j.employment_type_label}</span>
          <span>{j.level}</span>
        </p>
        <div className="glass mt-6 rounded-xl2 p-5 sm:p-7">
          <Description text={j.description ?? ''} />
        </div>
      </div>
      <section className="lg:sticky lg:top-24 lg:self-start" aria-label="Job summary">
        <div className="glass rounded-xl2 p-5">
          {cta}
          <dl className="mt-5 space-y-3 text-sm">
            <div>
              <dt className="text-muted">Department</dt>
              <dd className="font-medium text-ink">{j.department.name}</dd>
            </div>
            <div>
              <dt className="text-muted">Openings</dt>
              <dd className="font-medium text-ink">{j.openings}</dd>
            </div>
            {j.published_at && (
              <div>
                <dt className="text-muted">Posted</dt>
                <dd className="font-medium text-ink">{formatDate(j.published_at)}</dd>
              </div>
            )}
          </dl>
          <h2 className="mt-5 text-sm font-semibold text-ink">Required skills</h2>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {j.required_skills.map((s) => (
              <li key={s.slug}>
                <Chip>{s.name}</Chip>
              </li>
            ))}
          </ul>
          {j.nice_to_have_skills.length > 0 && (
            <>
              <h2 className="mt-4 text-sm font-semibold text-ink">Nice to have</h2>
              <ul className="mt-2 flex flex-wrap gap-1.5">
                {j.nice_to_have_skills.map((s) => (
                  <li key={s.slug}>
                    <Chip>{s.name}</Chip>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </section>
    </article>
  );
}
