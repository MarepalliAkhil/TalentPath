import policyJson from '@shared/policy.json';

export const ROLES = ['candidate', 'recruiter', 'manager', 'employee', 'hr', 'admin'] as const;
export type Role = (typeof ROLES)[number];
export type Principal = Role | 'anonymous';

const routes = policyJson.routes as Record<string, string[]>;
const dashboards = policyJson.dashboards as Record<Role, string>;

function expand(tokens: string[]): Principal[] {
  const out = new Set<Principal>();
  for (const token of tokens) {
    if (token === 'any') {
      ROLES.forEach((r) => out.add(r));
      out.add('anonymous');
    } else if (token === 'authenticated') {
      ROLES.forEach((r) => out.add(r));
    } else {
      out.add(token as Principal);
    }
  }
  return [...out];
}

/** Deny by default: a route that is not in shared/policy.json is not visitable. */
export function canVisit(route: string, role: Role | null): boolean {
  const tokens = routes[route];
  if (!tokens) return false;
  return expand(tokens).includes(role ?? 'anonymous');
}

export function dashboardFor(role: Role): string {
  return dashboards[role] ?? '/';
}

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && (ROLES as readonly string[]).includes(value);
}
