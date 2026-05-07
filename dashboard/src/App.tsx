import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import Accounts from './components/Accounts'
import Login from './components/Login'

export type Page = 'dashboard' | 'accounts' | 'login'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div className="flex h-screen overflow-hidden bg-[#121212]">
      <Sidebar activePage={page} onNavigate={setPage} />
      <main className="flex-1 overflow-y-auto p-5 bg-gradient-to-b from-[#121212] to-[#0d0d0d]">
        {page === 'dashboard' && <Dashboard />}
        {page === 'accounts' && <Accounts onNavigate={setPage} />}
        {page === 'login' && <Login onNavigate={setPage} />}
      </main>
    </div>
  )
}
