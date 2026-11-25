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
  csrfPromise ??= fetchWithWake('/api/auth/csrf', { credentials: 'same-origin' })
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
    const res = await fetchWithWake('/api/auth/refresh', {
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

/*
 * Free hosting sleeps after a quiet spell. While it wakes, the proxy answers 502, 503 or 504
 * (or the connection fails). Those requests are retried for about a minute and a
 * "Waking up the server" notice is shown. Writes are retried only on 502/503 and network
 * errors, where the request never reached the app; 504 is retried for reads only.
 */
export const WAKE_DELAYS_MS = [2_000, 4_000, 6_000, 8_000, 10_000, 10_000, 10_000, 10_000];
type WakeListener = (waking: boolean) => void;
const wakeListeners = new Set<WakeListener>();
let wakingRequests = 0;

export function onWakeChange(listener: WakeListener): () => void {
  wakeListeners.add(listener);
  return () => wakeListeners.delete(listener);
}

function setWaking(delta: number) {
  const before = wakingRequests > 0;
  wakingRequests = Math.max(0, wakingRequests + delta);
  const after = wakingRequests > 0;
  if (before !== after) wakeListeners.forEach((listener) => listener(after));
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

function retryable(status: number, method: string): boolean {
  if (status === 502 || status === 503) return true;
  return status === 504 && (method === 'GET' || method === 'HEAD');
}

/** fetch that waits for a sleeping server to wake up (see above). */
export async function fetchWithWake(input: string, init: RequestInit = {}): Promise<Response> {
  const method = (init.method ?? 'GET').toUpperCase();
  let waiting = false;
  try {
    for (let attempt = 0; ; attempt += 1) {
      let response: Response | null = null;
      let failure: unknown = null;
      try {
        response = await fetch(input, init);
      } catch (error) {
        failure = error;
      }
      const again = response ? retryable(response.status, method) : true;
      if (!again || attempt >= WAKE_DELAYS_MS.length) {
        if (response) return response;
        throw failure;
      }
      if (!waiting) {
        waiting = true;
        setWaking(1);
      }
      await sleep(WAKE_DELAYS_MS[attempt]);
    }
  } finally {
    if (waiting) setWaking(-1);
  }
}

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
  const res = await fetchWithWake(`/api${path}`, { method, headers, body, credentials: 'same-origin' });
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
