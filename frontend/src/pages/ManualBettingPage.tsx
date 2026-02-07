/**
 * CHIMERA v2 Manual Betting Page
 * Market list + runner table with live prices + bet slip
 */

import { useEffect, useState } from 'react'
import { useMarketsStore } from '../store/markets'
import { useBetSlipStore } from '../store/betslip'
import { useToastStore } from '../store/toast'
import { formatTime, formatOdds, formatGBP, groupByVenue, minutesToRace } from '../lib/utils'
import LoadingSpinner from '../components/shared/LoadingSpinner'
import StatusBadge from '../components/shared/StatusBadge'
import type { Market, Runner } from '../types/betfair'

export default function ManualBettingPage() {
  const { markets, selectedMarketId, livePrices, marketStatuses, fetchMarkets, selectMarket, loading } = useMarketsStore()
  const selectedMarket = useMarketsStore((s) => s.getSelectedMarket())

  useEffect(() => {
    fetchMarkets()
    const interval = setInterval(fetchMarkets, 60000) // Refresh catalogue every 60s
    return () => clearInterval(interval)
  }, [fetchMarkets])

  const grouped = groupByVenue(markets)

  return (
    <div className="flex flex-col lg:flex-row gap-4 h-[calc(100vh-8rem)] animate-fade-in">
      {/* Left: Market List */}
      <div className="w-full lg:w-72 flex-shrink-0 overflow-y-auto">
        <div className="glass-card rounded-xl p-3 space-y-3">
          <h2 className="text-sm font-semibold text-chimera-text-secondary px-1">Markets</h2>
          {loading && markets.length === 0 ? (
            <LoadingSpinner size="sm" className="py-8" />
          ) : (
            Object.entries(grouped).map(([venue, venueMarkets]) => (
              <VenueGroup
                key={venue}
                venue={venue}
                markets={venueMarkets}
                selectedId={selectedMarketId}
                marketStatuses={marketStatuses}
                onSelect={selectMarket}
              />
            ))
          )}
        </div>
      </div>

      {/* Center: Runner Table */}
      <div className="flex-1 overflow-y-auto">
        {selectedMarket ? (
          <RunnerTable
            market={selectedMarket}
            livePrices={livePrices[selectedMarket.marketId] || {}}
            marketStatus={marketStatuses[selectedMarket.marketId]}
          />
        ) : (
          <div className="glass-card rounded-xl flex items-center justify-center h-64">
            <p className="text-chimera-muted">Select a market to view runners</p>
          </div>
        )}
      </div>

      {/* Right: Bet Slip */}
      <div className="w-full lg:w-80 flex-shrink-0">
        <BetSlip />
      </div>
    </div>
  )
}

// ── Venue Group ──

function VenueGroup({
  venue,
  markets,
  selectedId,
  marketStatuses,
  onSelect,
}: {
  venue: string
  markets: Market[]
  selectedId: string | null
  marketStatuses: Record<string, { status: string; inPlay: boolean }>
  onSelect: (id: string) => void
}) {
  return (
    <div>
      <div className="text-xs font-bold text-chimera-accent uppercase tracking-wider px-1 mb-1">
        {venue}
      </div>
      {markets.map((m) => {
        const minsToRace = minutesToRace(m.marketStartTime)
        const status = marketStatuses[m.marketId]
        const isInPlay = status?.inPlay
        const isSelected = m.marketId === selectedId

        return (
          <button
            key={m.marketId}
            onClick={() => onSelect(m.marketId)}
            className={`w-full text-left px-2 py-1.5 rounded-lg text-sm transition-colors ${
              isSelected
                ? 'bg-chimera-accent/10 text-chimera-accent border border-chimera-accent/20'
                : 'hover:bg-chimera-bg-card-hover text-chimera-text'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs">
                {formatTime(m.marketStartTime)}
              </span>
              {isInPlay && <StatusBadge status="IN-PLAY" />}
              {minsToRace !== null && minsToRace <= 5 && !isInPlay && (
                <span className="text-[10px] text-chimera-warning">
                  {Math.round(minsToRace)}m
                </span>
              )}
            </div>
          </button>
        )
      })}
    </div>
  )
}

// ── Runner Table ──

function RunnerTable({
  market,
  livePrices,
  marketStatus,
}: {
  market: Market
  livePrices: Record<number, { atb: number[][]; atl: number[][]; ltp: number | null; tv: number }>
  marketStatus?: { status: string; inPlay: boolean }
}) {
  const { setSelection } = useBetSlipStore()

  const handleLayClick = (runner: Runner, odds: number) => {
    setSelection(market.marketId, runner.selectionId, runner.runnerName, odds)
  }

  return (
    <div className="glass-card rounded-xl overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-chimera-border flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-chimera-text">{market.venue}</h2>
          <p className="text-xs text-chimera-muted">
            {formatTime(market.marketStartTime)} — {market.marketName}
          </p>
        </div>
        {marketStatus?.inPlay && <StatusBadge status="IN-PLAY" />}
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-chimera-muted text-xs border-b border-chimera-border">
              <th className="px-4 py-2 text-left">Runner</th>
              <th className="px-2 py-2 text-center" colSpan={3}>Back</th>
              <th className="px-2 py-2 text-center" colSpan={3}>Lay</th>
              <th className="px-2 py-2 text-right">LTP</th>
            </tr>
          </thead>
          <tbody>
            {market.runners.map((runner) => {
              const prices = livePrices[runner.selectionId]
              const atb = prices?.atb || []
              const atl = prices?.atl || []
              const ltp = prices?.ltp

              return (
                <tr
                  key={runner.selectionId}
                  className="border-b border-chimera-border/30 hover:bg-chimera-bg-card-hover"
                >
                  <td className="px-4 py-2">
                    <span className="font-medium text-chimera-text">
                      {runner.runnerName}
                    </span>
                  </td>

                  {/* Back prices (3 levels, reversed order: deepest first) */}
                  {[2, 1, 0].map((i) => (
                    <td key={`back-${i}`} className="px-1 py-1.5">
                      {atb[i] ? (
                        <div className="price-back">
                          <div className="font-mono font-medium">{formatOdds(atb[i][0])}</div>
                          <div className="text-[10px] opacity-60">{formatGBP(atb[i][1])}</div>
                        </div>
                      ) : (
                        <div className="text-center text-chimera-muted">-</div>
                      )}
                    </td>
                  ))}

                  {/* Lay prices (3 levels) — clickable */}
                  {[0, 1, 2].map((i) => (
                    <td key={`lay-${i}`} className="px-1 py-1.5">
                      {atl[i] ? (
                        <button
                          onClick={() => handleLayClick(runner, atl[i][0])}
                          className="price-lay w-full"
                        >
                          <div className="font-mono font-medium">{formatOdds(atl[i][0])}</div>
                          <div className="text-[10px] opacity-60">{formatGBP(atl[i][1])}</div>
                        </button>
                      ) : (
                        <div className="text-center text-chimera-muted">-</div>
                      )}
                    </td>
                  ))}

                  {/* LTP */}
                  <td className="px-2 py-2 text-right font-mono text-chimera-text-secondary">
                    {formatOdds(ltp)}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}

// ── Bet Slip ──

function BetSlip() {
  const {
    marketId, selectionId, runnerName, odds, stake,
    placing, lastResult,
    setOdds, setStake, placeBet, clear,
  } = useBetSlipStore()
  const { addToast } = useToastStore()

  if (!marketId || !selectionId) {
    return (
      <div className="glass-card rounded-xl p-6 flex items-center justify-center h-48">
        <p className="text-chimera-muted text-sm text-center">
          Click a lay price to add to bet slip
        </p>
      </div>
    )
  }

  const liability = stake * (odds - 1)
  const profit = stake

  const handlePlace = async () => {
    const success = await placeBet()
    if (success) {
      addToast(`Bet placed: ${runnerName} @ ${odds}`, 'success')
      clear()
    } else {
      addToast('Bet placement failed', 'error')
    }
  }

  return (
    <div className="glass-card rounded-xl p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Lay Bet Slip</h3>
        <button onClick={clear} className="text-xs text-chimera-muted hover:text-chimera-error">
          Clear
        </button>
      </div>

      {/* Runner info */}
      <div className="p-3 rounded-lg bg-pink-500/5 border border-pink-500/10">
        <p className="font-medium text-chimera-text">{runnerName}</p>
        <p className="text-xs text-chimera-muted">LAY</p>
      </div>

      {/* Odds input */}
      <div>
        <label className="text-xs text-chimera-muted">Odds</label>
        <input
          type="number"
          value={odds}
          onChange={(e) => setOdds(parseFloat(e.target.value) || 0)}
          step="0.01"
          min="1.01"
          className="input-field font-mono mt-1"
        />
      </div>

      {/* Stake input */}
      <div>
        <label className="text-xs text-chimera-muted">Stake (Backer's Stake)</label>
        <input
          type="number"
          value={stake}
          onChange={(e) => setStake(parseFloat(e.target.value) || 0)}
          step="0.5"
          min="0.01"
          className="input-field font-mono mt-1"
        />
      </div>

      {/* Summary */}
      <div className="space-y-1 text-sm">
        <div className="flex justify-between">
          <span className="text-chimera-muted">Liability</span>
          <span className="font-mono text-chimera-error">{formatGBP(liability)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-chimera-muted">Profit if loses</span>
          <span className="font-mono text-chimera-success">{formatGBP(profit)}</span>
        </div>
      </div>

      {/* Place button */}
      <button
        onClick={handlePlace}
        disabled={placing || odds <= 1 || stake <= 0}
        className="btn-primary w-full"
      >
        {placing ? (
          <LoadingSpinner size="sm" />
        ) : (
          `Place Lay — ${formatGBP(liability)} liability`
        )}
      </button>

      {/* Result */}
      {lastResult && (
        <div className={`p-2 rounded-lg text-xs ${
          lastResult.status === 'SUCCESS'
            ? 'bg-chimera-success-bg text-chimera-success'
            : 'bg-chimera-error-bg text-chimera-error'
        }`}>
          {lastResult.status === 'SUCCESS'
            ? `Bet placed! ID: ${lastResult.bet_id}`
            : `Error: ${lastResult.error || 'Unknown'}`
          }
        </div>
      )}
    </div>
  )
}
