import path from "node:path"
import { fileURLToPath } from "node:url"

import { expect, test } from "@playwright/test"

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../backend/tests/fixtures/1UBQ.pdb",
)

test("uploads 1UBQ, shows the viewer, changes chain, and downloads a report", async ({ page }) => {
  await page.goto("/proteins")
  await page.locator("#structure-file").setInputFiles(fixture)
  await expect(page.getByRole("heading", { name: "1UBQ.pdb" })).toBeVisible()
  await expect(page.getByRole("cell", { name: "76" }).first()).toBeVisible()

  const canvas = page.getByTestId("structure-viewer").locator("canvas")
  await expect(canvas).toBeVisible()
  const box = await canvas.boundingBox()
  expect(box).not.toBeNull()
  expect(box?.width ?? 0).toBeGreaterThan(0)
  expect(box?.height ?? 0).toBeGreaterThan(0)

  await page.getByTestId("chain-select").selectOption("A")
  await expect(page.getByTestId("chain-select")).toHaveValue("A")

  const downloadPromise = page.waitForEvent("download")
  await page.getByRole("link", { name: "Download HTML" }).click()
  const download = await downloadPromise
  expect(download.suggestedFilename()).toMatch(/\.html$/)
})
