import { useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { JobCard } from '@/components/JobCard';
import { Icon } from '@/components/Icon';
import { buttonClass, Button } from '@/components/ui';
import { api } from '@/lib/api';
import { brand } from '@/lib/brand';
import { useSeo } from '@/lib/hooks';
import type { Department, Paginated, PublicJob } from '@/lib/types';

const STEPS = ['Discover', 'Match', 'Apply', 'Interview', 'Onboard'];
const SEO = {
  title: `${brand.name} · ${brand.tagline}`,
  description: `Find open roles at ${brand.employerName}, apply in minutes with your resume and follow every step from application to your first day.`,
};

function JourneyLine() {
  return (
    <figure className="glass mt-10 rounded-xl2 p-5" aria-labelledby="journey-caption">
      <svg viewBox="0 0 600 90" className="h-auto w-full" aria-hidden="true" focusable="false">
        <path
          className="path-line"
          d="M20 60 C 120 60, 120 25, 160 25 S 260 70, 300 55 S 400 15, 440 30 S 540 60, 580 35"
          fill="none"
          stroke="rgb(var(--c-primary))"
          strokeWidth="4"
          strokeLinecap="round"
        />
        {[20, 160, 300, 440, 580].map((x, i) => (
          <circle key={x} cx={x} cy={[60, 25, 55, 30, 35][i]} r="8" fill={i === 4 ? 'rgb(var(--c-accent))' : 'white'} stroke="rgb(var(--c-primary))" strokeWidth="3" />
        ))}
      </svg>
      <figcaption id="journey-caption">
        <ol className="mt-3 grid grid-cols-5 gap-1 text-center text-xs font-semibold text-ink-soft sm:text-sm">
          {STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </figcaption>
    </figure>
  );
}

export function HomePage() {
  useSeo(SEO);
  const navigate = useNavigate();
  const [q, setQ] = useState('');
  const latest = useQuery({
    queryKey: ['public-jobs', 'latest'],
    queryFn: () => api<Paginated<PublicJob>>('/public/jobs?page_size=6'),
  });
  const departments = useQuery({ queryKey: ['departments'], queryFn: () => api<Department[]>('/departments') });

  const onSearch = (event: FormEvent) => {
    event.preventDefault();
    navigate(q.trim() ? `/jobs?q=${encodeURIComponent(q.trim())}` : '/jobs');
  };

  return (
    <>
      <section className="grid gap-10 lg:grid-cols-[1.2fr_1fr] lg:items-center">
        <div>
          <p className="inline-flex items-center gap-2 rounded-full bg-white/70 px-3 py-1 text-sm font-semibold text-primary-strong">
            Careers at {brand.employerName}
          </p>
          <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight text-ink sm:text-5xl">
            {brand.tagline}
          </h1>
          <p className="mt-4 max-w-xl text-lg text-muted">
            Search open roles, apply in a few minutes and see exactly where your application stands. We look at your
            skills, not your surname, photo or college.
          </p>
          <form role="search" onSubmit={onSearch} className="mt-6 flex max-w-xl flex-col gap-2 sm:flex-row">
            <label htmlFor="home-search" className="sr-only">
              Search jobs by title or keyword
            </label>
            <input
              id="home-search"
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Try “React”, “Data” or “Sales”"
              className="min-h-12 flex-1 rounded-xl border border-ink/15 bg-white/90 px-4 text-ink placeholder:text-muted focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <Button type="submit" className="min-h-12">
              <Icon name="search" /> Search jobs
            </Button>
          </form>
          {departments.data && departments.data.length > 0 && (
            <ul className="mt-5 flex flex-wrap gap-2" aria-label="Browse by department">
              {departments.data.map((d) => (
                <li key={d.slug}>
                  <Link
                    to={`/jobs?department=${d.slug}`}
                    className="inline-flex min-h-9 items-center rounded-full border border-ink/10 bg-white/70 px-3 text-sm font-medium text-ink-soft hover:border-primary hover:text-primary-strong"
                  >
                    {d.name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </div>
        <JourneyLine />
      </section>

      <section className="mt-14" aria-labelledby="latest-heading">
        <div className="mb-4 flex items-end justify-between gap-4">
          <h2 id="latest-heading" className="font-display text-2xl font-semibold text-ink">
            Latest roles
          </h2>
          <Link to="/jobs" className={buttonClass('secondary')}>
            All jobs <Icon name="arrow" className="h-4 w-4" />
          </Link>
        </div>
        {latest.isPending && <p className="text-muted">Loading roles…</p>}
        {latest.data && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {latest.data.results.map((job) => (
              <JobCard key={job.slug} job={job} headingLevel="h3" />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
