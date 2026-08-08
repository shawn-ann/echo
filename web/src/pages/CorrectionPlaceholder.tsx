import { useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/store/auth-context'

export default function CorrectionPlaceholder() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex min-h-screen flex-col bg-[#f0fdfa]">
      <header className="flex h-16 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-8">
        <div className="flex items-center gap-2">
          <div className="flex size-8 items-center justify-center rounded-lg bg-[#0ca678] text-sm font-semibold text-white">
            E
          </div>
          <span className="text-lg font-semibold text-[#0a7053]">
            Echo · 地道英语纠错
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-[#495057]">
            {user?.username ?? ''}
          </span>
          <Button
            variant="outline"
            onClick={handleLogout}
            className="h-9 border-[#ced4da] bg-white px-4 text-[#343a40] hover:bg-[#f1f3f5]"
          >
            退出
          </Button>
        </div>
      </header>

      <main className="flex flex-1 items-center justify-center p-6">
        <p className="text-center text-[#868e96]">
          纠错主页（待开发）· 登录流程验证完毕
        </p>
      </main>
    </div>
  )
}
