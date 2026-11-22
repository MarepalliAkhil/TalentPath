import { useMutation, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from './api';
import type { StaffApplication } from './types';

export const STAGE_LABELS: Record<string, string> = {
  applied: 'Applied',
  screening: 'Screening',
  interview: 'Interview',
  offer: 'Offer',
  hired: 'Hired',
  rejected: 'Not selected',
  withdrawn: 'Withdrawn',
};

export const DEFAULT_REASONS = [
  { value: 'skills_gap', label: 'Required skills not shown' },
  { value: 'experience_gap', label: 'Experience below what the role needs' },
  { value: 'stronger_fit', label: 'Other candidates were a closer fit' },
  { value: 'role_filled', label: 'Role filled or closed' },
  { value: 'interview_outcome', label: 'Interview outcome' },
  { value: 'no_response', label: 'Candidate did not respond' },
  { value: 'other', label: 'Other' },
];

export function useMoveMutation(jobId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status, reason, note }: { id: string; status: string; reason?: string; note?: string }) =>
      api<StaffApplication>(`/applications/${id}/status`, { method: 'POST', body: { status, reason, note } }),
    onSuccess: (_data, vars) => {
      void client.invalidateQueries({ queryKey: ['board', jobId] });
      void client.invalidateQueries({ queryKey: ['job-applications', jobId] });
      void client.invalidateQueries({ queryKey: ['application', vars.id] });
    },
  });
}

export function errorText(error: unknown): string {
  if (error instanceof ApiError) return Object.values(error.fieldErrors)[0] ?? error.message;
  return 'Something went wrong. Please try again.';
}
