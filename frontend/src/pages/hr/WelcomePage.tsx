import { useEffect } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Checklist, FirstWeek, PersonCard } from '@/components/hr';
import { EmptyState, PageHeader, PageLoader } from '@/components/ui';
import { api, ApiError } from '@/lib/api';
import { brand } from '@/lib/brand';
import { firstName } from '@/lib/format';
import { useDocumentTitle } from '@/lib/hooks';
import { day, type Onboarding } from '@/lib/hr';

/** First login after one-click hire: checklist, buddy, manager and the first-week plan. */
export function WelcomePage() {
  useDocumentTitle('Welcome');
  const query = useQuery({ queryKey: ['onboarding-me'], queryFn: () => api<Onboarding>('/onboarding/me'), retry: false });
  const seen = useMutation({ mutationFn: () => api('/onboarding/me', { method: 'POST', body: {} }) });
  const pending = query.data?.welcome_pending;
  const { mutate } = seen;
  useEffect(() => {
    if (pending) mutate();
  }, [pending, mutate]);

  if (query.isPending) return <PageLoader />;
  if (query.isError) {
    const missing = query.error instanceof ApiError && query.error.status === 404;
    return (
      <>
        <PageHeader title="Welcome" />
        <EmptyState title={missing ? 'No employee record yet' : 'We could not load your onboarding'}>
          {missing ? 'HR creates it when you are hired.' : 'Please refresh the page.'}
        </EmptyState>
      </>
    );
  }
  const data = query.data;
  const e = data.employee;
  return (
    <>
      <PageHeader
        title={`Welcome to ${brand.employerName}, ${firstName(e.name)}`}
        intro={
          <>
            {e.designation}, {e.department} · {e.location}. Employee ID <strong className="text-ink">{e.code}</strong>. Your first day is{' '}
            <strong className="text-ink">{day(e.joined_on)}</strong>.
          </>
        }
      />
      <div className="mb-6 grid gap-4 sm:grid-cols-2">
        <PersonCard role="Reporting manager" person={data.manager} />
        <PersonCard role="Your buddy" person={data.buddy} />
      </div>
      <div className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        {data.tasks.length ? <Checklist data={data} queryKey={['onboarding-me']} /> : <EmptyState title="No checklist">Nothing to do here.</EmptyState>}
        <div className="flex flex-col gap-6">
          {data.first_week.length > 0 && <FirstWeek plan={data.first_week} />}
          <section className="glass rounded-xl2 p-5" aria-labelledby="next-heading">
            <h2 id="next-heading" className="font-display text-xl font-semibold text-ink">
              Good to know
            </h2>
            <ul className="mt-2 space-y-1 text-sm">
              <li>
                <Link to="/hr/policies" className="font-semibold text-primary-strong underline">
                  Policies and holidays
                </Link>
              </li>
              <li>
                <Link to="/leave" className="font-semibold text-primary-strong underline">
                  Your leave balance
                </Link>
              </li>
              <li>
                <Link to="/attendance" className="font-semibold text-primary-strong underline">
                  Check in and out
                </Link>
              </li>
            </ul>
            <p className="mt-2 text-sm text-muted">You can also ask HIRA, bottom right: “who is my buddy?” or “leave balance”.</p>
          </section>
        </div>
      </div>
    </>
  );
}
