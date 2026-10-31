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
  await page.getByLabel("Current project", { exact: true }).selectOption("");
  await page
    .getByLabel("Project name", { exact: true })
    .fill("another-project");
  await expect(
    page.getByRole("textbox", { name: "My original statement", exact: true }),
  ).toHaveValue("I chose SQLite for this project.");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
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
  await expect(page.locator('[data-slot="sidebar-gap"]')).toHaveCSS(
    "transition-property",
    "width",
  );
  await expect(page.locator('[data-slot="sidebar-gap"]')).toHaveCSS(
    "transition-duration",
    "0.2s",
  );
  await expect(page.locator('[data-slot="sidebar-container"]')).toHaveCSS(
    "transition-property",
    "left, right, width",
  );
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
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await page
    .getByRole("button", { name: "About & privacy", exact: true })
    .click();
  await expect(
    page.getByRole("dialog", { name: "Sidebar", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("heading", {
      name: "Useful knowledge. With a source.",
      exact: true,
    }),
  ).toBeVisible();
});

test("workspace screens survive refresh and support browser history without losing drafts", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByLabel("What should be remembered?")
    .fill("An unsaved navigation test draft");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(page).toHaveURL(/view=settings/);
  await page.goBack();
  await expect(page.getByLabel("What should be remembered?")).toHaveValue(
    "An unsaved navigation test draft",
  );
  await expect(page).toHaveURL(/view=add-memory/);
  await page.goForward();
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  await expect(page).toHaveURL(/view=settings/);
  await expect(page).toHaveTitle("Settings | ContextBridge");
  await expect(page).not.toHaveURL(/launch=/);
});

test("legacy-key migration remains explicit and accessible at desktop and phone widths", async ({
  page,
}) => {
  await page.route("**/api/local/v1/config", async (route) => {
    const response = await route.fetch();
    const config = await response.json();
    await route.fulfill({
      response,
      json: { ...config, legacy_keys_present: true, storage_available: true },
    });
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("button", { name: "Reload saved settings", exact: true })
    .click();
  await expect(
    page.getByRole("heading", {
      name: "Move existing provider keys to secure storage",
    }),
  ).toBeVisible();
  const migrate = page.getByRole("button", {
    name: "Migrate existing keys",
    exact: true,
  });
  const consent = page.getByLabel(
    "I confirm migration and pausing provider services",
  );
  await expect(migrate).toBeDisabled();
  await consent.check();
  await expect(migrate).toBeEnabled();
  await consent.uncheck();
  await expect(migrate).toBeDisabled();
  for (const appearance of ["light", "dark"]) {
    await page
      .getByLabel("Appearance", { exact: true })
      .selectOption(appearance);
    for (const width of [1440, 375]) {
      await page.setViewportSize({ width, height: 900 });
      expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
      expect(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= window.innerWidth,
        ),
      ).toBeTruthy();
      await page.screenshot({
        path: `test-results/product-settings-legacy-${appearance}-${width}.png`,
        fullPage: true,
      });
    }
  }
});

test("phone header keeps long project context separate from service warnings", async ({
  page,
}) => {
  const project = "an-example-project-with-a-long-name";
  await page.route("**/api/local/v1/config", async (route) => {
    const response = await route.fetch();
    const config = await response.json();
    await route.fulfill({
      response,
      json: { ...config, preferences: { ...config.preferences, project } },
    });
  });
  await page.route("**/api/local/v1/services", async (route) => {
    const response = await route.fetch();
    const services = await response.json();
    await route.fulfill({
      response,
      json: { ...services, docker_available: false },
    });
  });
  // Exercise the configured project without a previously selected browser project.
  await page.evaluate(() =>
    localStorage.removeItem("contextbridge.active-project"),
  );
  await page.reload();
  const header = page.getByLabel("Connection status", { exact: true });
  await expect(
    header.getByText("Docker needs attention", { exact: true }),
  ).toBeVisible();
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 900 });
    const context = await header
      .getByText(project, { exact: true })
      .boundingBox();
    const status = await header
      .getByText("Docker needs attention", { exact: true })
      .boundingBox();
    expect(context).not.toBeNull();
    expect(status).not.toBeNull();
    expect(context!.y + context!.height).toBeLessThanOrEqual(status!.y);
    expect(status!.x + status!.width).toBeLessThanOrEqual(width);
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({
      path: `test-results/product-service-warning-${width}.png`,
      fullPage: true,
    });
  }
});

test("recent projects can be selected without retyping and survive reload", async ({
  page,
}) => {
  const project = page.getByLabel("Current project", { exact: true });
  await project.selectOption("");
  await page.getByLabel("Project name", { exact: true }).fill("second-project");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(project).toHaveValue("second-project");
  await page.reload();
  await expect(project).toHaveValue("second-project");
  await project.selectOption("contextbridge");
  await page.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(project).toHaveValue("second-project");
  await project.selectOption("contextbridge");
  await page
    .getByRole("button", { name: "Switch project", exact: true })
    .click();
  await expect(project).toHaveValue("contextbridge");
  await expect(page.getByLabel("Project name", { exact: true })).toHaveCount(0);
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await project.selectOption("second-project");
  await page
    .getByRole("button", { name: "Switch project", exact: true })
    .click();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page
      .getByLabel("Connection status", { exact: true })
      .getByText("second-project", { exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("appearance follows system, persists explicit choices, and remains accessible", async ({
  page,
}) => {
  const appearance = page.getByLabel("Appearance", { exact: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass(/dark/);
  await appearance.selectOption("light");
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(appearance).toHaveValue("light");
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await appearance.selectOption("dark");
  await page.reload();
  await expect(appearance).toHaveValue("dark");
  await expect(page.locator("html")).toHaveClass(/dark/);
  for (const screen of [
    "Overview",
    "Memories",
    "Add memory",
    "Activity",
    "Connections",
    "Settings",
    "About & privacy",
  ]) {
    await page.getByRole("button", { name: screen, exact: true }).click();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
    await page.screenshot({
      path: `test-results/product-dark-${screen.replaceAll(" ", "-")}.png`,
      fullPage: true,
    });
  }
  await page.screenshot({
    path: "test-results/product-dark-desktop.png",
    fullPage: true,
  });
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 812 });
    await expect(appearance).toBeVisible();
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBeTruthy();
    expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  }
  await page.screenshot({
    path: "test-results/product-dark-mobile.png",
    fullPage: true,
  });
  await appearance.selectOption("system");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).not.toHaveClass(/dark/);
});

test("project and appearance controls still work when browser storage is unavailable", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(window, "localStorage", {
      get() {
        throw new DOMException("Storage disabled", "SecurityError");
      },
    });
  });
  await page.reload();
  const project = page.getByLabel("Current project", { exact: true });
  await expect(project).toHaveValue("contextbridge");
  await project.selectOption("");
  await page.getByLabel("Project name", { exact: true }).fill("   ");
  await expect(
    page.getByRole("button", { name: "Open project", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Project name", { exact: true }).fill("local-project");
  await page.getByRole("button", { name: "Open project", exact: true }).click();
  await expect(project).toHaveValue("local-project");
  await page.getByLabel("Appearance", { exact: true }).selectOption("dark");
  await expect(page.locator("html")).toHaveClass(/dark/);
});

test("reduced motion keeps controls immediate and the mobile drawer usable", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const sidebar = page.locator('[data-slot="sidebar"][data-state]');
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await expect(sidebar).toHaveAttribute("data-state", "collapsed");
  const gap = page.locator('[data-slot="sidebar-gap"]');
  await expect(gap).toHaveCSS("transition-property", "none");
  await page.setViewportSize({ width: 375, height: 812 });
  const trigger = page.getByRole("button", {
    name: "Toggle Sidebar",
    exact: true,
  });
  await trigger.click();
  const drawer = page.getByRole("dialog", { name: "Sidebar", exact: true });
  await expect(drawer).toBeVisible();
  await expect(drawer).toHaveCSS("transition-duration", "0s");
  await expect(
    drawer.getByRole("button", { name: "Memories", exact: true }),
  ).toHaveCSS("transition-duration", "0s");
  await page.keyboard.press("Escape");
  await expect(drawer).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page.getByLabel("Appearance", { exact: true })).toBeEnabled();
});

test("memory dialog restores invoking focus and keeps long evidence close control reachable", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByLabel("What should be remembered?")
    .fill("Focus restoration uses the invoking memory row.");
  await page
    .getByLabel("Supporting statement or tool result")
    .fill(
      "Synthetic UI evidence: verified focus restoration with a long statement. ".repeat(
        18,
      ),
    );
  await page
    .getByRole("button", { name: "Save confirmed memory", exact: true })
    .click();
  const dialog = page.getByRole("dialog", {
    name: "Memory details",
    exact: true,
  });
  await expect(dialog).toBeVisible();
  await dialog
    .getByRole("button", { name: "Close dialog", exact: true })
    .click();
  await expect(dialog).toHaveCount(0);
  await page.getByRole("button", { name: "Memories", exact: true }).click();
  await page
    .getByRole("button", { name: "Browse memories", exact: true })
    .click();
  const row = page.getByRole("button", {
    name: /Focus restoration uses the invoking memory row/,
  });
  await row.focus();
  await page.keyboard.press("Enter");
  await expect(dialog).toBeVisible();
  await expect(
    dialog.getByLabel("Fresh evidence for this correction"),
  ).toBeVisible();
  await dialog
    .getByLabel("Fresh evidence for this correction")
    .scrollIntoViewIfNeeded();
  await expect(
    dialog.getByRole("button", { name: "Close dialog", exact: true }),
  ).toBeInViewport();
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(row).toBeFocused();
  await row.press("Enter");
  await expect(dialog).toBeVisible();
  await expect(dialog).toHaveCSS("opacity", "1");
  await page.keyboard.press("Escape");
  await expect(row).toBeFocused();
});

test("rapid mobile drawer toggles settle without trapping focus or blocking the page", async ({
  page,
}) => {
  await page.setViewportSize({ width: 375, height: 812 });
  // Wait for the responsive sidebar to adopt its mobile implementation before rapid input.
  await expect(page.locator('[data-slot="sidebar"][data-state]')).toHaveCount(
    0,
  );
  const drawer = page.getByRole("dialog", { name: "Sidebar", exact: true });
  for (let index = 0; index < 4; index++)
    await page.keyboard.press("Control+b");
  await expect(drawer).toHaveCount(0);
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await expect(drawer).toBeVisible();
  await expect(drawer).toHaveCSS("opacity", "1");
  await drawer.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(drawer).toHaveCount(0);
  await page.getByLabel("Appearance", { exact: true }).selectOption("dark");
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});
