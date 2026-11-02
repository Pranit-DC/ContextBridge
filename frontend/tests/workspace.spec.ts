import { test, expect } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

type TestPage = import("@playwright/test").Page;
// The launcher opens a landing page; entering the workspace is one explicit click.
async function enter(page: TestPage) {
  await page.getByRole("button", { name: "Open workspace" }).first().click();
}
async function setTheme(page: TestPage, theme: string) {
  await page
    .getByRole("radio", {
      name: theme.charAt(0).toUpperCase() + theme.slice(1),
      exact: true,
    })
    .click();
}
const projectMenu = (page: TestPage) =>
  page.getByRole("button", { name: /^Current project/ });
async function switchProject(page: TestPage, name: string) {
  await projectMenu(page).click();
  await page.getByLabel("Find or create a project").fill(name);
  const existing = page.getByRole("option", { name, exact: true });
  if (await existing.count()) await existing.click();
  else await page.getByRole("option", { name: `Create “${name}”` }).click();
}

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
    page.getByRole("heading", {
      name: "One memory for every coding assistant.",
    }),
  ).toBeVisible();
  await enter(page);
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
});

test("onboarding, responsive navigation and accessible labels", async ({
  page,
}) => {
  await expect(page.getByText("Get started")).toBeVisible();
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
  // Let the drawer finish closing so axe never samples its fading text.
  await expect(
    page.getByRole("dialog", { name: "Sidebar", exact: true }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "Test connection for Groq", exact: true }),
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
  await page
    .getByLabel("API key", { exact: true })
    .fill("synthetic-browser-key-123456789");
  await page
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await expect(page.getByLabel("API key", { exact: true })).toHaveCount(0);
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
  await expect(
    page.getByText(/contextbridge.mcp_adapter.cli/).first(),
  ).toBeVisible();
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
  await other.goto("/?view=memories");
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
  await projectMenu(page).click();
  await page.getByLabel("Find or create a project").fill("another-project");
  await expect(
    page.getByRole("textbox", { name: "My original statement", exact: true }),
  ).toHaveValue("I chose SQLite for this project.");
  await page.getByRole("option", { name: "Create “another-project”" }).click();
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
      name: "About & privacy",
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
    await setTheme(page, appearance);
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
  const header = page.locator("header.workspace-topbar");
  await expect(
    header.getByText("Docker needs attention", { exact: true }),
  ).toBeVisible();
  for (const width of [320, 375]) {
    await page.setViewportSize({ width, height: 900 });
    const context = await header
      .getByRole("button", { name: project, exact: true })
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
  await switchProject(page, "second-project");
  await expect(projectMenu(page)).toContainText("second-project");
  await page.reload();
  await expect(projectMenu(page)).toContainText("second-project");
  // Closing the menu leaves the project unchanged.
  await projectMenu(page).click();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("listbox", { name: "Projects" })).toHaveCount(0);
  await expect(projectMenu(page)).toContainText("second-project");
  // A remembered project is chosen from the list, with no typing.
  await switchProject(page, "contextbridge");
  await expect(projectMenu(page)).toContainText("contextbridge");
  await page.setViewportSize({ width: 375, height: 812 });
  await page
    .getByRole("button", { name: "Toggle Sidebar", exact: true })
    .click();
  await switchProject(page, "second-project");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page
      .locator("header.workspace-topbar")
      .getByRole("button", { name: "second-project", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("appearance follows system, persists explicit choices, and remains accessible", async ({
  page,
}) => {
  const choice = (name: string) =>
    page.getByRole("radio", { name, exact: true });
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass(/dark/);
  await setTheme(page, "light");
  await expect(choice("Light")).toBeChecked();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await page.reload();
  await expect(choice("Light")).toBeChecked();
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await setTheme(page, "dark");
  await page.reload();
  await expect(choice("Dark")).toBeChecked();
  await expect(page.locator("html")).toHaveClass(/dark/);
  // Arrow keys move through the group like any radio group.
  await choice("Dark").focus();
  await page.keyboard.press("ArrowLeft");
  await expect(choice("Light")).toBeChecked();
  await expect(choice("Light")).toBeFocused();
  await setTheme(page, "dark");
  for (const screen of [
    "Overview",
    "Memories",
    "Add memory",
    "Activity",
    "Connections",
    "Settings",
    "Docs",
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
    await expect(choice("Dark")).toBeVisible();
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
  await setTheme(page, "system");
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
  await expect(projectMenu(page)).toContainText("contextbridge");
  await projectMenu(page).click();
  await page.getByLabel("Find or create a project").fill("   ");
  await expect(page.getByRole("option", { name: /^Create/ })).toHaveCount(0);
  await page.getByLabel("Find or create a project").fill("local-project");
  await page.getByRole("option", { name: "Create “local-project”" }).click();
  await expect(projectMenu(page)).toContainText("local-project");
  await setTheme(page, "dark");
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
  await expect(
    page.getByRole("radio", { name: "Dark", exact: true }),
  ).toBeEnabled();
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
  await setTheme(page, "dark");
  await expect(
    page.getByRole("heading", { name: "Settings", exact: true }),
  ).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
});

test("processing project uses remembered choices and persists without retyping", async ({
  page,
}) => {
  await switchProject(page, "demo-ux");
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByRole("combobox", { name: "Processing project", exact: true })
    .selectOption("demo-ux");
  await page
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await expect(page.getByText(/Showing saved settings/)).toBeVisible();
  await page.reload();
  await expect(projectMenu(page)).toContainText("demo-ux");
  await expect(
    page.getByLabel("Processing project", { exact: true }),
  ).toHaveValue("demo-ux");
});

test("provider checks require saved changes and the Free-plan confirmation", async ({
  page,
}) => {
  let checks = 0;
  await page.route("**/api/local/v1/providers/check", async (route) => {
    checks++;
    expect(route.request().postDataJSON().confirmed).toBe(true);
    await route.fulfill({
      json: { ok: true, message: "Synthetic Groq connection passed." },
    });
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page
    .getByLabel("API key", { exact: true })
    .fill("synthetic-browser-ux-provider-key");
  await page.getByLabel("Enable AI processing", { exact: true }).check();
  await expect(
    page.getByText("Confirm your Groq Free plan to enable AI processing."),
  ).toBeVisible();
  await page
    .getByLabel("I confirm this Groq account is on the Free plan")
    .check();
  await expect(
    page.getByText(
      "Save your changes before checking a provider. Checks use saved settings.",
    ),
  ).toBeVisible();
  await page.getByLabel("Allow this single online connection check").check();
  await expect(
    page.getByRole("button", { name: "Test connection for Groq", exact: true }),
  ).toBeDisabled();
  expect(checks).toBe(0);
  await page
    .getByRole("button", { name: "Save settings", exact: true })
    .click();
  await expect(page.getByText("Key saved", { exact: true })).toBeVisible();
  await page.getByLabel("Allow this single online connection check").check();
  await page
    .getByRole("button", { name: "Test connection for Groq", exact: true })
    .click();
  await expect(
    page.getByText("Synthetic Groq connection passed."),
  ).toBeVisible();
  await expect(
    page.locator(".test-list").getByText("Connected", { exact: true }),
  ).toBeVisible();
  expect(checks).toBe(1);
});

test("missing Cloudflare account explains blocked save", async ({ page }) => {
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByLabel("Enable meaning search", { exact: true }).check();
  await expect(page.getByLabel("Account ID", { exact: true })).toHaveAttribute(
    "aria-invalid",
    "true",
  );
  await expect(
    page.getByText(
      "Meaning search needs your 32-character Cloudflare Workers AI account ID.",
    ),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save settings", exact: true }),
  ).toBeDisabled();
});

test("action errors stay visible without scrolling or losing the draft", async ({
  page,
}) => {
  await page.route("**/api/local/v1/config", async (route) => {
    if (route.request().method() === "PUT")
      await route.fulfill({
        status: 409,
        json: { detail: "Synthetic save failure. Your draft is preserved." },
      });
    else await route.continue();
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "Advanced", exact: true }).click();
  await page.getByLabel("Daily processing token ceiling").fill("40000");
  const save = page.getByRole("button", {
    name: "Save settings",
    exact: true,
  });
  await save.scrollIntoViewIfNeeded();
  const before = await page.evaluate(() => window.scrollY);
  await save.click();
  const error = page
    .getByRole("alert")
    .filter({ hasText: "Synthetic save failure" });
  await expect(error).toBeVisible();
  const box = await error.boundingBox();
  expect(box!.y).toBeGreaterThanOrEqual(0);
  expect(box!.y + box!.height).toBeLessThanOrEqual(page.viewportSize()!.height);
  expect(
    Math.abs((await page.evaluate(() => window.scrollY)) - before),
  ).toBeLessThan(2);
  await expect(page.getByLabel("Daily processing token ceiling")).toHaveValue(
    "40000",
  );
  await page.getByRole("button", { name: "Dismiss notification" }).click();
  await expect(error).toHaveCount(0);
});

test("services distinguish successful migration and explain consent and unsaved changes", async ({
  page,
}) => {
  await page.route("**/api/local/v1/services", async (route) => {
    await route.fulfill({
      json: {
        docker_available: true,
        phase: "stopped",
        applied_revision: null,
        services: [
          { Service: "db", State: "exited", Health: "", ExitCode: 0 },
          { Service: "migrate", State: "exited", Health: "", ExitCode: 0 },
          { Service: "api", State: "created", Health: "" },
        ],
      },
    });
  });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await page.getByRole("button", { name: "2. Services", exact: true }).click();
  await page
    .getByRole("button", { name: "Refresh service status", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Services stopped", exact: true }),
  ).toBeVisible();
  await expect(
    page.locator(".svc-list li").filter({ hasText: "Database setup" }),
  ).toContainText("Completed");
  await expect(
    page.locator(".svc-list li").filter({ hasText: "Memory database" }),
  ).toContainText("Stopped");
  const apply = page.getByRole("button", {
    name: "Apply saved settings",
    exact: true,
  });
  await expect(apply).toBeDisabled();
  await page
    .getByLabel("I’m ready to restart services with these saved settings")
    .check();
  await expect(apply).toBeEnabled();
  await page.getByRole("button", { name: "1. Providers", exact: true }).click();
  await page.getByLabel("Enable AI processing", { exact: true }).check();
  await page.getByRole("button", { name: "2. Services", exact: true }).click();
  await expect(apply).toBeDisabled();
  await expect(
    page.getByText("Save your changes in Providers before applying settings."),
  ).toBeVisible();
});

test("capture project mismatch blocks installation and VS Code config needs no manual arguments", async ({
  page,
}) => {
  await switchProject(page, "different-project");
  await page.getByRole("button", { name: "Connections", exact: true }).click();
  await page
    .getByLabel("Workspace directory (absolute path)")
    .fill("/tmp/demo");
  await page
    .getByLabel("I approve changing ContextBridge’s hook in this workspace")
    .check();
  await expect(
    page.getByRole("button", { name: "Enable capture", exact: true }),
  ).toBeDisabled();
  await expect(
    page.getByText(/Capture processing is set to contextbridge/),
  ).toBeVisible();
  await page.getByRole("button", { name: /VS Code Copilot/ }).click();
  await page
    .getByRole("button", { name: "Generate connection instructions" })
    .click();
  const config = JSON.parse(await page.locator("pre").first().innerText());
  expect(config.servers["contextbridge-demo"].type).toBe("stdio");
  expect(config.servers["contextbridge-demo"].args.slice(-2)).toEqual([
    "--project-id",
    "different-project",
  ]);
});

test("settings sections stay accessible without overflow in both themes", async ({
  page,
}) => {
  test.setTimeout(120000);
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  for (const theme of ["light", "dark"]) {
    await setTheme(page, theme);
    for (const width of [320, 375, 1280, 1920]) {
      await page.setViewportSize({ width, height: 900 });
      for (const section of ["1. Providers", "2. Services", "Advanced"]) {
        await page.getByRole("button", { name: section, exact: true }).click();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBeTruthy();
        expect((await new AxeBuilder({ page }).analyze()).violations).toEqual(
          [],
        );
      }
      await page.screenshot({
        path: `test-results/ux-settings-${theme}-${width}.png`,
        fullPage: true,
      });
    }
  }
});

test("all eight workspace screens remain readable in both themes and narrow layouts", async ({
  page,
}) => {
  test.setTimeout(120000);
  for (const theme of ["light", "dark"]) {
    await setTheme(page, theme);
    for (const width of [320, 375, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      for (const view of [
        "overview",
        "memories",
        "add-memory",
        "activity",
        "connections",
        "settings",
        "docs",
        "about",
      ]) {
        await page.goto(`/?view=${view}`);
        await expect(page.locator("main h1")).toBeVisible();
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
        ).toBeTruthy();
        expect((await new AxeBuilder({ page }).analyze()).violations).toEqual(
          [],
        );
        if (width !== 320)
          await page.screenshot({
            path: `test-results/ux-${view}-${theme}-${width}.png`,
            fullPage: true,
          });
      }
    }
  }
});

test("memories load on arrival without requiring a separate Browse click", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Add memory", exact: true }).click();
  await page
    .getByLabel("What should be remembered?")
    .fill("The launch codename is Amber Birch.");
  await page
    .getByLabel("Supporting statement or tool result")
    .fill("I confirm Amber Birch is our launch codename.");
  await page
    .getByRole("button", { name: "Save confirmed memory", exact: true })
    .click();
  await page.getByRole("button", { name: "Close dialog", exact: true }).click();
  await page.getByRole("button", { name: "Memories", exact: true }).click();
  await expect(
    page.getByRole("button", { name: /The launch codename is Amber Birch/ }),
  ).toBeVisible();
  await expect(
    page.getByText("Loading memories…", { exact: true }),
  ).toHaveCount(0);
});

test("landing page enters the workspace and links to public docs", async ({
  page,
  request,
}) => {
  const reset = await request.post("/__test__/reset");
  await page.goto((await reset.json()).url);
  await expect(page).toHaveTitle("ContextBridge | Memory workspace");
  await expect(page).not.toHaveURL(/launch=/);
  await expect(page.getByText("Private local session ready.")).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/product-landing.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Read the docs" }).first().click();
  await expect(page).toHaveURL(/view=docs/);
  await expect(
    page.getByRole("heading", { name: "Documentation", exact: true }),
  ).toBeVisible();
  await page.getByRole("link", { name: "3. Add a memory" }).click();
  await expect(
    page.getByRole("heading", { name: "3. Add a memory" }),
  ).toBeInViewport();
  await page.goBack();
  await page.goBack();
  await page.getByRole("button", { name: "Open workspace" }).first().click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Home", exact: true }).click();
  await expect(
    page.getByRole("heading", {
      name: "One memory for every coding assistant.",
    }),
  ).toBeVisible();
  await expect(page).not.toHaveURL(/view=/);
});

test("breadcrumbs name the project and screen, and the status light explains services", async ({
  page,
}) => {
  const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  await expect(crumbs.getByText("Settings", { exact: true })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(
    crumbs.getByRole("button", { name: "contextbridge", exact: true }),
  ).toBeVisible();
  await crumbs.getByRole("button", { name: "contextbridge" }).click();
  await expect(
    page.getByRole("heading", { name: "Overview", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "About & privacy" }).click();
  await expect(
    crumbs.getByRole("button", { name: "contextbridge" }),
  ).toHaveCount(0);
  const status = page.getByRole("group", { name: "Connection status" });
  await status.getByRole("button", { name: /Services|Docker/ }).click();
  await expect(status.getByText("Private session")).toBeVisible();
  await expect(status.getByText("Docker", { exact: true })).toBeVisible();
  await expect(status.getByText("Connected").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(status.getByText("Local services")).toHaveCount(0);
});

test("services light follows live status without a manual refresh", async ({
  page,
}) => {
  let running = false;
  await page.route("**/api/local/v1/services", async (route) => {
    await route.fulfill({
      json: {
        docker_available: true,
        phase: "running",
        applied_revision: null,
        services: running
          ? [
              { Service: "db", State: "running", Health: "healthy" },
              { Service: "api", State: "running", Health: "healthy" },
            ]
          : [
              { Service: "db", State: "exited", Health: "" },
              { Service: "api", State: "exited", Health: "" },
            ],
      },
    });
  });
  await page.reload();
  const status = page.getByRole("group", { name: "Connection status" });
  await expect(status.getByText("Services stopped")).toBeVisible();
  running = true;
  await expect(status.getByText("Services running")).toBeVisible({
    timeout: 15000,
  });
});

test("new memory form opens from the memories page, saves and refreshes the list", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Memories", exact: true }).click();
  await page.getByRole("button", { name: "New memory" }).first().click();
  const form = page.getByRole("dialog", { name: "New memory", exact: true });
  await form
    .getByLabel("What should be remembered?")
    .fill("The cache layer is Redis.");
  await form
    .getByLabel("Supporting statement or tool result")
    .fill("We confirmed Redis for the cache layer.");
  await form.getByLabel("Memory type").selectOption("DECISION");
  await form.getByRole("button", { name: "Save confirmed memory" }).click();
  const details = page.getByRole("dialog", { name: "Memory details" });
  await expect(details).toBeVisible();
  await details.getByRole("button", { name: "Close dialog" }).click();
  const card = page.getByRole("button", { name: /The cache layer is Redis/ });
  await expect(card).toBeVisible();
  await expect(card).toContainText("Decision");
  await page
    .getByRole("group", { name: "Filter by type" })
    .getByRole("button", { name: /Decision/ })
    .click();
  await expect(card).toBeVisible();
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([]);
  await page.screenshot({
    path: "test-results/product-memories-list.png",
    fullPage: true,
  });
});

test("activity loads on arrival and settings show the save-then-apply order", async ({
  page,
}) => {
  await page.getByRole("button", { name: "Activity", exact: true }).click();
  await expect(page.getByText("No activity yet")).toBeVisible();
  await expect(page.getByText(/^Live/)).toBeVisible();
  await page.getByRole("button", { name: "Settings", exact: true }).click();
  const steps = page.getByRole("list", { name: "Settings progress" });
  await expect(steps.getByText("Configure")).toBeVisible();
  await expect(steps.getByText("Save", { exact: true })).toBeVisible();
  await expect(steps.getByText("Apply", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save settings", exact: true }),
  ).toBeDisabled();
  await page.getByLabel("Enable AI processing", { exact: true }).check();
  await expect(page.getByText("Unsaved changes").first()).toBeVisible();
  await expect(steps.getByText("After saving")).toBeVisible();
  await page.getByRole("button", { name: "Discard changes" }).click();
  await expect(page.getByText("All changes saved")).toBeVisible();
});

test("connections offer a setup per assistant", async ({ page }) => {
  await page.getByRole("button", { name: "Connections", exact: true }).click();
  const picker = page.getByRole("group", { name: "Choose your assistant" });
  for (const name of [
    "Codex",
    "Claude Code",
    "VS Code Copilot",
    "Other MCP client",
  ])
    await expect(picker.getByRole("button", { name })).toBeVisible();
  await picker.getByRole("button", { name: /Claude Code/ }).click();
  await page
    .getByRole("button", { name: "Generate connection instructions" })
    .click();
  await expect(
    page.getByText(/claude mcp add --transport stdio/),
  ).toBeVisible();
  await picker.getByRole("button", { name: /^Codex/ }).click();
  await expect(page.getByText(/codex mcp add contextbridge/)).toBeVisible();
});
