import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 5000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'npm run dev -- --port 5173 --host 127.0.0.1',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
      env: {
        ...(process.env.VITE_CLERK_PUBLISHABLE_KEY ? { VITE_CLERK_PUBLISHABLE_KEY: process.env.VITE_CLERK_PUBLISHABLE_KEY } : {}),
        ...(process.env.VITE_API_BASE_URL ? { VITE_API_BASE_URL: process.env.VITE_API_BASE_URL } : {}),
      },
    },
    {
      command: 'python -m uvicorn app.main:app --port 8000 --host 127.0.0.1',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      cwd: '../backend',
      timeout: 30_000,
      env: { PYTHONPATH: '.' },
    },
  ],
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
