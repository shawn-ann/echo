import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { ApiError } from '@/api/client'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth } from '@/store/auth-context'

function BrandMark() {
  return (
    <div className="flex size-11 items-center justify-center rounded-xl bg-[#0ca678] text-xl font-semibold text-white">
      E
    </div>
  )
}

function BrandPoints() {
  return (
    <ul className="space-y-2 text-sm text-[#495057]">
      <li>· 会话式纠错 + 无限追问</li>
      <li>· 中式英语专项纠正</li>
      <li>· 帮你记住每一个错误</li>
    </ul>
  )
}

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const navigate = useNavigate()
  const { login } = useAuth()

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (loading) return
    setFormError(null)

    const uname = username.trim()
    let invalid = false
    if (!uname) {
      setUsernameError('请输入用户名')
      invalid = true
    } else {
      setUsernameError(null)
    }
    if (!password) {
      setPasswordError('请输入密码')
      invalid = true
    } else {
      setPasswordError(null)
    }
    if (invalid) return

    setLoading(true)
    try {
      await login(uname, password)
      navigate('/correction', { replace: true })
    } catch (err) {
      setPassword('')
      if (err instanceof ApiError && err.status === 403) {
        setFormError(err.message)
      } else if (err instanceof ApiError && err.status === 401) {
        setFormError('用户名或密码错误')
      } else {
        setFormError('登录失败，请稍后重试')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#f0fdfa]">
      <div className="min-h-screen md:flex">
        {/* 品牌区 · 桌面端 */}
        <div className="hidden w-[55%] flex-col items-center justify-center gap-6 px-12 md:flex">
          <BrandMark />
          <h1 className="text-center text-[30px] font-semibold text-[#0a7053]">
            Echo · 地道英语纠错
          </h1>
          <p className="max-w-md text-center text-[#495057]">
            会帮你记住每一个错误的 AI 英语教练
          </p>
          <BrandPoints />
        </div>

        {/* 登录区 */}
        <div className="flex min-h-full flex-1 flex-col items-center justify-center px-4 py-10">
          {/* 品牌区 · 移动端 */}
          <div className="mb-8 text-center md:hidden">
            <BrandMark />
            <h1 className="mt-3 text-[30px] font-semibold text-[#0a7053]">
              Echo · 地道英语纠错
            </h1>
            <p className="mt-1 text-sm text-[#495057]">
              会帮你记住每一个错误的 AI 英语教练
            </p>
          </div>

          <Card className="w-full max-w-[400px] rounded-[14px] bg-white p-8 shadow-[0_2px_8px_rgba(33,37,41,0.06)]">
            <CardHeader className="px-0 pt-0">
              <CardTitle className="text-xl font-semibold">登录</CardTitle>
              <CardDescription className="text-sm text-[#868e96]">
                使用内置账号体验（demo / demo1234）
              </CardDescription>
            </CardHeader>
            <CardContent className="px-0">
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-1.5">
                  <Label htmlFor="username">用户名</Label>
                  <Input
                    id="username"
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="h-11 rounded-lg border-[#ced4da] bg-[#f8f9fa] px-3.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
                    aria-invalid={usernameError ? true : undefined}
                  />
                  {usernameError && (
                    <p className="text-sm text-[#fa5252]">{usernameError}</p>
                  )}
                </div>

                <div className="space-y-1.5">
                  <Label htmlFor="password">密码</Label>
                  <Input
                    id="password"
                    type="password"
                    name="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-11 rounded-lg border-[#ced4da] bg-[#f8f9fa] px-3.5 text-base focus-visible:border-[#0ca678] focus-visible:ring-[#0ca678]/50"
                    aria-invalid={passwordError ? true : undefined}
                  />
                  {passwordError && (
                    <p className="text-sm text-[#fa5252]">{passwordError}</p>
                  )}
                </div>

                {formError && (
                  <p className="text-sm text-[#fa5252]">{formError}</p>
                )}

                <Button
                  type="submit"
                  disabled={loading}
                  className="h-12 w-full bg-[#0ca678] text-base text-white hover:bg-[#12c493] disabled:bg-[#99f0d8]"
                >
                  {loading ? '登录中…' : '登录'}
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
