import { test, expect } from "@playwright/test";

// Authenticate before all dashboard tests
test.beforeEach(async ({ page }) => {
  await page.context().addCookies([
    {
      name: "a2a_token",
      value: "mock_jwt_token",
      domain: "localhost",
      path: "/",
    },
  ]);
});

test.describe("Dashboard", () => {
  test("dashboard overview loads", async ({ page }) => {
    await page.goto("/dashboard");
    // Wait for API data to load — the page title should be "Overview"
    await expect(page.locator("h1:has-text('Overview')")).toBeVisible({
      timeout: 10000,
    });
  });

  test("sessions page loads", async ({ page }) => {
    await page.goto("/dashboard/sessions");
    await expect(page.locator("h1:has-text('Sessions')")).toBeVisible({
      timeout: 10000,
    });
  });

  test("escrow page loads", async ({ page }) => {
    await page.goto("/dashboard/escrow");
    await expect(page.locator("h1:has-text('Escrow')")).toBeVisible({
      timeout: 10000,
    });
  });

  test("compliance page loads", async ({ page }) => {
    await page.goto("/dashboard/compliance");
    await expect(page.locator("h1:has-text('Compliance')")).toBeVisible({
      timeout: 10000,
    });
  });

  test("audit trail page loads", async ({ page }) => {
    await page.goto("/dashboard/audit");
    await expect(
      page.locator("h1:has-text('Audit Trail')")
    ).toBeVisible({ timeout: 10000 });
  });

  test("settings page loads", async ({ page }) => {
    await page.goto("/dashboard/settings");
    await expect(page.locator("h1:has-text('Settings')")).toBeVisible({
      timeout: 10000,
    });
  });

  test("sidebar shows all navigation links", async ({ page }) => {
    await page.goto("/dashboard");
    // Desktop sidebar links
    await expect(page.locator("text=Overview").first()).toBeVisible();
    await expect(page.locator("text=Sessions").first()).toBeVisible();
    await expect(page.locator("text=Escrow").first()).toBeVisible();
    await expect(page.locator("text=Compliance").first()).toBeVisible();
    await expect(page.locator("text=Audit Trail").first()).toBeVisible();
    await expect(page.locator("text=Settings").first()).toBeVisible();
  });

  test("sidebar shows A2A Treasury branding", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(
      page.locator("aside >> text=A2A Treasury")
    ).toBeVisible();
  });

  test("sidebar Sign Out button is visible", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(
      page.locator("button:has-text('Sign Out')").first()
    ).toBeVisible();
  });

  test("header shows TestNet badge", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("text=TestNet").first()).toBeVisible({
      timeout: 10000,
    });
  });

  test("sidebar links navigate correctly", async ({ page }) => {
    await page.goto("/dashboard");
    await page.click("a:has-text('Sessions')");
    await expect(page).toHaveURL("/dashboard/sessions");
    await page.click("a:has-text('Escrow')");
    await expect(page).toHaveURL("/dashboard/escrow");
    await page.click("a:has-text('Compliance')");
    await expect(page).toHaveURL("/dashboard/compliance");
  });
});
