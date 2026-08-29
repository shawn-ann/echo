import { expect, test, type Page } from '@playwright/test'

const USERNAME = 'shawn'
const PASSWORD = 'shawn!QAZ1qaz'

// 清空当前用户的全部笔记，保证每个用例独立（N-05 空态需要）
async function clearNotes(page: Page) {
  const token = await page.evaluate(() => localStorage.getItem('echo_token'))
  const headers = { Authorization: `Bearer ${token}` }
  const res = await page.request.get('http://localhost:8000/api/v1/notes', { headers })
  if (res.status() !== 200) return
  const body = await res.json()
  for (const note of body.notes ?? []) {
    await page.request.delete(`http://localhost:8000/api/v1/notes/${note.id}`, { headers })
  }
}

test.beforeEach(async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
  await clearNotes(page)
})

async function loginAndSubmit(page: Page) {
  // 纠错历史在套件内会累计，故对报告断言用 .first()
  await page.getByPlaceholder('输入英文，AI 将为你纠错').fill('Yesterday I go to the park')
  await page.getByRole('button', { name: '发送' }).click()
  // 等待纠错报告出现
  await expect(page.getByText('错误分析').first()).toBeVisible({ timeout: 15000 })
}

test('N-01 单个错误记笔记', async ({ page }) => {
  await loginAndSubmit(page)
  // 点击第一个 ErrorCard 的「记笔记」按钮
  await page.getByRole('button', { name: '📝 记笔记' }).first().click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
})

test('N-02 全部记笔记', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).first().click()
  await expect(page.getByText(/已记入 \d+ 条规则笔记/)).toBeVisible({ timeout: 15000 })
})

test('N-03 笔记列表页显示笔记', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).first().click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
  // 导航到笔记页
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  // NoteCard 展开按钮内包含 rule_title
  await expect(page.getByRole('button', { name: /介词后加 -ing 形式/ })).toBeVisible()
})

test('N-04 笔记展开显示案例', async ({ page }) => {
  await loginAndSubmit(page)
  await page.getByRole('button', { name: '📝 全部记笔记' }).first().click()
  await expect(page.getByText(/已记入/)).toBeVisible({ timeout: 15000 })
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  // 点击 NoteCard 展开
  await page.getByRole('button', { name: /介词后加 -ing 形式/ }).click()
  await expect(page.getByText(/原文/).first()).toBeVisible()
})

test('N-05 笔记列表空态', async ({ page }) => {
  // beforeEach 已登录并清空笔记
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByText('还没有笔记')).toBeVisible()
})

test('N-06 导航切换纠错↔笔记', async ({ page }) => {
  // beforeEach 已登录并停留在 /correction
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await page.getByRole('link', { name: /纠错/ }).click()
  await expect(page).toHaveURL(/\/correction$/)
})
