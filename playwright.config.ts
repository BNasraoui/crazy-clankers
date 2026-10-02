import { defineConfig } from '@playwright/test';

// UI tests: every screen at desktop, laptop, Steam Deck and phone sizes (tests/ui/).
// Snapshots are made in the same container CI uses (mcr.microsoft.com/playwright, see
// .github/workflows/ui.yml), because fonts render slightly differently on every machine.
const phone = { isMobile: true, hasTouch: true, deviceScaleFactor: 2 };

export default defineConfig({
  testDir: 'tests/ui',
  timeout: 180_000,
  expect: { timeout: 30_000, toHaveScreenshot: { maxDiffPixelRatio: 0.01, animations: 'disabled' } },
  fullyParallel: true,
  workers: process.env.CI ? 2 : 2,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  updateSnapshots: 'missing', // a new screen's first run approves its snapshot (CI commits it)
  snapshotPathTemplate: '{testDir}/snapshots/{projectName}/{arg}{ext}',
  use: {
    baseURL: 'http://localhost:4173',
    launchOptions: { args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] },
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'npx vite build && npx vite preview --port 4173 --strictPort',
    url: 'http://localhost:4173',
    reuseExistingServer: !process.env.CI,
    timeout: 180_000,
  },
  projects: [
    { name: 'deck-1280x800', use: { viewport: { width: 1280, height: 800 } } },
    { name: 'laptop-1000x532', use: { viewport: { width: 1000, height: 532 } } },
    { name: 'laptop-1366x768', use: { viewport: { width: 1366, height: 768 } } },
    { name: 'desktop-1920x1080', use: { viewport: { width: 1920, height: 1080 } } },
    { name: 'phone-780x300', use: { viewport: { width: 780, height: 300 }, ...phone } },
    { name: 'phone-915x412', use: { viewport: { width: 915, height: 412 }, ...phone } },
  ],
});
