import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'shawn'
const PASSWORD = 'shawn!QAZ1qaz'

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
}

async function send(page: Page, text: string) {
  await page.getByPlaceholder('输入英文，AI 将为你纠错').fill(text)
  await page.getByRole('button', { name: '发送' }).click()
}

// U-C-01 首次进入空态
test('U-C-01 首次进入纠错主页显示空态引导', async ({ page }) => {
  await login(page)
  await expect(page.getByText('输入英文，AI 将为你纠错')).toBeVisible()
})

// U-C-02 提交含错英文 → 报告
test('U-C-02 提交含错英文呈现纠错报告', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await expect(page.getByText('interested in reading').first()).toBeVisible()
  await expect(page.getByText('改写').first()).toBeVisible()
  await expect(page.getByText('最小修正').first()).toBeVisible()
  await expect(page.getByText('地道表达').first()).toBeVisible()
})

// U-C-03 无错误文本 → 鼓励文案
test('U-C-03 无错误文本展示鼓励文案', async ({ page }) => {
  await login(page)
  await send(page, 'no-error')
  await expect(page.getByText(/这段英文写得不错/).first()).toBeVisible()
  await expect(page.getByText('地道表达').first()).toBeVisible()
})

// U-C-04 纯中文也返回纠错报告（单轮纠错，无追问）
test('U-C-04 纯中文返回纠错报告', async ({ page }) => {
  await login(page)
  await send(page, '为什么不能用 very？')
  await expect(page.getByText('错误分析').first()).toBeVisible()
})

// U-C-05 连续提交均正常返回报告
test('U-C-05 连续提交多次均正常返回报告', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await send(page, 'She go to school')
  await expect(page.getByText('错误分析').first()).toBeVisible()
})

// U-C-06 超 2000 字符 → 字数标红 + 发送禁用
test('U-C-06 输入超 2000 字符发送禁用', async ({ page }) => {
  await login(page)
  const longText = 'x'.repeat(2001)
  await page.getByPlaceholder('输入英文，AI 将为你纠错').fill(longText)
  await expect(page.getByText('请将文本缩短至 2000 字符以内再提交')).toBeVisible()
  await expect(page.getByRole('button', { name: '发送' })).toBeDisabled()
})

// U-C-07 多行输入自动延伸
test('U-C-07 多行输入输入框增高', async ({ page }) => {
  await login(page)
  const ta = page.getByPlaceholder('输入英文，AI 将为你纠错')
  await ta.fill('line one\nline two\nline three')
  const height = await ta.evaluate((el) => el.scrollHeight)
  expect(height).toBeGreaterThan(40)
})

// U-C-08 复制改写
test('U-C-08 点击复制按钮复制改写文本', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('最小修正').first()).toBeVisible()
  const copyButton = page.getByRole('button', { name: '复制最小修正' }).first()
  await copyButton.click()
  await expect(copyButton.getByText('✓')).toBeVisible()
})

// U-C-09 刷新后历史仍在
test('U-C-09 刷新页面历史全量加载', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await page.reload()
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await expect(page.getByText('Yesterday I go to the park').first()).toBeVisible()
})

// U-C-10 手机宽度
test('U-C-10 手机宽度布局正常', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 812 })
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await expect(page.getByRole('button', { name: '退出' })).toBeVisible()
})

// U-C-11 会话过期提示重新登录
test('U-C-11 会话过期提示重新登录', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()

  const token = await page.evaluate(() => localStorage.getItem('echo_token'))
  const res = await page.request.post('http://localhost:8000/api/v1/auth/logout', {
    headers: { Authorization: `Bearer ${token}` },
  })
  expect(res.status()).toBe(204)

  await send(page, 'Another sentence here')
  await expect(page.getByText('会话已过期，请重新登录')).toBeVisible()
  await expect(page.getByRole('button', { name: '重新登录' })).toBeVisible()
})

// U-C-12 请求失败保留消息可重试
test('U-C-12 请求失败保留消息可重试', async ({ page }) => {
  await login(page)
  let fail = true
  await page.route('**/api/v1/messages', async (route) => {
    if (route.request().method() === 'POST' && fail) {
      fail = false
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          code: 'LLM_SERVICE_UNAVAILABLE',
          message: 'AI 服务不可用，请稍后重试',
          details: {},
        }),
      })
    } else {
      await route.continue()
    }
  })
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('AI 服务不可用，请稍后重试')).toBeVisible()
  await expect(page.getByText('Yesterday I go to the park').first()).toBeVisible()
  await page.getByRole('button', { name: '重试' }).click()
  await expect(page.getByText('错误分析').first()).toBeVisible()
})
