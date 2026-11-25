import AxeBuilder from '@axe-core/playwright';
import { expect, test, type Page } from '@playwright/test';

/*
 * Week 2 flows against the seeded demo data. Moves change the data, so after
 * many runs some steps may find no candidate in the needed stage and skip.
 * `python manage.py seed --reset` restores a fresh pipeline.
 */
const PASSWORD = process.env.DEMO_PASSWORD ?? 'Demo@Pass2026';

async function signIn(page: Page, email: string) {
  await page.goto('/login');
  await page.getByLabel('Email').fill(email);
  await page.getByLabel('Password', { exact: false }).first().fill(PASSWORD);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).not.toHaveURL(/\/login/, { timeout: 15_000 });
  if (/^(recruiter|admin)@/.test(email)) await dismissHiraBriefing(page);
}

/** Recruiters and HR admins get HIRA's briefing once per session; close it so it does not cover the page. */
async function dismissHiraBriefing(page: Page) {
  const dialog = page.getByRole('dialog', { name: 'HIRA briefing' });
  try {
    await dialog.waitFor({ state: 'visible', timeout: 8_000 });
  } catch {
    return; // already seen in this session
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

async function openFirstJob(page: Page, view: 'Candidates' | 'Board') {
  // The newest job in the seed is closed and has no applicants, so filter to
  // open jobs and pick the first one that actually has candidates.
  await page.goto('/recruiter/jobs');
  const [response] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/api/jobs') && r.url().includes('status=open') && r.ok()),
    page.getByRole('button', { name: 'Open', exact: true }).click(),
  ]);
  const body = (await response.json()) as { results: { id: string; application_count?: number }[] };
  const job = body.results.find((j) => (j.application_count ?? 0) > 0);
  expect(job, 'an open job with candidates (run `python manage.py seed --reset`)').toBeTruthy();
  const path = view === 'Candidates' ? 'applications' : 'board';
  await page.locator(`a[href="/recruiter/jobs/${job!.id}/${path}"]`).click();
}

test('recruiter sees a ranked list with an explanation drawer', async ({ page }) => {
  await signIn(page, 'recruiter@demo.example');
  await openFirstJob(page, 'Candidates');
  await expect(page.getByRole('heading', { level: 1, name: /^Candidates · / })).toBeVisible();
  await expectAccessible(page);
  await page
    .getByRole('button', { name: /^Explain score for / })
    .first()
    .click();
  const drawer = page.getByRole('dialog', { name: 'Application details' });
  await expect(drawer.getByRole('heading', { name: /^Why \d+/ })).toBeVisible();
  await expect(drawer.getByRole('list', { name: 'Reasons for this score' })).toBeVisible();
  await expectAccessible(page);
});

test('blind candidates show a code and a redacted resume', async ({ page }) => {
  await signIn(page, 'recruiter@demo.example');
  await openFirstJob(page, 'Candidates');
  const blindRow = page.getByRole('button', { name: /^Explain score for Candidate #/ }).first();
  test.skip((await blindRow.count()) === 0, 'No blind candidates left in this job');
  await blindRow.click();
  const drawer = page.getByRole('dialog', { name: 'Application details' });
  await expect(drawer.getByText(/^Blind screening:/)).toBeVisible();
  await expect(drawer.getByRole('heading', { name: 'Resume (redacted)' })).toBeVisible();
  await expect(drawer.locator('pre')).toContainText('[hidden]');
  await expect(drawer.getByText(/Download original/)).toHaveCount(0);
});

test('board: drag a card from Applied to Screening', async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop', 'Drag is checked on desktop; mobile uses Move to');
  await signIn(page, 'recruiter@demo.example');
  await openFirstJob(page, 'Board');
  const applied = page.getByRole('region', { name: /^Applied/ });
  const handle = applied.getByRole('button', { name: /^Drag / }).first();
  test.skip((await handle.count()) === 0, 'No Applied candidates left to drag');
  const who = (await handle.getAttribute('aria-label'))!.replace(/^Drag /, '');
  const from = (await handle.boundingBox())!;
  const to = (await page.getByRole('region', { name: /^Screening/ }).boundingBox())!;
  await page.mouse.move(from.x + from.width / 2, from.y + from.height / 2);
  await page.mouse.down();
  await page.mouse.move(from.x + 40, from.y + 10, { steps: 5 });
  await page.mouse.move(to.x + to.width / 2, to.y + 60, { steps: 15 });
  await page.mouse.up();
  await expect(page.getByRole('status').filter({ hasText: `${who} moved to Screening.` })).toBeVisible();
});

test('board: keyboard Move to, and identity revealed at Interview', async ({ page }) => {
  await signIn(page, 'recruiter@demo.example');
  await openFirstJob(page, 'Board');
  await expectAccessible(page);
  const screening = page.getByRole('region', { name: /^Screening/ });
  const select = screening.getByLabel(/^Move Candidate #.* to$/).first();
  test.skip((await select.count()) === 0, 'No blind candidate waiting in Screening');
  const label = (await select.getAttribute('id'))!;
  const code = (await page.locator(`label[for="${label}"]`).innerText()).replace(/^Move /, '').replace(/ to$/, '');
  const cardId = (await select.locator('xpath=ancestor::li[1]').getAttribute('data-testid'))!;
  await select.selectOption('interview');
  await screening.getByRole('button', { name: `Move ${code}` }).click();
  await expect(page.getByRole('status').filter({ hasText: `${code} moved to Interview.` })).toBeVisible();
  // This job reveals identity at Interview: the card now shows a name, not the code.
  const card = page.getByRole('region', { name: /^Interview/ }).getByTestId(cardId);
  await expect(card).toBeVisible();
  await expect(card).not.toContainText('Candidate #');
});

test('hiring manager adds a note at Screening', async ({ page }) => {
  await signIn(page, 'manager@demo.example');
  await page
    .getByRole('link', { name: /^Board for / })
    .first()
    .click();
  const screening = page.getByRole('region', { name: /^Screening/ });
  const details = screening.getByRole('button', { name: /^Details and notes for / }).first();
  test.skip((await details.count()) === 0, 'No candidates in Screening for this manager');
  await expect(screening.getByLabel(/^Move .* to$/)).toHaveCount(0); // managers do not move cards
  await details.click();
  const drawer = page.getByRole('dialog', { name: 'Application details' });
  const note = `Good depth on APIs (${Date.now()})`;
  await drawer.getByLabel('Add a note').fill(note);
  await drawer.getByRole('button', { name: 'Thumbs up' }).click();
  await expect(drawer.getByText(note)).toBeVisible();
});

test('candidate asks HIRA for their application status', async ({ page }) => {
  await signIn(page, 'candidate@demo.example');
  await page.getByRole('button', { name: 'Ask HIRA' }).click();
  const panel = page.getByRole('dialog', { name: 'Ask HIRA' });
  await panel.getByRole('button', { name: 'What is my application status?' }).click();
  await expect(panel.getByText(/^Here is where your applications stand/)).toBeVisible();
  await expect(panel.getByRole('list', { name: 'Your applications' })).toBeVisible();
  await expectAccessible(page);
});

test('visitor asks HIRA for jobs', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Ask HIRA' }).click();
  const panel = page.getByRole('dialog', { name: 'Ask HIRA' });
  await panel.getByLabel('Your question').fill('python jobs in hyderabad');
  await panel.getByRole('button', { name: 'Send' }).click();
  await expect(panel.getByText(/^I found \d+ open jobs? for Python/)).toBeVisible();
  await expect(panel.getByRole('list', { name: 'Jobs' }).getByRole('link').first()).toBeVisible();
});

test('hr runs the fairness check', async ({ page }) => {
  await signIn(page, 'hr@demo.example');
  await page.goto('/hr/fairness');
  await page.getByRole('button', { name: 'Run the check' }).click();
  await expect(page.getByRole('heading', { level: 2, name: /variants tested, 0 score changes\.$/ })).toBeVisible();
  await expectAccessible(page);
});
