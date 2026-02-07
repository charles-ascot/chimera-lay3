/**
 * CHIMERA v2 Auto Betting Page
 * Engine controls with STAGING / LIVE modes, plugin manager, settings, activity log, bet list
 *
 * Modes:
 *   STOPPED  -> Engine off
 *   STAGING  -> Engine evaluates everything, shows what it WOULD bet, but no real money
 *   LIVE     -> Real bets placed via Betfair API
 *   PAUSED   -> Engine loop alive but skips scanning. Resume instantly.
 *
 * User can:
 *   - Choose mode (Staged or Live) before starting
 *   - Start / Pause / Stop the engine
 *   - Switch from STAGING -> LIVE ("Go Live") without restarting
 *   - Switch from LIVE -> STAGING without restarting
 *   - Manage plugins (enable/disable, reorder)
 *   - Edit auto-betting settings (risk limits)
 */

import { useEffect, useState } from 'react'
import { useAutoStore } from '../store/auto'
import { useToastStore } from '../store/toast'
import { formatGBP, formatDateTime, pnlClass, zoneBgColor, formatOdds, formatRelative } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'
import type { AutoBettingSettings } from '../types/app'

export default function AutoBettingPage() {
  const {
    status, plugins, autoBets, activityLog, loading,
    fetchStatus, fetchPlugins, fetchAutoBets,
    startEngine, stopEngine, goLive, goStaging, pauseEngine, resumeEngine, togglePlugin,
    updateSettings,
  } = useAutoStore()
  const { addToast } = useToastStore()
  const [showLiveConfirm, setShowLiveConfirm] = useState(false)
  const [selectedMode, setSelectedMode] = useState<'STAGING' | 'LIVE'>('STAGING')
  const [showSettings, setShowSettings] = useState(false)
  const [showPlugins, setShowPlugins] = useState(false)

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
    if (selectedMode === 'LIVE') {
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

  const handlePause = async () => {
    const ok = await pauseEngine()
    addToast(ok ? 'Engine paused' : 'Failed to pause', ok ? 'info' : 'error')
  }

  const handleResume = async () => {
    const ok = await resumeEngine()
    addToast(ok ? 'Engine resumed' : 'Failed to resume', ok ? 'success' : 'error')
  }

  return (
    <div className="max-w-7xl mx-auto space-y-6 animate-fade-in">
      {/* Engine Control Bar — compact & sticky */}
      <div className="glass-card rounded-xl px-4 py-3 sticky top-0 z-40">
        {/* Row 1: Title + Controls */}
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-base font-semibold flex items-center gap-2 flex-shrink-0">
            Auto-Betting Engine
            <ModeBadge mode={mode} />
          </h1>

          <div className="flex items-center gap-2">
            {/* Quick Action Buttons */}
            <button
              onClick={() => setShowPlugins(!showPlugins)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                showPlugins
                  ? 'bg-chimera-accent/10 border border-chimera-accent/30 text-chimera-accent'
                  : 'bg-chimera-bg-card border border-chimera-border text-chimera-text-secondary hover:text-chimera-text'
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 6.087c0-.355.186-.676.401-.959.221-.29.349-.634.349-1.003 0-1.036-1.007-1.875-2.25-1.875s-2.25.84-2.25 1.875c0 .369.128.713.349 1.003.215.283.401.604.401.959v0a.64.64 0 0 1-.657.643 48.39 48.39 0 0 1-4.163-.3c.186 1.613.293 3.25.315 4.907a.656.656 0 0 1-.658.663v0c-.355 0-.676-.186-.959-.401a1.647 1.647 0 0 0-1.003-.349c-1.036 0-1.875 1.007-1.875 2.25s.84 2.25 1.875 2.25c.369 0 .713-.128 1.003-.349.283-.215.604-.401.959-.401v0c.31 0 .555.26.532.57a48.039 48.039 0 0 1-.642 5.056c1.518.19 3.058.309 4.616.354a.64.64 0 0 0 .657-.643v0c0-.355-.186-.676-.401-.959a1.647 1.647 0 0 1-.349-1.003c0-1.035 1.008-1.875 2.25-1.875 1.243 0 2.25.84 2.25 1.875 0 .369-.128.713-.349 1.003-.215.283-.4.604-.4.959v0c0 .333.277.599.61.58a48.1 48.1 0 0 0 5.427-.63 48.05 48.05 0 0 0 .582-4.717.532.532 0 0 0-.533-.57v0c-.355 0-.676.186-.959.401-.29.221-.634.349-1.003.349-1.035 0-1.875-1.007-1.875-2.25s.84-2.25 1.875-2.25c.37 0 .713.128 1.003.349.283.215.604.401.959.401v0a.656.656 0 0 0 .658-.663 48.422 48.422 0 0 0-.37-5.36c-1.886.342-3.81.574-5.766.689a.578.578 0 0 1-.61-.58v0Z" />
              </svg>
              Plugins
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 ${
                showSettings
                  ? 'bg-chimera-accent/10 border border-chimera-accent/30 text-chimera-accent'
                  : 'bg-chimera-bg-card border border-chimera-border text-chimera-text-secondary hover:text-chimera-text'
              }`}
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
              </svg>
              Settings
            </button>

            <div className="w-px h-6 bg-chimera-border/50 mx-1" />

            {/* Engine Control Buttons */}
            {!isRunning ? (
              <>
                <div className="flex rounded-lg overflow-hidden border border-chimera-border">
                  <button
                    onClick={() => setSelectedMode('STAGING')}
                    className={`px-3 py-1.5 text-xs font-medium transition-all ${
                      selectedMode === 'STAGING'
                        ? 'bg-chimera-cyan/20 text-chimera-cyan border-r border-chimera-cyan/30'
                        : 'bg-chimera-bg-card text-chimera-muted border-r border-chimera-border hover:bg-chimera-bg-card-hover'
                    }`}
                  >
                    Staged
                  </button>
                  <button
                    onClick={() => setSelectedMode('LIVE')}
                    className={`px-3 py-1.5 text-xs font-medium transition-all ${
                      selectedMode === 'LIVE'
                        ? 'bg-chimera-error/20 text-chimera-error'
                        : 'bg-chimera-bg-card text-chimera-muted hover:bg-chimera-bg-card-hover'
                    }`}
                  >
                    Live
                  </button>
                </div>
                <button
                  onClick={handleStart}
                  disabled={loading}
                  className={`px-5 py-1.5 rounded-lg text-xs font-bold transition-all ${
                    selectedMode === 'LIVE'
                      ? 'bg-chimera-error/10 border-2 border-chimera-error/30 text-chimera-error hover:bg-chimera-error/20'
                      : 'bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success hover:bg-chimera-success/20'
                  }`}
                >
                  {loading ? <LoadingSpinner size="sm" /> : 'START'}
                </button>
              </>
            ) : mode === 'PAUSED' ? (
              <>
                <button
                  onClick={handleResume}
                  disabled={loading}
                  className="px-5 py-1.5 rounded-lg text-xs font-bold transition-all
                    bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success
                    hover:bg-chimera-success/20"
                >
                  {loading ? <LoadingSpinner size="sm" /> : 'RESUME'}
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                    bg-chimera-bg-card border border-chimera-border text-chimera-muted
                    hover:text-chimera-error hover:border-chimera-error/30"
                >
                  STOP
                </button>
              </>
            ) : mode === 'STAGING' ? (
              <>
                <button
                  onClick={handleGoLive}
                  disabled={loading}
                  className="px-5 py-1.5 rounded-lg text-xs font-bold transition-all
                    bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success
                    hover:bg-chimera-success/20 glow-success"
                >
                  {loading ? <LoadingSpinner size="sm" /> : 'GO LIVE'}
                </button>
                <button
                  onClick={handlePause}
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                    bg-chimera-warning/10 border border-chimera-warning/30 text-chimera-warning
                    hover:bg-chimera-warning/20"
                >
                  PAUSE
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                    bg-chimera-bg-card border border-chimera-border text-chimera-muted
                    hover:text-chimera-error hover:border-chimera-error/30"
                >
                  STOP
                </button>
              </>
            ) : (
              <>
                <button
                  onClick={handleGoStaging}
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                    bg-chimera-cyan/10 border border-chimera-cyan/30 text-chimera-cyan
                    hover:bg-chimera-cyan/20"
                >
                  STAGING
                </button>
                <button
                  onClick={handlePause}
                  disabled={loading}
                  className="px-4 py-1.5 rounded-lg text-xs font-medium transition-all
                    bg-chimera-warning/10 border border-chimera-warning/30 text-chimera-warning
                    hover:bg-chimera-warning/20"
                >
                  PAUSE
                </button>
                <button
                  onClick={handleStop}
                  disabled={loading}
                  className="px-5 py-1.5 rounded-lg text-xs font-bold transition-all
                    bg-chimera-error/10 border-2 border-chimera-error/30 text-chimera-error
                    hover:bg-chimera-error/20"
                >
                  STOP
                </button>
              </>
            )}
          </div>
        </div>

        {/* Row 2: Compact Stats */}
        {status && (
          <div className="flex items-center gap-4 mt-2 pt-2 border-t border-chimera-border/20 text-xs flex-wrap">
            <InlineStat label="P/L" value={formatGBP(status.daily_pnl, true)} className={pnlClass(status.daily_pnl)} />
            <InlineStat label="Bets" value={String(status.bets_placed_today)} className="text-chimera-cyan" />
            <InlineStat label="W/L" value={`${status.wins_today}/${status.losses_today}`} className="text-chimera-text" />
            <InlineStat label="Exposure" value={formatGBP(status.daily_exposure)} className="text-chimera-warning" />
            <InlineStat label="Scanned" value={String(status.processed_markets_count)} className="text-chimera-muted" />
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
                  onClick={!isRunning ? handleStartLiveConfirmed : handleGoLiveConfirmed}
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

      {/* Plugin Manager Panel */}
      {showPlugins && (
        <PluginManagerPanel
          plugins={plugins}
          onToggle={togglePlugin}
          onClose={() => setShowPlugins(false)}
        />
      )}

      {/* Settings Editor Panel */}
      {showSettings && status?.settings && (
        <SettingsEditorPanel
          settings={status.settings}
          onSave={async (s) => {
            await updateSettings(s)
            addToast('Settings saved', 'success')
          }}
          onClose={() => setShowSettings(false)}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Quick Stats + Risk Limits */}
        <div className="space-y-4">
          {/* Plugins Summary */}
          <div className="glass-card rounded-xl p-4">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-chimera-text-secondary">Active Plugins</h2>
              <button
                onClick={() => setShowPlugins(true)}
                className="text-xs text-chimera-accent hover:text-chimera-accent/80 transition-colors"
              >
                Manage
              </button>
            </div>
            {plugins.length === 0 ? (
              <p className="text-xs text-chimera-muted">No plugins loaded</p>
            ) : (
              <div className="space-y-2">
                {plugins.map((p) => (
                  <div key={p.id} className="flex items-center justify-between py-1.5">
                    <div className="flex items-center gap-2">
                      <span className={`w-2 h-2 rounded-full ${p.enabled ? 'bg-chimera-success' : 'bg-chimera-muted'}`} />
                      <span className={`text-sm ${p.enabled ? 'text-chimera-text' : 'text-chimera-muted'}`}>{p.name}</span>
                    </div>
                    <span className="text-xs text-chimera-muted">v{p.version}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Settings Summary */}
          {status?.settings && (
            <div className="glass-card rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold text-chimera-text-secondary">Risk Limits</h2>
                <button
                  onClick={() => setShowSettings(true)}
                  className="text-xs text-chimera-accent hover:text-chimera-accent/80 transition-colors"
                >
                  Edit
                </button>
              </div>
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
                        ? `${entry.data?.message || `Switched to ${entry.data?.mode}`}`
                        : entry.data?.runner_name
                          ? `${entry.type === 'bet_staged' ? '[SIM] ' : ''}${entry.data.venue} | ${entry.data.runner_name} @ ${formatOdds(entry.data.odds)} (${entry.data.zone})`
                          : entry.data?.reason || entry.data?.message || (entry.data ? JSON.stringify(entry.data).slice(0, 80) : 'Activity')
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
            <div className="overflow-auto max-h-96">
              {autoBets.length === 0 ? (
                <p className="text-xs text-chimera-muted py-8 text-center">No bets yet — start the engine to begin</p>
              ) : (
                <table className="w-full text-xs">
                  <thead className="sticky top-0 z-10 bg-chimera-bg-secondary">
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

// ── Plugin Manager Panel ──

function PluginManagerPanel({
  plugins,
  onToggle,
  onClose,
}: {
  plugins: Array<{ id: string; name: string; version: string; author: string; description: string; enabled: boolean | number }>
  onToggle: (pluginId: string, enabled: boolean) => Promise<void>
  onClose: () => void
}) {
  return (
    <div className="glass-card rounded-xl p-6 border border-chimera-accent/20">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-chimera-text flex items-center gap-2">
          <svg className="w-5 h-5 text-chimera-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 6.087c0-.355.186-.676.401-.959.221-.29.349-.634.349-1.003 0-1.036-1.007-1.875-2.25-1.875s-2.25.84-2.25 1.875c0 .369.128.713.349 1.003.215.283.401.604.401.959v0a.64.64 0 0 1-.657.643 48.39 48.39 0 0 1-4.163-.3c.186 1.613.293 3.25.315 4.907a.656.656 0 0 1-.658.663v0c-.355 0-.676-.186-.959-.401a1.647 1.647 0 0 0-1.003-.349c-1.036 0-1.875 1.007-1.875 2.25s.84 2.25 1.875 2.25c.369 0 .713-.128 1.003-.349.283-.215.604-.401.959-.401v0c.31 0 .555.26.532.57a48.039 48.039 0 0 1-.642 5.056c1.518.19 3.058.309 4.616.354a.64.64 0 0 0 .657-.643v0c0-.355-.186-.676-.401-.959a1.647 1.647 0 0 1-.349-1.003c0-1.035 1.008-1.875 2.25-1.875 1.243 0 2.25.84 2.25 1.875 0 .369-.128.713-.349 1.003-.215.283-.4.604-.4.959v0c0 .333.277.599.61.58a48.1 48.1 0 0 0 5.427-.63 48.05 48.05 0 0 0 .582-4.717.532.532 0 0 0-.533-.57v0c-.355 0-.676.186-.959.401-.29.221-.634.349-1.003.349-1.035 0-1.875-1.007-1.875-2.25s.84-2.25 1.875-2.25c.37 0 .713.128 1.003.349.283.215.604.401.959.401v0a.656.656 0 0 0 .658-.663 48.422 48.422 0 0 0-.37-5.36c-1.886.342-3.81.574-5.766.689a.578.578 0 0 1-.61-.58v0Z" />
          </svg>
          Manage Plugins
        </h2>
        <button
          onClick={onClose}
          className="text-chimera-muted hover:text-chimera-text transition-colors p-1"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {plugins.length === 0 ? (
        <p className="text-sm text-chimera-muted py-4 text-center">No plugins found</p>
      ) : (
        <div className="space-y-3">
          {plugins.map((p) => (
            <div key={p.id} className="glass-card-hover rounded-lg p-4">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-semibold text-chimera-text">{p.name}</h3>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-chimera-bg-card border border-chimera-border text-chimera-muted">
                      v{p.version}
                    </span>
                  </div>
                  <p className="text-xs text-chimera-muted mt-0.5">by {p.author}</p>
                  <p className="text-xs text-chimera-text-secondary mt-2">{p.description}</p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer ml-4 flex-shrink-0">
                  <input
                    type="checkbox"
                    checked={!!p.enabled}
                    onChange={(e) => onToggle(p.id, e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-11 h-6 bg-chimera-border rounded-full peer peer-checked:bg-chimera-success/50 after:content-[''] after:absolute after:top-0.5 after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
                </label>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Settings Editor Panel ──

function SettingsEditorPanel({
  settings,
  onSave,
  onClose,
}: {
  settings: AutoBettingSettings
  onSave: (settings: Record<string, any>) => Promise<void>
  onClose: () => void
}) {
  const [form, setForm] = useState({
    max_liability_per_bet: settings.max_liability_per_bet || 9,
    max_daily_exposure: settings.max_daily_exposure || 75,
    daily_stop_loss: settings.daily_stop_loss || -25,
    max_concurrent_bets: settings.max_concurrent_bets || 10,
    max_bets_per_race: settings.max_bets_per_race || 1,
  })
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    await onSave(form)
    setSaving(false)
    onClose()
  }

  const hasChanges =
    form.max_liability_per_bet !== (settings.max_liability_per_bet || 9) ||
    form.max_daily_exposure !== (settings.max_daily_exposure || 75) ||
    form.daily_stop_loss !== (settings.daily_stop_loss || -25) ||
    form.max_concurrent_bets !== (settings.max_concurrent_bets || 10) ||
    form.max_bets_per_race !== (settings.max_bets_per_race || 1)

  return (
    <div className="glass-card rounded-xl p-6 border border-chimera-accent/20">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-chimera-text flex items-center gap-2">
          <svg className="w-5 h-5 text-chimera-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128.332-.183.582-.495.644-.869l.214-1.28Z" />
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
          </svg>
          Auto-Betting Settings
        </h2>
        <button
          onClick={onClose}
          className="text-chimera-muted hover:text-chimera-text transition-colors p-1"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18 18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SettingInput
          label="Max Liability per Bet"
          value={form.max_liability_per_bet}
          onChange={(v) => setForm({ ...form, max_liability_per_bet: v })}
          prefix="£"
          step={0.5}
          min={0.5}
          max={100}
        />
        <SettingInput
          label="Max Daily Exposure"
          value={form.max_daily_exposure}
          onChange={(v) => setForm({ ...form, max_daily_exposure: v })}
          prefix="£"
          step={5}
          min={5}
          max={500}
        />
        <SettingInput
          label="Daily Stop-Loss"
          value={form.daily_stop_loss}
          onChange={(v) => setForm({ ...form, daily_stop_loss: v })}
          prefix="£"
          step={5}
          min={-500}
          max={0}
        />
        <SettingInput
          label="Max Concurrent Bets"
          value={form.max_concurrent_bets}
          onChange={(v) => setForm({ ...form, max_concurrent_bets: v })}
          step={1}
          min={1}
          max={50}
          isInteger
        />
        <SettingInput
          label="Max Bets per Race"
          value={form.max_bets_per_race}
          onChange={(v) => setForm({ ...form, max_bets_per_race: v })}
          step={1}
          min={1}
          max={10}
          isInteger
        />
      </div>

      <div className="flex items-center justify-end gap-3 mt-6 pt-4 border-t border-chimera-border/30">
        <button
          onClick={onClose}
          className="btn-secondary px-4 py-2 text-sm"
        >
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={saving || !hasChanges}
          className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${
            hasChanges
              ? 'bg-chimera-success/10 border-2 border-chimera-success/30 text-chimera-success hover:bg-chimera-success/20'
              : 'bg-chimera-bg-card border border-chimera-border text-chimera-muted cursor-not-allowed'
          }`}
        >
          {saving ? <LoadingSpinner size="sm" /> : 'Save Settings'}
        </button>
      </div>
    </div>
  )
}

// ── Shared Components ──

function SettingInput({
  label,
  value,
  onChange,
  prefix,
  step = 1,
  min,
  max,
  isInteger = false,
}: {
  label: string
  value: number
  onChange: (value: number) => void
  prefix?: string
  step?: number
  min?: number
  max?: number
  isInteger?: boolean
}) {
  return (
    <div>
      <label className="block text-xs text-chimera-muted mb-1.5">{label}</label>
      <div className="flex items-center gap-2">
        {prefix && <span className="text-sm text-chimera-muted">{prefix}</span>}
        <input
          type="number"
          value={value}
          onChange={(e) => {
            const v = isInteger ? parseInt(e.target.value) : parseFloat(e.target.value)
            if (!isNaN(v)) onChange(v)
          }}
          step={step}
          min={min}
          max={max}
          className="w-full px-3 py-2 rounded-lg text-sm font-mono
            bg-chimera-bg-card border border-chimera-border text-chimera-text
            focus:outline-none focus:border-chimera-accent/50 focus:ring-1 focus:ring-chimera-accent/20
            transition-all"
        />
      </div>
    </div>
  )
}

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
  if (mode === 'PAUSED') {
    return (
      <span className="badge bg-chimera-warning/10 text-chimera-warning border-chimera-warning/20 flex items-center gap-1.5">
        <span className="w-2 h-2 rounded-full bg-chimera-warning" />
        PAUSED
      </span>
    )
  }
  return (
    <span className="badge bg-chimera-bg-card text-chimera-muted border-chimera-border">
      STOPPED
    </span>
  )
}

function InlineStat({ label, value, className = '' }: { label: string; value: string; className?: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="text-chimera-muted">{label}:</span>
      <span className={`font-mono font-semibold ${className}`}>{value}</span>
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
