import { expect, test, type Page, type TestInfo } from '@playwright/test';
import { readFileSync } from 'node:fs';

// Read with fs: Playwright loads specs as ES modules, where a plain JSON import is refused.
const policy = JSON.parse(readFileSync(new URL('../../shared/policy.json', import.meta.url), 'utf8')) as {
  routes: Record<string, string[]>;
};

/*
 * Week 4B: every route, for every role, with no console errors and no failed requests.
 * Run against fresh demo data (python manage.py seed --reset) with the backend on :8000.
 *
 * Routes come from shared/policy.json (the same file the app guards with), so a new route is
 * covered automatically. Routes with an :id or :slug are opened from a link found on the pages
 * already visited; a pattern with no link in the demo data is reported as a test annotation.
 * /schedule/:token needs a single-use emailed token and is covered by week3.spec.ts.
 */
const PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo@Pass2026';

type Role = 'anonymous' | 'candidate' | 'recruiter' | 'manager' | 'employee' | 'hr' | 'admin';

const ACCOUNTS: Record<Exclude<Role, 'anonymous'>, string> = {
  candidate: 'candidate@demo.example',
  recruiter: 'recruiter@demo.example',
  manager: 'manager@demo.example',
  employee: 'employee@demo.example',
  hr: 'hr@demo.example',
  admin: 'admin@demo.example',
};

/** Public pages outside the policy's guarded routes (the policy lists only guarded ones and a few public ones). */
const PUBLIC_EXTRA = ['/', '/login', '/register', '/forgot-password', '/reset-password', '/demo-inbox', '/terms', '/privacy'];
const SKIPPED = new Set(['/schedule/:token']);

function routesFor(role: Role): string[] {
  const routes = policy.routes;
  const allowed = Object.entries(routes)
    .filter(([route, roles]) => {
      if (SKIPPED.has(route)) return false;
      if (roles.includes('any')) return true;
      if (role === 'anonymous') return false;
      return roles.includes('authenticated') || roles.includes(role);
    })
    .map(([route]) => route);
  return role === 'anonymous' ? [...PUBLIC_EXTRA, ...allowed] : allowed;
}

const isPattern = (route: string) => route.includes(':');
const patternRegex = (route: string) => new RegExp(`^${route.replace(/:[a-z]+/g, '[^/?#]+')}$`);

/*
 * Responses that are expected and harmless:
 * - /hira/*.webp: optional artwork; when missing the app shows an initials avatar (public/hira/README.md);
 * - 401 from /api/auth/* while signed out: how the app learns there is no session.
 */
function expected(url: string, status: number, role: Role): boolean {
  const path = new URL(url).pathname;
  if (path.startsWith('/hira/') && status === 404) return true;
  return role === 'anonymous' && status === 401 && path.startsWith('/api/auth/');
}

function watch(page: Page, role: Role) {
  const problems: string[] = [];
  let current = '';
  page.on('console', (msg) => {
    if (msg.type() !== 'error') return;
    const url = msg.location().url;
    // Chrome logs every 4xx/5xx resource as a console error; those are judged on the response below.
    if (msg.text().startsWith('Failed to load resource')) return;
    problems.push(`${current}: console error: ${msg.text()}${url ? ` (${url})` : ''}`);
  });
  page.on('pageerror', (error) => problems.push(`${current}: uncaught ${error.name}: ${error.message}`));
  page.on('requestfailed', (request) => {
    const reason = request.failure()?.errorText ?? '';
    if (reason.includes('ERR_ABORTED')) return; // cancelled when the next page loads
    problems.push(`${current}: request failed: ${request.method()} ${request.url()} ${reason}`);
  });
  page.on('response', (response) => {
    const status = response.status();
    if (status < 400 || expected(response.url(), status, role)) return;
    problems.push(`${current}: ${status} for ${response.request().method()} ${response.url()}`);
  });
  return {
    problems,
    at(route: string) {
      current = route;
    },
  };
}

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: false }).first().fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

async function settle(page: Page) {
  try {
    await page.waitForLoadState('networkidle', { timeout: 10_000 });
  } catch {
    // Pages that poll never go fully idle; the heading check below still waits for the content.
  }
}

async function visit(page: Page, path: string, signedIn = true): Promise<{ title: string; links: string[] }> {
  await page.goto(path);
  await settle(page);
  await expect(page.locator('h1').first(), `${path} shows a page heading`).toBeVisible();
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toHaveCount(0);
  if (signedIn) await expect(page, `${path} was not sent back to sign in`).not.toHaveURL(/\/login(\?|$)/);
  for (const img of await page.locator('img').all()) {
    expect(await img.getAttribute('alt'), `every image on ${path} has an alt attribute`).not.toBeNull();
  }
  const links = await page.locator('a[href^="/"]').evaluateAll((els) => els.map((a) => a.getAttribute('href') ?? ''));
  return { title: await page.title(), links };
}

function annotate(testInfo: TestInfo, text: string) {
  testInfo.annotations.push({ type: 'not covered', description: text });
}

const ROLES: Role[] = ['anonymous', 'candidate', 'recruiter', 'manager', 'employee', 'hr', 'admin'];

for (const role of ROLES) {
  test(`every ${role} route loads with no console errors or failed requests`, async ({ page }, testInfo) => {
    test.skip(testInfo.project.name !== 'desktop', 'Same routes on every viewport; runs once');
    test.setTimeout(240_000);
    // Signing in starts signed out (401 from /api/auth/me is expected then), so watch from the first visit on.
    if (role !== 'anonymous') await signIn(page, ACCOUNTS[role]);
    const watcher = watch(page, role);

    const routes = routesFor(role);
    const found = new Set<string>();
    const titles = new Map<string, string>();

    for (const route of routes.filter((r) => !isPattern(r))) {
      watcher.at(route);
      const { title, links } = await visit(page, route, role !== 'anonymous');
      titles.set(route, title);
      links.forEach((link) => found.add(link.split(/[?#]/)[0]));
    }

    // A candidate applies from a job page, so the apply route is reachable from any open job.
    const jobs = [...found].filter((link) => patternRegex('/jobs/:slug').test(link));
    if (jobs.length) found.add(`${jobs[0]}/apply`);

    for (const route of routes.filter(isPattern)) {
      const regex = patternRegex(route);
      const target = [...found].find((link) => regex.test(link));
      if (!target) {
        annotate(testInfo, `${role}: no link to ${route} in the demo data`);
        continue;
      }
      watcher.at(`${route} (${target})`);
      const { links } = await visit(page, target, role !== 'anonymous');
      links.forEach((link) => found.add(link.split(/[?#]/)[0]));
    }

    // Each page has its own title, so tabs and history are easy to tell apart.
    const seen = new Map<string, string>();
    for (const [route, title] of titles) {
      expect(title, `${route} has a title`).toBeTruthy();
      expect(seen.get(title), `${route} shares its title "${title}"`).toBeUndefined();
      seen.set(title, route);
    }
    expect(watcher.problems).toEqual([]);
  });
}

test('public pages have unique titles and descriptions, a valid JobPosting, sitemap and robots', async ({ page, request }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Runs once');
  const watcher = watch(page, 'anonymous');
  const meta: Array<{ path: string; title: string; description: string }> = [];

  watcher.at('/jobs');
  await page.goto('/jobs');
  await settle(page);
  const job = await page.locator('a[href^="/jobs/"]').first().getAttribute('href');
  expect(job, 'an open job is listed').toBeTruthy();

  for (const path of ['/', '/jobs', '/for-recruiters', job as string]) {
    watcher.at(path);
    await page.goto(path);
    await settle(page);
    await expect(page.locator('h1').first()).toBeVisible();
    const description = (await page.locator('meta[name="description"]').getAttribute('content')) ?? '';
    meta.push({ path, title: await page.title(), description });
    expect(description.length, `${path} has a meta description of 50 to 160 characters`).toBeGreaterThanOrEqual(50);
    expect(description.length).toBeLessThanOrEqual(160);
  }
  expect(new Set(meta.map((m) => m.title)).size, JSON.stringify(meta)).toBe(meta.length);
  expect(new Set(meta.map((m) => m.description)).size, JSON.stringify(meta)).toBe(meta.length);

  // JobPosting structured data on the job page (Google's required properties).
  const ld = JSON.parse((await page.locator('script[type="application/ld+json"]').first().textContent()) ?? '{}');
  expect(ld['@context']).toBe('https://schema.org');
  expect(ld['@type']).toBe('JobPosting');
  for (const key of ['title', 'description', 'datePosted', 'validThrough', 'hiringOrganization', 'jobLocation']) {
    expect(ld[key], `JobPosting.${key}`).toBeTruthy();
  }
  expect(ld.hiringOrganization.name).toBeTruthy();
  expect(Number.isNaN(Date.parse(ld.datePosted))).toBe(false);
  expect(Date.parse(ld.validThrough)).toBeGreaterThan(Date.parse(ld.datePosted));

  const sitemap = await request.get('/sitemap.xml');
  expect(sitemap.ok()).toBe(true);
  const xml = await sitemap.text();
  expect(xml).toContain('<urlset');
  expect(xml).toContain(`${job}</loc>`);
  const robots = await request.get('/robots.txt');
  expect(robots.ok()).toBe(true);
  expect(await robots.text()).toMatch(/Sitemap: https?:\/\/\S+\/sitemap\.xml/);

  expect(watcher.problems).toEqual([]);
});
