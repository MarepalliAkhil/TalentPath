import { canVisit, type Role } from './policy';

export type IconName =
  | 'home'
  | 'briefcase'
  | 'search'
  | 'bell'
  | 'users'
  | 'building'
  | 'shield'
  | 'mail'
  | 'layers'
  | 'scale'
  | 'calendar'
  | 'sparkle'
  | 'document'
  | 'sun'
  | 'clock'
  | 'check'
  | 'clipboard';

export interface NavItem {
  to: string;
  label: string;
  /** Route key in shared/policy.json that decides visibility. */
  route: string;
  icon: IconName;
  /** Optional narrowing for routes everyone may visit (e.g. the public job list). */
  only?: Role[];
}

export const NAV: NavItem[] = [
  { to: '/candidate', label: 'My applications', route: '/candidate', icon: 'briefcase' },
  { to: '/jobs', label: 'Browse jobs', route: '/jobs', icon: 'search', only: ['candidate'] },
  { to: '/recruiter', label: 'Overview', route: '/recruiter', icon: 'home' },
  { to: '/recruiter/jobs', label: 'My jobs', route: '/recruiter/jobs', icon: 'briefcase' },
  { to: '/manager', label: 'Overview', route: '/manager', icon: 'home' },
  { to: '/employee', label: 'Overview', route: '/employee', icon: 'home' },
  { to: '/admin', label: 'Overview', route: '/admin', icon: 'home' },
  { to: '/admin/jobs', label: 'All jobs', route: '/admin/jobs', icon: 'briefcase' },
  { to: '/offers', label: 'Offers', route: '/offers', icon: 'document' },
  { to: '/hira', label: 'HIRA activity', route: '/hira', icon: 'sparkle' },
  { to: '/interviews', label: 'My interviews', route: '/interviews', icon: 'calendar' },
  { to: '/leave', label: 'Leave', route: '/leave', icon: 'sun' },
  { to: '/leave/approvals', label: 'Approvals', route: '/leave/approvals', icon: 'check' },
  { to: '/team-calendar', label: 'Team calendar', route: '/team-calendar', icon: 'calendar' },
  { to: '/attendance', label: 'Attendance', route: '/attendance', icon: 'clock' },
  { to: '/onboarding', label: 'Onboarding', route: '/onboarding', icon: 'clipboard' },
  { to: '/hr/policies', label: 'Policies and holidays', route: '/hr/policies', icon: 'document' },
  { to: '/admin/staff', label: 'People', route: '/admin/staff', icon: 'users' },
  { to: '/admin/org', label: 'Organisation', route: '/admin/org', icon: 'building' },
  { to: '/admin/audit', label: 'Audit log', route: '/admin/audit', icon: 'shield' },
  { to: '/admin/outbox', label: 'Simulated emails', route: '/admin/outbox', icon: 'mail' },
  { to: '/admin/fairness', label: 'Fairness check', route: '/admin/fairness', icon: 'scale' },
  { to: '/admin/hr-settings', label: 'HR settings', route: '/admin/hr-settings', icon: 'building' },
  { to: '/notifications', label: 'Notifications', route: '/notifications', icon: 'bell' },
];

export function navFor(role: Role): NavItem[] {
  return NAV.filter((item) => canVisit(item.route, role) && (!item.only || item.only.includes(role)));
}
