import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useAuth } from '@/auth/AuthContext';
import { Button, Card, ErrorNote, PageHeader, PageLoader, Pager, SelectField, SuccessNote, TextField } from '@/components/ui';
import { api, ApiError, qs } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { staffSchema, validate, type Errors } from '@/lib/schemas';
import type { Paginated, User } from '@/lib/types';

const ROLE_OPTIONS = [
  { value: 'recruiter', label: 'Recruiter' },
  { value: 'hiring_manager', label: 'Hiring manager' },
  { value: 'employee', label: 'Employee' },
  { value: 'hr_admin', label: 'HR admin' },
];

export function StaffAdminPage() {
  useDocumentTitle('People');
  const { user: me } = useAuth();
  const client = useQueryClient();
  const [role, setRole] = useState('');
  const [page, setPage] = useState(1);
  const [values, setValues] = useState({ full_name: '', email: '', role: 'recruiter' });
  const [errors, setErrors] = useState<Errors>({});
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const users = useQuery({
    queryKey: ['users', role, page],
    queryFn: () => api<Paginated<User>>(`/users${qs({ role, page })}`),
  });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: Partial<User> }) => api<User>(`/users/${id}`, { method: 'PATCH', body }),
    onSuccess: () => void client.invalidateQueries({ queryKey: ['users'] }),
    onError: (e) => setError(e instanceof ApiError ? e.message : 'Update failed.'),
  });

  const onCreate = async (event: FormEvent) => {
    event.preventDefault();
    setMessage('');
    setError('');
    const { data, errors: found } = validate(staffSchema, values);
    setErrors(found);
    if (!data) return;
    try {
      const created = await api<User>('/users', { method: 'POST', body: data });
      setMessage(`${created.full_name} was invited. A set-password email is in the outbox.`);
      setValues({ full_name: '', email: '', role: 'recruiter' });
      void client.invalidateQueries({ queryKey: ['users'] });
    } catch (e) {
      if (e instanceof ApiError) {
        setErrors(e.fieldErrors);
        setError(e.message);
      }
    }
  };

  return (
    <>
      <PageHeader title="People" intro="Create staff accounts and manage roles. Candidates register themselves." />
      <Card className="mb-6">
        <h2 className="font-display text-lg font-semibold">Invite a staff member</h2>
        <form onSubmit={onCreate} noValidate className="mt-4 grid gap-4 md:grid-cols-4 md:items-end">
          <TextField label="Full name" value={values.full_name} error={errors.full_name} onChange={(e) => setValues({ ...values, full_name: e.target.value })} required />
          <TextField label="Work email" type="email" value={values.email} error={errors.email} onChange={(e) => setValues({ ...values, email: e.target.value })} required />
          <SelectField label="Role" value={values.role} error={errors.role} onChange={(e) => setValues({ ...values, role: e.target.value })}>
            {ROLE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </SelectField>
          <Button type="submit">Send invite</Button>
        </form>
        <div className="mt-3">
          {message && <SuccessNote>{message}</SuccessNote>}
          {error && <ErrorNote>{error}</ErrorNote>}
        </div>
      </Card>

      <div className="mb-3 max-w-xs">
        <SelectField label="Show" value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
          <option value="">Everyone</option>
          <option value="candidate">Candidates</option>
          {ROLE_OPTIONS.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}s
            </option>
          ))}
        </SelectField>
      </div>
      {users.isPending && <PageLoader />}
      <div className="glass overflow-x-auto rounded-xl2">
        <table className="w-full min-w-[40rem] text-left text-sm">
          <caption className="sr-only">User accounts</caption>
          <thead className="text-muted">
            <tr>
              <th scope="col" className="px-4 py-3 font-medium">Name</th>
              <th scope="col" className="px-4 py-3 font-medium">Email</th>
              <th scope="col" className="px-4 py-3 font-medium">Role</th>
              <th scope="col" className="px-4 py-3 font-medium">Status</th>
            </tr>
          </thead>
          <tbody>
            {users.data?.results.map((u) => (
              <tr key={u.id} className="border-t border-ink/10">
                <td className="px-4 py-3 font-medium text-ink">{u.full_name}</td>
                <td className="px-4 py-3 text-ink-soft">{u.email}</td>
                <td className="px-4 py-3">{u.role_label}</td>
                <td className="px-4 py-3">
                  {u.id === me?.id ? (
                    <span className="text-muted">You</span>
                  ) : (
                    <Button variant="ghost" className="min-h-9 px-2" onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}>
                      {u.is_active ? 'Deactivate' : 'Activate'}
                      <span className="sr-only"> {u.full_name}</span>
                    </Button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Pager page={page} hasNext={Boolean(users.data?.next)} hasPrevious={Boolean(users.data?.previous)} onChange={setPage} />
    </>
  );
}
