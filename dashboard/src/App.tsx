import { useState } from 'react'
import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'
import Sessions from './components/Sessions'

export type Page = 'dashboard' | 'sessions'

export default function App() {
  const [page, setPage] = useState<Page>('dashboard')

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activePage={page} onNavigate={setPage} />
      <main className="flex-1 overflow-y-auto p-6">
        {page === 'dashboard' && <Dashboard />}
        {page === 'sessions' && <Sessions />}
      </main>
    </div>
  )
}
