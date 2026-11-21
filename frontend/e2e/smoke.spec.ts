import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

const PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo@Pass2026';
const LOGINS = [
  { email: 'candidate@demo.example', dashboard: '/candidate', heading: 'My applications' },
  { email: 'recruiter@demo.example', dashboard: '/recruiter', heading: 'Hiring overview' },
  { email: 'manager@demo.example', dashboard: '/manager', heading: 'Your hiring' },
  { email: 'employee@demo.example', dashboard: '/employee', heading: /^Hello/ },
  { email: 'admin@demo.example', dashboard: '/admin', heading: 'Organisation overview' },
];

async function expectHealthyPage(page: Page) {
  await expect(page.locator('h1')).toHaveCount(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, 'no horizontal scrolling').toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map((v) => `${v.id} (${v.nodes.length})`)).toEqual([]);
}

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: false }).first().fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page, 'sign-in should leave the login page').not.toHaveURL(/\/login/);
}

for (const path of ['/', '/jobs', '/login', '/register', '/this-page-does-not-exist']) {
  test(`public page ${path} is accessible and fits the screen`, async ({ page }) => {
    await page.goto(path);
    await expect(page.locator('h1')).toBeVisible();
    await expectHealthyPage(page);
  });
}

test('job detail has SEO tags and JSON-LD', async ({ page }) => {
  await page.goto('/jobs');
  await page.locator('article h2 a').first().click();
  await expect(page.locator('h1')).toBeVisible();
  const ld = JSON.parse((await page.locator('#jobposting-ld').textContent()) ?? '{}');
  expect(ld['@type']).toBe('JobPosting');
  await expect(page.locator('meta[name="description"]')).toHaveAttribute('content', /.{50,}/);
  await expectHealthyPage(page);
});

for (const login of LOGINS) {
  test(`${login.email} lands on ${login.dashboard}`, async ({ page }) => {
    await signIn(page, login.email);
    await expect(page).toHaveURL(new RegExp(`${login.dashboard}$`));
    await expect(page.getByRole('heading', { level: 1, name: login.heading })).toBeVisible();
    await expectHealthyPage(page);
  });
}

test('candidate sees their applications and can sign out', async ({ page }) => {
  await signIn(page, 'candidate@demo.example');
  await expect(page.getByRole('heading', { level: 2 }).first()).toBeVisible();
  await page.getByRole('button', { name: /account menu/i }).click();
  await expect(page.getByRole('menuitem')).toHaveText(['Profile', 'Log out']);
  await page.getByRole('menuitem', { name: 'Log out' }).click();
  await expect(page).toHaveURL(/\/login$/);
});

test('a candidate cannot open the admin area', async ({ page }) => {
  await signIn(page, 'candidate@demo.example');
  await page.goto('/admin');
  await expect(page).toHaveURL(/\/candidate$/);
});
