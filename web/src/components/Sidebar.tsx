import { NavLink } from 'react-router-dom'

const navItems = [
  { to: '/correction', label: '对话纠错', icon: '💬' },
  { to: '/stream', label: '流式纠错', icon: '⚡' },
  { to: '/coach', label: 'Coach', icon: '🎓' },
  { to: '/notes', label: '我的笔记', icon: '📖' },
]

export default function Sidebar() {
  return (
    <nav className="flex flex-col gap-1 p-3">
      {navItems.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className={({ isActive }) =>
            `flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
              isActive
                ? 'bg-[#0ca678] text-white'
                : 'text-[#495057] hover:bg-[#f1f3f5]'
            }`
          }
        >
          <span>{item.icon}</span>
          <span>{item.label}</span>
        </NavLink>
      ))}
    </nav>
  )
}
