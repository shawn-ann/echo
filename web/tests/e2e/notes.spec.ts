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

async function waitUntilNotePersisted(page: Page) {
  // 后台任务异步入库，先轮询 API 等待笔记落库，再导航避免页面首拉竞态
  const token = await page.evaluate(() => localStorage.getItem('echo_token'))
  const headers = { Authorization: `Bearer ${token}` }
  let found = false
  for (let i = 0; i < 20; i++) {
    const res = await page.request.get('http://localhost:8000/api/v1/notes', { headers })
    if (res.status() === 200) {
      const body = await res.json()
      if ((body.notes ?? []).some((n: { rule_title: string }) => n.rule_title === '介词后加 -ing 形式')) {
        found = true
        break
      }
    }
    await page.waitForTimeout(1000)
  }
  expect(found, '笔记应在 20 秒内落库').toBe(true)
  await page.goto('/notes')
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByRole('button', { name: /介词后加 -ing 形式/ })).toBeVisible({ timeout: 5000 })
}

test('N-01 纠错后自动保存笔记', async ({ page }) => {
  await loginAndSubmit(page)
  // 自动保存无 UI 按钮，等待后台入库后导航到笔记页确认
  await waitUntilNotePersisted(page)
})

test('N-02 笔记列表页显示笔记', async ({ page }) => {
  await loginAndSubmit(page)
  await waitUntilNotePersisted(page)
})

test('N-03 笔记展开显示 8 字段', async ({ page }) => {
  await loginAndSubmit(page)
  await waitUntilNotePersisted(page)
  await page.getByRole('button', { name: /介词后加 -ing 形式/ }).click()
  await expect(page.getByText('📌 核心知识点')).toBeVisible()
  await expect(page.getByText(/介词后接动词/).first()).toBeVisible()
  await expect(page.getByText('⚠️ 个人易错警示')).toBeVisible()
  await expect(page.getByText('💼 职场同义备选')).toBeVisible()
  await expect(page.getByText('❓ 费曼自测')).toBeVisible()
  await expect(page.getByText('📝 我的错误')).toBeVisible()
  await expect(page.getByText(/interested in read → interested in reading/)).toBeVisible()
})

test('N-04 无错误不生成笔记', async ({ page }) => {
  await page.getByPlaceholder('输入英文，AI 将为你纠错').fill('no-error')
  await page.getByRole('button', { name: '发送' }).click()
  await expect(page.getByText(/这段英文写得不错/).first()).toBeVisible()
  // 等待后台任务（若有）完成，避免极端情况下导航过早
  await page.waitForTimeout(1500)
  await page.getByRole('link', { name: /我的笔记/ }).click()
  await expect(page).toHaveURL(/\/notes$/)
  await expect(page.getByText('还没有笔记')).toBeVisible({ timeout: 20000 })
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
