import { defineConfig, devices } from '@playwright/test';

/**
 * End-to-end tests. They expect the backend on :8000 with the demo seed loaded
 * (python manage.py seed). The frontend dev server is started automatically.
 */
export default defineConfig({
  testDir: './e2e',
  // The local dev server runs Django's sync views one at a time, so pages can be slow while
  // several browsers sign in at once: two workers, roomier timeouts.
  timeout: 60_000,
  expect: { timeout: 10_000 },
  workers: 2,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } },
    {
      name: 'mobile-390',
      use: { ...devices['Desktop Chrome'], viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
    },
  ],
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:5173',
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
