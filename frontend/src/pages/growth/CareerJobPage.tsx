import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { BandPill, LearningPath } from '@/components/growth';
import { ErrorNote, PageHeader, PageLoader, buttonClass } from '@/components/ui';
import { api } from '@/lib/api';
import { SOURCE_LABEL, type JobMap, type SkillRow } from '@/lib/growth';
import { useDocumentTitle } from '@/lib/hooks';

function SkillList({
  title,
  rows,
  empty,
  showEvidence = false,
}: {
  title: string;
  rows: SkillRow[];
  empty: string;
  showEvidence?: boolean;
}) {
  return (
    <section className="glass rounded-xl2 p-5" aria-label={title}>
      <h2 className="font-display text-lg font-semibold text-ink">
        {title} ({rows.length})
      </h2>
      {rows.length === 0 ? (
        <p className="mt-1 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-2 space-y-1.5 text-sm">
          {rows.map((row) => (
            <li key={row.slug}>
              <span className="font-semibold text-ink">{row.name}</span>
              {showEvidence && row.evidence && <span className="block text-xs text-muted">“{row.evidence}”</span>}
              {!showEvidence && row.effort && <span className="ml-1 text-xs text-muted">({row.effort} effort)</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** The skill-gap map for one job. */
export function CareerJobPage() {
  const { id = '' } = useParams();
  const { user } = useAuth();
  const query = useQuery({ queryKey: ['career-map', id], queryFn: () => api<JobMap>(`/career/map/${id}`) });
  useDocumentTitle(query.data ? `Skill map: ${query.data.job.title}` : 'Skill map');
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not find this job for you.</ErrorNote>;
  const data = query.data;
  const job = data.job;
  return (
    <>
      <PageHeader
        title={`Skill map: ${job.title}`}
        intro={`${job.department} · ${job.location} · ${job.level}. Based on ${SOURCE_LABEL[data.source]}.`}
        actions={
          <Link to="/career" className="text-sm font-semibold text-primary-strong underline">
            All jobs
          </Link>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <BandPill band={job.band} label={job.band_label} score={job.score} />
        <span className="text-sm text-muted">The same score a recruiter sees for this job.</span>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <SkillList title="Skills you have" rows={data.have} empty="None of the listed skills yet." showEvidence />
        <SkillList title="Required skills missing" rows={data.missing_required} empty="You have every required skill." />
        <SkillList title="Nice to have, missing" rows={data.missing_nice} empty="Nothing missing here." />
      </div>
      <section className="mt-6" aria-labelledby="path-heading">
        <h2 id="path-heading" className="mb-1 font-display text-xl font-semibold text-ink">
          Your learning path
        </h2>
        <p className="mb-3 text-sm text-muted">
          In order: a skill never comes before the skills it builds on. Effort is a rough label, not a promise. Links go only to official
          documentation.
        </p>
        <LearningPath steps={data.path} />
      </section>
      <div className="mt-6 flex flex-wrap gap-2">
        {data.applied ? (
          <p className="text-sm font-semibold text-success">You have applied for this job.</p>
        ) : user?.role === 'candidate' ? (
          <Link to={`/jobs/${job.slug}/apply`} className={buttonClass('primary')}>
            Apply for this job
          </Link>
        ) : data.can_apply_internally ? (
          <Link to="/internal-jobs" className={buttonClass('primary')}>
            Apply internally
          </Link>
        ) : null}
      </div>
    </>
  );
}
