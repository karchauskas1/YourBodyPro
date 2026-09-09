import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  workers: 2,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:43720',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'mobile-chrome', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium', channel: process.env.CI ? undefined : 'chrome' } }],
  webServer: {
    command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 43720 --strictPort',
    url: 'http://127.0.0.1:43720',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
