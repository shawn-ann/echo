import { expect, type Page } from '@playwright/test'

export const USERNAME = 'shawn'
export const PASSWORD = 'shawn!QAZ1qaz'

export async function login(page: Page) {
  await page.goto('/login')
  await page.getByLabel('用户名').fill(USERNAME)
  await page.getByLabel('密码').fill(PASSWORD)
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page).toHaveURL(/\/correction$/)
}
