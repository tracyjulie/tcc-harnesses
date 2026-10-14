import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  outputDir: process.env.PW_OUTPUT_DIR ?? 'test-results',
  timeout: 45000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [
    ['list'],
    ['json', { outputFile: process.env.PW_REPORT ?? 'playwright-report.json' }],
  ],
  use: {
    baseURL: process.env.APP_URL ?? 'http://127.0.0.1:4173',
    headless: true,
    viewport: { width: 960, height: 720 },
    trace: 'off',
    screenshot: 'off',
  },
});
