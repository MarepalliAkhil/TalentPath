/**
 * Reads frontend/vercel.json at build time.
 *
 * vercel.json cannot read environment variables, so the Render URL is written there literally,
 * in ONE rewrite. Everything else (the WebSocket origin, the placeholder check) is derived from it.
 */
import { readFileSync } from 'node:fs';

export const PLACEHOLDER_HOST = 'REPLACE-WITH-RENDER-SERVICE.onrender.com';

export interface Rewrite {
  source: string;
  destination: string;
}

export interface VercelConfig {
  rewrites?: Rewrite[];
  headers?: { source: string; headers: { key: string; value: string }[] }[];
}

export function readVercelConfig(path: string): VercelConfig {
  return JSON.parse(readFileSync(path, 'utf-8')) as VercelConfig;
}

/** Every external (https://) rewrite destination origin, e.g. https://talentpath-api.onrender.com. */
export function backendOrigins(config: VercelConfig): string[] {
  const origins = new Set<string>();
  for (const r of config.rewrites ?? []) {
    const m = /^(https:\/\/[^/]+)/.exec(r.destination);
    if (m) origins.add(m[1]);
  }
  return [...origins];
}

/** The single Render origin, or null when it is missing, repeated with different hosts, or still the placeholder. */
export function renderOrigin(config: VercelConfig): string | null {
  const origins = backendOrigins(config);
  if (origins.length !== 1) return null;
  return origins[0].includes(PLACEHOLDER_HOST) ? null : origins[0];
}

/** Problems that must block a Vercel deployment. Empty list = ready. */
export function vercelConfigProblems(config: VercelConfig): string[] {
  const problems: string[] = [];
  const origins = backendOrigins(config);
  if (origins.length === 0) problems.push('vercel.json has no rewrite to the Render backend.');
  if (origins.length > 1) problems.push(`vercel.json names ${origins.length} backend hosts; write the Render URL in one rewrite only.`);
  if (origins.some((o) => o.includes(PLACEHOLDER_HOST))) {
    problems.push(
      `vercel.json still points at the placeholder ${PLACEHOLDER_HOST}. ` +
        'Paste your Render URL into the /api rewrite (see docs/DEPLOY.md, step 5).',
    );
  }
  if (origins.some((o) => !o.endsWith('.onrender.com'))) {
    problems.push('The backend rewrite must point at an https://*.onrender.com URL (the CSP allows only that WebSocket origin).');
  }
  return problems;
}

/** wss:// origin for live updates, derived from the Render rewrite (Vercel cannot proxy WebSockets). */
export function websocketOrigin(config: VercelConfig): string {
  const origin = renderOrigin(config);
  return origin ? origin.replace(/^https:/, 'wss:') : '';
}

/**
 * The first path segments the SPA serves (one `/:section(a|b|c)` rewrite). Paths outside this list
 * are not rewritten, so Vercel answers them with a real 404 status (and our 404.html page).
 */
export function spaSections(config: VercelConfig): string[] {
  for (const r of config.rewrites ?? []) {
    const m = /^\/:section\(([^)]+)\)$/.exec(r.source);
    if (m && r.destination === '/index.html') return m[1].split('|');
  }
  return [];
}

/** True when Vercel would serve the app for this path (used by tests to prove every route is covered). */
export function servesApp(config: VercelConfig, path: string): boolean {
  if (path === '/') return true;
  const first = path.split('/')[1] ?? '';
  return spaSections(config).includes(first);
}
