/** Plugin system types */

export interface Plugin {
  id: string
  name: string
  version: string
  author: string
  description: string
  enabled: boolean | number
  priority: number
  config: PluginConfig
}

export interface PluginConfig {
  strategy?: {
    name: string
    version: string
    description: string
  }
  rules?: Record<string, any>
  risk_management?: Record<string, any>
  expected_performance?: Record<string, any>
}

export interface DecisionLogEntry {
  id: number
  market_id: string
  market_name?: string
  venue?: string
  race_time?: string
  plugin_id: string
  action: 'ACCEPT' | 'REJECT' | 'SKIP'
  reason?: string
  runners_snapshot?: string
  candidates?: string
  daily_pnl?: number
  daily_exposure?: number
  bets_today_count?: number
  time_to_race_minutes?: number
  created_at: string
}
