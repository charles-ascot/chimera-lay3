/**
 * CHIMERA v2 Auto Betting Page
 * Engine controls with STAGING / LIVE modes, plugin manager, settings, activity log, bet list
 *
 * Modes:
 *   STOPPED  → Engine off
 *   STAGING  → Engine evaluates everything, shows what it WOULD bet, but no real money
 *   LIVE     → Real bets placed via Betfair API
 *
 * User can:
 *   - Start in STAGING (default) or LIVE
 *   - Switch from STAGING → LIVE ("Go Live") without restarting
 *   - Switch from LIVE → STAGING without restarting
 *   - Stop from any mode
 */

import { useEffect, useState } from 'react'
import { useAutoStore } from '../store/auto'
import { useToastStore } from '../store/toast'
import { formatGBP, formatDateTime, pnlClass, zoneBgColor, formatOdds, formatRelative } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'

export default function AutoBettingPage() {
  const {
    status, plugins, autoBets, activityLog, loading,
    fetchStatus, fetchPlugins, fetchAutoBets,
    startEngine, stopEngine, goLive, goStaging, togglePlugin,
  } = useAutoStore()
  const { addToast } = useToastStore()
  const [showLiveConfirm, setShowLiveConfirm] = useState(false)
  const [skipStaging, setSkipStaging] = useState(false)

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

  const isRunning = status?.is_running || false
  const mode = status?.mode || 'STOPPED'

  const handleStart = async () => {
    const startMode = skipStaging ? 'LIVE' : 'STAGING'
    if (startMode === 'LIVE') {
      setShowLiveConfirm(true)
      return
    }
    const ok = await startEngine('STAGING')
    addToast(ok ? 'Engine started in STAGING mode' : 'Failed to start engine', ok ? 'success' : 'error')
  }

  const handleStartLiveConfirmed = async () => {
    setShowLiveConfirm(false)
    const ok = await startEngine('LIVE')
    addToast(ok ? 'Engine started in LIVE mode — real bets active!' : 'Failed to start engine', ok ? 'success' : 'error')
  }

  const handleStop = async () => {
    const ok = await stopEngine()
    addToast(ok ? 'Engine stopped' : 'Failed to stop engine', ok ? 'info' : 'error')
  }

  const handleGoLive = async () => {
    setShowLiveConfirm(true)
  }

  const handleGoLiveConfirmed = async () => {
    setShowLiveConfirm(false)
    const ok = await goLive()
    addToast(
      ok ? 'LIVE MODE — Real bets are now active!' : 'Failed to switch to live',
      ok ? 'success' : 'error'
    )
  }

  const handleGoStaging = async () => {
    const ok = await goStaging()
    addToast(
      ok ? 'Switched to STAGING — no real bets' : 'Failed to switch to staging',
      ok ? 'info' : 'error'
    )
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Engine Control Bar */}
      <div className="glass-card rounded-xl p-6">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <h1 className="text-xl font-semibold flex items-center gap-3">
              Auto-Betting Engine
              <ModeBadge mode={mode} />
            </h1>
            <p className="text-sm text-chimera-muted mt-1">
              {mode === 'STAGING' && `Simulating bets | ${status?.bets_placed_today || 0} evaluated today`}
              {mode === 'LIVE' && `LIVE — Real bets active | ${status?.bets_placed_today || 0} bets today`}
              {mode === 'STOPPED' && 'Click Stage to begin simulated evaluation'}
            </p>
          </div>

          {/* Control Buttons */}
          <div className="flex items-center gap-3">
            {!isRunning ? (
              /* Stopped — show Start buttons */
              <>
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className="px-6 py-3 rounded-xl font-semibold transition-all
                    bg-chimera-cyan/10 border-2 border-chimera-cyan/30 text-chimera-cyan
                    hover:bg-chimera-cyan/20"
                >
                  {loading ? <LoadingSpinner size="sm" /> : skipStaging ? 'START LIVE' : 'STAGE'}
                </button>
                <label className="flex items-center gap-2 text-xs text-chimera-muted cursor-pointer">
                  <input
                    type="checkbox"
                    checked={skipStaging}
                    onChange={(e) => setSkipStaging(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-chimera-border bg-chimera-bg-card accent-chimera-accent"
                  />
                  Skip staging
                </label>
              </>
            ) : mode === 'STAGING' ? (
              /* Staging — show Go Live + Stop */
              <>
                <button
                  onClick={handleGoLive}
                  disabled={loading}
                  className="px-6 py-3 rounded-xl font-semibold transition-all
                    bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success
                    hover:bg-chimera-success/20 glow-success"
                >
                  {loading ? <LoadingSpinner size="sm" /> : 'GO LIVE'}
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="px-5 py-3 rounded-xl font-medium transition-all
                    bg-chimera-bg-card border border-chimera-border text-chimera-muted
                    hover:text-chimera-error hover:border-chimera-error/30"
                >
                  STOP
                </button>
              </>
            ) : (
              /* Live — show Go Staging + Stop */
              <>
                <button
                  onClick={handleGoStaging}
                  disabled={loading}
                  className="px-5 py-3 rounded-xl font-medium transition-all
                    bg-chimera-cyan/10 border border-chimera-cyan/30 text-chimera-cyan
                    hover:bg-chimera-cyan/20"
                >
                  STAGING
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="px-6 py-3 rounded-xl font-semibold transition-all
                    bg-chimera-error/10 border-2 border-chimera-error/30 text-chimera-error
                    hover:bg-chimera-error/20"
                >
                  STOP
                </button>
              </>
            )}
          </div>
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

      {/* Live Confirmation Modal */}
      {showLiveConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="glass-card rounded-2xl p-8 max-w-md mx-4 border border-chimera-error/30">
            <div className="text-center">
              <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-chimera-error/10 flex items-center justify-center">
                <svg className="w-7 h-7 text-chimera-error" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126ZM12 15.75h.007v.008H12v-.008Z" />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-chimera-text mb-2">Go Live?</h2>
              <p className="text-sm text-chimera-text-secondary mb-6">
                This will place <strong>real bets with real money</strong> on Betfair Exchange.
                Make sure you're happy with the strategy and settings.
              </p>
              <div className="flex gap-3 justify-center">
                <button
                  onClick={() => setShowLiveConfirm(false)}
                  className="btn-secondary px-6"
                >
                  Cancel
                </button>
                <button
                  onClick={skipStaging && !isRunning ? handleStartLiveConfirmed : handleGoLiveConfirmed}
                  className="px-6 py-2.5 rounded-lg font-semibold text-sm
                    bg-chimera-error/10 border-2 border-chimera-error/40 text-chimera-error
                    hover:bg-chimera-error/20 transition-all"
                >
                  Confirm — Go Live
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

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
                      entry.type === 'bet_staged' ? 'text-chimera-cyan' :
                      entry.type === 'bet_failed' ? 'text-chimera-error' :
                      entry.type === 'mode_change' ? 'text-chimera-warning font-semibold' :
                      'text-chimera-text'
                    }>
                      {entry.type === 'mode_change'
                        ? `⚡ ${entry.data?.message || `Switched to ${entry.data?.mode}`}`
                        : entry.data?.runner_name
                          ? `${entry.type === 'bet_staged' ? '🔍 ' : ''}${entry.data.venue} | ${entry.data.runner_name} @ ${formatOdds(entry.data.odds)} (${entry.data.zone})`
                          : entry.data?.reason || entry.data?.message || JSON.stringify(entry.data).slice(0, 80)
                      }
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Bet List */}
          <div className="glass-card rounded-xl overflow-hidden">
            <div className="px-4 py-3 border-b border-chimera-border">
              <h2 className="text-sm font-semibold text-chimera-text-secondary">
                Bets ({autoBets.length})
              </h2>
            </div>
            <div className="overflow-x-auto max-h-96">
              {autoBets.length === 0 ? (
                <p className="text-xs text-chimera-muted py-8 text-center">No bets yet — start the engine to begin</p>
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
                      <th className="px-3 py-2 text-center">Type</th>
                      <th className="px-3 py-2 text-center">Status</th>
                      <th className="px-3 py-2 text-right">P/L</th>
                    </tr>
                  </thead>
                  <tbody>
                    {autoBets.map((bet) => (
                      <tr
                        key={bet.id}
                        className={`border-b border-chimera-border/30 hover:bg-chimera-bg-card-hover ${
                          bet.source === 'STAGED' ? 'opacity-75' : ''
                        }`}
                      >
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
                          {bet.source === 'STAGED' ? (
                            <span className="badge bg-chimera-cyan/10 text-chimera-cyan border-chimera-cyan/20">
                              STAGED
                            </span>
                          ) : (
                            <span className="badge bg-chimera-success/10 text-chimera-success border-chimera-success/20">
                              LIVE
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-center">
                          <StatusBadge status={bet.result || bet.status} />
                        </td>
                        <td className={`px-3 py-2 text-right font-mono ${
                          bet.source === 'STAGED' ? 'text-chimera-muted' : pnlClass(bet.profit_loss)
                        }`}>
                          {bet.source === 'STAGED' ? '-' : formatGBP(bet.profit_loss, true)}
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

// ── Mode Badge ──

function ModeBadge({ mode }: { mode: string }) {
  if (mode === 'LIVE') {
    return (
      <span className="badge bg-chimera-error/10 text-chimera-error border-chimera-error/20 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-chimera-error animate-pulse" />
        LIVE
      </span>
    )
  }
  if (mode === 'STAGING') {
    return (
      <span className="badge bg-chimera-cyan/10 text-chimera-cyan border-chimera-cyan/20 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-chimera-cyan animate-pulse" />
        STAGING
      </span>
    )
  }
  return (
    <span className="badge bg-chimera-bg-card text-chimera-muted border-chimera-border">
      STOPPED
    </span>
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
