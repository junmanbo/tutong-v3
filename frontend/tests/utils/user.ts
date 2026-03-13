import { expect, type Page } from "@playwright/test"

export async function signUpNewUser(
  page: Page,
  name: string,
  email: string,
  password: string,
) {
  await page.goto("/auth/register")

  await page.getByTestId("full-name-input").fill(name)
  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByTestId("confirm-password-input").fill(password)
  await page.getByLabel("이용약관에 동의합니다 (필수)").click()
  await page.getByLabel("투자 위험 고지에 동의합니다 (필수)").click()
  await page.getByRole("button", { name: "회원가입", exact: true }).click()
  await page.goto("/auth/login")
}

export async function logInUser(page: Page, email: string, password: string) {
  await page.goto("/auth/login")

  await page.getByTestId("email-input").fill(email)
  await page.getByTestId("password-input").fill(password)
  await page.getByRole("button", { name: "로그인", exact: true }).click()
  await page.waitForURL("/")
  await expect(page.getByText("대시보드")).toBeVisible()
}

export async function logOutUser(page: Page) {
  await page.getByRole("button", { name: "알림" }).locator("..").locator("button").last().click()
  await page.getByRole("menuitem", { name: "로그아웃" }).click()
  await page.waitForURL("/auth/login")
}
