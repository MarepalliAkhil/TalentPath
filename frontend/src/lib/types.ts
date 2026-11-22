import type { Role } from './policy';
import type { HrCard } from './hr';

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  role_label: string;
  dashboard: string;
  is_active: boolean;
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface SkillRef {
  id: string;
  name: string;
  slug: string;
}

export interface Seo {
  title: string;
  description: string;
  canonical: string;
  json_ld: Record<string, unknown>;
}

export interface PublicJob {
  slug: string;
  title: string;
  department: { name: string; slug: string };
  location: { name: string; slug: string; country: string };
  level: string;
  work_mode: 'onsite' | 'hybrid' | 'remote';
  work_mode_label: string;
  employment_type: string;
  employment_type_label: string;
  openings: number;
  published_at: string | null;
  required_skills: SkillRef[];
  nice_to_have_skills: SkillRef[];
  excerpt: string;
  description?: string;
  seo?: Seo;
}

export interface Ref {
  id: string;
  name: string;
}

export interface StaffJob {
  id: string;
  slug: string;
  title: string;
  department: Ref;
  location: Ref;
  level: Ref;
  work_mode: string;
  work_mode_label: string;
  employment_type: string;
  description: string;
  required_skills: SkillRef[];
  nice_to_have_skills: SkillRef[];
  openings: number;
  status: 'draft' | 'open' | 'closed';
  status_label: string;
  created_by: Ref;
  hiring_manager: Ref | null;
  blind_screening: boolean;
  reveal_stage: 'interview' | 'offer';
  application_count: number | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
}

export interface AppEvent {
  to_status: string;
  label: string;
  at: string;
}

export interface CandidateApplication {
  id: string;
  status: string;
  status_label: string;
  created_at: string;
  updated_at: string;
  resume_filename: string;
  can_withdraw: boolean;
  job: { slug: string; title: string; department: string; location: string; is_open: boolean };
  cover_note?: string;
  events?: AppEvent[];
}

export type Band = 'strong' | 'good' | 'partial' | 'low';

export interface FitChip {
  kind: 'positive' | 'gap' | 'bonus' | 'info';
  label: string;
}

export interface Fit {
  score: number;
  band: Band;
  band_label: string;
  version: number;
  computed_at: string;
  explanation: {
    chips: FitChip[];
    raise_score: string[];
    breakdown: { component: string; weight: number; points: number }[];
    matched_required: number;
    required_total: number;
    matched_nice: number;
    nice_total: number;
    strong_evidence: number;
    experience_years: number | null;
    min_years: number;
  };
}

export interface NoteItem {
  id: string;
  kind: 'note' | 'vote' | 'candidate_message';
  vote: 'up' | 'down' | null;
  stage: string;
  body: string;
  author: string;
  author_role: string;
  created_at: string;
}

export interface StaffApplication {
  id: string;
  status: string;
  status_label: string;
  created_at: string;
  updated_at: string;
  resume_filename: string | null;
  blind: boolean;
  /** While blind every identity field is null and only `code` is set. */
  candidate: {
    id: string | null;
    code: string;
    full_name: string | null;
    email: string | null;
    headline: string | null;
    location: string | null;
  };
  job: { id: string; title: string; slug: string };
  allowed_transitions: string[];
  fit: Fit | null;
  skills: { slug: string; name: string; section: string }[];
  rejection_reason?: string;
  cover_note?: string;
  resume_text?: string;
  rejection_note?: string;
  events?: (AppEvent & { reason?: string })[];
  evidence?: { slug: string; name: string; section: string; snippet: string }[];
  notes?: NoteItem[];
  revealed?: { at: string; reason: string } | null;
  reveal_stage?: string;
}

export interface BoardColumn {
  status: string;
  label: string;
  drop_target: boolean;
  note: string;
  cards: StaffApplication[];
}

export interface BoardJob {
  id: string;
  title: string;
  status: string;
  blind_screening: boolean;
  reveal_stage: string;
}

export interface Board {
  job: BoardJob;
  can_move: boolean;
  can_note: boolean;
  transitions: Record<string, string[]>;
  rejection_reasons: { value: string; label: string }[];
  columns: BoardColumn[];
}

export interface HiraReply {
  intent: string;
  answer: string;
  chips: string[];
  jobs: PublicJob[];
  applications: { id: string; title: string; status: string; status_label: string }[];
  action: { type: 'message_recruiter' } | null;
  link: string | null;
  needs_sign_in: boolean;
  /** Week 3B: HR answers for employees (balances, leave confirmation, holidays...). */
  card?: HrCard | null;
}

export interface FairnessResult {
  applications: number;
  variants: number;
  changes: number;
  passed: boolean;
  summary: string;
  examples: { application: string; variant: string; original: number; variant_score: number }[];
  changed_fields: string[];
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string;
  read: boolean;
  created_at: string;
}

export interface EmailItem {
  id: string;
  to_email: string;
  kind: string;
  subject: string;
  body: string;
  attachment?: { name: string; content_type: string; content: string } | null;
  created_at: string;
}

export interface AuditEntry {
  id: string;
  action: string;
  actor: string | null;
  target_type: string;
  target_id: string;
  ip_address: string | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface Department {
  id: string;
  name: string;
  slug: string;
}
export interface Location {
  id: string;
  name: string;
  slug: string;
  country: string;
}
export interface Level {
  id: string;
  name: string;
  rank: number;
}
export interface Skill {
  id: string;
  name: string;
  slug: string;
  kind: 'tech' | 'non_tech';
  category: string;
  synonyms: string[];
}

export interface ProfileData extends User {
  headline: string;
  location_text: string;
  phone: string;
  address: string;
}

export interface Summary {
  role: Role;
  applications_total?: number;
  applications_by_status?: Record<string, number>;
  jobs_by_status?: Record<string, number>;
  users_by_role?: Record<string, number>;
  open_jobs?: number;
}

// ---------------------------------------------------------------- week 3A
export type InterviewMode = 'video' | 'in_person' | 'phone';
export type InterviewStatus = 'pending' | 'scheduled' | 'completed' | 'no_show' | 'cancelled';

export interface Person {
  id: string;
  name: string;
  role?: string;
}

export interface InterviewRound {
  id: string;
  order: number;
  name: string;
  duration_minutes: number;
  mode: InterviewMode;
  mode_label: string;
  interviewers_needed: number;
  pool?: Person[];
}

export interface Slot {
  id: string;
  starts_at: string;
  ends_at: string;
  label: string;
  status: 'open' | 'held' | 'taken' | 'withdrawn';
  held_until: string | null;
}

export interface Interview {
  id: string;
  application: string;
  job: { id: string; title: string };
  round: InterviewRound;
  status: InterviewStatus;
  status_label: string;
  starts_at: string | null;
  ends_at: string | null;
  when: string;
  mode: InterviewMode;
  mode_label: string;
  meeting_link: string;
  location: string;
  meeting_note: string;
  simulated: boolean;
  reschedule_count: number;
  interviewers: { id: string; name: string; status: 'assigned' | 'declined' }[];
  slots: Slot[];
  // Candidate view
  reschedules_left?: number;
  can_reschedule?: boolean;
  // Staff view
  candidate?: { code: string; full_name: string | null };
  attention?: string;
  attention_label?: string;
  scheduled_by?: string;
  scorecard_due_at?: string | null;
  my_assignment?: 'assigned' | 'declined' | null;
  my_scorecard_submitted?: boolean;
  can_decline?: boolean;
  can_mark_no_show?: boolean;
  can_submit_scorecard?: boolean;
}

export interface Criterion {
  key: string;
  label: string;
  kind: 'skill' | 'general';
}

export type Recommendation = 'strong_no' | 'no' | 'yes' | 'strong_yes';

export interface ScorecardItem {
  id: string;
  interviewer: { id: string; name: string };
  criteria: (Criterion & { rating: number | null; comment: string })[];
  recommendation: Recommendation;
  recommendation_label: string;
  summary: string;
  submitted_at: string;
}

export interface ScorecardSummary {
  submitted: number;
  expected: number;
  hidden: boolean;
  criteria: { key: string; label: string; average: number; count: number }[];
  recommendations: Record<Recommendation, number>;
}

export interface ScorecardPage {
  interview: Interview;
  template: Criterion[];
  comment_required_for: number[];
  mine: ScorecardItem | null;
  others: ScorecardItem[];
  others_hidden: boolean;
  summary: ScorecardSummary;
}

export interface OfferBrief {
  id: string;
  status: string;
  status_label: string;
  approval_step: '' | 'hiring_manager' | 'hr_admin';
  approval_step_label: string;
  expires_on: string;
  created_at: string;
}

export interface ApplicationInterviews {
  application: string;
  status: string;
  hira_enabled: boolean;
  rounds: { round: InterviewRound; interview: Interview | null; outcome: 'passed' | 'not_passed' | null; summary: ScorecardSummary | null }[];
  final_round_passed: boolean;
  can_schedule: boolean;
  offer: OfferBrief | null;
}

export interface InterviewPlan {
  job: { id: string; title: string };
  hira_enabled: boolean;
  rounds: InterviewRound[];
}

export type WorkingHours = Record<string, [string, string]>;

export interface Interviewer extends Person {
  skills: SkillRef[];
  working_hours: WorkingHours;
  active: boolean;
  interviews_this_week: number;
}

export interface Availability {
  timezone: string;
  working_hours: WorkingHours;
  skills: string[];
  blocked: { id: string; starts_at: string; ends_at: string; label: string; reason: string }[];
}

export interface AssignedInterviews {
  upcoming: Interview[];
  needs_feedback: Interview[];
  past: Interview[];
}

export interface OfferTerms {
  designation: string;
  department: string;
  location: string;
  reporting_manager_id?: string;
  reporting_manager_name: string;
  joining_date: string;
  fixed_pay: number;
  variable_pay: number;
  joining_bonus: number;
  total: number;
  display: { fixed_pay: string; variable_pay: string; joining_bonus: string; total: string };
  currency: 'INR';
}

export interface StaffOffer extends OfferBrief {
  application: string;
  job: { id: string; title: string };
  candidate: { code: string; full_name: string | null };
  terms: OfferTerms;
  created_by: string;
  approvals: Record<'hiring_manager' | 'hr_admin', { name: string | null; at: string | null }>;
  rejected: { reason: string; at: string } | null;
  sent_at: string | null;
  responded_at: string | null;
  decline_reason: string;
  revoke_reason: string;
  has_letter: boolean;
  actions: Record<'edit' | 'submit' | 'approve' | 'reject' | 'send' | 'revoke', boolean> & { hire?: boolean };
  /** Week 3B: set once the one-click hire has run. */
  hired?: { employee: string; code: string; joined_on: string } | null;
}

export interface CandidateOffer extends OfferBrief {
  job: { title: string };
  terms: OfferTerms;
  sent_at: string | null;
  responded_at: string | null;
  can_respond: boolean;
  has_letter: boolean;
  acknowledgement: string;
  demo: boolean;
}

export interface HiraItem {
  id: string;
  action: string;
  label: string;
  reason_code: string;
  job: { id: string; title: string } | null;
  application: string | null;
  candidate: string;
  interview: string | null;
  round: string;
  created_at: string;
  link: string;
  needs_you?: boolean;
}

export interface HiraBriefing {
  since: string;
  counts: Record<string, number>;
  needs_you_count: number;
  needs_you: HiraItem[];
  message: string;
  spoken: string;
}

export interface HiraDay {
  date: string;
  scheduled: number;
  rescheduled: number;
  chased: number;
  reminders: number;
  needs_you: number;
}

export interface HiraSummary {
  days: number;
  kpis: Record<'actions' | 'scheduled' | 'reschedules' | 'replacements' | 'chased' | 'reminders' | 'needs_you', number>;
  by_day: HiraDay[];
  needs_you: HiraItem[];
  actions: { value: string; label: string }[];
}

export interface ScheduleLink {
  job: { title: string };
  round: InterviewRound;
  status: InterviewStatus;
  slots: Slot[];
  expires_at: string;
  hold_minutes: number;
  simulated: boolean;
}
