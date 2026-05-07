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

// Inline SVG icons (Lucide-style, 16x16)
const icons = {
  dashboard: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>`,
  accounts: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  models: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>`,
  key: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M21 2l-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0l3 3L22 7l-3-3m-3.5 3.5L19 4"/></svg>`,
  proxy: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z"/></svg>`,
  filters: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="4" x2="4" y1="21" y2="14"/><line x1="4" x2="4" y1="10" y2="3"/><line x1="12" x2="12" y1="21" y2="12"/><line x1="12" x2="12" y1="8" y2="3"/><line x1="20" x2="20" y1="21" y2="16"/><line x1="20" x2="20" y1="12" y2="3"/><line x1="2" x2="6" y1="14" y2="14"/><line x1="10" x2="14" y1="8" y2="8"/><line x1="18" x2="22" y1="16" y2="16"/></svg>`,
  login: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" x2="3" y1="12" y2="12"/></svg>`,
  requests: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" x2="8" y1="13" y2="13"/><line x1="16" x2="8" y1="17" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>`,
  usage: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><line x1="18" x2="18" y1="20" y2="10"/><line x1="12" x2="12" y1="20" y2="4"/><line x1="6" x2="6" y1="20" y2="14"/></svg>`,
}

const navSections: NavSection[] = [
  {
    title: 'ACCOUNTS',
    items: [
      { label: 'Accounts', icon: 'accounts', page: 'accounts' },
      { label: 'Models', icon: 'models' },
    ],
  },
  {
    title: 'PROXY',
    items: [
      { label: 'API Key', icon: 'key' },
      { label: 'Proxy', icon: 'proxy' },
      { label: 'Filters', icon: 'filters' },
    ],
  },
  {
    title: 'LOGS & ANALYTICS',
    items: [
      { label: 'Login', icon: 'login', page: 'login' },
      { label: 'Requests', icon: 'requests' },
      { label: 'Usage', icon: 'usage' },
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
          <span className="w-4 h-4 opacity-70" dangerouslySetInnerHTML={{ __html: icons.dashboard }} />
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
                      <span className="w-4 h-4 opacity-70" dangerouslySetInnerHTML={{ __html: icons[item.icon as keyof typeof icons] || '' }} />
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
