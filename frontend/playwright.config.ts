import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 45000,
  use: {
    baseURL: "http://127.0.0.1:18501",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "uv run --no-sync python -m tests.product.browser_server",
    cwd: "..",
    url: "http://127.0.0.1:18501/__test__/ready",
    reuseExistingServer: false,
    timeout: 30000,
  },
});
