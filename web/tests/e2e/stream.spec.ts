import { expect, test } from '@playwright/test'

test('U-S-01 流式纠错先错误后改写', async ({ page }) => {
  await page.goto('/stream')
  await page.getByPlaceholder('输入英文，开始流式纠错').fill('Yesterday I go to school.')
  await page.getByRole('button', { name: '开始' }).click()
  await expect(page.getByTestId('stream-errors')).toContainText('时态错误')
  await expect(page.getByTestId('stream-minimal')).toContainText('Yesterday I went to school.')
  await expect(page.getByTestId('stream-fluency')).toContainText('I went to school yesterday.')
})
