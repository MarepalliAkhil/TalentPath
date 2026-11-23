/** Week 3B types and helpers: onboarding, leave, team calendar, attendance, HR settings. */

export interface PersonRef {
  id: string;
  name: string;
  designation: string;
  department: string;
  email: string;
}

export interface OnboardingTask {
  id: string;
  title: string;
  description: string;
  category: string;
  category_label: string;
  owner_kind: string;
  owner_label: string;
  owner_name: string;
  kind: 'task' | 'upload' | 'acknowledge';
  due_on: string;
  done: boolean;
  done_at: string | null;
  done_by: string | null;
  has_document: boolean;
  can_complete: boolean;
  overdue: boolean;
}

export interface Onboarding {
  employee: {
    id: string;
    code: string;
    name: string;
    designation: string;
    department: string;
    location: string;
    joined_on: string;
    status: 'onboarding' | 'active';
  };
  manager: PersonRef | null;
  buddy: PersonRef | null;
  progress: { done: number; total: number; percent: number };
  tasks: OnboardingTask[];
  first_week: { day: string; starts: string; title: string; host: string }[];
  welcome_pending: boolean;
}

export interface OnboardingRow {
  id: string;
  code: string;
  name: string;
  designation: string;
  department: string;
  joined_on: string;
  status: string;
  manager: string | null;
  buddy: string | null;
  progress: { done: number; total: number; percent: number };
  overdue: number;
  relationship: 'hr' | 'manager' | 'buddy';
}

export interface Balance {
  type: string;
  name: string;
  unpaid: boolean;
  balance: number | null;
  pending: number;
  taken: number;
  available: number | null;
  /** Booked for a later month against accruals not credited yet. */
  booked_ahead?: number;
}

export interface LeaveTypeInfo {
  code: string;
  name: string;
  half_day_allowed: boolean;
  unpaid: boolean;
  min_notice_days: number;
  document_after_days: number | null;
}

export interface Balances {
  year: number;
  balances: Balance[];
  types: LeaveTypeInfo[];
  hr_approval_over_days: number;
}

export interface DayRow {
  date: string;
  kind: 'working' | 'weekly_off' | 'holiday' | 'sandwich';
  counted: number;
  label: string;
}

export interface LeaveCheck {
  days: number;
  days_label: string;
  breakdown: DayRow[];
  errors: Record<string, string>;
  warnings: string[];
  needs_document: boolean;
  needs_hr_approval: boolean;
  available: number | null;
  ok: boolean;
}

export interface LeaveRequest {
  id: string;
  employee: { id: string; name: string; code: string };
  leave_type: string;
  leave_type_name: string;
  start: string;
  end: string;
  half: '' | 'first' | 'second';
  days: number;
  days_label: string;
  status: 'pending' | 'approved' | 'rejected' | 'cancelled';
  status_label: string;
  stage: string;
  approver: string | null;
  delegated: boolean;
  escalated: boolean;
  reason: string | null;
  has_document: boolean;
  decision_note: string | null;
  created_at: string;
  can_cancel: boolean;
  can_act: boolean;
  warnings?: string[];
  timeline?: { action: string; detail: string; actor: string; at: string }[];
}

export interface Regularisation {
  id: string;
  employee: { id: string; name: string };
  date: string;
  check_in: string;
  check_out: string;
  mode: string;
  reason: string | null;
  status: string;
  status_label: string;
  approver: string;
  decision_note: string;
  can_decide: boolean;
}

export interface Approvals {
  leave: LeaveRequest[];
  regularisations: Regularisation[];
  needs_attention: LeaveRequest[];
}

export interface TeamCalendar {
  month: string;
  team: { name: string; members: { id: string; name: string; designation: string }[] };
  sees_reasons: boolean;
  threshold_pct: number;
  days: { date: string; kind: 'working' | 'weekly_off' | 'holiday'; holiday: string }[];
  entries: {
    id: string;
    employee: string;
    name: string;
    start: string;
    end: string;
    half: string;
    status: 'pending' | 'approved';
    type: string | null;
    reason: string | null;
  }[];
  joiners: { name: string; joined_on: string; designation: string }[];
  has_reports: boolean;
  me: string | null;
}

export interface AttendanceDay {
  date: string;
  status: 'present' | 'leave' | 'absent' | 'today' | 'weekly_off' | 'holiday' | 'working';
  holiday: string;
  check_in: string | null;
  check_out: string | null;
  mode: string | null;
  late: boolean;
  early: boolean;
  missing_checkout: boolean;
  regularised: boolean;
}

export interface AttendanceCounts {
  working_days: number;
  present: number;
  office: number;
  remote: number;
  late: number;
  early: number;
  missing_checkout: number;
  on_leave: number;
  holidays: number;
  absent: number;
}

export interface AttendanceMe {
  today: { date: string; check_in: string | null; check_out: string | null; mode: string; late: boolean; early: boolean } | null;
  shift: { start: string; end: string; late_grace_minutes: number; early_grace_minutes: number; location: string };
  summary: { month: string; counts: AttendanceCounts; days: AttendanceDay[] };
  regularisations: Regularisation[];
}

export interface AttendanceTeam {
  month: string;
  scope: 'all' | 'reports';
  rows: ({ employee: string; name: string; code: string; department: string } & AttendanceCounts)[];
}

export interface LeaveTypeConfig {
  id: string;
  location: string;
  location_name: string;
  code: string;
  name: string;
  yearly_quota: number;
  monthly_accrual: boolean;
  prorate_joiners: boolean;
  carry_forward_cap: number;
  min_notice_days: number;
  backdate_days: number;
  max_consecutive_days: number | null;
  half_day_allowed: boolean;
  document_after_days: number | null;
  sandwich_rule: boolean;
  unpaid: boolean;
  active: boolean;
  summary: string;
}

export interface Holiday {
  id: string;
  date: string;
  name: string;
  regional: boolean;
  note: string;
  location?: string;
}

export interface WorkPolicy {
  location: string;
  location_name: string;
  shift_start: string;
  shift_end: string;
  late_grace_minutes: number;
  early_grace_minutes: number;
  weekly_off: number[];
  hr_approval_over_days: number;
  min_team_available_pct: number;
  escalate_after_hours: number;
  /** Week 4A: when an internal applicant's reporting manager is told. */
  internal_manager_notice?: 'interview' | 'offer';
}

export interface Policies {
  handbook: { slug: string; title: string; body: string }[];
  location: { id: string; name: string } | null;
  leave_types: LeaveTypeConfig[];
  holidays: Holiday[];
  work_policy: WorkPolicy | null;
}

export interface HrConfig {
  locations: { id: string; name: string }[];
  leave_types: LeaveTypeConfig[];
  work_policies: WorkPolicy[];
  holidays: Holiday[];
  codes: { code: string; label: string }[];
}

export type HrCard =
  | { kind: 'balances'; rows: Balances['balances'] }
  | { kind: 'leave_confirm'; payload: { leave_type: string; start: string; end: string; half: string; reason: string }; check: LeaveCheck; type_name: string }
  | { kind: 'holidays'; rows: { date: string; name: string; regional: boolean }[]; note: string }
  | { kind: 'person'; name: string; designation: string; role: string; email: string }
  | { kind: 'checklist'; progress: { done: number; total: number; percent: number }; rows: { title: string; due_on: string; done: boolean; owner: string }[] }
  | { kind: 'attendance'; counts: Record<string, number>; month: string }
  | { kind: 'pending'; rows: { kind: string; name: string; detail: string; escalated: boolean }[] }
  | { kind: 'source'; title: string; link: string };

export interface Attention {
  leave: LeaveRequest[];
  overdue_tasks: { employee: string; name: string; title: string; due_on: string }[];
  no_buddy: { employee: string; name: string }[];
}

const WD = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const MONTH = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

/** "Mon 8 Dec 2026" from an ISO date: same wording as the server, no time-zone drift. */
export function day(iso: string, withYear = true): string {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number);
  const dow = new Date(Date.UTC(y, m - 1, d)).getUTCDay();
  return `${WD[dow]} ${d} ${MON[m - 1]}${withYear ? ` ${y}` : ''}`;
}

export function dateRange(start: string, end: string, half = ''): string {
  const halfLabel = half === 'first' ? ' (first half)' : half === 'second' ? ' (second half)' : '';
  return start === end ? `${day(start)}${halfLabel}` : `${day(start, false)} to ${day(end)}`;
}

export function daysLabel(n: number | null): string {
  if (n === null) return 'No limit';
  return `${n} ${n === 1 ? 'day' : 'days'}`;
}

export function monthLabel(month: string): string {
  const [y, m] = month.split('-').map(Number);
  return `${MONTH[m - 1]} ${y}`;
}

export function shiftMonth(month: string, delta: number): string {
  const [y, m] = month.split('-').map(Number);
  const total = y * 12 + (m - 1) + delta;
  return `${Math.floor(total / 12)}-${String((total % 12) + 1).padStart(2, '0')}`;
}

export function thisMonth(): string {
  const now = new Date(Date.now() + 330 * 60_000); // IST
  return now.toISOString().slice(0, 7);
}

export function todayIso(): string {
  return new Date(Date.now() + 330 * 60_000).toISOString().slice(0, 10);
}

export const LEAVE_STATUS_STYLE: Record<string, string> = {
  pending: 'bg-warning-soft text-warning',
  approved: 'bg-success-soft text-success',
  rejected: 'bg-danger-soft text-danger',
  cancelled: 'bg-canvas-deep text-muted',
};

export const WEEKDAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
