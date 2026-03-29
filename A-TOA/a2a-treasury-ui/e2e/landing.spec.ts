import { test, expect } from "@playwright/test";

test.describe("Landing Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test("page title contains A2A Treasury", async ({ page }) => {
    await expect(page).toHaveTitle(/A2A Treasury/i);
  });

  test("hero section renders with headline", async ({ page }) => {
    await expect(page.locator("text=Zero Human Intervention")).toBeVisible();
  });

  test("hero section renders sub-headline", async ({ page }) => {
    await expect(
      page.locator("text=AI agents discover, negotiate")
    ).toBeVisible();
  });

  test("animated terminal shows negotiation line", async ({ page }) => {
    // Wait for the first terminal animation line to appear
    await expect(
      page.locator("text=Buyer Agent").first()
    ).toBeVisible({ timeout: 5000 });
  });

  test("all 6 feature cards are visible when scrolled", async ({ page }) => {
    await page.locator("#features").scrollIntoViewIfNeeded();
    await expect(page.locator("text=AI Agent Negotiation")).toBeVisible();
    await expect(page.locator("text=Guardrail Enforcement")).toBeVisible();
    await expect(
      page.locator("text=Algorand Smart Contract Escrow")
    ).toBeVisible();
    await expect(page.locator("text=x402 Payment Protocol")).toBeVisible();
    await expect(page.locator("text=FEMA/RBI Compliance")).toBeVisible();
    await expect(
      page.locator("text=Cryptographic Audit Trail")
    ).toBeVisible();
  });

  test("how-it-works section exists", async ({ page }) => {
    await page.locator("#how-it-works").scrollIntoViewIfNeeded();
    await expect(page.locator("#how-it-works")).toBeVisible();
  });

  test("Get Started navigates to register", async ({ page }) => {
    // Use the first "Get Started" link visible (navbar)
    const getStarted = page.locator("a:has-text('Get Started')").first();
    await getStarted.click();
    await expect(page).toHaveURL("/auth/register");
  });

  test("Sign In navigates to login", async ({ page }) => {
    const signIn = page.locator("a:has-text('Sign In')").first();
    await signIn.click();
    await expect(page).toHaveURL("/auth/login");
  });

  test("no horizontal overflow on mobile", async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 812 });
    await page.waitForTimeout(500);
    const bodyWidth = await page.evaluate(
      () => document.body.scrollWidth
    );
    const viewportWidth = await page.evaluate(() => window.innerWidth);
    expect(bodyWidth).toBeLessThanOrEqual(viewportWidth + 1);
  });

  test("micro stats are visible on hero", async ({ page }) => {
    await expect(page.locator("text=2–3 Rounds")).toBeVisible();
    await expect(page.locator("text=< 30s")).toBeVisible();
    await expect(page.locator("text=100%")).toBeVisible();
  });
});
