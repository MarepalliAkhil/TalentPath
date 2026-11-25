import { validate, resumeSchema } from './schemas';
import type { CompanyBrief, ExperienceRow, ScreeningQuestion } from './types';

/** The application form (D-83): seven steps with progress, a saved draft and the declarations. */
export interface ApplyContext {
  job: { slug: string; title: string; company: CompanyBrief | null; screening_questions: ScreeningQuestion[] };
  already_applied: boolean;
  draft: { data: Partial<FormState>; step: number; saved_at: string } | null;
  prefill: {
    personal: { full_name: string; email: string; phone: string; current_city: string; date_of_birth: string | null };
    education: { college: string; branch: string; graduation_year: string; score: string };
    experience: { status: 'fresher' | 'experienced'; roles: ExperienceRow[] };
    links: { linkedin_url: string; github_url: string; portfolio_url: string };
  };
  locked: { date_of_birth: boolean };
  profile_resume: { filename: string } | null;
  notice_periods: { value: string; label: string }[];
  qualifications: string[];
  terms_version: string;
}

export interface FormState {
  personal: { phone: string; current_city: string; willing_to_relocate: '' | 'yes' | 'no'; date_of_birth: string };
  education: {
    highest_qualification: string;
    college: string;
    branch: string;
    graduation_year: string;
    score_type: 'cgpa' | 'percentage';
    score: string;
    tenth_percentage: string;
    twelfth_percentage: string;
  };
  experience: { status: 'fresher' | 'experienced'; roles: ExperienceRow[]; total_years: string };
  compensation: { current_ctc_lpa: string; expected_ctc_lpa: string; notice_period: string; earliest_joining: string };
  links: { linkedin_url: string; github_url: string; portfolio_url: string };
  answers: Record<string, string>;
  use_profile_resume: boolean;
  cover_letter: string;
  declarations: { info_true: boolean; accept_terms: boolean };
}

export const STEPS = ['Personal', 'Education', 'Experience', 'Compensation', 'Links and questions', 'Resume', 'Review and submit'];
export const SECTION_STEP: Record<string, number> = {
  personal: 0,
  education: 1,
  experience: 2,
  compensation: 3,
  links: 4,
  answers: 4,
  resume: 5,
  cover_letter: 5,
  use_profile_resume: 5,
  declarations: 6,
};
export const EMPTY_ROLE: ExperienceRow = { company: '', title: '', start: '', end: '', responsibilities: '' };

export function initialState(ctx: ApplyContext): FormState {
  const p = ctx.prefill;
  const base: FormState = {
    personal: {
      phone: p.personal.phone,
      current_city: p.personal.current_city,
      willing_to_relocate: '',
      date_of_birth: p.personal.date_of_birth ?? '',
    },
    education: {
      highest_qualification: "Bachelor's degree",
      college: p.education.college,
      branch: p.education.branch,
      graduation_year: p.education.graduation_year,
      score_type: 'cgpa',
      score: p.education.score,
      tenth_percentage: '',
      twelfth_percentage: '',
    },
    experience: { status: p.experience.status, roles: p.experience.roles, total_years: p.experience.status === 'fresher' ? '0' : '' },
    compensation: {
      current_ctc_lpa: p.experience.status === 'fresher' ? '0' : '',
      expected_ctc_lpa: '',
      notice_period: '',
      earliest_joining: '',
    },
    links: { ...p.links },
    answers: {},
    use_profile_resume: Boolean(ctx.profile_resume),
    cover_letter: '',
    declarations: { info_true: false, accept_terms: false },
  };
  const draft = ctx.draft?.data;
  if (!draft) return base;
  return {
    ...base,
    ...draft,
    personal: { ...base.personal, ...draft.personal, ...(ctx.locked.date_of_birth ? { date_of_birth: base.personal.date_of_birth } : {}) },
    education: { ...base.education, ...draft.education },
    experience: { ...base.experience, ...draft.experience },
    compensation: { ...base.compensation, ...draft.compensation },
    links: { ...base.links, ...draft.links },
    answers: { ...draft.answers },
    declarations: { info_true: false, accept_terms: false },
  };
}

/** Server errors arrive nested ({"compensation": {"current_ctc_lpa": ["..."]}}); flatten to "section.field". */
export function flattenErrors(data: unknown, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {};
  if (Array.isArray(data)) {
    if (data.length && typeof data[0] === 'string') out[prefix || 'form'] = String(data[0]);
    else data.forEach((item, i) => Object.assign(out, flattenErrors(item, `${prefix}.${i}`)));
  } else if (data && typeof data === 'object') {
    for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
      Object.assign(out, flattenErrors(value, prefix ? `${prefix}.${key}` : key));
    }
  } else if (typeof data === 'string') {
    out[prefix || 'form'] = data;
  }
  return out;
}

export function stepErrors(step: number, f: FormState, ctx: ApplyContext, file: File | null): Record<string, string> {
  const e: Record<string, string> = {};
  const need = (cond: boolean, key: string, message: string) => {
    if (!cond) e[key] = message;
  };
  if (step === 0) {
    need(f.personal.phone.trim().length >= 7, 'personal.phone', 'Enter your phone number.');
    need(f.personal.current_city.trim().length >= 2, 'personal.current_city', 'Enter your current city.');
    need(f.personal.willing_to_relocate !== '', 'personal.willing_to_relocate', 'Choose yes or no.');
    need(Boolean(f.personal.date_of_birth), 'personal.date_of_birth', 'Enter your date of birth.');
  }
  if (step === 1) {
    need(f.education.college.trim().length >= 2, 'education.college', 'Enter your college.');
    need(f.education.branch.trim().length >= 2, 'education.branch', 'Enter your branch or major.');
    need(/^\d{4}$/.test(f.education.graduation_year), 'education.graduation_year', 'Enter the year, like 2024.');
    need(f.education.score !== '', 'education.score', 'Enter your CGPA or percentage.');
    need(f.education.tenth_percentage !== '', 'education.tenth_percentage', 'Enter your 10th percentage.');
    need(f.education.twelfth_percentage !== '', 'education.twelfth_percentage', 'Enter your 12th percentage.');
  }
  if (step === 2) {
    need(f.experience.total_years !== '', 'experience.total_years', 'Enter your total experience in years (0 for freshers).');
    if (f.experience.status === 'experienced')
      need(f.experience.roles.length > 0, 'experience.roles', 'Add at least one role, or choose fresher.');
  }
  if (step === 3) {
    need(f.compensation.current_ctc_lpa !== '', 'compensation.current_ctc_lpa', 'Enter your current CTC (0 if you are a fresher).');
    need(f.compensation.expected_ctc_lpa !== '', 'compensation.expected_ctc_lpa', 'Enter your expected CTC.');
    need(f.compensation.notice_period !== '', 'compensation.notice_period', 'Choose your notice period.');
    need(Boolean(f.compensation.earliest_joining), 'compensation.earliest_joining', 'Pick your earliest joining date.');
  }
  if (step === 4) {
    for (const q of ctx.job.screening_questions) {
      if (q.required) need(Boolean(f.answers[q.id]?.trim()), `answers.${q.id}`, 'Answer this question.');
    }
  }
  if (step === 5 && !f.use_profile_resume) {
    const { errors } = validate(resumeSchema, { resume: file ?? undefined });
    if (errors.resume) e.resume = errors.resume;
  }
  if (step === 6) {
    need(f.declarations.info_true, 'declarations.info_true', 'Confirm that the information is true.');
    need(f.declarations.accept_terms, 'declarations.accept_terms', 'Accept the Terms and Conditions and the Privacy Policy.');
  }
  return e;
}
