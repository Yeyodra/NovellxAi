import { useEffect, useState } from 'react'

interface Session {
  id: number
  email: string
  status: string
  has_api_key: boolean
  credits: number
  credits_limit?: number
  created_at: string
}

interface ProviderDetailProps {
  providerName: string
  onClose: () => void
}

const statusConfig: Record<string, { bg: string; text: string; border: string; label: string }> = {
  active: { bg: 'bg-[#1c9749]/15', text: 'text-[#1c9749]', border: 'border-[#1c9749]/30', label: 'Active' },
  exhausted: { bg: 'bg-[#ffc107]/15', text: 'text-[#ffc107]', border: 'border-[#ffc107]/30', label: 'Exhausted' },
  banned: { bg: 'bg-[#e11d48]/15', text: 'text-[#e11d48]', border: 'border-[#e11d48]/30', label: 'Banned' },
  expired: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30', label: 'Expired' },
  failed: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30', label: 'Failed' },
  error: { bg: 'bg-gray-500/15', text: 'text-gray-400', border: 'border-gray-500/30', label: 'Error' },
}

function StatusBadge({ status }: { status: string }) {
  const cfg = statusConfig[status] ?? statusConfig.error
  return (
    <span className={`inline-flex items-center px-2 py-0.5 text-[10px] font-medium rounded-full border ${cfg.bg} ${cfg.text} ${cfg.border}`}>
      {cfg.label}
    </span>
  )
}

export default function ProviderDetail({ providerName, onClose }: ProviderDetailProps) {
  const [sessions, setSessions] = useState<Session[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchSessions = async () => {
      setLoading(true)
      try {
        const res = await fetch('/api/sessions')
        if (res.ok) {
          const json = await res.json()
          setSessions(json.sessions ?? [])
        }
      } catch {
        // silent fail
      } finally {
        setLoading(false)
      }
    }
    fetchSessions()
  }, [])

  // Status counts
  const counts = sessions.reduce(
    (acc, s) => {
      const key = s.status as keyof typeof acc
      if (key in acc) acc[key]++
      return acc
    },
    { active: 0, exhausted: 0, banned: 0, error: 0 }
  )

  const summaryCards = [
    { label: 'Active', count: counts.active, color: '#1c9749' },
    { label: 'Exhausted', count: counts.exhausted, color: '#ffc107' },
    { label: 'Banned', count: counts.banned, color: '#e11d48' },
    { label: 'Error', count: counts.error, color: '#6b7280' },
  ]

  return (
    <div className="bg-[#0d0d0d] border border-white/[0.08] rounded-lg overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3.5 border-b border-white/[0.08]">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-white">{providerName}</h3>
          <span className="text-[11px] text-gray-500">{sessions.length} accounts</span>
        </div>
        <button
          type="button"
          onClick={onClose}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.08] rounded-md transition-colors"
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none" className="opacity-70" aria-hidden="true">
            <title>Back arrow</title>
            <path d="M7.5 9L4.5 6L7.5 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back
        </button>
      </div>

      {/* Status Summary Grid */}
      <div className="grid grid-cols-4 gap-3 px-5 py-4">
        {summaryCards.map((card) => (
          <div
            key={card.label}
            className="bg-[#1a1a1a] rounded-md p-3 border-l-2"
            style={{ borderLeftColor: card.color }}
          >
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">{card.label}</p>
            <p className="text-lg font-semibold text-white mt-0.5">{card.count}</p>
          </div>
        ))}
      </div>

      {/* Account List */}
      <div className="px-5 pb-4">
        <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-lg overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-[1fr_100px_120px_100px] gap-2 px-4 py-2.5 border-b border-white/[0.06] text-[10px] font-medium text-gray-500 uppercase tracking-wide">
            <span>Email</span>
            <span>Status</span>
            <span>Credits</span>
            <span>Added</span>
          </div>

          {/* Rows */}
          <div className="max-h-[280px] overflow-y-auto scrollbar-thin">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="w-4 h-4 border-2 border-[#16b195]/30 border-t-[#16b195] rounded-full animate-spin" />
                <span className="ml-2 text-xs text-gray-500">Loading accounts…</span>
              </div>
            ) : sessions.length === 0 ? (
              <div className="flex items-center justify-center py-8">
                <span className="text-xs text-gray-500 italic">No accounts found</span>
              </div>
            ) : (
              sessions.map((session) => (
                <div
                  key={session.id}
                  className="grid grid-cols-[1fr_100px_120px_100px] gap-2 px-4 py-2.5 border-b border-white/[0.04] last:border-b-0 hover:bg-white/[0.02] transition-colors"
                >
                  <span className="text-xs text-[#d0d1d7] truncate">{session.email}</span>
                  <span><StatusBadge status={session.status} /></span>
                  <span className="text-xs text-gray-400 tabular-nums">
                    {session.credits.toFixed(1)}/{session.credits_limit ?? 250}
                  </span>
                  <span className="text-xs text-gray-500">
                    {new Date(session.created_at).toLocaleDateString('en-GB', { day: '2-digit', month: 'short' })}
                  </span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
