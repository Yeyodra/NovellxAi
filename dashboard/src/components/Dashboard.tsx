import { useEffect, useRef, useState } from 'react'

// Types matching the API response
interface DashboardData {
  accounts: { active: number; total: number }
  requests: { total: number; success: number; failed: number }
  success_rate: number
  uptime_seconds: number
  providers: Record<string, {
    active: number
    total: number
    exhausted?: number
    credits_used?: number
    credits_total?: number
  }>
  token_usage: { total: number; prompt: number; completion: number }
}

// Fallback mock data
const fallbackData: DashboardData = {
  accounts: { active: 3, total: 3 },
  requests: { total: 45, success: 44, failed: 1 },
  success_rate: 97.3,
  uptime_seconds: 9000,
  providers: {
    codebuddy: { active: 3, total: 3, exhausted: 0, credits_used: 250, credits_total: 750 },
    kiro: { active: 0, total: 0 },
  },
  token_usage: { total: 128450, prompt: 89200, completion: 39250 },
}

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

// Simple SVG chart placeholder
function MiniChart() {
  const points = [20, 35, 25, 45, 30, 55, 40, 60, 50, 45, 65, 55, 70, 60, 75, 68, 72, 80, 75, 85]
  const max = Math.max(...points)
  const w = 100
  const h = 40
  const pathD = points
    .map((p, i) => {
      const x = (i / (points.length - 1)) * w
      const y = h - (p / max) * h
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`
    })
    .join(' ')

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-24 mt-3" preserveAspectRatio="none" aria-hidden="true">
      <title>Token usage chart</title>
      <defs>
        <linearGradient id="chartGrad" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#16b195" stopOpacity="0.3" />
          <stop offset="100%" stopColor="#16b195" stopOpacity="0" />
        </linearGradient>
        <linearGradient id="chartLine" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#16b195" />
          <stop offset="100%" stopColor="#3e62c0" />
        </linearGradient>
      </defs>
      <path d={`${pathD} L ${w} ${h} L 0 ${h} Z`} fill="url(#chartGrad)" />
      <path d={pathD} fill="none" stroke="url(#chartLine)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

const statIcons: Record<string, string> = {
  accounts: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>`,
  requests: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>`,
  success: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 7 13.5 15.5 8.5 10.5 2 17"/><polyline points="16 7 22 7 22 13"/></svg>`,
  uptime: `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>`,
}

function StatCard({ label, value, sub, icon }: { label: string; value: string; sub?: string; icon: string }) {
  const prevValue = useRef(value)
  const [animate, setAnimate] = useState(false)

  useEffect(() => {
    if (prevValue.current !== value) {
      setAnimate(true)
      prevValue.current = value
      const t = setTimeout(() => setAnimate(false), 400)
      return () => clearTimeout(t)
    }
  }, [value])

  return (
    <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-lg p-4 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-medium text-gray-500 uppercase tracking-wide">{label}</span>
        <span className="w-4 h-4 text-gray-500" dangerouslySetInnerHTML={{ __html: statIcons[icon] || '' }} />
      </div>
      <p className={`text-xl font-semibold text-white transition-all duration-300 ${animate ? 'value-updated' : ''}`}>{value}</p>
      {sub && <p className={`text-xs text-gray-500 transition-opacity duration-300 ${animate ? 'opacity-70' : 'opacity-100'}`}>{sub}</p>}
    </div>
  )
}

interface ProviderData {
  name: string
  active: number
  total: number
  exhausted: number
  creditsUsed: number
  creditsTotal: number
}

function ProviderCard({ provider }: { provider: ProviderData }) {
  const pct = provider.creditsTotal > 0 ? (provider.creditsUsed / provider.creditsTotal) * 100 : 0
  const prevCredits = useRef(provider.creditsUsed)
  const [animate, setAnimate] = useState(false)

  useEffect(() => {
    if (prevCredits.current !== provider.creditsUsed) {
      setAnimate(true)
      prevCredits.current = provider.creditsUsed
      const t = setTimeout(() => setAnimate(false), 400)
      return () => clearTimeout(t)
    }
  }, [provider.creditsUsed])

  return (
    <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-sm font-semibold text-white">{provider.name}</h3>
          <p className="text-xs text-gray-500">{provider.active}/{provider.total} accounts</p>
        </div>
        {provider.active > 0 && (
          <span className="text-[10px] font-medium bg-[#1c9749]/15 text-[#1c9749] px-2 py-0.5 rounded-full">
            {provider.active} active
          </span>
        )}
      </div>

      {provider.creditsTotal > 0 ? (
        <div>
          <div className="flex justify-between text-xs text-gray-400 mb-1.5">
            <span>Credits</span>
            <span className={`transition-all duration-300 ${animate ? 'value-updated text-[#16b195]' : ''}`}>
              {provider.creditsUsed} / {provider.creditsTotal}
            </span>
          </div>
          <div className="w-full h-2 bg-white/[0.08] rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-[#16b195] to-[#3e62c0] progress-fill"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className={`text-[11px] text-gray-500 mt-1.5 transition-all duration-300 ${animate ? 'value-updated' : ''}`}>
            {pct.toFixed(1)}% used
          </p>
        </div>
      ) : (
        <p className="text-xs text-gray-500 italic">No accounts</p>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [timeRange, setTimeRange] = useState('7d')
  const [data, setData] = useState<DashboardData>(fallbackData)
  const ranges = ['1d', '7d', '30d', 'all']

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/dashboard')
        if (res.ok) {
          const json: DashboardData = await res.json()
          setData(json)
        }
      } catch {
        // Keep fallback data on error
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 10000) // refresh every 10s
    return () => clearInterval(interval)
  }, [])

  // Transform providers map to array for rendering
  const providersList: ProviderData[] = Object.entries(data.providers).map(([key, val]) => ({
    name: key.charAt(0).toUpperCase() + key.slice(1),
    active: val.active,
    total: val.total,
    exhausted: val.exhausted ?? 0,
    creditsUsed: val.credits_used ?? 0,
    creditsTotal: val.credits_total ?? 0,
  }))

  return (
    <div className="w-full space-y-4">
      {/* Stats Row */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard
          label="Accounts"
          value={`${data.accounts.active}/${data.accounts.total}`}
          sub="active / total"
          icon="accounts"
        />
        <StatCard label="Requests" value={String(data.requests.total)} icon="requests" />
        <StatCard
          label="Success Rate"
          value={`${data.success_rate}%`}
          sub={`${data.requests.success} ok / ${data.requests.failed} fail`}
          icon="success"
        />
        <StatCard label="Uptime" value={formatUptime(data.uptime_seconds)} icon="uptime" />
      </div>

      {/* Providers */}
      <div>
        <h2 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">Providers</h2>
        <div className="grid grid-cols-2 gap-3">
          {providersList.map((p) => (
            <ProviderCard key={p.name} provider={p} />
          ))}
        </div>
      </div>

      {/* Token Usage */}
      <div className="bg-[#1a1a1a] border border-white/[0.08] rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-sm font-semibold text-white">Token Usage</h2>
          <div className="flex gap-1">
            {ranges.map((r) => (
              <button
                type="button"
                key={r}
                onClick={() => setTimeRange(r)}
                className={`px-2.5 py-1 text-xs rounded-md transition-colors ${
                  timeRange === r
                    ? 'bg-[#16b195]/20 text-[#16b195]'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.08]'
                }`}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-3 gap-4 mb-2">
          <div>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Total</p>
            <p className="text-lg font-semibold text-white">{data.token_usage.total.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Prompt</p>
            <p className="text-lg font-semibold text-[#16b195]">{data.token_usage.prompt.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">Completion</p>
            <p className="text-lg font-semibold text-[#3e62c0]">{data.token_usage.completion.toLocaleString()}</p>
          </div>
        </div>

        <MiniChart />
      </div>
    </div>
  )
}
