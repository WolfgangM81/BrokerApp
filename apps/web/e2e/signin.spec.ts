import { expect, test } from "@playwright/test";

test("unauthenticated visit redirects to /auth/signin", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/auth\/signin/);
  await expect(page.getByRole("button", { name: /authentik/i })).toBeVisible();
});
