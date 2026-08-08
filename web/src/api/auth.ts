import { http } from './client'

export interface User {
  id: string
  username: string
}

export interface LoginResult {
  token: string
  expires_at: string
  user: User
}

export async function login(
  username: string,
  password: string,
): Promise<LoginResult> {
  return http.post<LoginResult>('/auth/login', { username, password })
}

export async function logout(): Promise<void> {
  await http.post<void>('/auth/logout')
}

export async function fetchMe(): Promise<User> {
  return http.get<User>('/auth/me')
}
