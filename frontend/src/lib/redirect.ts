/**
 * The `?next=` path after sign-in. Only same-site paths are allowed: it must start with one "/",
 * and backslashes and control characters are refused, because browsers read `/\evil.example`
 * as `//evil.example` (another site). That closes the open-redirect pattern behind
 * GHSA-wrjc-x8rr-h8h6 without a major react-router upgrade.
 */
export function safeNext(next: string | null): string | null {
  if (!next || !next.startsWith('/') || next.startsWith('//')) return null;
  // eslint-disable-next-line no-control-regex
  if (/[\\\u0000-\u001f\u007f]/.test(next)) return null;
  return next;
}
