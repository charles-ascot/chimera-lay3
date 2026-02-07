/**
 * CHIMERA v2 Auto Betting Page
 * Engine controls, plugin manager, settings, activity log, bet list
 */

import { useEffect } from 'react'
import { useAutoStore } from '../store/auto'
import { useToastStore } from '../store/toast'
import { formatGBP, formatDateTime, pnlClass, zoneBgColor, formatOdds, formatRelative } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'

export default function AutoBettingPage() {
  const {
    status, plugins, autoBets, activityLog, loading,
    fetchStatus, fetchPlugins, fetchAutoBets, startEngine, stopEngine, togglePlugin,
  } = useAutoStore()
  const { addToast } = useToastStore()

  useEffect(() => {
    fetchStatus()
    fetchPlugins()
    fetchAutoBets()
    const interval = setInterval(() => {
      fetchStatus()
      fetchAutoBets()
    }, 5000)
    return () => clearInterval(interval)
  }, [fetchStatus, fetchPlugins, fetchAutoBets])

  const handleStart = async () => {
    const ok = await startEngine()
    addToast(ok ? 'Engine started' : 'Failed to start engine', ok ? 'success' : 'error')
  }

  const handleStop = async () => {
    const ok = await stopEngine()
    addToast(ok ? 'Engine stopped' : 'Failed to stop engine', ok ? 'info' : 'error')
  }

  const isRunning = status?.is_running || false

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Engine Control Bar */}
      <div className="glass-card rounded-xl p-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-3">
              Auto-Betting Engine
              {isRunning ? (
                <span className="badge-success flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-chimera-success animate-pulse" />
                  RUNNING
                </span>
              ) : (
                <span className="badge bg-chimera-bg-card text-chimera-muted border-chimera-border">
                  STOPPED
                </span>
              )}
            </h1>
            <p className="text-sm text-chimera-muted mt-1">
              {isRunning
                ? `Processing markets | ${status?.bets_placed_today || 0} bets today`
                : 'Click Start to begin auto-betting'
              }
            </p>
          </div>

          <button
            onClick={isRunning ? handleStop : handleStart}
            disabled={loading}
            className={`px-8 py-3 rounded-xl font-semibold text-lg transition-all ${
              isRunning
                ? 'bg-chimera-error/10 border-2 border-chimera-error/30 text-chimera-error hover:bg-chimera-error/20'
                : 'bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success hover:bg-chimera-success/20 glow-success'
            }`}
          >
            {loading ? <LoadingSpinner size="sm" /> : isRunning ? 'STOP' : 'START'}
          </button>
        </div>

        {/* Stats Bar */}
        {status && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mt-6">
            <MiniStat label="Today's P/L" value={formatGBP(status.daily_pnl, true)} className={pnlClass(status.daily_pnl)} />
            <MiniStat label="Bets Placed" value={String(status.bets_placed_today)} className="text-chimera-cyan" />
            <MiniStat label="Wins / Losses" value={`${status.wins_today} / ${status.losses_today}`} className="text-chimera-text" />
            <MiniStat label="Exposure" value={formatGBP(status.daily_exposure)} className="text-chimera-warning" />
            <MiniStat label="Markets Scanned" value={String(status.processed_markets_count)} className="text-chimera-muted" />
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Plugins + Settings */}
        <div className="space-y-4">
          {/* Plugins */}
          <div className="glass-card rounded-xl p-4">
            <h2 className="text-sm font-semibold text-chimera-text-secondary mb-3">Strategy Plugins</h2>
            {plugins.length === 0 ? (
              <p className="text-xs text-chimera-muted">No plugins loaded</p>
            ) : (
              <div className="space-y-2">
                {plugins.map((p) => (
                  <div key={p.id} className="glass-card-hover rounded-lg p-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="text-sm font-medium">{p.name}</h3>
                        <p className="text-xs text-chimera-muted">v{p.version} by {p.author}</p>
                      </div>
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input
                          type="checkbox"
                          checked={!!p.enabled}
                          onChange={(e) => togglePlugin(p.id, e.target.checked)}
                          className="sr-only peer"
                        />
                        <div className="w-9 h-5 bg-chimera-border rounded-full peer peer-checked:bg-chimera-success/50 after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:after:translate-x-full" />
                      </label>
                    </div>
                    <p className="text-xs text-chimera-muted mt-1">{p.description}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Settings Summary */}
          {status?.settings && (
            <div className="glass-card rounded-xl p-4">
              <h2 className="text-sm font-semibold text-chimera-text-secondary mb-3">Risk Limits</h2>
              <div className="space-y-2 text-xs">
                <SettingRow label="Max Liability / Bet" value={formatGBP(status.settings.max_liability_per_bet || 9)} />
                <SettingRow label="Max Daily Exposure" value={formatGBP(status.settings.max_daily_exposure || 75)} />
                <SettingRow label="Daily Stop-Loss" value={formatGBP(Math.abs(status.settings.daily_stop_loss || 25))} />
                <SettingRow label="Max Concurrent Bets" value={String(status.settings.max_concurrent_bets || 10)} />
                <SettingRow label="Max Bets / Race" value={String(status.settings.max_bets_per_race || 1)} />
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Activity Log + Bet List */}
        <div className="lg:col-span-2 space-y-4">
          {/* Activity Log */}
          <div className="glass-card rounded-xl p-4">
            <h2 className="text-sm font-semibold text-chimera-text-secondary mb-3">Activity Log</h2>
            <div className="max-h-48 overflow-y-auto space-y-1">
              {activityLog.length === 0 ? (
                <p className="text-xs text-chimera-muted py-4 text-center">No activity yet</p>
              ) : (
                activityLog.map((entry, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs py-1 border-b border-chimera-border/30 last:border-0">
                    <span className="text-chimera-muted flex-shrink-0">
                      {formatRelative(entry.timestamp)}
                    </span>
                    <span className={
                      entry.type === 'bet_placed' ? 'text-chimera-success' :
                      entry.type === 'bet_failed' ? 'text-chimera-error' :
                      'text-chimera-text'
                    }>
                      {entry.data?.runner_name
                        ? `${entry.data.venue} | ${entry.data.runner_name} @ ${formatOdds(entry.data.odds)} (${entry.data.zone})`
                        : entry.data?.reason || JSON.stringify(entry.data).slice(0, 80)
                      }
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Auto Bet List */}
          <div className="glass-card rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-chimera-border">
              <h2 className="text-sm font-semibold text-chimera-text-secondary">
                Auto Bets ({autoBets.length})
              </h2>
            </div>
            <div className="overflow-x-auto max-h-96">
              {autoBets.length === 0 ? (
                <p className="text-xs text-chimera-muted py-8 text-center">No auto bets placed yet</p>
              ) : (
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-chimera-muted border-b border-chimera-border">
                      <th className="px-3 py-2 text-left">Time</th>
                      <th className="px-3 py-2 text-left">Venue</th>
                      <th className="px-3 py-2 text-left">Runner</th>
                      <th className="px-3 py-2 text-right">Odds</th>
                      <th className="px-3 py-2 text-right">Stake</th>
                      <th className="px-3 py-2 text-right">Liability</th>
                      <th className="px-3 py-2 text-center">Zone</th>
                      <th className="px-3 py-2 text-center">Status</th>
                      <th className="px-3 py-2 text-right">P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {autoBets.map((bet) => (
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
                          <StatusBadge status={bet.result || bet.status} />
                        </td>
                        <td className={`px-3 py-2 text-right font-mono ${pnlClass(bet.profit_loss)}`}>
                          {formatGBP(bet.profit_loss, true)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

function MiniStat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="text-center py-2">
      <div className="text-[10px] text-chimera-muted uppercase tracking-wider">{label}</div>
      <div className={`text-lg font-semibold font-mono ${className}`}>{value}</div>
    </div>
  )
}

function SettingRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-chimera-muted">{label}</span>
      <span className="font-mono text-chimera-text">{value}</span>
    </div>
  )
}
