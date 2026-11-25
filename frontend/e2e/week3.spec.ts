import AxeBuilder from '@axe-core/playwright';
import { expect, test, type APIRequestContext, type BrowserContext, type Page } from '@playwright/test';

/*
 * Week 3A flows against the seeded demo data (python manage.py seed --reset).
 * Some steps change data, so on a re-run a few may find nothing to do and skip.
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

/** JSON API call with the browser context's cookies and CSRF token. */
async function apiCall(context: BrowserContext, request: APIRequestContext, method: 'GET' | 'POST', path: string, data?: object) {
  const csrf = (await context.cookies()).find((c) => c.name === 'csrftoken')?.value ?? '';
  const response = await request.fetch(`/api${path}`, {
    method,
    data,
    headers: method === 'GET' ? {} : { 'X-CSRFToken': csrf },
  });
  return { status: response.status(), body: response.ok() ? await response.json() : null };
}

test('recruiter gets the HIRA briefing once, then the activity page', async ({ page }) => {
  await signIn(page, 'recruiter@demo.example');
  const dialog = page.getByRole('dialog', { name: 'HIRA briefing' });
  await expect(dialog).toBeVisible({ timeout: 10_000 });
  await expect(dialog.getByTestId('hira-message')).toContainText('While you were away, HIRA');
  await expect(dialog.getByRole('button', { name: 'Play spoken briefing' })).toBeVisible();
  await expectAccessible(page);
  await dialog.getByRole('button', { name: 'Close' }).click();
  await page.reload();
  await expect(page.getByRole('heading', { level: 1, name: 'Hiring overview' })).toBeVisible();
  await page.waitForTimeout(1_000);
  await expect(dialog).toHaveCount(0); // once per session
  // The sidebar sits behind the menu at 390 px, so go straight to the page.
  await page.goto('/hira');
  await expect(page.getByRole('heading', { level: 1, name: 'HIRA activity' })).toBeVisible();
  await expect(page.getByText('Interviews scheduled')).toBeVisible();
  await page.getByRole('button', { name: 'Table' }).click();
  await expect(page.getByRole('table', { name: 'HIRA actions per day' })).toBeVisible();
  await expect(page.getByRole('table', { name: /activity log/ })).toBeVisible();
  await expectAccessible(page);
});

test('candidate picks a slot HIRA offered after the recruiter moves them to Interview', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Changes shared data; run once');
  const candidateContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const candidate = await candidateContext.newPage();
  await signIn(candidate, 'candidate@demo.example');
  let mine = await apiCall(candidateContext, candidate.request, 'GET', '/my/interviews');
  const active = (mine.body?.results ?? []).filter((i: { status: string }) => ['pending', 'scheduled'].includes(i.status));
  if (active.length === 0) {
    // Move one of the candidate's early applications to Interview as the recruiter who owns it.
    const apps = await apiCall(candidateContext, candidate.request, 'GET', '/applications?page_size=50');
    const early = (apps.body?.results ?? []).find(
      (a: { status: string; job: { title: string } }) =>
        ['applied', 'screening'].includes(a.status) && a.job.title === 'Java Backend Engineer',
    );
    test.skip(!early, 'No early-stage application left for the demo candidate');
    const recruiterContext = await browser.newContext();
    const recruiter = await recruiterContext.newPage();
    await signIn(recruiter, 'recruiter@demo.example');
    if (early.status === 'applied') {
      expect(
        (await apiCall(recruiterContext, recruiter.request, 'POST', `/applications/${early.id}/status`, { status: 'screening' })).status,
      ).toBe(200);
    }
    expect(
      (await apiCall(recruiterContext, recruiter.request, 'POST', `/applications/${early.id}/status`, { status: 'interview' })).status,
    ).toBe(200);
    await recruiterContext.close();
    mine = await apiCall(candidateContext, candidate.request, 'GET', '/my/interviews');
  }
  await candidate.goto('/candidate');
  const picker = candidate.getByRole('group', { name: /Times when your interviewers are free/ });
  const calendar = candidate.getByRole('link', { name: /Add to calendar/ }).first();
  // count() does not wait, so wait until the interviews have loaded: either slots to pick or a booked time.
  await expect(picker.or(calendar).first()).toBeVisible();
  if (await picker.isVisible()) {
    await Promise.all([
      candidate.waitForResponse((r) => r.url().includes('/hold') && r.request().method() === 'POST'),
      picker.getByRole('radio').first().check(),
    ]);
    await expect(candidate.getByText(/Held for you until/)).toBeVisible();
    await Promise.all([
      candidate.waitForResponse((r) => r.url().includes('/confirm') && r.request().method() === 'POST'),
      candidate.getByRole('button', { name: 'Confirm this time' }).click(),
    ]);
  }
  await expect(candidate.getByRole('link', { name: /Add to calendar/ }).first()).toBeVisible();
  await expect(candidate.getByText('Simulated').first()).toBeVisible();
  await expectAccessible(candidate);
  await candidateContext.close();
});

test('an interviewer fills in a scorecard', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Submits once; the form is checked at 390 px below');
  await signIn(page, 'employee@demo.example');
  await page.getByRole('link', { name: 'My interviews' }).first().click();
  await expect(page.getByRole('heading', { level: 1, name: 'My interviews' })).toBeVisible();
  const fill = page.getByRole('link', { name: /^Fill in scorecard/ }).first();
  test.skip((await fill.count()) === 0, 'No scorecards waiting for employee@demo.example');
  await fill.click();
  await expect(page.getByText(/Hidden until you submit your own scorecard|No other scorecards yet/)).toBeVisible();
  const groups = page.getByRole('group').filter({ has: page.getByRole('radio', { name: /4: Strong/ }) });
  const count = await groups.count();
  for (let i = 0; i < count; i += 1) {
    await groups
      .nth(i)
      .getByRole('radio', { name: /4: Strong/ })
      .check({ force: true });
  }
  await page.getByRole('radio', { name: 'Yes', exact: true }).check();
  await expectAccessible(page);
  await page.getByRole('button', { name: 'Submit scorecard' }).click();
  await expect(page.getByText(/Your scorecard is in/)).toBeVisible();
});

test('scorecard page and my interviews fit a phone', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-390', 'Phone layout check');
  await signIn(page, 'employee@demo.example');
  await page.goto('/interviews');
  await expect(page.getByRole('heading', { level: 1, name: 'My interviews' })).toBeVisible();
  await expectAccessible(page);
  const any = page.getByRole('link', { name: /^(Fill in scorecard|View feedback)/ }).first();
  test.skip((await any.count()) === 0, 'No interviews with feedback for employee@demo.example');
  await any.click();
  await expect(page.getByRole('heading', { level: 1, name: /^Scorecard: / })).toBeVisible();
  await expectAccessible(page);
});

test('offer approval: hiring manager, then HR', async ({ browser }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Changes shared data; run once');
  const managerContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const manager = await managerContext.newPage();
  await signIn(manager, 'manager@demo.example');
  await manager.goto('/offers');
  await expect(manager.getByRole('heading', { level: 1, name: 'Offers' })).toBeVisible();
  const open = manager.getByRole('link', { name: /^Open/ }).first();
  test.skip((await open.count()) === 0, 'No offers waiting for this hiring manager');
  await open.click();
  await manager.getByRole('button', { name: 'Approve' }).click();
  await expect(manager.getByText('Waiting for HR')).toBeVisible();
  const offerUrl = manager.url();
  await expectAccessible(manager);
  await managerContext.close();

  const adminContext = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const admin = await adminContext.newPage();
  await signIn(admin, 'hr@demo.example');
  await closeBriefing(admin);
  await admin.goto(offerUrl);
  await admin.getByRole('button', { name: 'Approve' }).click();
  await expect(admin.getByText('Approved', { exact: true })).toBeVisible();
  await adminContext.close();
});

test('recruiter reads the interview plan and the offers list on a phone', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile-390', 'Phone layout check');
  await signIn(page, 'recruiter@demo.example');
  await closeBriefing(page);
  await page.goto('/offers');
  await expect(page.getByRole('heading', { level: 1, name: 'Offers' })).toBeVisible();
  await expectAccessible(page);
  await page.goto('/recruiter/jobs');
  await page
    .getByRole('link', { name: /^Board for / })
    .first()
    .click();
  await page.getByRole('link', { name: 'Interview plan' }).click();
  await expect(page.getByRole('heading', { level: 1, name: /^Interview plan/ })).toBeVisible();
  await expect(page.getByText('Let HIRA schedule')).toBeVisible();
  await expectAccessible(page);
});

test('scheduling link: a tampered link is refused kindly', async ({ page }) => {
  await page.goto('/schedule/not-a-real-token');
  await expect(page.getByRole('heading', { level: 1, name: 'Pick your interview time' })).toBeVisible();
  await expect(page.getByText(/This scheduling link is not valid/)).toBeVisible();
  await expectAccessible(page);
});
