const navSections = [
  {
    title: 'ACCOUNTS',
    items: [
      { label: 'Accounts', icon: '👤', active: true },
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
      { label: 'Requests', icon: '📋' },
      { label: 'Usage', icon: '📊' },
    ],
  },
]

export default function Sidebar() {
  return (
    <aside className="w-56 h-screen bg-[#0f1117] border-r border-[#2a2d35] flex flex-col shrink-0">
      {/* Logo */}
      <div className="p-5 border-b border-[#2a2d35]">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-teal-400 to-cyan-500 flex items-center justify-center text-xs font-bold text-black">
            N
          </div>
          <div>
            <h1 className="text-sm font-semibold text-white leading-none">NovellxAI</h1>
            <span className="text-[10px] text-gray-500">v0.1.0</span>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-4 px-3 space-y-5 overflow-y-auto">
        {navSections.map((section) => (
          <div key={section.title}>
            <p className="text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-2 mb-2">
              {section.title}
            </p>
            <ul className="space-y-0.5">
              {section.items.map((item) => (
                <li key={item.label}>
                  <button
                    className={`w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded-md text-sm transition-colors ${
                      item.active
                        ? 'bg-[#1a1d23] text-white'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-[#1a1d23]/50'
                    }`}
                  >
                    <span className="text-xs">{item.icon}</span>
                    <span>{item.label}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {/* Status */}
      <div className="p-4 border-t border-[#2a2d35]">
        <div className="flex items-center gap-2 text-xs text-gray-400">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          <span>Proxy running</span>
        </div>
      </div>
    </aside>
  )
}
