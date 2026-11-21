import { useEffect, useState, type FormEvent } from 'react';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import { JobCard } from '@/components/JobCard';
import { Button, EmptyState, ErrorNote, Pager, SelectField, TextField } from '@/components/ui';
import { api, qs } from '@/lib/api';
import { brand } from '@/lib/brand';
import { useSeo } from '@/lib/hooks';
import type { Department, Location, Paginated, PublicJob, Skill } from '@/lib/types';

const FILTERS = ['q', 'department', 'location', 'work_mode', 'skill'] as const;
const SEO = {
  title: `Open jobs | ${brand.name}`,
  description: `Browse open roles at ${brand.employerName} by department, location, work mode and skill.`,
};

export function JobsPage() {
  useSeo(SEO);
  const [params, setParams] = useSearchParams();
  const page = Number(params.get('page') ?? '1') || 1;
  const current = Object.fromEntries(FILTERS.map((f) => [f, params.get(f) ?? ''])) as Record<(typeof FILTERS)[number], string>;
  const [draft, setDraft] = useState(current);
  const paramsKey = params.toString();
  useEffect(() => {
    setDraft(Object.fromEntries(FILTERS.map((f) => [f, params.get(f) ?? ''])) as typeof current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey]);

  const departments = useQuery({ queryKey: ['departments'], queryFn: () => api<Department[]>('/departments') });
  const locations = useQuery({ queryKey: ['locations'], queryFn: () => api<Location[]>('/locations') });
  const skills = useQuery({ queryKey: ['skills'], queryFn: () => api<Skill[]>('/skills'), staleTime: 300_000 });
  const jobs = useQuery({
    queryKey: ['public-jobs', paramsKey],
    queryFn: () => api<Paginated<PublicJob>>(`/public/jobs${qs({ ...current, page })}`),
    placeholderData: keepPreviousData,
  });

  const apply = (next: Record<string, string>, nextPage = 1) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(next)) if (value) search.set(key, value);
    if (nextPage > 1) search.set('page', String(nextPage));
    setParams(search);
  };

  const onSubmit = (event: FormEvent) => {
    event.preventDefault();
    apply(draft);
  };

  const count = jobs.data?.count ?? 0;
  return (
    <>
      <h1 className="font-display text-3xl font-semibold tracking-tight text-ink">Open roles</h1>
      <p className="mt-1 text-muted">Filter by what matters to you. Skill search understands common short forms like “JS” or “k8s”.</p>

      <form onSubmit={onSubmit} className="glass mt-6 grid gap-4 rounded-xl2 p-4 sm:grid-cols-2 lg:grid-cols-6" aria-label="Job filters">
        <div className="lg:col-span-2">
          <TextField label="Keyword" name="q" value={draft.q} onChange={(e) => setDraft({ ...draft, q: e.target.value })} placeholder="Title or keyword" />
        </div>
        <SelectField label="Department" value={draft.department} onChange={(e) => setDraft({ ...draft, department: e.target.value })}>
          <option value="">All departments</option>
          {departments.data?.map((d) => (
            <option key={d.slug} value={d.slug}>
              {d.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="Location" value={draft.location} onChange={(e) => setDraft({ ...draft, location: e.target.value })}>
          <option value="">All locations</option>
          {locations.data?.map((l) => (
            <option key={l.slug} value={l.slug}>
              {l.name}
            </option>
          ))}
        </SelectField>
        <SelectField label="Work mode" value={draft.work_mode} onChange={(e) => setDraft({ ...draft, work_mode: e.target.value })}>
          <option value="">Any</option>
          <option value="onsite">On-site</option>
          <option value="hybrid">Hybrid</option>
          <option value="remote">Remote</option>
        </SelectField>
        <div>
          <TextField label="Skill" list="skill-options" value={draft.skill} onChange={(e) => setDraft({ ...draft, skill: e.target.value })} placeholder="e.g. Python" />
          <datalist id="skill-options">
            {skills.data?.map((s) => (
              <option key={s.slug} value={s.name} />
            ))}
          </datalist>
        </div>
        <div className="flex gap-2 sm:col-span-2 lg:col-span-6">
          <Button type="submit">Show jobs</Button>
          <Button variant="ghost" onClick={() => apply({})}>
            Clear filters
          </Button>
        </div>
      </form>

      <p className="mt-6 text-sm font-medium text-ink-soft" role="status" aria-live="polite">
        {jobs.isPending ? 'Searching…' : `${count} ${count === 1 ? 'role' : 'roles'} found`}
      </p>
      {jobs.isError && <ErrorNote>We could not load jobs. Please try again.</ErrorNote>}
      {jobs.data && jobs.data.results.length === 0 && (
        <EmptyState title="No roles match these filters">Try removing a filter or searching for a related skill.</EmptyState>
      )}
      {jobs.data && jobs.data.results.length > 0 && (
        <div className="mt-4 grid gap-4 md:grid-cols-2">
          {jobs.data.results.map((job) => (
            <JobCard key={job.slug} job={job} />
          ))}
        </div>
      )}
      <Pager
        page={page}
        hasNext={Boolean(jobs.data?.next)}
        hasPrevious={Boolean(jobs.data?.previous)}
        onChange={(p) => apply(current, p)}
      />
    </>
  );
}
