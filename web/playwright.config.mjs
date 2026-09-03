import { defineConfig, devices } from 'playwright/test';

// Keep Playwright's local web-server probe off corporate HTTP proxies. This
// prevents a proxy-generated 400 response from being mistaken for an existing
// Vite server on port 4173.
const localNoProxy = ['127.0.0.1', 'localhost', '::1'];
for (const key of ['NO_PROXY', 'no_proxy']) {
  const current = (process.env[key] || '').split(',').map((item) => item.trim()).filter(Boolean);
  process.env[key] = [...new Set([...current, ...localNoProxy])].join(',');
}

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  // The integrated dashboard renders the 252-row planning matrix, workforce
  // rows and governance panels after the API response. Keep assertions
  // tolerant of cold CI runners without weakening the test cases themselves.
  expect: { timeout: 15000 },
  fullyParallel: false,
  workers: 1,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    headless: true,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'scripts/run_backend_for_e2e.sh',
      cwd: '..',
      url: 'http://127.0.0.1:8000/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
  ],
});
