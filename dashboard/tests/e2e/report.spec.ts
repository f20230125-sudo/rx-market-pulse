import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

async function open(page: Page, scheme: "light" | "dark" = "light") {
  await page.emulateMedia({ colorScheme: scheme });

  if (scheme === "dark") await page.addInitScript(() => localStorage.setItem("rx-theme", "dark"));
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  return errors;
}

test("loads with the headline numbers and no console errors", async ({ page }) => {
  const errors = await open(page);
  const ledger = page.getByRole("term").filter({ hasText: /Spend in 2025/ });
  await expect(ledger).toBeVisible();
  await expect(page.locator(".led-hero")).toHaveText("$116.9B");
  await expect(page.getByRole("heading", { level: 2 }).first()).toContainText("Brands are 14% of prescriptions and 89% of spend");
  expect(errors).toEqual([]);
});

test("the area filter rescopes the numbers and the headline", async ({ page }) => {
  await open(page);
  await page.locator("#area").selectOption("Diabetes & obesity");
  await expect(page.locator(".led-hero")).not.toHaveText("$116.9B");
  await expect(page.locator(".led-hero")).toHaveText(/^\$\d+\.\d+B$/);
  await expect(page.locator("#market h2")).toContainText("of prescriptions");
  // The tile map and bridge follow the same scope.
  await expect(page.locator("#states")).toContainText("Diabetes & obesity");
  await expect(page.locator(".report-context")).toContainText("Diabetes & obesity · 2019–2025");
});

test("phone navigation reaches sections without hiding their headings, and keeps the theme available", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  const navigation = page.getByRole("navigation", { name: "Sections" });
  await expect(navigation).toBeVisible();
  const quality = navigation.getByRole("link", { name: "Quality", exact: true });
  await quality.click();
  await expect(quality).toHaveAttribute("aria-current", "location");
  await expect(page).toHaveURL(/#quality$/);
  const toolbar = await page.locator(".report-toolbar").boundingBox();
  const heading = await page.locator("#quality h2").boundingBox();
  expect(heading!.y).toBeGreaterThanOrEqual(toolbar!.y + toolbar!.height);
  const theme = page.getByRole("button", { name: "Switch between light and dark theme" });
  await expect(theme).toBeVisible();
  await theme.click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("the compact toolbar fits small phones, tablets and desktop screens", async ({ page }) => {
  await open(page);
  for (const width of [320, 390, 768, 1024, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth), `width ${width}`).toBeLessThanOrEqual(0);
    await expect(page.locator("#area")).toBeVisible();
    await expect(page.getByRole("navigation", { name: "Sections" })).toBeVisible();
  }
});

test("choosing a different pair of years changes the bridge", async ({ page }) => {
  await open(page);
  const heading = page.locator("#growth h2");
  const before = await heading.innerText();
  await page.getByRole("button", { name: "2019 to 2022" }).click();
  await expect(page.locator("#growth")).toContainText("Why spend changed, 2019 to 2022");
  expect(await heading.innerText()).not.toBe(before);
});

test("selecting an area bar scopes the whole page; selecting it again clears it", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /^Immunology & inflammation:/ }).click();
  await expect(page.locator("#area")).toHaveValue("Immunology & inflammation");
  await page.getByRole("button", { name: /^Immunology & inflammation:/ }).click();
  await expect(page.locator("#area")).toHaveValue("All areas");
});

test("selecting a company shows its brands", async ({ page }) => {
  await open(page);
  await expect(page.locator("#sellers")).toContainText("Merck (MSD): largest brands in this data");
  await expect(page.locator("#sellers")).toContainText("JANUVIA");
  await page.getByRole("button", { name: /^AbbVie, number/ }).click();
  await expect(page.locator("#sellers")).toContainText("AbbVie: largest brands in this data");
});

test("the erosion chart can be read with the keyboard", async ({ page }) => {
  await open(page);
  const chart = page.locator("#generics svg[tabindex='0']");
  await chart.focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.locator("#generics .tip")).toBeVisible();
  await expect(page.locator("#generics .tip")).toContainText("Median brand");
  await page.keyboard.press("Escape");
  await expect(page.locator("#generics .tip")).toHaveCount(0);
});

test("the erosion chart can highlight one brand", async ({ page }) => {
  await open(page);
  await page.getByLabel("Highlight a brand").selectOption({ label: "LATUDA" });
  await expect(page.locator("#generics .legend")).toContainText("LATUDA");
});

test("every chart has a table view", async ({ page }) => {
  await open(page);
  for (const id of ["market", "growth", "sellers", "generics", "protection", "states", "outlook"]) {
    const section = page.locator(`#${id}`);
    const toggles = section.getByRole("button", { name: "Table" });
    const n = await toggles.count();
    expect(n, `${id} has a table toggle`).toBeGreaterThan(0);
    await toggles.first().click();
    await expect(section.locator("table.tbl").first()).toBeVisible();
  }
});

test("the state table lists all 51 states and flags the ones that changed reporting", async ({ page }) => {
  await open(page);
  await page.locator("#states").getByRole("button", { name: "Table" }).click();
  await expect(page.locator("#states table.tbl tbody tr")).toHaveCount(51);
  await expect(page.locator("#states table.tbl")).toContainText("Check:");
});

test("choosing a protection year lists brands whose protection ends then", async ({ page }) => {
  await open(page);
  await page.getByRole("button", { name: /^2028: / }).click();
  await expect(page.locator("#protection table.tbl").last()).toContainText("in 2028");
});

test("the theme can be switched and is remembered", async ({ page }) => {
  await open(page, "light");
  await page.getByRole("button", { name: /Switch between light and dark theme/ }).click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
});

test("the downloads are served", async ({ request }) => {
  for (const f of ["/downloads/Territory-Targeting-Model.xlsx", "/downloads/data-quality-scorecard.md"]) {
    const res = await request.get(f);
    expect(res.status(), f).toBe(200);
    expect((await res.body()).length).toBeGreaterThan(1000);
  }
});

test("nothing overflows sideways on a phone", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await open(page);
  const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(over).toBeLessThanOrEqual(0);
});

for (const scheme of ["light", "dark"] as const) {
  test(`no serious accessibility violations (${scheme})`, async ({ page }) => {
    await open(page, scheme);
    const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
    const bad = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(bad.map((v) => `${v.id}: ${v.nodes.slice(0, 3).map((n) => n.target.join(" ")).join(" | ")}`)).toEqual([]);
  });
}

test("opens in light mode even when the system prefers dark", async ({ page }) => {
  await page.emulateMedia({ colorScheme: "dark" });
  await page.goto("/");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
