/**
 * CHIMERA v2 Bet Slip Store (Zustand)
 * Manual bet placement
 */

import { create } from 'zustand'
import { ordersApi } from '../lib/api'

interface BetSlipState {
  marketId: string | null
  selectionId: number | null
  runnerName: string | null
  odds: number
  stake: number
  placing: boolean
  lastResult: any | null

  setSelection: (marketId: string, selectionId: number, runnerName: string, odds: number) => void
  setOdds: (odds: number) => void
  setStake: (stake: number) => void
  placeBet: () => Promise<boolean>
  clear: () => void
}

export const useBetSlipStore = create<BetSlipState>((set, get) => ({
  marketId: null,
  selectionId: null,
  runnerName: null,
  odds: 0,
  stake: 2,
  placing: false,
  lastResult: null,

  setSelection: (marketId, selectionId, runnerName, odds) => {
    set({ marketId, selectionId, runnerName, odds, lastResult: null })
  },

  setOdds: (odds) => set({ odds }),
  setStake: (stake) => set({ stake }),

  placeBet: async () => {
    const { marketId, selectionId, odds, stake } = get()
    if (!marketId || !selectionId || odds <= 1 || stake <= 0) return false

    set({ placing: true })
    try {
      const { data } = await ordersApi.place({
        market_id: marketId,
        selection_id: selectionId,
        odds,
        stake,
      })
      set({ placing: false, lastResult: data })
      return data.status === 'SUCCESS'
    } catch (err: any) {
      set({
        placing: false,
        lastResult: { status: 'ERROR', error: err.response?.data?.detail || err.message },
      })
      return false
    }
  },

  clear: () => set({
    marketId: null,
    selectionId: null,
    runnerName: null,
    odds: 0,
    stake: 2,
    lastResult: null,
  }),
}))
