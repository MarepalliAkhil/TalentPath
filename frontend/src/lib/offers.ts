import type { OfferTerms } from './types';

export interface OfferDraft {
  designation: string;
  reporting_manager_id: string;
  joining_date: string;
  expires_on: string;
  fixed_pay: string;
  variable_pay: string;
  joining_bonus: string;
}

function isoIn(days: number) {
  const d = new Date(Date.now() + days * 86_400_000);
  return d.toISOString().slice(0, 10);
}

export function draftFrom(terms?: OfferTerms, expires?: string, designation = ''): OfferDraft {
  return {
    designation: terms?.designation ?? designation,
    reporting_manager_id: terms?.reporting_manager_id ?? '',
    joining_date: terms?.joining_date ?? isoIn(45),
    expires_on: expires ?? isoIn(7),
    fixed_pay: terms ? String(terms.fixed_pay) : '',
    variable_pay: terms ? String(terms.variable_pay) : '0',
    joining_bonus: terms ? String(terms.joining_bonus) : '0',
  };
}

export function draftBody(draft: OfferDraft) {
  return {
    designation: draft.designation,
    reporting_manager_id: draft.reporting_manager_id || undefined,
    joining_date: draft.joining_date,
    expires_on: draft.expires_on,
    fixed_pay: draft.fixed_pay,
    variable_pay: draft.variable_pay || '0',
    joining_bonus: draft.joining_bonus || '0',
  };
}
