import type { Role } from './policy';

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

export interface StaffApplication {
  id: string;
  status: string;
  status_label: string;
  created_at: string;
  resume_filename: string;
  candidate: { id: string; full_name: string; email: string; headline: string; location: string };
  job: { id: string; title: string; slug: string };
  allowed_transitions: string[];
  cover_note?: string;
  resume_text?: string;
  events?: AppEvent[];
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
