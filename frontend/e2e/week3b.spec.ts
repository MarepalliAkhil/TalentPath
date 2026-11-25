import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type Page } from '@playwright/test';

/*
 * Week 3B walkthrough against fresh demo data (python manage.py seed --reset):
 * hire the accepted candidate, sign in as the new employee, finish a checklist item,
 * apply for leave on a day the team is already short (clash warning), the manager
 * approves, and Ask HIRA shows the balance. The serial flow changes data, so it runs
 * once (desktop) and skips itself when the hire has already happened.
 */
const PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo@Pass2026';
const JOINER = 'joiner@demo.example';
const JOINER_NAME = 'Ishaan Malhotra';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: false }).first().fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
}

/** Sign in as the joiner; skip the rest of the flow when the hire has not happened. */
async function signInAsJoiner(page: Page) {
  await signIn(page, JOINER);
  test.skip(/\/candidate/.test(page.url()), 'The demo joiner has not been hired yet (run: python manage.py seed --reset)');
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

async function apiGet<T>(request: APIRequestContext, path: string): Promise<T | null> {
  const response = await request.get(`/api${path}`);
  return response.ok() ? ((await response.json()) as T) : null;
}

type Calendar = {
  days: { date: string; kind: string }[];
  entries: { employee: string; start: string; end: string }[];
  team: { members: unknown[] };
};

/** The working day (from the joining date on) in the next two months on which most teammates are already off. */
async function busiestDay(request: APIRequestContext): Promise<string | null> {
  const me = await apiGet<{ employee: { joined_on: string } }>(request, '/onboarding/me');
  const now = new Date(Date.now() + 330 * 60_000);
  const months = [0, 1].map((d) => {
    const m = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + d, 1));
    return m.toISOString().slice(0, 7);
  });
  const today = now.toISOString().slice(0, 10);
  const from = me && me.employee.joined_on > today ? me.employee.joined_on : today;
  let best: { day: string; off: number } | null = null;
  for (const month of months) {
    const cal = await apiGet<Calendar>(request, `/team-calendar?month=${month}`);
    if (!cal) continue;
    for (const d of cal.days) {
      if (d.kind !== 'working' || d.date <= from) continue;
      const off = new Set(cal.entries.filter((e) => e.start <= d.date && d.date <= e.end).map((e) => e.employee)).size;
      if (!best || off > best.off) best = { day: d.date, off };
    }
  }
  return best && best.off >= 2 ? best.day : null;
}

const desktopOnly = () => test.skip(test.info().project.name !== 'desktop', 'Changes shared data; runs once');

test.describe.serial('one-click hire to first leave', () => {
  test('hr hires the accepted candidate in one click', async ({ page }) => {
    desktopOnly();
    await signIn(page, 'hr@demo.example');
    await closeBriefing(page);
    const offers = await apiGet<{
      results: { id: string; status: string; job: { title: string }; candidate: { full_name: string | null } }[];
    }>(page.request, '/offers?status=accepted');
    const offer = offers?.results.find((o) => o.candidate.full_name === JOINER_NAME || o.job.title === 'Frontend Engineer (React)');
    test.skip(!offer, 'No accepted offer for the demo joiner (run: python manage.py seed --reset)');
    await page.goto(`/offers/${offer!.id}`);
    await expect(page.getByRole('heading', { level: 1, name: /^Offer:/ })).toBeVisible();
    const hire = page.getByRole('button', { name: 'Hire', exact: true });
    test.skip((await hire.count()) === 0, 'Already hired');
    await hire.click();
    const dialog = page.getByRole('dialog', { name: `Hire ${JOINER_NAME}?` });
    await expect(dialog.getByText(/switch the same login to the employee role/)).toBeVisible();
    await dialog.getByRole('button', { name: 'Hire now' }).click();
    await expect(page.getByText(/Hired: employee LW\d+/)).toBeVisible();
    await page.getByRole('link', { name: 'See onboarding progress' }).click();
    await expect(page.getByRole('heading', { level: 1, name: `Onboarding: ${JOINER_NAME}` })).toBeVisible();
    await expect(page.getByRole('progressbar')).toBeVisible();
  });

  test('the new employee sees the welcome page and finishes a checklist item', async ({ page }) => {
    desktopOnly();
    await signInAsJoiner(page);
    await expect(page.getByRole('heading', { level: 1, name: /Welcome to Lumina Works, Ishaan/ })).toBeVisible();
    await expect(page.getByText('Your buddy', { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { name: 'Your first week' })).toBeVisible();
    const ack = page.getByRole('button', { name: /I have read and accept: Read and acknowledge the code of conduct/ });
    if (await ack.count()) {
      await ack.click();
      await expect(ack).toHaveCount(0);
    }
    await expect(page.getByText(/Read and acknowledge the code of conduct \(done\)/)).toBeAttached();
    await expectAccessible(page);
  });

  test('applying for leave on a busy day shows the clash warning, and it is not blocked', async ({ page }) => {
    desktopOnly();
    await signInAsJoiner(page);
    const day = await busiestDay(page.request);
    test.skip(!day, 'No day where the team is already short');
    await page.goto('/leave');
    await expect(page.getByRole('heading', { level: 1, name: 'Leave' })).toBeVisible();
    await page.getByLabel(/Leave type/).selectOption('casual');
    await page.getByLabel(/^From/).fill(day!);
    await expect(page.getByTestId('days-counted')).toHaveText('1 day');
    await expect(page.getByText(/are already off on/)).toBeVisible();
    await expect(page.getByText(/you can still go ahead/)).toBeVisible();
    await page.getByRole('button', { name: 'Apply for 1 day' }).click();
    await expect(page.getByText(/Sent for approval/)).toBeVisible();
  });

  test('the reporting manager approves, seeing the same warning', async ({ page }) => {
    desktopOnly();
    await signIn(page, 'manager@demo.example');
    await page.goto('/leave/approvals');
    await expect(page.getByRole('heading', { level: 1, name: 'Approvals' })).toBeVisible();
    await expect(page.getByRole('heading', { level: 2, name: /^Leave \(/ })).toBeVisible();
    const approve = page.getByRole('button', { name: `Approve leave for ${JOINER_NAME}` });
    test.skip((await approve.count()) === 0, 'Nothing waiting for the manager from the joiner');
    await expect(page.getByText(/are already off on/).first()).toBeVisible();
    await approve.first().click();
    await page.getByRole('dialog').getByRole('button', { name: 'Approve' }).click();
    await expect(page.getByText(`Approved: ${JOINER_NAME}.`)).toBeVisible();
  });

  test('Ask HIRA answers the leave balance from the employee’s own data', async ({ page }) => {
    desktopOnly();
    await signInAsJoiner(page);
    await page.getByRole('button', { name: /Ask HIRA/ }).click();
    const panel = page.getByRole('dialog', { name: 'Ask HIRA' });
    await panel.getByLabel('Your question').fill('how many leaves do i have left');
    await panel.getByRole('button', { name: 'Send' }).click();
    await expect(panel.getByText(/Available now: Casual leave/)).toBeVisible();
    await expect(panel.getByRole('table', { name: 'Your leave balances' })).toBeVisible();
  });
});

test.describe('week 3B screens are accessible', () => {
  for (const path of ['/leave', '/leave/approvals', '/team-calendar', '/attendance', '/hr/policies']) {
    test(`employee ${path}`, async ({ page }) => {
      await signIn(page, 'employee@demo.example');
      await page.goto(path);
      await expect(page.locator('h1')).toBeVisible();
      await page.waitForLoadState('networkidle');
      await expectAccessible(page);
    });
  }

  test('hr onboarding and HR settings', async ({ page }) => {
    await signIn(page, 'hr@demo.example');
    await closeBriefing(page);
    for (const path of ['/onboarding', '/hr/settings']) {
      await page.goto(path);
      await expect(page.locator('h1')).toBeVisible();
      await page.waitForLoadState('networkidle');
      await expectAccessible(page);
    }
  });
});
