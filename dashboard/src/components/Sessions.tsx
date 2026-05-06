import { useState, useEffect, useCallback } from 'react'

interface SessionItem {
  id: number
  email: string
  status: string
  has_api_key: boolean
  credits: number
  created_at: string
}

interface LoginStatus {
  running: boolean
  completed: number
  total: number
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    active: 'bg-emerald-500/15 text-emerald-400',
    pending: 'bg-gray-500/15 text-gray-400',
    exhausted: 'bg-yellow-500/15 text-yellow-400',
    expired: 'bg-red-500/15 text-red-400',
    failed: 'bg-red-500/15 text-red-400',
    banned: 'bg-red-500/15 text-red-400',
  }
  return (
    <span className={`text-[10px] font-medium px-2 py-0.5 rounded-full ${styles[status] || styles.pending}`}>
      {status}
    </span>
  )
}

export default function Sessions() {
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [addText, setAddText] = useState('')
  const [loginStatus, setLoginStatus] = useState<LoginStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions')
      if (res.ok) {
        const json = await res.json()
        setSessions(json.sessions || [])
      }
    } catch { /* ignore */ }
  }, [])

  const fetchLoginStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions/login-status')
      if (res.ok) {
        const json: LoginStatus = await res.json()
        setLoginStatus(json)
        if (!json.running) return false
      }
    } catch { /* ignore */ }
    return true
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  // Poll login status when running
  useEffect(() => {
    if (!loginStatus?.running) return
    const interval = setInterval(async () => {
      const stillRunning = await fetchLoginStatus()
      if (!stillRunning) {
        clearInterval(interval)
        fetchSessions()
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [loginStatus?.running, fetchLoginStatus, fetchSessions])

  const handleAdd = async () => {
    const lines = addText.trim().split('\n').filter(Boolean)
    const accounts = lines.map(line => {
      const [email, password] = line.split(':')
      return { email: email?.trim(), password: password?.trim() || '' }
    }).filter(a => a.email)

    if (accounts.length === 0) return

    setLoading(true)
    try {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ accounts }),
      })
      if (res.ok) {
        setAddText('')
        setShowAdd(false)
        fetchSessions()
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`/api/sessions/${id}`, { method: 'DELETE' })
      if (res.ok) fetchSessions()
    } catch { /* ignore */ }
  }

  const handleLogin = async () => {
    try {
      const res = await fetch('/api/sessions/login', { method: 'POST' })
      if (res.ok) {
        const json = await res.json()
        if (json.started) {
          setLoginStatus({ running: true, completed: 0, total: json.total })
        }
      }
    } catch { /* ignore */ }
  }

  return (
    <div className="max-w-5xl space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold text-white">Accounts</h1>
        <button
          onClick={() => setShowAdd(!showAdd)}
          className="px-3 py-1.5 text-xs font-medium rounded-md bg-teal-500/15 text-teal-400 hover:bg-teal-500/25 transition-colors"
        >
          {showAdd ? 'Cancel' : 'Add Accounts'}
        </button>
      </div>

      {/* Add form */}
      {showAdd && (
        <div className="bg-[#1a1d23] border border-[#2a2d35] rounded-lg p-4 space-y-3">
          <textarea
            value={addText}
            onChange={e => setAddText(e.target.value)}
            placeholder="email:password (one per line)..."
            rows={4}
            className="w-full bg-[#0f1117] border border-[#2a2d35] rounded-md px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-teal-500/50 resize-none"
          />
          <button
            onClick={handleAdd}
            disabled={loading || !addText.trim()}
            className="px-4 py-1.5 text-xs font-medium rounded-md bg-teal-500 text-black hover:bg-teal-400 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Adding...' : 'Add'}
          </button>
        </div>
      )}

      {/* Login progress */}
      {loginStatus?.running && (
        <div className="bg-[#1a1d23] border border-[#2a2d35] rounded-lg p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs text-gray-400">Logging in...</span>
            <span className="text-xs text-teal-400">{loginStatus.completed}/{loginStatus.total}</span>
          </div>
          <div className="w-full h-2 bg-[#2a2d35] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-teal-400 to-cyan-400 transition-all"
              style={{ width: `${loginStatus.total > 0 ? (loginStatus.completed / loginStatus.total) * 100 : 0}%` }}
            />
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-[#1a1d23] border border-[#2a2d35] rounded-lg overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[#2a2d35]">
              <th className="text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Email</th>
              <th className="text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Status</th>
              <th className="text-left text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Credits</th>
              <th className="text-right text-[10px] font-semibold text-gray-500 uppercase tracking-wider px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sessions.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-4 py-8 text-center text-sm text-gray-500">
                  No accounts yet. Add some above.
                </td>
              </tr>
            ) : (
              sessions.map(s => (
                <tr key={s.id} className="border-b border-[#2a2d35] last:border-0 hover:bg-[#1e2128]">
                  <td className="px-4 py-3 text-sm text-white">{s.email}</td>
                  <td className="px-4 py-3"><StatusBadge status={s.status} /></td>
                  <td className="px-4 py-3 text-sm text-gray-400">{s.credits || '—'}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleDelete(s.id)}
                      className="text-xs text-gray-500 hover:text-red-400 transition-colors"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Login button */}
      {!loginStatus?.running && (
        <button
          onClick={handleLogin}
          className="px-4 py-2 text-xs font-medium rounded-md bg-teal-500 text-black hover:bg-teal-400 transition-colors"
        >
          Login All Pending
        </button>
      )}
    </div>
  )
}
