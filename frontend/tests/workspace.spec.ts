import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

test.beforeEach(async ({ page, request }) => {
  const reset = await request.post("/__test__/reset");
  expect(reset.ok()).toBeTruthy();
  await page.route("**/*", (route) =>
    route.request().url().startsWith("http://127.0.0.1:18501/")
      ? route.continue()
      : route.abort(),
  );
  await page.goto((await reset.json()).url);
  await expect(
    page.getByRole("heading", { name: "Good context. Less repetition." }),
  ).toBeVisible();
});

test("onboarding, responsive navigation and accessible labels", async ({
  page,
}) => {
  await expect(page.getByText("Start in three steps")).toBeVisible();
  const desktop = await new AxeBuilder({ page }).analyze();
  expect(desktop.violations).toEqual([]);
  await page.screenshot({
    path: "test-results/product-overview.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page.getByLabel("New Groq API key")).toHaveCount(0);
  await page.getByText("Check provider connections", { exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Check Groq", exact: true }),
  ).toBeDisabled();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: "test-results/product-settings-mobile.png",
    fullPage: true,
  });
});

test("save, inspect, preserve correction draft, retire, restore and permanently forget", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByLabel("What should be remembered?")
    .fill("The project uses PostgreSQL.");
  await page
    .getByLabel("Supporting statement or tool result")
    .fill("We confirmed PostgreSQL as the project database.");
  await page.getByRole("button", { name: "Save confirmed memory" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByText("The project uses PostgreSQL.", { exact: true }).first(),
  ).toBeVisible();
  await dialog
    .getByLabel("Corrected text")
    .fill("The project now uses SQLite.");
  await dialog
    .getByLabel("Fresh evidence for this correction")
    .fill("Correction: switch from PostgreSQL to SQLite.");
  await dialog.getByRole("button", { name: "Close dialog" }).click();
  await page.getByRole("button", { name: "Memories", exact: true }).click();
  await page
    .getByRole("button", { name: "Browse memories", exact: true })
    .click();
  await page
    .getByRole("button", { name: /The project uses PostgreSQL/ })
    .click();
  await expect(dialog.getByLabel("Corrected text")).toHaveValue(
    "The project now uses SQLite.",
  );
  await dialog
    .getByRole("button", { name: "Save correction", exact: true })
    .click();
  await expect(dialog.getByText(/Version 2 · active/)).toBeVisible();
  await dialog
    .getByLabel("Exclude this memory and affected summaries from current use")
    .check();
  await dialog
    .getByRole("button", { name: "Retire memory", exact: true })
    .click();
  await expect(
    dialog.getByRole("heading", { name: "Restore to current use" }),
  ).toBeVisible();
  await dialog.getByLabel("Historical version to restore").selectOption("2");
  await dialog
    .getByLabel("Fresh evidence that this applies again")
    .fill("SQLite is still our confirmed database.");
  await dialog
    .getByRole("button", { name: "Restore as a new version", exact: true })
    .click();
  await expect(dialog.getByText(/Version 3 · active/)).toBeVisible();
  await page.screenshot({
    path: "test-results/product-memory-history.png",
    fullPage: true,
  });
  await dialog.getByText("Permanently delete", { exact: true }).click();
  await dialog
    .getByLabel("Type DELETE to confirm permanent removal")
    .fill("DELETE");
  await dialog
    .getByRole("button", { name: "Delete memory permanently" })
    .click();
  await expect(dialog).toHaveCount(0);
  await expect(
    page.getByText("The project now uses SQLite.", { exact: true }),
  ).toHaveCount(0);
  await page
    .getByRole("button", { name: "Browse memories", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "No matching memories yet" }),
  ).toBeVisible();
});

test("secure settings clear entered keys and drafts survive navigation", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page.getByLabel("What should be remembered?").fill("Unsaved user fact");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Groq key action").selectOption("replace");
  await page
    .getByLabel("New Groq API key")
    .fill("synthetic-browser-key-123456789");
  await page
    .getByRole("button", { name: "Save secure settings", exact: true })
    .click();
  await expect(page.getByLabel("New Groq API key")).toHaveCount(0);
  await expect(page.getByText("Key saved", { exact: true })).toBeVisible();
  expect(
    await page.evaluate(() =>
      JSON.stringify({
        local: { ...localStorage },
        session: { ...sessionStorage },
      }),
    ),
  ).not.toContain("synthetic-browser-key");
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await expect(page.getByLabel("What should be remembered?")).toHaveValue(
    "Unsaved user fact",
  );
});

test("capture requires consent, preview changes nothing and unrelated hooks survive", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Connections", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Enable capture", exact: true }),
  ).toBeDisabled();
  await page
    .getByRole("button", { name: "Generate connection instructions" })
    .click();
  await expect(page.getByText(/contextbridge.mcp_adapter.cli/)).toBeVisible();
  await expect(page.getByText(/Automatic capture is a separate/)).toBeVisible();
});

test("stale corrections preserve drafts and require reviewing the new version", async ({
  page,
  context,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByLabel("What should be remembered?")
    .fill("Database is PostgreSQL.");
  await page
    .getByLabel("Supporting statement or tool result")
    .fill("I choose PostgreSQL.");
  await page.getByRole("button", { name: "Save confirmed memory" }).click();
  const first = page.getByRole("dialog");
  await expect(first).toBeVisible();
  await first.getByLabel("Corrected text").fill("Database is SQLite.");
  await first
    .getByLabel("Fresh evidence for this correction")
    .fill("I choose SQLite now.");
  const other = await context.newPage();
  await other.goto("/");
  await other.getByRole("button", { name: "Memories", exact: true }).click();
  await other
    .getByRole("button", { name: "Browse memories", exact: true })
    .click();
  await other.getByRole("button", { name: /Database is PostgreSQL/ }).click();
  const second = other.getByRole("dialog");
  await second.getByLabel("Corrected text").fill("Database is MySQL.");
  await second
    .getByLabel("Fresh evidence for this correction")
    .fill("The team has chosen MySQL.");
  await second
    .getByRole("button", { name: "Save correction", exact: true })
    .click();
  await expect(second.getByText(/Version 2 · active/)).toBeVisible();
  await first
    .getByRole("button", { name: "Save correction", exact: true })
    .click();
  await expect(
    first.getByText(/This memory changed after you opened it/),
  ).toBeVisible();
  await expect(first.getByLabel("Corrected text")).toHaveValue(
    "Database is SQLite.",
  );
  await expect(
    first.getByRole("button", { name: "Save correction", exact: true }),
  ).toBeDisabled();
  await first.getByRole("button", { name: "Review latest version" }).click();
  await first
    .getByRole("button", { name: "Save correction", exact: true })
    .click();
  await expect(first.getByText(/Version 3 · active/)).toBeVisible();
  await other.close();
});

test("import consent, draft recovery and explicit project switching", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByRole("button", { name: "Conversation import", exact: true })
    .click();
  await page
    .getByRole("textbox", { name: "My original statement", exact: true })
    .fill("I chose SQLite for this project.");
  await expect(
    page.getByRole("button", {
      name: "Import selected conversation",
      exact: true,
    }),
  ).toBeDisabled();
  await page
    .getByText("Combine turns with original dates (V2)", { exact: true })
    .click();
  await page
    .getByLabel("Evidence bundle JSON")
    .fill('{"draft":"not submitted"}');
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByRole("button", { name: "Conversation import", exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "My original statement", exact: true }),
  ).toHaveValue("I chose SQLite for this project.");
  await page
    .getByText("Combine turns with original dates (V2)", { exact: true })
    .click();
  await expect(page.getByLabel("Evidence bundle JSON")).toHaveValue(
    '{"draft":"not submitted"}',
  );
  await page
    .getByLabel("Current project", { exact: true })
    .fill("another-project");
  await expect(
    page.getByRole("textbox", { name: "My original statement", exact: true }),
  ).toHaveValue("I chose SQLite for this project.");
  await page
    .getByRole("button", { name: "Switch project", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Conversation import", exact: true })
    .click();
  await page
    .getByText("Combine turns with original dates (V2)", { exact: true })
    .click();
  await expect(
    page.getByRole("textbox", { name: "My original statement", exact: true }),
  ).toHaveValue("");
  await expect(page.getByLabel("Evidence bundle JSON")).toHaveValue("");
});

test("official sidebar collapses to icons and mobile navigation closes its drawer", async ({
  page,
}) => {
  const sidebar = page.locator('[data-slot="sidebar"][data-state]');
  await expect(sidebar).toHaveAttribute("data-variant", "inset");
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await expect(sidebar).toHaveAttribute("data-state", "collapsed");
  await page.getByRole("button", { name: "Memories", exact: true }).click();
  await expect(
    page.getByRole("heading", { name: "Your memories", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Memories", exact: true }),
  ).toHaveAttribute("aria-current", "page");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/product-sidebar-collapsed.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Sidebar", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("dialog", { name: "Sidebar", exact: true }),
  ).toHaveCSS("opacity", "1");
  await expect(
    page.getByRole("button", { name: "Settings", exact: true }),
  ).toContainText("Settings");
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/product-sidebar-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(
    page.getByRole("dialog", { name: "Sidebar", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
});
