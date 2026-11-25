import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';
import {
  Button,
  Card,
  ErrorNote,
  PageHeader,
  PageLoader,
  Pager,
  SelectField,
  SuccessNote,
  TextAreaField,
  TextField,
} from '@/components/ui';
import { api, ApiError, qs } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { errorText } from '@/lib/pipeline';
import { staffSchema, validate, type Errors } from '@/lib/schemas';
import type { AdminUser, CompanyBrief, Department, Location, Paginated } from '@/lib/types';

const ROLE_OPTIONS = [
  { value: 'recruiter', label: 'Recruiter' },
  { value: 'manager', label: 'Manager' },
  { value: 'employee', label: 'Employee' },
  { value: 'hr', label: 'HR' },
];

function useLists() {
  const departments = useQuery({ queryKey: ['departments'], queryFn: () => api<Department[]>('/departments') });
  const locations = useQuery({ queryKey: ['locations'], queryFn: () => api<Location[]>('/locations') });
  const companies = useQuery({ queryKey: ['companies'], queryFn: () => api<CompanyBrief[]>('/companies') });
  const managers = useQuery({
    queryKey: ['users', 'managers'],
    queryFn: () => api<Paginated<AdminUser>>(`/users${qs({ has_employee: 1, active: 1, page_size: 200 })}`),
  });
  const managerOptions = (managers.data?.results ?? []).filter((u) => u.employee);
  return {
    departments: departments.data ?? [],
    locations: locations.data ?? [],
    companies: companies.data ?? [],
    managers: managerOptions,
  };
}

function InviteCard() {
  const client = useQueryClient();
  const lists = useLists();
  const [values, setValues] = useState({ full_name: '', email: '', role: 'recruiter' });
  const [withRecord, setWithRecord] = useState(true);
  const [emp, setEmp] = useState({ department: '', location: '', designation: '', joined_on: '', manager: '', company: '' });
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    setError('');
    const { data, errors: found } = validate(staffSchema, values);
    setErrors(found);
    if (!data) return;
    const employee = withRecord ? { ...emp, manager: emp.manager || null, company: emp.company || null } : null;
    try {
      const created = await api<AdminUser>('/users', { method: 'POST', body: { ...data, employee } });
      setMessage(`${created.full_name} was invited. The set-password email is in the email log.`);
      setValues({ full_name: '', email: '', role: 'recruiter' });
      void client.invalidateQueries({ queryKey: ['users'] });
    } catch (e) {
      if (e instanceof ApiError) {
        setErrors(e.fieldErrors);
        setError(e.message);
      } else {
        setError('Could not create the account.');
      }
    }
  };

  return (
    <Card className="mb-6">
      <h2 className="font-display text-lg font-semibold">Add a staff member</h2>
      <p className="mt-1 text-sm text-muted">They get an email to set their password. Candidates register themselves.</p>
      <form onSubmit={onCreate} noValidate className="mt-4 grid gap-4 md:grid-cols-3 md:items-end">
        <TextField
          label="Full legal name"
          value={values.full_name}
          error={errors.full_name}
          onChange={(e) => setValues({ ...values, full_name: e.target.value })}
          required
        />
        <TextField
          label="Work email"
          type="email"
          value={values.email}
          error={errors.email}
          onChange={(e) => setValues({ ...values, email: e.target.value })}
          required
        />
        <SelectField label="Role" value={values.role} error={errors.role} onChange={(e) => setValues({ ...values, role: e.target.value })}>
          {ROLE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </SelectField>
        <label className="flex items-center gap-2 text-sm text-ink md:col-span-3">
          <input type="checkbox" className="h-4 w-4" checked={withRecord} onChange={(e) => setWithRecord(e.target.checked)} />
          Also create their employee record (ID, department, reporting manager)
        </label>
        {withRecord && (
          <>
            <SelectField
              label="Department"
              value={emp.department}
              error={errors.employee}
              onChange={(e) => setEmp({ ...emp, department: e.target.value })}
            >
              <option value="">Choose…</option>
              {lists.departments.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name}
                </option>
              ))}
            </SelectField>
            <SelectField label="Location" value={emp.location} onChange={(e) => setEmp({ ...emp, location: e.target.value })}>
              <option value="">Choose…</option>
              {lists.locations.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </SelectField>
            <TextField label="Designation" value={emp.designation} onChange={(e) => setEmp({ ...emp, designation: e.target.value })} />
            <TextField
              label="Joining date"
              type="date"
              value={emp.joined_on}
              onChange={(e) => setEmp({ ...emp, joined_on: e.target.value })}
            />
            <SelectField label="Reporting manager" value={emp.manager} onChange={(e) => setEmp({ ...emp, manager: e.target.value })}>
              <option value="">Nobody yet</option>
              {lists.managers.map((m) => (
                <option key={m.id} value={m.employee?.id}>
                  {m.full_name} ({m.role_label})
                </option>
              ))}
            </SelectField>
            <SelectField label="Company" value={emp.company} onChange={(e) => setEmp({ ...emp, company: e.target.value })}>
              <option value="">Not set</option>
              {lists.companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SelectField>
          </>
        )}
        <Button type="submit" className="md:col-span-3 md:justify-self-start">
          Send invite
        </Button>
      </form>
      <div className="mt-3">
        {message && <SuccessNote>{message}</SuccessNote>}
        {error && <ErrorNote>{error}</ErrorNote>}
      </div>
    </Card>
  );
}

/** Change one person (D-80, D-81). Locked fields and roles need a reason; every change is audited. */
function EditPerson({ person, onClose }: { person: AdminUser; onClose: () => void }) {
  const client = useQueryClient();
  const { user: me } = useAuth();
  const lists = useLists();
  const detail = useQuery({ queryKey: ['users', person.id], queryFn: () => api<AdminUser>(`/users/${person.id}`) });
  const [role, setRole] = useState(person.role);
  const [manager, setManager] = useState(person.employee?.manager?.id ?? '');
  const [company, setCompany] = useState(person.employee?.company?.id ?? '');
  const [locked, setLocked] = useState({ full_name: '', email: '', date_of_birth: '', employee_code: '', joined_on: '' });
  const [reason, setReason] = useState('');
  const [done, setDone] = useState('');
  const save = useMutation({
    mutationFn: (body: Record<string, unknown>) => api<AdminUser>(`/users/${person.id}`, { method: 'PATCH', body }),
    onSuccess: () => {
      setDone('Saved. The change is in the audit log and the person was told.');
      void client.invalidateQueries({ queryKey: ['users'] });
    },
  });
  const isStaff = person.role !== 'candidate' && person.role !== 'admin';

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setDone('');
    const body: Record<string, unknown> = {};
    if (isStaff && role !== person.role) body.role = role;
    if (person.employee) {
      if (manager !== (person.employee.manager?.id ?? '')) body.manager = manager || null;
      if (company !== (person.employee.company?.id ?? '')) body.company = company || null;
    }
    for (const [key, value] of Object.entries(locked)) if (value.trim()) body[key] = value.trim();
    if (reason.trim()) body.reason = reason.trim();
    save.mutate(body);
  };

  return (
    <Card className="mt-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="font-display text-lg font-semibold">Edit {person.full_name}</h2>
          <p className="text-sm text-muted">
            {person.email} · {person.role_label}
            {person.employee ? ` · ${person.employee.code}` : ''}
            {detail.data?.date_of_birth ? ` · born ${detail.data.date_of_birth}` : ''}
          </p>
        </div>
        <Button variant="ghost" onClick={onClose}>
          Close
        </Button>
      </div>
      <form onSubmit={submit} className="mt-4 grid gap-4 md:grid-cols-2">
        {isStaff && (
          <SelectField
            label="Role"
            value={role}
            onChange={(e) => setRole(e.target.value as AdminUser['role'])}
            hint="Changing a role needs a reason."
          >
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </SelectField>
        )}
        {person.employee && (
          <>
            <SelectField label="Reporting manager" value={manager} onChange={(e) => setManager(e.target.value)}>
              <option value="">Nobody</option>
              {lists.managers
                .filter((m) => m.id !== person.id)
                .map((m) => (
                  <option key={m.id} value={m.employee?.id}>
                    {m.full_name} ({m.role_label})
                  </option>
                ))}
            </SelectField>
            <SelectField label="Company" value={company} onChange={(e) => setCompany(e.target.value)}>
              <option value="">Not set</option>
              {lists.companies.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </SelectField>
          </>
        )}
        <fieldset className="grid gap-4 rounded-xl border border-ink/10 p-3 md:col-span-2 md:grid-cols-2">
          <legend className="px-1 text-sm font-semibold text-ink">Correct locked fields (leave empty to keep)</legend>
          <TextField
            label="New full legal name"
            value={locked.full_name}
            onChange={(e) => setLocked({ ...locked, full_name: e.target.value })}
          />
          <TextField
            label="New email"
            type="email"
            value={locked.email}
            onChange={(e) => setLocked({ ...locked, email: e.target.value })}
          />
          {person.role !== 'candidate' && (
            <TextField
              label="New date of birth"
              type="date"
              value={locked.date_of_birth}
              onChange={(e) => setLocked({ ...locked, date_of_birth: e.target.value })}
            />
          )}
          {person.employee && (
            <>
              <TextField
                label="New employee ID"
                value={locked.employee_code}
                placeholder="LW1234"
                onChange={(e) => setLocked({ ...locked, employee_code: e.target.value })}
              />
              <TextField
                label="New joining date"
                type="date"
                value={locked.joined_on}
                onChange={(e) => setLocked({ ...locked, joined_on: e.target.value })}
              />
            </>
          )}
        </fieldset>
        <div className="md:col-span-2">
          <TextAreaField
            label="Reason"
            rows={2}
            hint="Required for role and locked-field changes (at least 10 characters). It goes into the audit log."
            value={reason}
            onChange={(e) => setReason(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2 md:col-span-2">
          <Button type="submit" disabled={save.isPending}>
            Save changes
          </Button>
          {person.id !== me?.id && (
            <Button variant={person.is_active ? 'danger' : 'secondary'} onClick={() => save.mutate({ is_active: !person.is_active })}>
              {person.is_active ? 'Deactivate account' : 'Reactivate account'}
            </Button>
          )}
        </div>
        <div className="md:col-span-2">
          {done && <SuccessNote>{done}</SuccessNote>}
          {save.isError && <ErrorNote>{errorText(save.error)}</ErrorNote>}
        </div>
      </form>
      <p className="mt-3 text-xs text-muted">People are never deleted: deactivated accounts keep their history and cannot sign in.</p>
    </Card>
  );
}

export function StaffAdminPage() {
  useDocumentTitle('People');
  const [role, setRole] = useState('');
  const [active, setActive] = useState('');
  const [q, setQ] = useState('');
  const [page, setPage] = useState(1);
  const [editing, setEditing] = useState<AdminUser | null>(null);

  const users = useQuery({
    queryKey: ['users', role, active, q, page],
    queryFn: () => api<Paginated<AdminUser>>(`/users${qs({ role, active, q, page })}`),
  });

  return (
    <>
      <PageHeader title="People" intro="Create staff accounts, assign roles and reporting managers, and correct locked details." />
      <InviteCard />
      <div className="mb-3 grid max-w-3xl gap-3 sm:grid-cols-3">
        <SelectField
          label="Role"
          value={role}
          onChange={(e) => {
            setRole(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Everyone</option>
          <option value="candidate">Candidates</option>
          {ROLE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
          <option value="admin">Admins</option>
        </SelectField>
        <SelectField
          label="Status"
          value={active}
          onChange={(e) => {
            setActive(e.target.value);
            setPage(1);
          }}
        >
          <option value="">Active and deactivated</option>
          <option value="1">Active</option>
          <option value="0">Deactivated</option>
        </SelectField>
        <TextField
          label="Search"
          type="search"
          value={q}
          onChange={(e) => {
            setQ(e.target.value);
            setPage(1);
          }}
        />
      </div>
      {users.isPending && <PageLoader />}
      <div className="glass overflow-x-auto rounded-xl2">
        <table className="w-full min-w-[44rem] text-left text-sm">
          <caption className="sr-only">Accounts</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">
                Name
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Role
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Reports to
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                Status
              </th>
              <th scope="col" className="px-4 py-3 font-medium">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {users.data?.results.map((u) => (
              <tr key={u.id} className="border-t border-ink/10">
                <td className="px-4 py-3">
                  <span className="font-medium text-ink">{u.full_name}</span>
                  <span className="block text-xs text-muted">{u.email}</span>
                </td>
                <td className="px-4 py-3">{u.role_label}</td>
                <td className="px-4 py-3 text-ink-soft">{u.employee?.manager?.name ?? '—'}</td>
                <td className="px-4 py-3">{u.is_active ? 'Active' : 'Deactivated'}</td>
                <td className="px-4 py-3 text-right">
                  <Button variant="ghost" className="min-h-9 px-2" onClick={() => setEditing(u)}>
                    Edit<span className="sr-only"> {u.full_name}</span>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} hasNext={Boolean(users.data?.next)} hasPrevious={Boolean(users.data?.previous)} onChange={setPage} />
      {editing && <EditPerson key={editing.id} person={editing} onClose={() => setEditing(null)} />}
    </>
  );
}
