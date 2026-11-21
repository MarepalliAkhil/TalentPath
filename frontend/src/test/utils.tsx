import type { ReactElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render } from '@testing-library/react';
import axe from 'axe-core';
import { MemoryRouter } from 'react-router-dom';
import { vi } from 'vitest';
import { AppRoutes } from '@/App';
import { AuthContext, type AuthValue } from '@/auth/AuthContext';
import { dashboardFor, type Role } from '@/lib/policy';
import type { User } from '@/lib/types';

export function fakeUser(role: Role): User {
  const labels: Record<Role, string> = {
    candidate: 'Candidate',
    recruiter: 'Recruiter',
    hiring_manager: 'Hiring manager',
    employee: 'Employee',
    hr_admin: 'HR admin',
  };
  return {
    id: `00000000-0000-4000-8000-00000000000${role.length % 10}`,
    email: `${role}@demo.example`,
    full_name: 'Asha Verma',
    role,
    role_label: labels[role],
    dashboard: dashboardFor(role),
    is_active: true,
  };
}

/** Stub fetch with a map of "/api/path?query" prefixes to JSON bodies. */
export function mockApi(routes: Record<string, unknown>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.pathname + input.search : input.url;
    const path = url.split('?')[0];
    const key = Object.keys(routes).find((candidate) => candidate === path);
    if (!key) return new Response(JSON.stringify({ detail: 'Not found' }), { status: 404, headers: { 'content-type': 'application/json' } });
    return new Response(JSON.stringify(routes[key]), { status: 200, headers: { 'content-type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

export function renderApp(route: string, role: Role | null = null, overrides: Partial<AuthValue> = {}) {
  const user = role ? fakeUser(role) : null;
  const auth: AuthValue = {
    user,
    loading: false,
    signedOut: false,
    login: vi.fn(async () => user ?? fakeUser('candidate')),
    register: vi.fn(async () => fakeUser('candidate')),
    logout: vi.fn(async () => undefined),
    ...overrides,
  };
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <AuthContext.Provider value={auth}>
          <AppRoutes />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

export function renderWith(ui: ReactElement) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

export function setViewport(width: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value: width });
}

export async function axeViolations(node: Element = document.body) {
  const result = await axe.run(node, {
    rules: {
      // jsdom has no layout engine, so contrast is checked in Playwright instead.
      'color-contrast': { enabled: false },
    },
  });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`);
}
