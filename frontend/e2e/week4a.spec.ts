import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/*
 * Week 4A against fresh demo data (python manage.py seed --reset): the candidate's skill-gap map,
 * an employee applying internally, hr_admin analytics, and the public For recruiters page with a
 * demo button (only when the backend runs with DEMO_MODE=true, as in backend/.env.example).
 */
const PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo@Pass2026';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: false }).first().fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

async function closeBriefing(page: Page) {
  const dialog = page.getByRole('dialog', { name: 'HIRA briefing' });
  try {
    await dialog.waitFor({ state: 'visible', timeout: 8_000 });
  } catch {
    return;
  }
  await dialog.getByRole('button', { name: 'Close' }).click();
  await expect(dialog).toBeHidden();
}

async function expectAccessible(page: Page) {
  await expect(page.locator('h1')).toHaveCount(1);
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow, 'no horizontal page scrolling').toBeLessThanOrEqual(0);
  const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa']).analyze();
  expect(results.violations.map((v) => `${v.id} (${v.nodes.length})`)).toEqual([]);
}

test('candidate sees jobs they are closest to and a skill-gap map', async ({ page }) => {
  await signIn(page, 'candidate@demo.example');
  await page.goto('/career');
  await expect(page.getByRole('heading', { level: 1, name: 'Your career map' })).toBeVisible();
  const first = page.getByRole('link', { name: /^See the skill map for / }).first();
  await expect(first).toBeVisible();
  await expectAccessible(page);
  await first.click();
  await expect(page.getByRole('heading', { level: 1, name: /^Skill map: / })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Your learning path' })).toBeVisible();
  for (const link of await page.locator('main a[href^="https://"]').all()) {
    expect(await link.getAttribute('rel')).toContain('noopener');
  }
  await expectAccessible(page);
});

test('employee applies internally after reading the manager rule', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Changes shared data; runs once');
  await signIn(page, 'employee@demo.example');
  await page.goto('/internal-jobs');
  await expect(page.getByRole('heading', { level: 1, name: 'Internal jobs' })).toBeVisible();
  await expect(page.getByText(/reaches the Interview stage/).first()).toBeVisible();
  const apply = page.getByRole('button', { name: 'Apply for Engineering Manager, Platform Services' });
  test.skip((await apply.count()) === 0, 'Already applied (run: python manage.py seed --reset)');
  await apply.click();
  const dialog = page.getByRole('dialog', { name: 'Apply for Engineering Manager, Platform Services?' });
  await expect(dialog.getByText(/Nobody is told when you apply/)).toBeVisible();
  await dialog.getByRole('button', { name: 'Send application' }).click();
  await expect(page.getByText('Application sent for Engineering Manager, Platform Services.')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'My internal applications' })).toBeVisible();
});

test('hr_admin analytics: summaries, table view and CSV', async ({ page }) => {
  await signIn(page, 'admin@demo.example');
  await closeBriefing(page);
  await page.goto('/analytics');
  await expect(page.getByRole('heading', { level: 1, name: 'Analytics' })).toBeVisible();
  await expect(page.getByTestId('summary-funnel')).toContainText('applications');
  await page.getByRole('button', { name: 'Table' }).first().click();
  await expect(page.locator('main table').first()).toBeVisible();
  const csv = page.getByRole('link', { name: 'CSV of Funnel conversion' });
  const response = await page.request.get((await csv.getAttribute('href')) ?? '');
  expect(response.status()).toBe(200);
  expect(await response.text()).toContain('Stage,Applications reaching it');
  await expectAccessible(page);
  await page.getByRole('button', { name: 'People' }).click();
  await expect(page.getByRole('heading', { name: 'Leave utilisation by type', exact: false })).toBeVisible();
  await expectAccessible(page);
});

test('the For recruiters page is public, accessible and can start the demo', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('link', { name: 'For recruiters' }).first().click();
  await expect(page.getByRole('heading', { level: 1, name: 'For recruiters' })).toBeVisible();
  await expect(page).toHaveTitle(/For recruiters/);
  await expect(page.locator('main img')).toHaveCount(0);
  for (const name of ['Phenom', 'TurboHire', 'Darwinbox', 'Keka']) {
    await expect(page.getByRole('heading', { level: 2, name })).toBeVisible();
  }
  await expectAccessible(page);
  const config = (await (await page.request.get('/api/demo/config')).json()) as { demo_mode: boolean };
  test.skip(!config.demo_mode, 'DEMO_MODE is off on this backend');
  await page.getByRole('button', { name: 'Try as candidate' }).click();
  await expect(page).toHaveURL(/\/candidate/);
  await expect(page.getByText('Demo data, resets nightly')).toBeVisible();
});
