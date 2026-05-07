import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import Accounts from './components/Accounts'
import ProviderDetail from './components/ProviderDetail'
import Login from './components/Login'

export type Page = 'dashboard' | 'accounts' | 'login' | `provider:${string}`

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  const providerMatch = page.match(/^provider:(.+)$/)
  const activeProvider = providerMatch ? providerMatch[1] : null

  return (
    <div className="flex h-screen overflow-hidden bg-[#121212]">
      <Sidebar activePage={page} onNavigate={setPage} />
      <main className="flex-1 overflow-y-auto p-5 bg-gradient-to-b from-[#121212] to-[#0d0d0d]">
        {page === 'dashboard' && <Dashboard onNavigate={setPage} />}
        {page === 'accounts' && <Accounts onNavigate={setPage} />}
        {activeProvider && (
          <ProviderDetail
            providerName={activeProvider}
            onClose={() => setPage('dashboard')}
          />
        )}
        {page === 'login' && <Login onNavigate={setPage} />}
      </main>
    </div>
  )
}
