import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'demo'
const PASSWORD = 'demo1234'

async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
}

async function send(page: Page, text: string) {
  await page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问').fill(text)
  await page.getByRole('button', { name: '发送' }).click()
}

// U-C-01 首次进入空态
test('U-C-01 首次进入纠错主页显示空态引导', async ({ page }) => {
  await login(page)
  await expect(page.getByText('输入英文，AI 将为你纠错；也可以随时提问')).toBeVisible()
})

// U-C-02 提交含错英文 → 报告
test('U-C-02 提交含错英文呈现纠错报告', async ({ page }) => {
  await login(page)
  await send(page, 'Yesterday I go to the park')
  await expect(page.getByText('错误分析').first()).toBeVisible()
  await expect(page.getByText('I went to').first()).toBeVisible()
  await expect(page.getByText('改写')).toBeVisible()
  await expect(page.getByText('最小修正')).toBeVisible()
  await expect(page.getByText('地道表达')).toBeVisible()
})

// U-C-03 无错误文本 → 鼓励文案
test('U-C-03 无错误文本展示鼓励文案', async ({ page }) => {
  await login(page)
  await send(page, 'no-error')
  await expect(page.getByText(/这段英文写得不错/)).toBeVisible()
})

// U-C-04 纯中文 → 追问回复
test('U-C-04 纯中文返回纯文本追问回复', async ({ page }) => {
  await login(page)
  await send(page, '为什么不能用 very？')
  await expect(page.getByText('delicious 是极限形容词')).toBeVisible()
})

// U-C-05 连续追问
test('U-C-05 连续追问多次均正常回复', async ({ page }) => {
  await login(page)
  await send(page, '为什么不能用 very？')
  await expect(page.getByText('delicious 是极限形容词')).toBeVisible()
  await send(page, '那 delicious 可以用什么词修饰？')
  await expect(page.getByText(/delicious/).first()).toBeVisible()
})

// U-C-06 超 2000 字符 → 字数标红 + 发送禁用
test('U-C-06 输入超 2000 字符发送禁用', async ({ page }) => {
  await login(page)
  const longText = 'x'.repeat(2001)
  await page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问').fill(longText)
  await expect(page.getByText('请将文本缩短至 2000 字符以内再提交')).toBeVisible()
  await expect(page.getByRole('button', { name: '发送' })).toBeDisabled()
})

// U-C-07 多行输入自动延伸
test('U-C-07 多行输入输入框增高', async ({ page }) => {
  await login(page)
  const ta = page.getByPlaceholder('输入英文，AI 将为你纠错；也可以随时提问')
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
