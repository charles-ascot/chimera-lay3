/**
 * CHIMERA v2 History Page
 * Date filters, stats, bet table, CSV export, built-in analysis, AI analysis
 */

import { useEffect, useState } from 'react'
import { historyApi } from '../lib/api'
import { formatGBP, formatDateTime, formatOdds, formatPercent, pnlClass, zoneBgColor } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'
import type { Bet, DailyStats } from '../types/app'

const PERIODS = [
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'week', label: 'This Week' },
  { value: 'month', label: 'This Month' },
  { value: 'all', label: 'All Time' },
]

export default function HistoryPage() {
  const [period, setPeriod] = useState('today')
  const [bets, setBets] = useState<Bet[]>([])
  const [stats, setStats] = useState<DailyStats | null>(null)
  const [analysis, setAnalysis] = useState<any>(null)
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null)
  const [aiLoading, setAiLoading] = useState(false)
  const [loading, setLoading] = useState(true)
  const [showAnalysis, setShowAnalysis] = useState(false)

  useEffect(() => {
    fetchData()
  }, [period])

  async function fetchData() {
    setLoading(true)
    try {
      const [betsRes, statsRes] = await Promise.all([
        historyApi.getBets({ period }),
        historyApi.getStats({ period }),
      ])
      setBets(betsRes.data.bets || [])
      setStats(statsRes.data)
    } catch {
      // Ignore
    } finally {
      setLoading(false)
    }
  }

  async function fetchAnalysis() {
    try {
      const { data } = await historyApi.getAnalysis({ period })
      setAnalysis(data)
      setShowAnalysis(true)
    } catch {
      // Ignore
    }
  }

  async function fetchAiAnalysis() {
    setAiLoading(true)
    try {
      const { data } = await historyApi.getAiAnalysis({ period })
      setAiAnalysis(data.analysis)
    } catch (err: any) {
      setAiAnalysis(`Error: ${err.response?.data?.detail || err.message}`)
    } finally {
      setAiLoading(false)
    }
  }

  async function handleExport() {
    try {
      const response = await historyApi.exportCsv({ period })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = `chimera_bets_${period}.csv`
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      // Ignore
    }
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-xl font-semibold">Bet History</h1>
        <div className="flex items-center gap-2">
          <button onClick={handleExport} className="btn-secondary text-xs">
            Export CSV
          </button>
          <button onClick={fetchAnalysis} className="btn-secondary text-xs">
            Stats
          </button>
          <button
            onClick={fetchAiAnalysis}
            disabled={aiLoading}
            className="btn-primary text-xs"
          >
            {aiLoading ? <LoadingSpinner size="sm" /> : 'Ask AI'}
          </button>
        </div>
      </div>

      {/* Period Filter */}
      <div className="flex gap-2 flex-wrap">
        {PERIODS.map((p) => (
          <button
            key={p.value}
            onClick={() => setPeriod(p.value)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              period === p.value
                ? 'bg-chimera-accent/10 text-chimera-accent border border-chimera-accent/20'
                : 'bg-chimera-bg-card text-chimera-muted border border-chimera-border hover:text-chimera-text'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          <StatCard label="Total Bets" value={String(stats.total_bets)} className="text-chimera-text" />
          <StatCard label="Staked" value={formatGBP(stats.total_staked)} className="text-chimera-text-secondary" />
          <StatCard label="P/L" value={formatGBP(stats.profit_loss, true)} className={pnlClass(stats.profit_loss)} />
          <StatCard label="Win Rate" value={formatPercent(stats.win_rate || 0)} className="text-chimera-cyan" />
          <StatCard label="ROI" value={formatPercent(stats.roi || 0)} className={pnlClass(stats.roi || 0)} />
        </div>
      )}

      {/* AI Analysis */}
      {aiAnalysis && (
        <div className="glass-card rounded-xl p-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold gradient-text">AI Analysis</h2>
            <button onClick={() => setAiAnalysis(null)} className="text-xs text-chimera-muted hover:text-chimera-error">
              Close
            </button>
          </div>
          <div className="prose prose-sm prose-invert max-w-none text-chimera-text-secondary whitespace-pre-wrap text-sm">
            {aiAnalysis}
          </div>
        </div>
      )}

      {/* Built-in Analysis */}
      {showAnalysis && analysis && (
        <div className="glass-card rounded-xl p-4">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-chimera-text-secondary">Performance Analysis</h2>
            <button onClick={() => setShowAnalysis(false)} className="text-xs text-chimera-muted hover:text-chimera-error">
              Close
            </button>
          </div>

          {/* Zone Performance */}
          {analysis.by_zone && (
            <div className="mb-4">
              <h3 className="text-xs font-semibold text-chimera-muted mb-2">By Zone</h3>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {Object.entries(analysis.by_zone as Record<string, any>).map(([zone, data]: [string, any]) => (
                  <div key={zone} className={`rounded-lg p-3 border ${zoneBgColor(zone)}`}>
                    <div className="font-semibold">{zone}</div>
                    <div className="text-xs mt-1 space-y-0.5">
                      <div>Bets: {data.bets} | {data.wins}W / {data.losses}L</div>
                      <div>Win Rate: {formatPercent(data.win_rate)}</div>
                      <div>P/L: {formatGBP(data.pnl, true)} | ROI: {formatPercent(data.roi)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Streaks */}
          {analysis.streaks && (
            <div className="flex gap-4 text-xs">
              <div>Max Win Streak: <span className="text-chimera-success font-mono">{analysis.streaks.max_winning_streak}</span></div>
              <div>Max Loss Streak: <span className="text-chimera-error font-mono">{analysis.streaks.max_losing_streak}</span></div>
            </div>
          )}
        </div>
      )}

      {/* Bet Table */}
      <div className="glass-card rounded-xl overflow-hidden">
        {loading ? (
          <LoadingSpinner size="md" className="py-12" />
        ) : bets.length === 0 ? (
          <p className="text-center text-chimera-muted py-12 text-sm">No bets for this period</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-chimera-muted border-b border-chimera-border">
                  <th className="px-3 py-2 text-left">Date</th>
                  <th className="px-3 py-2 text-left">Venue</th>
                  <th className="px-3 py-2 text-left">Runner</th>
                  <th className="px-3 py-2 text-right">Odds</th>
                  <th className="px-3 py-2 text-right">Stake</th>
                  <th className="px-3 py-2 text-right">Liability</th>
                  <th className="px-3 py-2 text-center">Zone</th>
                  <th className="px-3 py-2 text-center">Source</th>
                  <th className="px-3 py-2 text-center">Result</th>
                  <th className="px-3 py-2 text-right">P/L</th>
                </tr>
              </thead>
              <tbody>
                {bets.map((bet) => (
                  <tr key={bet.id} className="border-b border-chimera-border/30 hover:bg-chimera-bg-card-hover">
                    <td className="px-3 py-2 text-chimera-muted">{formatDateTime(bet.placed_at)}</td>
                    <td className="px-3 py-2">{bet.venue || '-'}</td>
                    <td className="px-3 py-2 font-medium">{bet.runner_name || '-'}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatOdds(bet.odds)}</td>
                    <td className="px-3 py-2 text-right font-mono">{formatGBP(bet.stake)}</td>
                    <td className="px-3 py-2 text-right font-mono text-chimera-error">{formatGBP(bet.liability)}</td>
                    <td className="px-3 py-2 text-center">
                      {bet.zone && <span className={`badge ${zoneBgColor(bet.zone)}`}>{bet.zone}</span>}
                    </td>
                    <td className="px-3 py-2 text-center">
                      <span className={`text-[10px] ${bet.source === 'AUTO' ? 'text-chimera-cyan' : 'text-chimera-muted'}`}>
                        {bet.source}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-center">
                      <StatusBadge status={bet.result || bet.status} />
                    </td>
                    <td className={`px-3 py-2 text-right font-mono ${pnlClass(bet.profit_loss)}`}>
                      {formatGBP(bet.profit_loss, true)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function StatCard({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`text-xl font-semibold font-mono ${className}`}>{value}</div>
    </div>
  )
}
