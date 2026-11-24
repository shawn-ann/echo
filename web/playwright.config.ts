import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  globalSetup: './tests/global-setup.ts',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  timeout: 30_000,
  use: {
    channel: 'chrome',
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'on-first-retry',
  },
  webServer: [
    {
      command: 'STREAM_MVP_ENABLED=true COACH_MVP_ENABLED=true LLM_MODE=mock .venv/bin/uvicorn app.main:app --port 8000',
      cwd: '../backend',
      url: 'http://localhost:8000/api/v1/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'npm run dev -- --port 5173',
      url: 'http://localhost:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
