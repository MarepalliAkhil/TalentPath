import { act, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import policy from '@shared/policy.json';
import vercelJson from '../../vercel.json';
import {
  PLACEHOLDER_HOST,
  backendOrigins,
  servesApp,
  spaSections,
  vercelConfigProblems,
  websocketOrigin,
  type VercelConfig,
} from '../../build/vercelConfig';
import { WakeNotice } from '@/components/WakeNotice';
import { fetchWithWake, WAKE_DELAYS_MS } from '@/lib/api';
import appSource from '../App.tsx?raw';

const vercel = vercelJson as VercelConfig;
const withHost = (host: string): VercelConfig => ({
  rewrites: [{ source: '/:path(api/.*|sitemap\\.xml|robots\\.txt)', destination: `https://${host}/:path` }],
});

describe('vercel.json', () => {
  it('writes the Render URL literally in one rewrite and fails the check while it is the placeholder', () => {
    expect(backendOrigins(vercel)).toHaveLength(1);
    const placeholder = withHost(PLACEHOLDER_HOST);
    expect(vercelConfigProblems(placeholder).join(' ')).toMatch(/placeholder/);
    expect(websocketOrigin(placeholder)).toBe('');

    const real = withHost('talentpath-api.onrender.com');
    expect(vercelConfigProblems(real)).toEqual([]);
    expect(websocketOrigin(real)).toBe('wss://talentpath-api.onrender.com');

    const two: VercelConfig = { rewrites: [...real.rewrites!, { source: '/x', destination: 'https://other.onrender.com/x' }] };
    expect(vercelConfigProblems(two).join(' ')).toMatch(/one rewrite only/);
    expect(vercelConfigProblems(withHost('example.com')).join(' ')).toMatch(/onrender\.com/);
  });

  it('proxies the API, the sitemap and robots.txt to the backend', () => {
    const api = vercel.rewrites!.find((r) => r.destination.startsWith('https://'))!;
    expect(api.source).toBe('/:path(api/.*|sitemap\\.xml|robots\\.txt)');
    expect(api.destination).toMatch(/^https:\/\/[^/]+\.onrender\.com\/:path$/);
  });

  it('serves the app for every route in policy.json and App.tsx, and nothing else (real 404s)', () => {
    const routes = Object.keys(policy.routes).map((r) => r.replace(/:[a-z]+/g, 'x'));
    const appPaths = [...appSource.matchAll(/path="([^"]+)"/g)].map((m) => `/${m[1]}`).filter((p) => p !== '/*');
    for (const path of [...routes, ...appPaths, '/']) {
      expect(servesApp(vercel, path), path).toBe(true);
    }
    expect(spaSections(vercel)).not.toContain('api');
    for (const path of ['/wp-admin', '/does-not-exist', '/.env', '/api-docs']) {
      expect(servesApp(vercel, path), path).toBe(false);
    }
  });

  it('sends security headers, a CSP that allows the Render WebSocket and long caching for hashed assets', () => {
    const all = vercel.headers!.find((h) => h.source === '/(.*)')!.headers;
    const csp = all.find((h) => h.key === 'Content-Security-Policy')!.value;
    expect(csp).toContain("default-src 'self'");
    expect(csp).toContain("script-src 'self'");
    expect(csp).not.toMatch(/script-src[^;]*unsafe/);
    expect(csp).toContain("connect-src 'self' wss://*.onrender.com");
    expect(csp).toContain("frame-ancestors 'none'");
    const keys = all.map((h) => h.key);
    expect(keys).toEqual(expect.arrayContaining(['Strict-Transport-Security', 'X-Content-Type-Options', 'Referrer-Policy']));
    const assets = vercel.headers!.find((h) => h.source === '/assets/(.*)')!.headers[0];
    expect(assets.value).toBe('public, max-age=31536000, immutable');
  });
});

describe('waking up the free server', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('retries on 502, 503 and 504 with a notice, then succeeds', async () => {
    vi.useFakeTimers();
    const statuses = [503, 502, 504, 200];
    const fetchMock = vi.fn(async () => new Response('{}', { status: statuses.shift() ?? 200 }));
    vi.stubGlobal('fetch', fetchMock);
    render(<WakeNotice />);
    let done: Response | null = null;
    const pending = fetchWithWake('/api/ping').then((r) => (done = r));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WAKE_DELAYS_MS[0]);
    });
    expect(screen.getByRole('status')).toHaveTextContent('Waking up the server, this can take up to a minute');
    await act(async () => {
      await vi.advanceTimersByTimeAsync(WAKE_DELAYS_MS[1] + WAKE_DELAYS_MS[2]);
      await pending;
    });
    expect(fetchMock).toHaveBeenCalledTimes(4);
    expect(done!.status).toBe(200);
    expect(screen.getByRole('status')).toHaveTextContent('');
  });

  it('does not repeat a write on 504 and gives up after about a minute', async () => {
    vi.useFakeTimers();
    const post = vi.fn(async () => new Response('{}', { status: 504 }));
    vi.stubGlobal('fetch', post);
    expect((await fetchWithWake('/api/applications', { method: 'POST' })).status).toBe(504);
    expect(post).toHaveBeenCalledTimes(1);

    const down = vi.fn(async () => new Response('{}', { status: 503 }));
    vi.stubGlobal('fetch', down);
    const pending = fetchWithWake('/api/jobs');
    await vi.advanceTimersByTimeAsync(WAKE_DELAYS_MS.reduce((a, b) => a + b, 0));
    expect((await pending).status).toBe(503);
    expect(down).toHaveBeenCalledTimes(WAKE_DELAYS_MS.length + 1);
    expect(WAKE_DELAYS_MS.reduce((a, b) => a + b, 0)).toBeLessThanOrEqual(65_000);
  });
});
