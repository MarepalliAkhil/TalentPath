/**
 * Fetch wrapper: same-origin cookies (HttpOnly JWT), CSRF header on writes,
 * one silent refresh on 401. Tokens never touch JavaScript.
 */

export type FieldErrors = Record<string, string>;

export class ApiError extends Error {
  status: number;
  data: unknown;
  fieldErrors: FieldErrors;

  constructor(status: number, data: unknown) {
    const fieldErrors: FieldErrors = {};
    let message = 'Something went wrong. Please try again.';
    if (data && typeof data === 'object') {
      for (const [key, value] of Object.entries(data as Record<string, unknown>)) {
        const text = Array.isArray(value) ? String(value[0]) : typeof value === 'string' ? value : '';
        if (!text) continue;
        if (key === 'detail' || key === 'non_field_errors') message = text;
        else fieldErrors[key] = text;
      }
      if (message.startsWith('Something') && Object.keys(fieldErrors).length) {
        message = 'Please fix the highlighted fields.';
      }
    }
    if (status === 429 && message.startsWith('Something')) message = 'Too many attempts. Please wait a moment.';
    super(message);
    this.status = status;
    this.data = data;
    this.fieldErrors = fieldErrors;
  }
}

export function getCookie(name: string): string | null {
  const match = document.cookie.split('; ').find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

let csrfPromise: Promise<void> | null = null;
async function ensureCsrf(): Promise<void> {
  if (getCookie('csrftoken')) return;
  csrfPromise ??= fetch('/api/auth/csrf', { credentials: 'same-origin' })
    .then(() => undefined)
    .finally(() => {
      csrfPromise = null;
    });
  await csrfPromise;
}

let refreshPromise: Promise<boolean> | null = null;
export function refreshSession(): Promise<boolean> {
  refreshPromise ??= (async () => {
    await ensureCsrf();
    const res = await fetch('/api/auth/refresh', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCookie('csrftoken') ?? '' },
    });
    return res.ok;
  })().finally(() => {
    refreshPromise = null;
  });
  return refreshPromise;
}

const NO_REFRESH = ['/auth/login', '/auth/register', '/auth/refresh', '/auth/logout'];

export interface ApiOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  form?: FormData;
  retry?: boolean;
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const method = options.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  let body: BodyInit | undefined;
  if (method !== 'GET') {
    await ensureCsrf();
    headers['X-CSRFToken'] = getCookie('csrftoken') ?? '';
  }
  if (options.form) {
    body = options.form;
  } else if (options.body !== undefined) {
    body = JSON.stringify(options.body);
    headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(`/api${path}`, { method, headers, body, credentials: 'same-origin' });
  if (res.status === 401 && options.retry !== false && !NO_REFRESH.includes(path)) {
    if (await refreshSession()) return api<T>(path, { ...options, retry: false });
  }
  if (res.status === 204) return undefined as T;
  const type = res.headers.get('content-type') ?? '';
  const data: unknown = type.includes('application/json') ? await res.json() : await res.text();
  if (!res.ok) throw new ApiError(res.status, data);
  return data as T;
}

export function qs(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}
