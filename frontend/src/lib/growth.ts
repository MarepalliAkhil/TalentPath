/** Week 4A types: career map, internal mobility, analytics, demo mode. */

export interface ProfileResume {
  has_resume: boolean;
  filename: string;
  updated_at: string | null;
  source: 'profile' | 'application' | 'hr_record' | 'none';
  skills: string[];
  experience_years: number | null;
}

export interface MapJob {
  id: string;
  slug: string;
  title: string;
  department: string;
  location: string;
  level: string;
  audience: 'both' | 'external' | 'internal';
  score: number;
  band: string;
  band_label: string;
}

export interface SkillRow {
  slug: string;
  name: string;
  effort: 'small' | 'medium' | 'large' | null;
  section?: string;
  evidence?: string;
}

export interface PathStep {
  slug: string;
  name: string;
  kind?: 'required' | 'nice' | 'prerequisite';
  effort: 'small' | 'medium' | 'large' | null;
  effort_label: string;
  prerequisites: string[];
  unlocks: string[];
  link: { title: string; url: string } | null;
}

export interface JobMap {
  job: MapJob;
  source: ProfileResume['source'];
  have: SkillRow[];
  missing_required: SkillRow[];
  missing_nice: SkillRow[];
  path: PathStep[];
  applied: boolean;
  can_apply_internally: boolean;
}

export interface NextRole {
  current_level: string | null;
  department: string;
  designation?: string;
  source: ProfileResume['source'];
  levels: {
    level: string;
    rank: number;
    titles: string[];
    skills_needed: { slug: string; name: string; jobs: number; effort: string | null }[];
    have: { slug: string; name: string }[];
    missing: { slug: string; name: string; effort: string | null }[];
    path: PathStep[];
  }[];
}

export interface InternalJobs {
  jobs: (MapJob & { applied: boolean; own_department: boolean })[];
  applications: { id: string; job: string; status: string; status_label: string; applied_at: string }[];
  rule: { stage: 'interview' | 'offer'; text: string; manager: string | null };
  has_resume: boolean;
}

export interface Section {
  key: string;
  title: string;
  summary: string;
  chart: { type: 'bar' | 'line'; x: string; series: { key: string; label: string }[] } | null;
  columns: { key: string; label: string }[];
  rows: Record<string, string | number | null>[];
  note: string;
}

export interface AnalyticsReport {
  report: 'hiring' | 'people';
  from: string;
  to: string;
  department: string;
  scope: 'all' | 'own';
  departments: { id: string; name: string }[];
  sections: Section[];
}

export interface DemoConfig {
  demo_mode: boolean;
  accounts: { role: string; label: string }[];
  upload_limit_bytes: number | null;
}

export const SOURCE_LABEL: Record<ProfileResume['source'], string> = {
  profile: 'the resume on your profile',
  application: 'the resume from your latest application',
  hr_record: 'the skills HR recorded for you',
  none: 'nothing yet',
};
