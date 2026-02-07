/** Application-level types */

export interface Bet {
  id: number
  bet_id?: string
  market_id: string
  market_name?: string
  venue?: string
  country_code?: string
  race_time?: string
  selection_id: number
  runner_name?: string
  side: string
  stake: number
  odds: number
  liability: number
  zone?: string
  confidence?: string
  rule_id?: string
  persistence_type?: string
  status: string
  result?: string
  profit_loss: number
  size_matched?: number
  size_remaining?: number
  avg_price_matched?: number
  placed_at: string
  matched_at?: string
  settled_at?: string
  source: string
}

export interface DailyStats {
  total_bets: number
  total_staked: number
  total_liability: number
  profit_loss: number
  wins: number
  losses: number
  pending: number
  exposure: number
  win_rate?: number
  roi?: number
}

export type EngineMode = 'STOPPED' | 'STAGING' | 'LIVE' | 'PAUSED'

export interface AutoBettingStatus {
  is_running: boolean
  mode: EngineMode
  active_plugins: string[]
  daily_exposure: number
  daily_pnl: number
  bets_placed_today: number
  processed_markets_count: number
  settings: AutoBettingSettings
  wins_today: number
  losses_today: number
  pending_today: number
  total_staked_today: number
}

export interface AutoBettingSettings {
  max_liability_per_bet: number
  max_daily_exposure: number
  daily_stop_loss: number
  max_concurrent_bets: number
  max_bets_per_race: number
  only_pre_race?: boolean
  pre_race_window_minutes?: number
}

export interface ToastMessage {
  id: string
  message: string
  type: 'success' | 'error' | 'info'
}

export interface StreamStats {
  connected: boolean
  authenticated: boolean
  messages_received: number
  cached_markets: number
  total_updates: number
  uptime_seconds: number
}
