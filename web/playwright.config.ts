import { defineConfig, devices } from "@playwright/test";
import { resolve } from "node:path";
const external = process.env.PLAYWRIGHT_BASE_URL;
const port = process.env.PLAYWRIGHT_HTTP_PORT || "18787";
const inspectorPort = process.env.PLAYWRIGHT_INSPECTOR_PORT || "18788";
const baseURL = external || `http://127.0.0.1:${port}`;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  workers: 2,
  timeout: 120000,
  expect: { timeout: 15000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions: { channel: process.env.PLAYWRIGHT_CHANNEL },
  },
  projects: [
    {
      name: "desktop-chromium",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1440, height: 1000 },
      },
    },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"] } },
  ],
  webServer: external
    ? undefined
    : {
        command: `npm run test:serve -- --port ${port} --inspector-port ${inspectorPort}`,
        url: baseURL + "/api/health",
        timeout: 120000,
        reuseExistingServer: false,
        env: {
          WRANGLER_SEND_METRICS: "false",
          WRANGLER_LOG_PATH: resolve(".wrangler/playwright-logs"),
        },
      },
});
