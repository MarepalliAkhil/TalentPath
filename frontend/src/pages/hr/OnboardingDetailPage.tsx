import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Checklist, FirstWeek, PersonCard } from '@/components/hr';
import { ErrorNote, PageHeader, PageLoader } from '@/components/ui';
import { api } from '@/lib/api';
import { useDocumentTitle } from '@/lib/hooks';
import { day, type Onboarding } from '@/lib/hr';

/** Manager, buddy or HR view of one joiner: tasks they own can be completed here. */
export function OnboardingDetailPage() {
  const { id = '' } = useParams();
  const query = useQuery({ queryKey: ['onboarding-detail', id], queryFn: () => api<Onboarding>(`/onboarding/${id}`) });
  useDocumentTitle(query.data ? `Onboarding: ${query.data.employee.name}` : 'Onboarding');
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <ErrorNote>We could not find this person’s onboarding.</ErrorNote>;
  const data = query.data;
  const e = data.employee;
  return (
    <>
      <PageHeader
        title={`Onboarding: ${e.name}`}
        intro={`${e.designation}, ${e.department} · ${e.code} · joins ${day(e.joined_on)}`}
        actions={
          <Link to="/onboarding" className="text-sm font-semibold text-primary-strong underline">
            All joiners
          </Link>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <PersonCard role="Reporting manager" person={data.manager} />
        <PersonCard role="Buddy" person={data.buddy} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        <Checklist data={data} queryKey={['onboarding-detail', id]} />
        {data.first_week.length > 0 && <FirstWeek plan={data.first_week} />}
      </div>
    </>
  );
}
