import { Link } from 'react-router-dom';
import { formatDate } from '@/lib/format';
import type { PublicJob } from '@/lib/types';
import { Icon } from './Icon';
import { Chip } from './ui';

export function JobCard({ job, headingLevel = 'h2' }: { job: PublicJob; headingLevel?: 'h2' | 'h3' }) {
  const Heading = headingLevel;
  return (
    <article className="glass group relative rounded-xl2 p-5 transition-shadow hover:shadow-lift">
      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold uppercase tracking-wide text-primary-strong">
        <span>{job.department.name}</span>
        <span aria-hidden="true">·</span>
        <span>{job.level}</span>
      </div>
      <Heading className="mt-2 font-display text-lg font-semibold text-ink">
        <Link to={`/jobs/${job.slug}`} className="after:absolute after:inset-0 after:rounded-xl2 focus:outline-none">
          {job.title}
        </Link>
      </Heading>
      <p className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
        <span className="inline-flex items-center gap-1">
          <Icon name="pin" className="h-4 w-4" />
          {job.location.name}
        </span>
        <span>{job.work_mode_label}</span>
        {job.published_at && (
          <span className="inline-flex items-center gap-1">
            <Icon name="clock" className="h-4 w-4" />
            Posted {formatDate(job.published_at)}
          </span>
        )}
      </p>
      <ul className="mt-3 flex flex-wrap gap-1.5" aria-label="Key skills">
        {job.required_skills.slice(0, 4).map((s) => (
          <li key={s.slug}>
            <Chip>{s.name}</Chip>
          </li>
        ))}
      </ul>
    </article>
  );
}
