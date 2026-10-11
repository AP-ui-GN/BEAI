import { defineConfig, devices } from "@playwright/test"

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:8732",
    trace: "retain-on-failure",
    ...devices["Desktop Chrome"],
  },
})
