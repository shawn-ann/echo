import { expect, test } from '@playwright/test'

const COMPOSER = '输入英文纠错，或继续追问'

test('U-S-01 流式纠错先错误后改写', async ({ page }) => {
  await page.goto('/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await expect(page.getByTestId('stream-minimal')).toContainText('Yesterday I went to school.')
  await expect(page.getByTestId('stream-fluency')).toContainText('I went to school yesterday.')
})

test('U-S-02 后端不可达时显示可重试错误，不展示空错误面板', async ({ page }) => {
  await page.route('**/api/v1/chat/stream', (route) => route.abort())
  await page.goto('/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  await expect(page.getByText('无法连接后端服务，请确认后端已启动')).toBeVisible()
  await expect(page.getByTestId('stream-errors')).toHaveCount(0)
  await expect(page.getByRole('button', { name: '重试' })).toBeVisible()
})

test('U-S-03 纠错后追问返回解释', async ({ page }) => {
  const bodies: Record<string, unknown>[] = []
  page.on('request', (request) => {
    if (!request.url().includes('/chat/stream')) return
    try {
      bodies.push(request.postDataJSON() as Record<string, unknown>)
    } catch {
      // ignore non-JSON requests
    }
  })

  await page.goto('/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await page.getByRole('button', { name: '追问这条' }).first().click()
  await page.getByPlaceholder('输入追问，例如：为什么这么改？').fill('为什么这么改？')
  await page.getByRole('button', { name: '发送追问' }).click()
  await expect(page.getByTestId('stream-explanation').last()).toContainText('go 是过去时间')

  // 点击后只消费一次显式引用；下一次自由追问不能再带 error_id。
  await page.getByPlaceholder(COMPOSER).fill('为什么这里用 an？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-explanation').last()).toBeVisible()
  const lastRequest = bodies.at(-1)
  expect(lastRequest?.content).toContain('为什么这里用 an')
  expect(lastRequest?.error_id).toBeUndefined()
})

test('U-S-05 等待态统一显示思考中', async ({ page }) => {
  await page.route('**/api/v1/chat/stream', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 800))
    await route.continue()
  })
  await page.goto('/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  await expect(page.getByTestId('thinking-indicator')).toContainText('思考中…')
  await expect(page.getByTestId('stream-errors')).toHaveCount(0)
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
})

test('U-S-04 跨轮自由追问按片段解析', async ({ page }) => {
  await page.goto('/stream')
  const input = page.getByPlaceholder(COMPOSER)
  await input.fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await input.fill('She go to work.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-errors').last()).toBeVisible()
  await input.fill('为什么 go 改成 went？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('stream-explanation').last()).toContainText('go 是过去时间')
})
