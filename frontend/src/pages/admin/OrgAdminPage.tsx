import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Chip, ErrorNote, PageHeader, TextAreaField, TextField } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import type { Company, Skill } from '@/lib/types';

type Row = { id: string; name: string } & Record<string, unknown>;

function OrgSection({
  title,
  resource,
  extraField,
}: {
  title: string;
  resource: string;
  extraField?: { name: string; label: string; type?: string };
}) {
  const client = useQueryClient();
  const [name, setName] = useState('');
  const [extra, setExtra] = useState('');
  const [error, setError] = useState('');
  const list = useQuery({ queryKey: [resource], queryFn: () => api<Row[]>(`/${resource}`) });
  const remove = useMutation({
    mutationFn: (id: string) => api(`/${resource}/${id}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: [resource] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Delete failed.'),
  });

  const onAdd = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    if (!name.trim()) {
      setError('Enter a name.');
      return;
    }
    const body: Record<string, unknown> = { name: name.trim() };
    if (extraField && extra) body[extraField.name] = extraField.type === 'number' ? Number(extra) : extra;
    try {
      await api(`/${resource}`, { method: 'POST', body });
      setName('');
      setExtra('');
      void client.invalidateQueries({ queryKey: [resource] });
    } catch (e) {
      setError(e instanceof ApiError ? (Object.values(e.fieldErrors)[0] ?? e.message) : 'Could not save.');
    }
  };

  return (
    <Card>
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      <ul className="mt-3 flex flex-col divide-y divide-ink/10">
        {list.data?.map((row) => (
          <li key={row.id} className="flex items-center justify-between py-2 text-sm">
            <span>
              {row.name}
              {extraField && row[extraField.name] !== undefined && <span className="text-muted"> · {String(row[extraField.name])}</span>}
            </span>
            <Button variant="ghost" className="min-h-9 px-2" onClick={() => remove.mutate(row.id)}>
              Delete<span className="sr-only"> {row.name}</span>
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={onAdd} className="mt-4 flex flex-col gap-3" noValidate>
        <TextField label={`New ${title.toLowerCase().replace(/s$/, '')}`} value={name} onChange={(e) => setName(e.target.value)} />
        {extraField && (
          <TextField label={extraField.label} type={extraField.type ?? 'text'} value={extra} onChange={(e) => setExtra(e.target.value)} />
        )}
        <Button type="submit" variant="secondary">
          Add
        </Button>
        {error && <ErrorNote>{error}</ErrorNote>}
      </form>
    </Card>
  );
}

function SkillsSection() {
  const [q, setQ] = useState('');
  const skills = useQuery({ queryKey: ['skills'], queryFn: () => api<Skill[]>('/skills'), staleTime: 300_000 });
  const all = skills.data ?? [];
  const t = q.trim().toLowerCase();
  const shown = t
    ? all.filter((s) => s.name.toLowerCase().includes(t) || s.synonyms.some((x) => x.toLowerCase().includes(t)))
    : all.slice(0, 40);
  return (
    <Card className="lg:col-span-3">
      <h2 className="font-display text-lg font-semibold">Skills taxonomy</h2>
      <p className="text-sm text-muted">
        {all.length} skills ({all.filter((s) => s.kind === 'tech').length} tech, {all.filter((s) => s.kind === 'non_tech').length}{' '}
        non-tech). Synonyms map short forms to one skill.
      </p>
      <div className="mt-3 max-w-sm">
        <TextField label="Search skills or synonyms" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      <ul className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {shown.map((s) => (
          <li key={s.id} className="rounded-xl bg-white/70 p-3 text-sm">
            <p className="font-semibold text-ink">{s.name}</p>
            <p className="text-xs text-muted">{s.category}</p>
            {s.synonyms.length > 0 && (
              <div className="mt-1 flex flex-wrap gap-1">
                {s.synonyms.slice(0, 4).map((syn) => (
                  <Chip key={syn}>{syn}</Chip>
                ))}
              </div>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** Fictional hiring companies (D-84). Real company names and real websites are refused by the server. */
function CompaniesSection() {
  const client = useQueryClient();
  const list = useQuery({ queryKey: ['companies'], queryFn: () => api<Company[]>('/companies') });
  const empty = { name: '', industry: '', headquarters: '', size: '', tagline: '', about: '', website: '' };
  const [values, setValues] = useState(empty);
  const [error, setError] = useState('');
  const remove = useMutation({
    mutationFn: (id: string) => api(`/companies/${id}`, { method: 'DELETE' }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['companies'] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Delete failed.'),
  });
  const onAdd = async (event: FormEvent) => {
    event.preventDefault();
    setError('');
    try {
      await api('/companies', { method: 'POST', body: values });
      setValues(empty);
      void client.invalidateQueries({ queryKey: ['companies'] });
    } catch (e) {
      setError(e instanceof ApiError ? (Object.values(e.fieldErrors)[0] ?? e.message) : 'Could not save.');
    }
  };
  const set = (key: keyof typeof empty) => ({
    value: values[key],
    onChange: (e: { target: { value: string } }) => setValues({ ...values, [key]: e.target.value }),
  });
  return (
    <Card className="lg:col-span-3">
      <h2 className="font-display text-lg font-semibold">Companies</h2>
      <p className="text-sm text-muted">Fictional companies only. Jobs show the company's story, benefits and hiring process.</p>
      <ul className="mt-3 grid gap-2 sm:grid-cols-2">
        {list.data?.map((c) => (
          <li key={c.id} className="flex items-start justify-between gap-3 rounded-xl bg-white/70 p-3 text-sm">
            <span className="flex items-start gap-3">
              <span
                aria-hidden="true"
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg font-semibold text-white"
                style={{ background: c.logo_color }}
              >
                {c.logo_initials}
              </span>
              <span>
                <span className="block font-semibold text-ink">{c.name}</span>
                <span className="text-xs text-muted">{[c.industry, c.headquarters].filter(Boolean).join(' · ')}</span>
              </span>
            </span>
            <Button variant="ghost" className="min-h-9 px-2" onClick={() => remove.mutate(c.id)}>
              Delete<span className="sr-only"> {c.name}</span>
            </Button>
          </li>
        ))}
      </ul>
      <form onSubmit={onAdd} className="mt-4 grid gap-3 md:grid-cols-3" noValidate>
        <TextField label="Company name" required {...set('name')} />
        <TextField label="Industry" {...set('industry')} />
        <TextField label="Headquarters" placeholder="Hyderabad, Telangana" {...set('headquarters')} />
        <TextField label="Size" placeholder="200 to 500 employees" {...set('size')} />
        <TextField label="Tagline" {...set('tagline')} />
        <TextField label="Website (placeholder)" placeholder="https://your-company.example" {...set('website')} />
        <div className="md:col-span-3">
          <TextAreaField label="About" rows={3} {...set('about')} />
        </div>
        <Button type="submit" variant="secondary" className="md:justify-self-start">
          Add company
        </Button>
        {error && (
          <div className="md:col-span-3">
            <ErrorNote>{error}</ErrorNote>
          </div>
        )}
      </form>
    </Card>
  );
}

export function OrgAdminPage() {
  useDocumentTitle('Organisation');
  return (
    <>
      <PageHeader title="Organisation" intro="Companies, departments, locations, job levels and the skills taxonomy used across jobs." />
      <div className="grid gap-4 lg:grid-cols-3">
        <OrgSection title="Departments" resource="departments" />
        <OrgSection title="Locations" resource="locations" extraField={{ name: 'country', label: 'Country' }} />
        <OrgSection title="Job levels" resource="job-levels" extraField={{ name: 'rank', label: 'Rank (number)', type: 'number' }} />
        <CompaniesSection />
        <SkillsSection />
      </div>
    </>
  );
}
