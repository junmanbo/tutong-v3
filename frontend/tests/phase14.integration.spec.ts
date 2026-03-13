import { expect, test } from "@playwright/test"

async function mockAuthenticatedSession(page: import("@playwright/test").Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("access_token", "e2e-access-token")
  })
  await page.route("**/api/v1/users/me", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "00000000-0000-0000-0000-000000000001",
        email: "admin@example.com",
        full_name: "Admin",
        is_active: true,
        is_superuser: true,
      }),
    })
  })
}

test.describe("Phase1-4 Integration", () => {
  test.use({ storageState: { cookies: [], origins: [] } })

  test("계좌 추가: 연결 테스트 성공 후에만 저장 가능", async ({ page }) => {
    await mockAuthenticatedSession(page)

    await page.route("**/api/v1/accounts/test-connection", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          is_valid: true,
          message: "연결 테스트에 성공했습니다.",
        }),
      })
    })
    await page.route("**/api/v1/accounts/", async (route) => {
      if (route.request().method() !== "POST") {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 201,
        contentType: "application/json",
        body: JSON.stringify({
          id: "11111111-1111-1111-1111-111111111111",
          exchange: "upbit",
          label: "E2E 계좌",
          is_active: true,
          is_valid: true,
          last_verified_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        }),
      })
    })

    await page.goto("/accounts")
    await page.getByRole("button", { name: "계좌 추가" }).click()

    await page.getByRole("combobox").first().click()
    await page.getByRole("option", { name: "업비트" }).click()
    await page.getByLabel(/계좌명/).fill("E2E 계좌")
    await page.getByLabel("API 키 *").fill("upbit-key")
    await page.getByLabel("API 시크릿 *").fill("upbit-secret")

    const saveButton = page.getByRole("button", { name: "연결 테스트 후 저장" })
    await expect(saveButton).toBeDisabled()

    await page.getByRole("button", { name: "연결 테스트", exact: true }).click()
    await expect(page.getByText("연결 테스트에 성공했습니다.")).toBeVisible()
    await expect(saveButton).toBeEnabled()

    await saveButton.click()
    await expect(page.getByText("계좌가 추가되었습니다")).toBeVisible()
  })

  test("봇 상세: 최근 주문에 실제 거래내역 테이블 표시", async ({ page }) => {
    await mockAuthenticatedSession(page)
    await page.route("**/api/v1/accounts**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          data: [
            {
              id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              exchange: "upbit",
              label: "업비트 실계좌",
              is_active: true,
              is_valid: true,
              last_verified_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        }),
      })
    })
    await page.route("**/api/v1/bots**", async (route) => {
      const url = route.request().url()
      if (url.includes("/orders?")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            data: [
              {
                id: "o-1",
                symbol: "SOL/KRW",
                side: "buy",
                placed_at: "2026-03-12T00:00:00Z",
              },
            ],
          }),
        })
        return
      }
      if (url.includes("/trades?")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            data: [
              {
                id: "t-1",
                order_id: "o-1",
                quantity: "1.25",
                price: "210000",
                fee: "262",
                fee_currency: "KRW",
                traded_at: "2026-03-12T00:00:01Z",
              },
            ],
          }),
        })
        return
      }
      if (url.includes("/snapshots?")) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            count: 1,
            data: [
              {
                id: "s-1",
                total_pnl: "0",
                total_pnl_pct: "0.00",
                portfolio_value: "1000000",
                snapshot_at: "2026-03-12T00:00:02Z",
              },
            ],
          }),
        })
        return
      }
      if (/\/api\/v1\/bots\/[^/?]+$/.test(url)) {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            id: "2f222222-2222-2222-2222-222222222222",
            account_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            name: "솔라나 DCA 봇",
            bot_type: "spot_dca",
            symbol: "SOL/KRW",
            base_currency: null,
            quote_currency: "KRW",
            investment_amount: "300000",
            stop_loss_pct: null,
            take_profit_pct: null,
            status: "running",
            config: {},
            total_pnl: "0",
            total_pnl_pct: "0.00",
            created_at: "2026-03-11T00:00:00Z",
          }),
        })
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 1,
          data: [
            {
              id: "2f222222-2222-2222-2222-222222222222",
              account_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              name: "솔라나 DCA 봇",
              bot_type: "spot_dca",
              symbol: "SOL/KRW",
              base_currency: null,
              quote_currency: "KRW",
              investment_amount: "300000",
              stop_loss_pct: null,
              take_profit_pct: null,
              status: "running",
              config: {},
              total_pnl: "0",
              total_pnl_pct: "0.00",
              created_at: "2026-03-11T00:00:00Z",
            },
          ],
        }),
      })
    })

    await page.goto("/bots")
    const botName = page.getByText("솔라나 DCA 봇").first()
    await expect(botName).toBeVisible({ timeout: 20000 })
    await botName.click()

    await expect(page.getByText("최근 주문")).toBeVisible()
    await expect(page.locator("table thead")).toContainText("체결시간")
    await expect(page.locator("table thead")).toContainText("거래금액")
    await expect(page.locator("table tbody tr").first()).toBeVisible({
      timeout: 15000,
    })
  })

  test("봇 목록: 상태 탭 + 거래소 필터 동작", async ({ page }) => {
    await mockAuthenticatedSession(page)

    await page.route("**/api/v1/accounts/**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 3,
          data: [
            {
              id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              exchange: "binance",
              label: "B 계좌",
              is_active: true,
              is_valid: true,
              last_verified_at: null,
              created_at: new Date().toISOString(),
            },
            {
              id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              exchange: "upbit",
              label: "U 계좌",
              is_active: true,
              is_valid: true,
              last_verified_at: null,
              created_at: new Date().toISOString(),
            },
            {
              id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
              exchange: "kis",
              label: "K 계좌",
              is_active: true,
              is_valid: true,
              last_verified_at: null,
              created_at: new Date().toISOString(),
            },
          ],
        }),
      })
    })
    await page.route("**/api/v1/bots/**", async (route) => {
      const url = route.request().url()
      if (url.includes("/orders") || url.includes("/trades") || url.includes("/snapshots")) {
        await route.continue()
        return
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          count: 3,
          data: [
            {
              id: "1f111111-1111-1111-1111-111111111111",
              account_id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
              name: "Bot A",
              bot_type: "spot_grid",
              symbol: "BTC/USDT",
              base_currency: null,
              quote_currency: "USDT",
              investment_amount: "1000",
              stop_loss_pct: null,
              take_profit_pct: null,
              status: "running",
              config: {},
              total_pnl: "0",
              total_pnl_pct: "1.00",
              created_at: new Date().toISOString(),
            },
            {
              id: "2f222222-2222-2222-2222-222222222222",
              account_id: "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
              name: "Bot B",
              bot_type: "spot_dca",
              symbol: "SOL/KRW",
              base_currency: null,
              quote_currency: "KRW",
              investment_amount: "5000",
              stop_loss_pct: null,
              take_profit_pct: null,
              status: "stopped",
              config: {},
              total_pnl: "0",
              total_pnl_pct: "0.00",
              created_at: new Date().toISOString(),
            },
            {
              id: "3f333333-3333-3333-3333-333333333333",
              account_id: "cccccccc-cccc-cccc-cccc-cccccccccccc",
              name: "Bot C",
              bot_type: "rebalancing",
              symbol: null,
              base_currency: null,
              quote_currency: "KRW",
              investment_amount: "3000000",
              stop_loss_pct: null,
              take_profit_pct: null,
              status: "error",
              config: {},
              total_pnl: "-1000",
              total_pnl_pct: "-0.50",
              created_at: new Date().toISOString(),
            },
          ],
        }),
      })
    })

    await page.goto("/bots")
    await expect(page.getByText("Bot A")).toBeVisible()
    await expect(page.getByText("Bot B")).toBeVisible()
    await expect(page.getByText("Bot C")).toBeVisible()

    await page.getByRole("tab", { name: "실행 중" }).click()
    await expect(page.getByText("Bot A")).toBeVisible()
    await expect(page.getByText("Bot B")).not.toBeVisible()

    await page.getByRole("combobox").last().click()
    await page.getByRole("option", { name: "한국투자증권" }).click()
    await expect(page.getByText("데이터가 없습니다.")).toBeVisible()

    await page.getByRole("tab", { name: "오류" }).click()
    await expect(page.getByText("Bot C")).toBeVisible()
  })
})
