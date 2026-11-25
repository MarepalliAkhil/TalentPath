import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';
import { BandPill, LearningPath, ResumeCard } from '@/components/growth';
import { EmptyState, ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { SOURCE_LABEL, type MapJob, type NextRole, type ProfileResume } from '@/lib/growth';
import { useDocumentTitle } from '@/lib/hooks';

function NextRoleSection() {
  const query = useQuery({ queryKey: ['next-role'], queryFn: () => api<NextRole>('/career/next-role'), retry: false });
  if (query.isPending || query.isError) return null;
  const data = query.data;
  return (
    <section className="glass mt-6 rounded-xl2 p-5" aria-labelledby="next-role-heading">
      <h2 id="next-role-heading" className="font-display text-xl font-semibold text-ink">
        Your next role
      </h2>
      {data.current_level === null ? (
        <p className="mt-1 text-sm text-muted">HR has not recorded your level yet, so we cannot show the next one.</p>
      ) : data.levels.length === 0 ? (
        <p className="mt-1 text-sm text-muted">
          No {data.department} roles above {data.current_level} are listed yet.
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-ink-soft">
            You are {data.current_level} in {data.department}. These are the skills {data.department} roles at the next levels ask for.
          </p>
          {data.levels.map((level) => (
            <div key={level.level} className="mt-4">
              <h3 className="font-semibold text-ink">
                {level.level}: {level.titles.join(', ')}
              </h3>
              <p className="text-sm text-ink-soft">
                You have {level.have.length} of {level.skills_needed.length} skills
                {level.missing.length > 0 && `; still to learn: ${level.missing.map((m) => m.name).join(', ')}`}.
              </p>
              {level.missing.length > 0 && (
                <div className="mt-2">
                  <LearningPath steps={level.path} />
                </div>
              )}
            </div>
          ))}
        </>
      )}
    </section>
  );
}

/** "Jobs you're closest to", ranked by the same scorer recruiters see. */
export function CareerPage() {
  useDocumentTitle('Career map');
  const { user } = useAuth();
  const map = useQuery({
    queryKey: ['career-map'],
    queryFn: () => api<{ source: ProfileResume['source']; jobs: MapJob[] }>('/career/map'),
  });
  return (
    <>
      <PageHeader
        title="Your career map"
        intro="Jobs you're closest to, scored by the same explainable scorer recruiters use, with the skills you have and an ordered path for the ones you don't."
      />
      <ResumeCard compact />
      <section className="mt-6" aria-labelledby="closest-heading">
        <h2 id="closest-heading" className="mb-1 font-display text-xl font-semibold text-ink">
          Jobs you're closest to
        </h2>
        {map.data && <p className="mb-3 text-sm text-muted">Based on {SOURCE_LABEL[map.data.source]}.</p>}
        {map.isPending && <PageLoader />}
        {map.isError && <ErrorNote>We could not load your map.</ErrorNote>}
        {map.data && map.data.jobs.length === 0 && (
          <EmptyState title="No map yet">Add your resume above and your closest jobs appear here.</EmptyState>
        )}
        {map.data && map.data.jobs.length > 0 && (
          <ul className="grid gap-3 md:grid-cols-2">
            {map.data.jobs.map((job) => (
              <li key={job.id} className="glass flex flex-col gap-2 rounded-xl2 p-4">
                <div className="flex items-start justify-between gap-2">
                  <Link
                    to={`/career/jobs/${job.id}`}
                    className="font-display text-lg font-semibold text-ink underline-offset-2 hover:underline"
                  >
                    {job.title}
                  </Link>
                  <BandPill band={job.band} label={job.band_label} score={job.score} />
                </div>
                <p className="text-sm text-ink-soft">
                  {job.department} · {job.location} · {job.level}
                  {job.audience === 'internal' && ' · internal only'}
                </p>
                <Link to={`/career/jobs/${job.id}`} className="text-sm font-semibold text-primary-strong underline">
                  See the skill map<span className="sr-only"> for {job.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
      {user?.role === 'employee' && <NextRoleSection />}
    </>
  );
}
