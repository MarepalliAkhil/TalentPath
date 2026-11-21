import { describe, expect, it } from 'vitest';
import { navFor } from './nav';
import { EXPECTED_NAV } from '@/test/fixtures';
import { canVisit, dashboardFor, ROLES } from './policy';

describe('policy-driven routing', () => {
  it('sends every role to its own dashboard', () => {
    expect(dashboardFor('candidate')).toBe('/candidate');
    expect(dashboardFor('recruiter')).toBe('/recruiter');
    expect(dashboardFor('hiring_manager')).toBe('/manager');
    expect(dashboardFor('employee')).toBe('/employee');
    expect(dashboardFor('hr_admin')).toBe('/admin');
  });

  it('isolates role areas and denies unknown routes', () => {
    expect(canVisit('/admin', 'hr_admin')).toBe(true);
    expect(canVisit('/admin', 'recruiter')).toBe(false);
    expect(canVisit('/candidate', 'employee')).toBe(false);
    expect(canVisit('/jobs/:slug/apply', 'recruiter')).toBe(false);
    expect(canVisit('/profile', null)).toBe(false);
    expect(canVisit('/jobs', null)).toBe(true);
    expect(canVisit('/not-in-policy', 'hr_admin')).toBe(false);
  });

  it('builds the sidebar per role from the policy', () => {
    for (const role of ROLES) {
      expect(navFor(role).map((item) => item.label)).toEqual(EXPECTED_NAV[role]);
    }
  });
});
