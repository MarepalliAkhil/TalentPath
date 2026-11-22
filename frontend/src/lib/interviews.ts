import type { Recommendation } from './types';

/** Every time is shown in India Standard Time, whatever the viewer's device says. */
const istFmt = new Intl.DateTimeFormat('en-IN', {
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
  timeZone: 'Asia/Kolkata',
});
const istTime = new Intl.DateTimeFormat('en-IN', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: 'Asia/Kolkata' });

export function ist(iso: string | null | undefined): string {
  return iso ? `${istFmt.format(new Date(iso))} IST` : '';
}

export function istRange(start: string | null, end: string | null): string {
  if (!start || !end) return '';
  return `${istFmt.format(new Date(start))} to ${istTime.format(new Date(end))} IST`;
}

export const RECOMMENDATIONS: { value: Recommendation; label: string }[] = [
  { value: 'strong_no', label: 'Strong no' },
  { value: 'no', label: 'No' },
  { value: 'yes', label: 'Yes' },
  { value: 'strong_yes', label: 'Strong yes' },
];

export const WEEKDAYS = [
  { key: '1', label: 'Monday' },
  { key: '2', label: 'Tuesday' },
  { key: '3', label: 'Wednesday' },
  { key: '4', label: 'Thursday' },
  { key: '5', label: 'Friday' },
  { key: '6', label: 'Saturday' },
  { key: '7', label: 'Sunday' },
];

export const MODES = [
  { value: 'video', label: 'Video call' },
  { value: 'in_person', label: 'In person' },
  { value: 'phone', label: 'Phone' },
];

const rupeeFmt = new Intl.NumberFormat('en-IN');
export function rupees(amount: number): string {
  return `₹${rupeeFmt.format(amount)}`;
}

/** Datetime-local input value ("2026-12-01T10:30") read as IST, sent with the +05:30 offset. */
export function istInputToIso(value: string): string {
  return value ? `${value}:00+05:30` : '';
}

/** localStorage can be unavailable (privacy modes); never let that break the page. */
export function readSetting(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

export function writeSetting(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

/** Counts only: the spoken text comes from the server and never includes names. */
export function speak(text: string): boolean {
  if (typeof window === 'undefined' || !('speechSynthesis' in window)) return false;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = 'en-IN';
  window.speechSynthesis.speak(utterance);
  return true;
}
