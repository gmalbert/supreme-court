import { test, expect, type Page } from "@playwright/test";
import { readFile } from "node:fs/promises";

const sections: [string, string][] = [
  ["/Cases", "⚖️ Cases"],
  ["/People", "👥 Justices & Advocates"],
  ["/History", "🏛️ Court History"],
  ["/Historical_Data", "📜 Historical Data Explorer"],
  ["/Circuit_Courts", "🏛️ Circuit Courts"],
  ["/Geography", "🗺️ Geography & Tools"],
  ["/Analysis", "📊 Analytics"],
  ["/Topics", "📚 Topics & Networks"],
  ["/Presidential_Legacy", "🏛️ Presidential Legacy"],
  ["/Research", "🔬 Research"],
  ["/Predictions", "🔮 Predictions"],
];

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (error) => errors.push(error.message));
  // Assert after the test, including failures in asynchronously loaded routes.
  (page as Page & { runtimeErrors: string[] }).runtimeErrors = errors;
});
test.afterEach(async ({ page }) => {
  expect((page as Page & { runtimeErrors: string[] }).runtimeErrors).toEqual(
    [],
  );
});

test("home, responsive layout, and navigation", async ({ page }, info) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", {
      name: "Supreme Scrutiny",
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "🔍 Find Cases by Description" }),
  ).toBeVisible();
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgba(0, 0, 0, 0)",
  );
  await expect(page.locator(".sidebar")).toHaveCSS(
    "background-color",
    "rgb(240, 242, 246)",
  );
  await expect(page.locator("h1")).toHaveCSS(
    "font-family",
    '"Source Sans", sans-serif',
  );
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth + 1,
    ),
  ).toBeTruthy();
  await page.screenshot({
    path: info.outputPath("overview.png"),
    fullPage: true,
  });
  const menu = page.getByRole("button", { name: "☰ Supreme Scrutiny" });
  if (await menu.isVisible()) await menu.click();
  await page
    .getByRole("navigation", { name: "Main navigation" })
    .getByRole("link", { name: "Cases" })
    .click();
  await expect(page.getByRole("heading", { name: "⚖️ Cases" })).toBeVisible();
});

test("real ranked search, saved cases, case details and reload", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByRole("textbox", { name: "Describe a legal situation" })
    .fill("Obergefell v. Hodges");
  await page.getByRole("button", { name: "🔍 Find Cases" }).click();
  const results = page.locator("main .case-card .case-name");
  await expect(results.first()).toHaveText("Obergefell v. Hodges");
  await results.first().click();
  await expect(
    page.getByRole("heading", { name: "Obergefell v. Hodges", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "The Court’s conclusion" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "☆ Save case", exact: true }).click();
  await page.reload();
  await expect(
    page.getByRole("button", { name: "★ Saved", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(
    page.getByRole("heading", { name: "The legal question" }),
  ).toBeVisible();
});

test("school-speech search preserves landmark recall", async ({ page }) => {
  await page.goto("/Cases?q=student%20expression%20at%20school");
  for (const name of ["Tinker", "Bethel", "Hazelwood", "Morse", "Mahanoy"])
    await expect(
      page
        .locator("main .case-card .case-name")
        .filter({ hasText: name })
        .first(),
    ).toBeVisible();
});

test("legacy shared links resolve to the exact case", async ({ page }) => {
  await page.goto("/Cases?q=Obergefell&case=Obergefell%20v.%20Hodges");
  await expect(page).toHaveURL(/\/case\/2014\/14-556$/);
  await expect(
    page.getByRole("heading", { name: "Obergefell v. Hodges", exact: true }),
  ).toBeVisible();
});

test("votes export and speaker-attributed transcript filtering", async ({
  page,
}) => {
  await page.goto("/case/2014/14-556");
  await page
    .getByRole("tab", { name: "Votes & opinions", exact: true })
    .click();
  await expect(
    page.getByRole("cell", { name: "Anthony M. Kennedy", exact: true }).first(),
  ).toBeVisible();
  const downloadEvent = page.waitForEvent("download");
  await page
    .getByRole("button", { name: "↓ Export CSV", exact: true })
    .first()
    .click();
  const download = await downloadEvent;
  const csv = await readFile((await download.path())!, "utf8");
  expect(csv).toContain("Justice");
  expect(csv).toContain("Kennedy");
  await page
    .getByRole("tab", { name: "🎙️ Oral Arguments", exact: true })
    .click();
  await expect(
    page.getByText("368 speaking turns", { exact: false }),
  ).toBeVisible();
  await page
    .getByRole("textbox", { name: "Find in transcript" })
    .fill("equal dignity");
  await expect(
    page.getByText("3 speaking turns", { exact: false }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Listen to the original audio on Oyez ↗" }),
  ).toHaveAttribute("href", "https://www.oyez.org/cases/2014/14-556");
});

test("all routes and feature sections render", async ({ page }) => {
  let tested = 0;
  for (const [path, heading] of sections) {
    await page.goto(path);
    await expect(
      page.getByRole("heading", { name: heading, exact: true }),
    ).toBeVisible();
    const categories = page.getByRole("tablist", { name: "Categories" });
    const groups = (await categories.count())
      ? await categories.getByRole("tab").allTextContents()
      : [null];
    for (const group of groups) {
      if (group)
        await categories.getByRole("tab", { name: group, exact: true }).click();
      const tabs = page.getByRole("tablist", { name: "Sections" });
      const labels = await tabs.getByRole("tab").allTextContents();
      for (const label of labels) {
        await tabs.getByRole("tab", { name: label, exact: true }).click();
        await expect(page.getByRole("tabpanel")).toBeVisible();
        await expect(
          page.getByText("We couldn’t display this page.", { exact: true }),
        ).toHaveCount(0);
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          `${path}: ${label}`,
        ).toBeTruthy();
        tested++;
      }
    }
  }
  expect(tested).toBe(55);
});

test("baseline prediction matches Python and updates with inputs", async ({
  page,
}) => {
  await page.goto("/Predictions");
  await page.getByRole("button", { name: "Generate prediction →" }).click();
  await expect(page.locator(".prediction-result strong")).toHaveText("68.4%");
  await page
    .getByRole("checkbox", { name: "Solicitor General supporting petitioner" })
    .check();
  await page.getByRole("button", { name: "Generate prediction →" }).click();
  await expect(page.locator(".prediction-result strong")).toHaveText("78.4%");
});

test("research returns evidence without a configured AI key", async ({
  page,
}) => {
  await page.goto("/Research");
  await page
    .getByRole("textbox", { name: "Ask a question or follow up" })
    .fill("Obergefell v. Hodges");
  await page.getByRole("button", { name: "Find supporting cases" }).click();
  await expect(
    page.getByRole("link", { name: "Obergefell v. Hodges", exact: true }),
  ).toBeVisible();
  const health = await (await page.request.get("/api/health")).json();
  if (!health.chat) {
    await expect(
      page.getByRole("button", { name: "Ask AI using these sources" }),
    ).toBeDisabled();
    await expect(
      page.getByText("The AI assistant is not enabled on this deployment.", {
        exact: false,
      }),
    ).toBeVisible();
  }
});

test("conditional static assets and missing data use correct HTTP responses", async ({
  request,
}) => {
  const first = await request.get("/data/manifest.json");
  expect(first.status()).toBe(200);
  const etag = first.headers().etag;
  expect(etag).toBeTruthy();
  const cached = await request.get("/data/manifest.json", {
    headers: { "If-None-Match": etag },
  });
  expect(cached.status()).toBe(304);
  const missing = await request.get("/data/not-a-real-file.json");
  expect(missing.status()).toBe(404);
  expect(missing.headers()["content-type"]).toContain("json");
});

test("original Streamlit model-card layout", async ({ page }, info) => {
  await page.goto("/Predictions?view=Model+card");
  await expect(
    page.getByRole("heading", {
      name: "📄 Model Card — Supreme Scrutiny Outcome Predictor",
    }),
  ).toBeVisible();
  for (const name of [
    "Overview",
    "Performance at a Glance",
    "Features Used",
    "Known Limitations",
    "Architecture Details",
    "Data Provenance",
  ])
    await expect(
      page.getByRole("heading", { name, exact: true }),
    ).toBeVisible();
  await page.screenshot({
    path: info.outputPath("model-card.png"),
    fullPage: true,
  });
});
