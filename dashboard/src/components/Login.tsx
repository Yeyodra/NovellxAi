import { useState, useEffect, useCallback, useRef } from 'react'
import type { Page } from '../App'

interface LoginStatus {
  running: boolean
  completed: number
  total: number
}

interface LogEntry {
  time: string
  message: string
  level: string
}

interface LoginProps {
  onNavigate: (page: Page) => void
}

export default function Login({ onNavigate }: LoginProps) {
  const [status, setStatus] = useState<LoginStatus>({ running: true, completed: 0, total: 0 })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const logsEndRef = useRef<HTMLDivElement>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions/login-status')
      if (res.ok) {
        const json: LoginStatus = await res.json()
        setStatus(json)
        return json.running
      }
    } catch { /* ignore */ }
    return false
  }, [])

  const fetchLogs = useCallback(async () => {
    try {
      const res = await fetch('/api/sessions/login-logs')
      if (res.ok) {
        const json = await res.json()
        if (json.logs) {
          setLogs(json.logs)
        }
      }
    } catch { /* ignore */ }
  }, [])

  useEffect(() => {
    fetchStatus()
    fetchLogs()
  }, [fetchStatus, fetchLogs])

  // Poll every 2s
  useEffect(() => {
    const interval = setInterval(async () => {
      const running = await fetchStatus()
      await fetchLogs()
      if (!running) {
        // One final fetch
        setTimeout(() => {
          fetchLogs()
        }, 1000)
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [fetchStatus, fetchLogs])

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  const percentage = status.total > 0 ? Math.round((status.completed / status.total) * 100) : 0

  return (
    <div className="max-w-4xl space-y-6">
      {/* Header */}
      <div>
        <button
          onClick={() => onNavigate('accounts')}
          className="text-xs text-teal-400 hover:text-teal-300 transition-colors mb-3 flex items-center gap-1"
        >
          <span>&larr;</span> Back to Accounts
        </button>
        <h1 className="text-xl font-semibold text-white tracking-tight">Add Accounts</h1>
        <p className="text-sm text-gray-500 mt-0.5">Real-time batch account addition progress</p>
      </div>

      {/* Progress Card */}
      <div className="bg-[#1a1d23] border border-[#2a2d35] rounded-xl p-5 space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {status.running ? (
              <div className="w-8 h-8 rounded-lg bg-teal-500/15 flex items-center justify-center">
                <div className="w-3 h-3 rounded-full border-2 border-teal-400 border-t-transparent animate-spin" />
              </div>
            ) : (
              <div className="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center">
                <span className="text-emerald-400 text-sm">&#10003;</span>
              </div>
            )}
            <div>
              <h3 className="text-sm font-semibold text-white">
                {status.running ? 'Adding Accounts' : 'Complete'}
              </h3>
              <p className="text-[11px] text-gray-500">
                {status.completed}/{status.total} accounts processed
              </p>
            </div>
          </div>
          <span className="text-2xl font-bold text-teal-400 tabular-nums">{percentage}%</span>
        </div>

        {/* Progress Bar */}
        <div className="w-full h-2.5 bg-[#0a0c10] rounded-full overflow-hidden">
          <div
            className="h-full rounded-full bg-gradient-to-r from-teal-500 to-cyan-400 transition-all duration-500 ease-out"
            style={{ width: `${percentage}%` }}
          />
        </div>
      </div>

      {/* Logs Card */}
      <div className="bg-[#1a1d23] border border-[#2a2d35] rounded-xl overflow-hidden">
        <div className="px-5 py-3 border-b border-[#2a2d35] flex items-center justify-between">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Output Logs</h3>
          <span className="text-[10px] text-gray-600">{logs.length} entries</span>
        </div>
        <div className="bg-[#0a0c10] p-4 max-h-[400px] overflow-y-auto font-mono text-xs leading-relaxed">
          {logs.length === 0 ? (
            <div className="text-gray-600 text-center py-8">
              {status.running ? 'Waiting for output...' : 'No logs available'}
            </div>
          ) : (
            logs.map((log, i) => (
              <div key={i} className="flex gap-3 py-0.5">
                <span className="text-gray-600 shrink-0 select-none">{log.time}</span>
                <span className={
                  log.level === 'error' ? 'text-red-400' :
                  log.level === 'success' ? 'text-emerald-400' :
                  'text-gray-400'
                }>
                  {log.message}
                </span>
              </div>
            ))
          )}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Done state */}
      {!status.running && status.total > 0 && (
        <div className="flex justify-end">
          <button
            onClick={() => onNavigate('accounts')}
            className="px-4 py-2 text-xs font-semibold rounded-lg bg-gradient-to-r from-teal-500 to-cyan-500 text-black hover:from-teal-400 hover:to-cyan-400 transition-all shadow-lg shadow-teal-500/20"
          >
            View Accounts
          </button>
        </div>
      )}
    </div>
  )
}
