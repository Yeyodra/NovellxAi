import type { Page } from '../App'

interface NavItem {
  label: string
  icon: string
  page?: Page
}

interface NavSection {
  title: string
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    title: 'ACCOUNTS',
    items: [
      { label: 'Accounts', icon: '👤', page: 'accounts' },
      { label: 'Models', icon: '🧠' },
    ],
  },
  {
    title: 'PROXY',
    items: [
      { label: 'API Key', icon: '🔑' },
      { label: 'Proxy', icon: '🔄' },
      { label: 'Filters', icon: '⚙️' },
    ],
  },
  {
    title: 'LOGS & ANALYTICS',
    items: [
      { label: 'Login', icon: '🔐', page: 'login' },
      { label: 'Requests', icon: '📋' },
      { label: 'Usage', icon: '📊' },
    ],
  },
]

interface SidebarProps {
  activePage: Page
  onNavigate: (page: Page) => void
}

export default function Sidebar({ activePage, onNavigate }: SidebarProps) {
  return (
    <aside className="w-56 h-screen bg-[#0d0d0d] border-r border-white/[0.08] flex flex-col shrink-0">
      {/* Logo */}
      <div className="p-5 border-b border-white/[0.08]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-[#16b195] to-[#3e62c0] flex items-center justify-center text-xs font-bold text-white">
            N
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white leading-none">NovellaxAI</h1>
            <span className="text-[10px] text-gray-500">v0.1.0</span>
          </div>
        </div>
      </div>

      {/* Dashboard link */}
      <div className="px-3 pt-4 pb-1">
        <button
          onClick={() => onNavigate('dashboard')}
          className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors ${
            activePage === 'dashboard'
              ? 'bg-[#121212] text-white'
              : 'text-gray-400 hover:text-gray-200 hover:bg-[#121212]/50'
          }`}
        >
          <span className="text-xs">📊</span>
          <span>Dashboard</span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-2 px-3 space-y-5 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.title}>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">
              {section.title}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => {
                const isActive = item.page ? activePage === item.page : false
                return (
                  <li key={item.label}>
                    <button
                      onClick={() => item.page && onNavigate(item.page)}
                      className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors ${
                        isActive
                          ? 'bg-[#121212] text-white'
                          : 'text-gray-400 hover:text-gray-200 hover:bg-[#121212]/50'
                      }`}
                    >
                      <span className="text-xs">{item.icon}</span>
                      <span>{item.label}</span>
                    </button>
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* Status */}
      <div className="p-4 border-t border-white/[0.08]">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="w-2 h-2 rounded-full bg-[#1c9749] animate-pulse" />
          <span>Proxy running</span>
        </div>
      </div>
    </aside>
  )
}
