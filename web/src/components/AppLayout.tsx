import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import Sidebar from '@/components/Sidebar'
import { useAuth } from '@/store/auth-context'

export default function AppLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const pageTitle = pathname.startsWith('/correction') ? '纠错' : ''
  const [drawerOpen, setDrawerOpen] = useState(false)

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-screen bg-[#f0fdfa]">
      {/* 桌面 sidebar */}
      <aside className="hidden w-[200px] shrink-0 flex-col border-r border-[#dee2e6] bg-white md:flex">
        <div className="flex items-center gap-2 px-4 py-4">
          <div className="flex size-7 items-center justify-center rounded-lg bg-[#0ca678] text-xs font-semibold text-white">
            E
          </div>
          <span className="text-base font-semibold text-[#0a7053]">Echo</span>
        </div>
        <Sidebar />
      </aside>

      {/* 移动端抽屉 */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setDrawerOpen(false)}
          />
          <aside className="absolute left-0 top-0 h-full w-[200px] bg-white">
            <div className="flex items-center gap-2 px-4 py-4">
              <div className="flex size-7 items-center justify-center rounded-lg bg-[#0ca678] text-xs font-semibold text-white">
                E
              </div>
              <span className="text-base font-semibold text-[#0a7053]">Echo</span>
            </div>
            <div onClick={() => setDrawerOpen(false)}>
              <Sidebar />
            </div>
          </aside>
        </div>
      )}

      {/* 主内容区 */}
      <div className="flex flex-1 flex-col overflow-hidden">
        <header className="flex h-14 shrink-0 items-center justify-between border-b border-[#dee2e6] bg-white px-4 md:px-6">
          <button
            type="button"
            className="text-xl text-[#495057] md:hidden"
            onClick={() => setDrawerOpen(true)}
            aria-label="打开菜单"
          >
            ☰
          </button>
          <div>
            {pageTitle && (
              <span className="text-sm font-semibold text-[#343a40]">{pageTitle}</span>
            )}
          </div>
          <div className="flex items-center gap-3">
            <span className="text-sm text-[#495057]">{user?.username ?? ''}</span>
            <Button
              variant="outline"
              onClick={handleLogout}
              className="h-8 border-[#ced4da] bg-white px-3 text-[#343a40] hover:bg-[#f1f3f5]"
            >
              退出
            </Button>
          </div>
        </header>
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
