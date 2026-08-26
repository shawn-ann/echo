import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'demo'
const PASSWORD = 'anshuai1234567'

async function fillAndSubmit(page: Page, username: string, password: string) {
  await page.getByLabel('用户名').fill(username)
  await page.getByLabel('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
}

async function login(page: Page) {
  await page.goto('/login')
  await fillAndSubmit(page, USERNAME, PASSWORD)
  await expect(page).toHaveURL(/\/correction$/)
}

// U-L-01 登录成功
test('U-L-01 登录成功进入纠错主页', async ({ page }) => {
  await login(page)
  await expect(page).toHaveURL(/\/correction$/)
  await expect(page.getByText(USERNAME)).toBeVisible()
  await expect(page.getByRole('button', { name: '退出' })).toBeVisible()
})

// U-L-02 用户名为空
test('U-L-02 用户名为空提交', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('请输入用户名')).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

// U-L-03 密码为空
test('U-L-03 密码为空提交', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('请输入密码')).toBeVisible()
  await expect(page).toHaveURL(/\/login$/)
})

// U-L-04 密码错误
test('U-L-04 密码错误提示且清空密码', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill('wrong-password')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByText('用户名或密码错误')).toBeVisible()
  await expect(page.getByLabel('密码')).toHaveValue('')
  await expect(page.getByLabel('用户名')).toHaveValue(USERNAME)
})

// U-L-05 刷新保持登录态
test('U-L-05 登录后刷新保持登录态', async ({ page }) => {
  await login(page)
  await page.reload()
  await expect(page).toHaveURL(/\/correction$/)
  await expect(page.getByRole('button', { name: '退出' })).toBeVisible()
})

// U-L-06 重开浏览器保持登录态（storageState 持久化）
test('U-L-06 重开浏览器保持登录态', async ({ browser }, testInfo) => {
  const statePath = testInfo.outputPath('storage-state.json')

  const context = await browser.newContext()
  const page = await context.newPage()
  await login(page)
  await expect(page).toHaveURL(/\/correction$/)
  await context.storageState({ path: statePath })
  await context.close()

  const context2 = await browser.newContext({ storageState: statePath })
  const page2 = await context2.newPage()
  await page2.goto('/correction')
  await expect(page2).toHaveURL(/\/correction$/)
  await expect(page2.getByRole('button', { name: '退出' })).toBeVisible()
  await context2.close()
})

// U-L-07 未登录访问业务页重定向
test('U-L-07 未登录访问纠错主页重定向登录页', async ({ page }) => {
  await page.goto('/correction')
  await expect(page).toHaveURL(/\/login$/)
})

// U-L-08 手机宽度渲染
test('U-L-08 手机宽度登录页正常显示', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await page.goto('/login')
  await expect(
    page.getByRole('heading', { name: 'Echo · 地道英语纠错' }).filter({ visible: true }),
  ).toBeVisible()
  await expect(page.getByLabel('用户名')).toBeVisible()
  await expect(page.getByLabel('密码')).toBeVisible()
  await expect(page.getByRole('button', { name: '登录' })).toBeVisible()
})

// U-L-09 退出登录后需重新登录
test('U-L-09 退出登录后需重新登录', async ({ page }) => {
  await login(page)
  await expect(page).toHaveURL(/\/correction$/)
  await page.getByRole('button', { name: '退出' }).click()
  await expect(page).toHaveURL(/\/login$/)

  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
})

test('对后端 API 契约的 E2E 兜底：登录接口返回 token', async ({ request }) => {
  const res = await request.post('http://localhost:8000/api/v1/auth/login', {
    data: { username: USERNAME, password: PASSWORD },
  })
  expect(res.status()).toBe(200)
  const body = await res.json()
  expect(body.token).toBeTruthy()
})
