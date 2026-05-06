import Sidebar from './components/Sidebar'
import Dashboard from './components/Dashboard'

export default function App() {
  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar />
      <main className="flex-1 overflow-y-auto p-6">
        <Dashboard />
      </main>
    </div>
  )
}
