import { z } from 'zod';

export const MAX_RESUME_BYTES = 5 * 1024 * 1024;

const email = z.string().trim().min(1, 'Enter your email address.').email('Enter a valid email address.');
const newPassword = z
  .string()
  .min(10, 'Use at least 10 characters.')
  .max(128, 'Use at most 128 characters.')
  .refine((v) => !/^\d+$/.test(v), 'Do not use only numbers.');

export const loginSchema = z.object({
  email,
  password: z.string().min(1, 'Enter your password.'),
});

export const registerSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name.').max(120, 'Keep it under 120 characters.'),
  email,
  password: newPassword,
});

export const forgotSchema = z.object({ email });

export const resetSchema = z
  .object({ password: newPassword, confirm: z.string() })
  .refine((v) => v.password === v.confirm, { message: 'Passwords do not match.', path: ['confirm'] });

export const applySchema = z.object({
  cover_note: z.string().max(2000, 'Keep the note under 2000 characters.'),
  resume: z
    .instanceof(File, { message: 'Attach your resume (PDF or DOCX).' })
    .refine((f) => /\.(pdf|docx)$/i.test(f.name), 'Upload a PDF or DOCX file.')
    .refine((f) => f.size > 0, 'This file is empty.')
    .refine((f) => f.size <= MAX_RESUME_BYTES, 'Resumes must be 5 MB or smaller.'),
});

export const jobSchema = z.object({
  title: z.string().trim().min(3, 'Give the job a title.').max(120),
  department: z.string().min(1, 'Choose a department.'),
  location: z.string().min(1, 'Choose a location.'),
  level: z.string().min(1, 'Choose a level.'),
  work_mode: z.enum(['onsite', 'hybrid', 'remote']),
  employment_type: z.enum(['full_time', 'part_time', 'contract', 'internship']),
  openings: z.coerce.number().int('Use a whole number.').min(1, 'At least 1 opening.').max(500),
  hiring_manager: z.string(),
  description: z.string().trim().min(30, 'Describe the role in at least 30 characters.'),
  required_skills: z.array(z.string()).max(15, 'Use at most 15 skills.'),
  nice_to_have_skills: z.array(z.string()).max(15, 'Use at most 15 skills.'),
});

export const staffSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter a name.'),
  email,
  role: z.enum(['recruiter', 'hiring_manager', 'employee', 'hr_admin']),
});

export const profileSchema = z.object({
  full_name: z.string().trim().min(2, 'Enter your name.').max(120),
  headline: z.string().max(160),
  location_text: z.string().max(120),
  phone: z
    .string()
    .trim()
    .refine((v) => v === '' || /^[+0-9 ()-]{7,20}$/.test(v), 'Use digits, spaces, +, - or brackets.'),
  address: z.string().max(300),
});

export type Errors = Record<string, string>;

export function validate<T>(schema: z.ZodType<T>, values: unknown): { data?: T; errors: Errors } {
  const result = schema.safeParse(values);
  if (result.success) return { data: result.data, errors: {} };
  const errors: Errors = {};
  for (const issue of result.error.issues) {
    const key = String(issue.path[0] ?? 'form');
    errors[key] ??= issue.message;
  }
  return { errors };
}
