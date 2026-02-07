/**
 * CHIMERA v2 Account Page
 * Balance, exposure, daily P/L, statement
 */

import { useEffect, useState } from 'react'
import { accountApi } from '../lib/api'
import { formatGBP, pnlClass, formatPercent, formatDateTime } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'
import type { AccountFunds } from '../types/betfair'
import type { DailyStats } from '../types/app'

export default function AccountPage() {
  const [balance, setBalance] = useState<AccountFunds | null>(null)
  const [todayStats, setTodayStats] = useState<DailyStats | null>(null)
  const [statement, setStatement] = useState<any[]>([])
  const [showStatement, setShowStatement] = useState(false)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  async function fetchData() {
    try {
      const { data } = await accountApi.getBalance()
      setBalance(data.balance)
      setTodayStats(data.today)
    } catch {
      // Ignore
    } finally {
      setLoading(false)
    }
  }

  async function fetchStatement() {
    try {
      const { data } = await accountApi.getStatement({ record_count: 50 })
      setStatement(data.accountStatement || [])
      setShowStatement(true)
    } catch {
      // Ignore
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <LoadingSpinner size="lg" />
      </div>
    )
  }

  const winRate = todayStats && todayStats.total_bets > 0
    ? (todayStats.wins / (todayStats.wins + todayStats.losses || 1)) * 100
    : 0

  return (
    <div className="max-w-6xl mx-auto space-y-6 animate-fade-in">
      <h1 className="text-xl font-semibold">Account Overview</h1>

      {/* Balance Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          label="Available"
          value={formatGBP(balance?.availableToBetBalance || 0)}
          className="text-chimera-success"
        />
        <StatCard
          label="Exposure"
          value={formatGBP(Math.abs(balance?.exposure || 0))}
          className="text-chimera-warning"
        />
        <StatCard
          label="Today's P/L"
          value={formatGBP(todayStats?.profit_loss || 0, true)}
          className={pnlClass(todayStats?.profit_loss || 0)}
        />
        <StatCard
          label="Today's Bets"
          value={String(todayStats?.total_bets || 0)}
          className="text-chimera-cyan"
        />
      </div>

      {/* Detailed Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <StatCard label="Wins" value={String(todayStats?.wins || 0)} className="text-chimera-success" />
        <StatCard label="Losses" value={String(todayStats?.losses || 0)} className="text-chimera-error" />
        <StatCard label="Pending" value={String(todayStats?.pending || 0)} className="text-chimera-warning" />
        <StatCard label="Win Rate" value={formatPercent(winRate)} className="text-chimera-cyan" />
        <StatCard
          label="Staked"
          value={formatGBP(todayStats?.total_staked || 0)}
          className="text-chimera-text-secondary"
        />
      </div>

      {/* Exposure Bar */}
      {balance && (
        <div className="glass-card p-4 rounded-xl">
          <div className="flex items-center justify-between mb-2">
            <span className="stat-label">Exposure Utilisation</span>
            <span className="text-sm text-chimera-muted">
              {formatGBP(Math.abs(balance.exposure))} / {formatGBP(balance.exposureLimit || 1000)}
            </span>
          </div>
          <div className="w-full h-2 bg-chimera-bg rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-chimera-success to-chimera-warning rounded-full transition-all duration-500"
              style={{
                width: `${Math.min(
                  (Math.abs(balance.exposure) / (balance.exposureLimit || 1000)) * 100,
                  100
                )}%`,
              }}
            />
          </div>
        </div>
      )}

      {/* Statement Toggle */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">Account Statement</h2>
        <button onClick={fetchStatement} className="btn-secondary text-sm">
          {showStatement ? 'Refresh' : 'View Statement'}
        </button>
      </div>

      {/* Statement Table */}
      {showStatement && statement.length > 0 && (
        <div className="glass-card rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-chimera-border text-chimera-muted text-left">
                  <th className="px-4 py-3">Date</th>
                  <th className="px-4 py-3">Ref</th>
                  <th className="px-4 py-3 text-right">Amount</th>
                  <th className="px-4 py-3 text-right">Balance</th>
                </tr>
              </thead>
              <tbody>
                {statement.map((item: any, i: number) => (
                  <tr key={i} className="border-b border-chimera-border/50 hover:bg-chimera-bg-card-hover">
                    <td className="px-4 py-2 text-chimera-text-secondary">
                      {item.itemDate ? formatDateTime(item.itemDate) : '-'}
                    </td>
                    <td className="px-4 py-2 text-chimera-text">
                      {item.refId || item.legacyData?.marketName || '-'}
                    </td>
                    <td className={`px-4 py-2 text-right font-mono ${pnlClass(item.amount || 0)}`}>
                      {formatGBP(item.amount || 0, true)}
                    </td>
                    <td className="px-4 py-2 text-right font-mono text-chimera-text">
                      {formatGBP(item.balance || 0)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="stat-card">
      <div className="stat-label">{label}</div>
      <div className={`stat-value ${className}`}>{value}</div>
    </div>
  )
}
