import { useState, useEffect, useCallback } from 'react'
import type { Page } from '../App'

interface SessionItem {
  id: number
  email: string
  status: string
  has_api_key: boolean
  credits: number
  created_at: string
}

interface AccountStats {
  total: number
  active: number
  exhausted: number
  banned: number
  error: number
}

interface AccountsProps {
  onNavigate: (page: Page) => void
}

export default function Accounts({ onNavigate }: AccountsProps) {
  const [sessions, setSessions] = useState<SessionItem[]>([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [addText, setAddText] = useState('')
  const [loading, setLoading] = useState(false)
  const [lastSynced, setLastSynced] = useState<string>('')

  const fetchSessions = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions')
      if (res.ok) {
        const json = await res.json()
        setSessions(json.sessions || [])
        setLastSynced(new Date().toLocaleTimeString())
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  const stats: AccountStats = {
    total: sessions.length,
    active: sessions.filter(s => s.status === 'active').length,
    exhausted: sessions.filter(s => s.status === 'exhausted').length,
    banned: sessions.filter(s => s.status === 'banned').length,
    error: sessions.filter(s => s.status === 'failed' || s.status === 'expired').length,
  }

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
        setShowAddModal(false)
        // Trigger login
        const loginRes = await fetch('/api/sessions/login', { method: 'POST' })
        if (loginRes.ok) {
          onNavigate('login')
        } else {
          fetchSessions()
        }
      }
    } catch { /* ignore */ }
    setLoading(false)
  }

  const handleDeleteByStatus = async (status: string) => {
    const toDelete = sessions.filter(s => s.status === status)
    for (const s of toDelete) {
      try {
        await fetch(`/api/sessions/${s.id}`, { method: 'DELETE' })
      } catch { /* ignore */ }
    }
    fetchSessions()
  }

  return (
    <div className="max-w-6xl space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white tracking-tight">Accounts</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage accounts for the AI proxy</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchSessions}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-[#1a1d23] border border-[#2a2d35] text-gray-300 hover:text-white hover:border-[#3a3d45] transition-colors"
          >
            Sync Accounts
          </button>
          <button
            onClick={() => handleDeleteByStatus('exhausted')}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 hover:bg-amber-500/20 transition-colors"
          >
            Delete Exhausted
          </button>
          <button
            onClick={() => handleDeleteByStatus('failed')}
            className="px-3 py-1.5 text-xs font-medium rounded-md bg-red-500/10 border border-red-500/20 text-red-400 hover:bg-red-500/20 transition-colors"
          >
            Delete Inactive
          </button>
        </div>
      </div>

      {/* Last synced bar */}
      {lastSynced && (
        <div className="flex items-center gap-2 px-3 py-2 bg-[#1a1d23]/50 border border-[#2a2d35] rounded-lg">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          <span className="text-[11px] text-gray-500">Last synced: {lastSynced}</span>
        </div>
      )}

      {/* Provider Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {/* CodeBuddy Provider Card */}
        <div
          onClick={() => onNavigate('provider:codebuddy')}
          className="bg-[#1a1d23] border border-[#2a2d35] rounded-xl p-5 space-y-4 cursor-pointer transition-all duration-200 hover:border-[#16b195]/40 hover:shadow-[0_0_12px_rgba(22,177,149,0.08)]"
        >
          {/* Card Header */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-cyan-400 to-teal-500 flex items-center justify-center">
                <span className="text-sm font-bold text-black">CB</span>
              </div>
              <div>
                <h3 className="text-sm font-semibold text-white">CodeBuddy</h3>
                <p className="text-[11px] text-gray-500">{stats.total} accounts</p>
              </div>
            </div>
            <button
              onClick={(e) => { e.stopPropagation(); setShowAddModal(true) }}
              className="px-3.5 py-1.5 text-xs font-semibold rounded-lg bg-gradient-to-r from-teal-500 to-cyan-500 text-black hover:from-teal-400 hover:to-cyan-400 transition-all shadow-lg shadow-teal-500/20"
            >
              Add
            </button>
          </div>

          {/* Stats Grid */}
          <div className="grid grid-cols-2 gap-2">
            <div className="bg-emerald-500/8 border border-emerald-500/15 rounded-lg px-3 py-2.5">
              <p className="text-[10px] font-medium text-emerald-400/70 uppercase tracking-wider">Active</p>
              <p className="text-lg font-bold text-emerald-400 mt-0.5">{stats.active}</p>
            </div>
            <div className="bg-amber-500/8 border border-amber-500/15 rounded-lg px-3 py-2.5">
              <p className="text-[10px] font-medium text-amber-400/70 uppercase tracking-wider">Exhausted</p>
              <p className="text-lg font-bold text-amber-400 mt-0.5">{stats.exhausted}</p>
            </div>
            <div className="bg-rose-500/8 border border-rose-500/15 rounded-lg px-3 py-2.5">
              <p className="text-[10px] font-medium text-rose-400/70 uppercase tracking-wider">Banned</p>
              <p className="text-lg font-bold text-rose-400 mt-0.5">{stats.banned}</p>
            </div>
            <div className="bg-red-500/8 border border-red-500/15 rounded-lg px-3 py-2.5">
              <p className="text-[10px] font-medium text-red-400/70 uppercase tracking-wider">Error</p>
              <p className="text-lg font-bold text-red-400 mt-0.5">{stats.error}</p>
            </div>
          </div>

          {/* Bottom Actions */}
          <div className="flex gap-2 pt-1">
            <button
              onClick={async () => {
                await fetch('/api/sessions/login', { method: 'POST' })
                onNavigate('login')
              }}
              className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 hover:bg-indigo-500/20 transition-colors"
            >
              Warmup
            </button>
            <button
              onClick={async () => {
                await fetch('/api/sessions/login', { method: 'POST' })
                onNavigate('login')
              }}
              className="flex-1 px-3 py-2 text-xs font-medium rounded-lg bg-violet-500/10 border border-violet-500/20 text-violet-400 hover:bg-violet-500/20 transition-colors"
            >
              Warmup All
            </button>
          </div>
        </div>

        {/* Placeholder cards (disabled) */}
        <div className="bg-[#1a1d23]/50 border border-[#2a2d35]/50 rounded-xl p-5 opacity-40 pointer-events-none">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gray-700/50 flex items-center justify-center">
              <span className="text-sm text-gray-500">GP</span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500">GPT Provider</h3>
              <p className="text-[11px] text-gray-600">Coming soon</p>
            </div>
          </div>
        </div>

        <div className="bg-[#1a1d23]/50 border border-[#2a2d35]/50 rounded-xl p-5 opacity-40 pointer-events-none">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-gray-700/50 flex items-center justify-center">
              <span className="text-sm text-gray-500">CL</span>
            </div>
            <div>
              <h3 className="text-sm font-semibold text-gray-500">Claude Provider</h3>
              <p className="text-[11px] text-gray-600">Coming soon</p>
            </div>
          </div>
        </div>
      </div>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowAddModal(false)} />
          <div className="relative bg-[#1a1d23] border border-[#2a2d35] rounded-xl p-6 w-full max-w-lg shadow-2xl">
            <h2 className="text-base font-semibold text-white mb-1">Add Accounts</h2>
            <p className="text-xs text-gray-500 mb-4">Enter credentials in email:password format, one per line</p>
            <textarea
              value={addText}
              onChange={e => setAddText(e.target.value)}
              placeholder={"user1@gmail.com:password123\nuser2@gmail.com:mypass456"}
              rows={6}
              className="w-full bg-[#0a0c10] border border-[#2a2d35] rounded-lg px-4 py-3 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-teal-500/50 resize-none font-mono"
              autoFocus
            />
            <div className="flex items-center justify-between mt-4">
              <span className="text-[11px] text-gray-500">
                {addText.trim() ? addText.trim().split('\n').filter(Boolean).length : 0} accounts
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2 text-xs font-medium rounded-lg bg-[#0f1117] border border-[#2a2d35] text-gray-400 hover:text-white transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAdd}
                  disabled={loading || !addText.trim()}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-gradient-to-r from-teal-500 to-cyan-500 text-black hover:from-teal-400 hover:to-cyan-400 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-lg shadow-teal-500/20"
                >
                  {loading ? 'Adding...' : 'Add & Login'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
