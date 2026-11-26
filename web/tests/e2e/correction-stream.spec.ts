import { expect, test } from '@playwright/test'

import { login } from './auth'

const COMPOSER = '输入英文，获取纠错和改写'

test.beforeEach(async ({ page }) => {
  await login(page)
})

test('C-S-01 单条纠错流式展示错误与三版改写', async ({ page }) => {
  await page.goto('/correction/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  await expect(page.getByTestId('correction-timing')).toContainText('总耗时')
  await expect(page.getByTestId('correction-timing')).toContainText('思考')
  await expect(page.getByText('时态错误')).toBeVisible()
  await expect(page.getByTestId('correction-rewrite-formal')).toContainText(
    'Yesterday I went to school and saw a substantial building.',
  )
  await expect(page.getByTestId('correction-rewrite-casual')).toContainText(
    'really big building',
  )
  await expect(page.getByTestId('correction-rewrite-minimal')).toContainText(
    'Yesterday I went to school and saw a very big building.',
  )
  await expect(page.getByText('学习要点')).toHaveCount(0)
})

test('C-S-02 请求体带 mode=correction', async ({ page }) => {
  const bodies: Record<string, unknown>[] = []
  page.on('request', (request) => {
    if (request.method() !== 'POST') return
    if (!request.url().includes('/correction/stream')) return
    try {
      bodies.push(request.postDataJSON() as Record<string, unknown>)
    } catch {
      // ignore
    }
  })

  await page.goto('/correction/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('correction-timing')).toContainText('总耗时')

  expect(bodies).toHaveLength(1)
  expect(bodies[0]).toEqual({
    content: 'Yesterday I go to school.',
    mode: 'correction',
  })
})

test('C-S-03 后端不可达时展示错误', async ({ page }) => {
  await page.route('**/api/v1/correction/stream', (route) => route.abort())
  await page.goto('/correction/stream')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByText('无法连接后端服务，请确认后端已启动')).toBeVisible()
})
