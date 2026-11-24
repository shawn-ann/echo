import { expect, test } from '@playwright/test'

const COMPOSER = '输入英文，或提问用法'

test('U-CO-01 结构化纠错流式展示思考、错误、改写与学习点', async ({ page }) => {
  await page.goto('/coach')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  await expect(page.getByTestId('coach-reasoning').first()).toBeVisible()
  await expect(page.getByTestId('coach-errors')).toContainText('时态错误')
  await expect(page.getByTestId('coach-errors')).toContainText('go')
  await expect(page.getByTestId('coach-rewrite-formal')).toContainText(
    'Yesterday I went to school and saw a substantial building.',
  )
  await expect(page.getByTestId('coach-rewrite-casual')).toContainText(
    'really big building',
  )
  await expect(page.getByTestId('coach-rewrite-minimal')).toContainText(
    'Yesterday I went to school and saw a very big building.',
  )
  await expect(page.getByTestId('coach-learnings')).toContainText('过去时间要用过去式')
  await expect(page.getByText('纠错', { exact: true })).toBeVisible()
})

test('U-CO-02 追问走 answer 模式并流式输出', async ({ page }) => {
  await page.goto('/coach')
  const input = page.getByPlaceholder(COMPOSER)
  await input.fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('coach-rewrite-minimal')).toBeVisible()

  await input.fill('为什么用 went？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('coach-answer').last()).toContainText('turn on')
  await expect(page.getByText('问答', { exact: true })).toBeVisible()
})

test('U-CO-03 客户端携带完整历史且 assistant 使用紧凑报告', async ({ page }) => {
  const bodies: Record<string, unknown>[] = []
  page.on('request', (request) => {
    if (!request.url().includes('/coach/stream')) return
    try {
      bodies.push(request.postDataJSON() as Record<string, unknown>)
    } catch {
      // ignore
    }
  })

  await page.goto('/coach')
  const input = page.getByPlaceholder(COMPOSER)
  await input.fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('coach-rewrite-minimal')).toBeVisible()

  await input.fill('为什么用 went？')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByTestId('coach-answer').last()).toContainText('turn on')

  expect(bodies.length).toBe(2)
  const messages = bodies[1].messages as { role: string; content: string }[]
  expect(messages.map((m) => m.role)).toEqual(['user', 'assistant', 'user'])
  expect(messages[1].content).toContain('"mode":"correct"')
  expect(messages[2].content).toBe('为什么用 went？')
})

test('U-CO-04 后端不可达时显示错误', async ({ page }) => {
  await page.route('**/api/v1/coach/stream', (route) => route.abort())
  await page.goto('/coach')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()
  await expect(page.getByText('无法连接后端服务，请确认后端已启动')).toBeVisible()
})

test('U-CO-05 思考过程自动滚动到最新内容', async ({ page }) => {
  await page.goto('/coach')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  const pre = page.getByTestId('coach-reasoning-content')
  await expect(pre).toBeVisible()
  await expect
    .poll(async () => pre.evaluate((el) => el.scrollTop))
    .toBeGreaterThan(0)
  expect(
    await pre.evaluate(
      (el) => el.scrollHeight - el.scrollTop - el.clientHeight < 8,
    ),
  ).toBe(true)
})

test('U-CO-06 显示思考耗时与完成总耗时', async ({ page }) => {
  await page.goto('/coach')
  await page.getByPlaceholder(COMPOSER).fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '发送', exact: true }).click()

  const timing = page.getByTestId('coach-timing')
  await expect(timing).toContainText('总耗时')
  await expect(timing).toContainText('思考')
  await expect(timing).toHaveText(/^思考 \d+\.\ds · 总耗时 \d+\.\ds$/)
  await expect(page.getByTestId('coach-reasoning')).toContainText('思考过程 ·')
})
