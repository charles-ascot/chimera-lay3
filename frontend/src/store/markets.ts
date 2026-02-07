/**
 * CHIMERA v2 Markets Store (Zustand)
 * Market catalogue + live price updates from WebSocket
 * Falls back to REST API polling when stream data is unavailable
 */

import { create } from 'zustand'
import { marketsApi } from '../lib/api'
import type { Market, Runner } from '../types/betfair'

interface MarketsState {
  markets: Market[]
  selectedMarketId: string | null
  livePrices: Record<string, Record<number, { atb: number[][]; atl: number[][]; ltp: number | null; tv: number }>>
  marketStatuses: Record<string, { status: string; inPlay: boolean }>
  loading: boolean
  error: string | null

  fetchMarkets: () => Promise<void>
  selectMarket: (marketId: string | null) => void
  updatePrices: (marketId: string, runners: any[]) => void
  updateMarketStatus: (marketId: string, status: string, inPlay: boolean) => void
  getSelectedMarket: () => Market | null
  fetchMarketBook: (marketId: string) => Promise<void>
}

export const useMarketsStore = create<MarketsState>((set, get) => ({
  markets: [],
  selectedMarketId: null,
  livePrices: {},
  marketStatuses: {},
  loading: false,
  error: null,

  fetchMarkets: async () => {
    set({ loading: true, error: null })
    try {
      const { data } = await marketsApi.getCatalogue()
      set({ markets: data.markets || [], loading: false })
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch markets',
        loading: false,
      })
    }
  },

  selectMarket: (marketId) => set({ selectedMarketId: marketId }),

  updatePrices: (marketId, runners) => {
    set((state) => {
      const updated = { ...state.livePrices }
      if (!updated[marketId]) updated[marketId] = {}

      for (const r of runners) {
        updated[marketId][r.selectionId] = {
          atb: r.atb || [],
          atl: r.atl || [],
          ltp: r.ltp ?? null,
          tv: r.tv || 0,
        }
      }

      return { livePrices: updated }
    })
  },

  updateMarketStatus: (marketId, status, inPlay) => {
    set((state) => ({
      marketStatuses: {
        ...state.marketStatuses,
        [marketId]: { status, inPlay },
      },
    }))
  },

  getSelectedMarket: () => {
    const { markets, selectedMarketId } = get()
    if (!selectedMarketId) return null
    return markets.find((m) => m.marketId === selectedMarketId) || null
  },

  fetchMarketBook: async (marketId) => {
    try {
      const { data } = await marketsApi.getSingleBook(marketId)
      if (!data?.runners) return

      // Convert REST API format to stream format for consistency
      const runners = data.runners.map((r: any) => {
        const ex = r.ex || {}
        // Convert {price, size}[] to [[price, size], ...] format
        const atb = (ex.availableToBack || []).map((ps: any) => [ps.price, ps.size])
        const atl = (ex.availableToLay || []).map((ps: any) => [ps.price, ps.size])
        return {
          selectionId: r.selectionId,
          atb,
          atl,
          ltp: r.lastPriceTraded ?? null,
          tv: r.totalMatched || 0,
        }
      })

      get().updatePrices(marketId, runners)

      // Also update market status
      if (data.status) {
        get().updateMarketStatus(marketId, data.status, data.inplay || false)
      }
    } catch {
      // Silently fail — stream is the primary source
    }
  },
}))
