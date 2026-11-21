import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { PageLoader } from '@/components/ui';
import { canVisit } from '@/lib/policy';
import { useAuth } from './AuthContext';

/** Route guard driven by shared/policy.json "routes". The API enforces the same rules. */
export function RequireRole({ route, children }: { route: string; children: ReactNode }) {
  const { user, loading, signedOut } = useAuth();
  const location = useLocation();
  if (loading) return <PageLoader />;
  if (!user) {
    const next = encodeURIComponent(location.pathname + location.search);
    return <Navigate to={signedOut ? '/login' : `/login?next=${next}`} replace />;
  }
  if (!canVisit(route, user.role)) return <Navigate to={user.dashboard} replace />;
  return <>{children}</>;
}
