import { test, expect } from "@playwright/test";

test.describe("Authentication Flow", () => {
  test("login page renders correctly", async ({ page }) => {
    await page.goto("/auth/login");
    await expect(page.locator("text=Welcome back")).toBeVisible();
    await expect(page.locator("input[type='email']")).toBeVisible();
    await expect(page.locator("input[type='password']")).toBeVisible();
  });

  test("unauthenticated user redirected from dashboard to login", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/auth\/login/);
  });

  test("authenticated user redirected from login to dashboard", async ({
    page,
  }) => {
    await page.context().addCookies([
      {
        name: "a2a_token",
        value: "mock_jwt_token",
        domain: "localhost",
        path: "/",
      },
    ]);
    await page.goto("/auth/login");
    await expect(page).toHaveURL(/\/dashboard/);
  });

  test("login form shows error for wrong credentials", async ({ page }) => {
    await page.goto("/auth/login");
    await page.fill("input[type='email']", "wrong@email.com");
    await page.fill("input[type='password']", "wrongpassword");
    await page.click("button[type='submit']");
    // Error should appear within timeout
    await expect(
      page.locator("text=/Invalid|error|failed/i")
    ).toBeVisible({ timeout: 10000 });
  });

  test("register page renders all form fields", async ({ page }) => {
    await page.goto("/auth/register");
    await expect(
      page.locator("text=Register Your Enterprise")
    ).toBeVisible();
    await expect(
      page.locator("[placeholder='Acme Textiles Pvt. Ltd.']")
    ).toBeVisible();
    await expect(
      page.locator("[placeholder='ABCDE1234F']")
    ).toBeVisible();
    await expect(
      page.locator("[placeholder='22ABCDE1234F1Z5']")
    ).toBeVisible();
  });

  test("register form validates PAN on blur", async ({ page }) => {
    await page.goto("/auth/register");
    await page.fill("[placeholder='ABCDE1234F']", "invalid");
    await page.keyboard.press("Tab");
    await expect(
      page.locator("text=/Invalid PAN/i")
    ).toBeVisible({ timeout: 5000 });
  });

  test("password strength indicator shows on register", async ({ page }) => {
    await page.goto("/auth/register");
    const passwordInput = page.locator("[placeholder='Min. 8 characters']");

    // Short password = Weak
    await passwordInput.fill("weak");
    await expect(page.locator("text=Weak")).toBeVisible();

    // Strong password with special chars
    await passwordInput.fill("StrongPass@1234");
    await expect(page.locator("text=Strong")).toBeVisible();
  });

  test("register page has link to login", async ({ page }) => {
    await page.goto("/auth/register");
    await expect(page.locator("a:has-text('Sign in')")).toBeVisible();
    await page.click("a:has-text('Sign in')");
    await expect(page).toHaveURL("/auth/login");
  });
});
