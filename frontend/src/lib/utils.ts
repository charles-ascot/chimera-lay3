/**
 * CHIMERA v2 Utilities
 */

import { format, formatDistanceToNow, parseISO, differenceInMinutes } from 'date-fns'

/** Format currency to GBP */
export function formatGBP(amount: number, showSign = false): string {
  const prefix = showSign && amount > 0 ? '+' : ''
  return `${prefix}\u00A3${Math.abs(amount).toFixed(2)}`
}

/** Format P/L with color class name */
export function pnlClass(amount: number): string {
  if (amount > 0) return 'text-chimera-success'
  if (amount < 0) return 'text-chimera-error'
  return 'text-chimera-muted'
}

/** Format odds to 2dp */
export function formatOdds(odds: number | null | undefined): string {
  if (odds == null) return '-'
  return odds.toFixed(2)
}

/** Format percentage */
export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`
}

/** Format date/time */
export function formatDateTime(iso: string): string {
  try {
    return format(parseISO(iso), 'dd MMM HH:mm')
  } catch {
    return iso
  }
}

/** Format time only */
export function formatTime(iso: string): string {
  try {
    return format(parseISO(iso), 'HH:mm')
  } catch {
    return iso
  }
}

/** Format relative time (e.g. "5 min ago") */
export function formatRelative(iso: string): string {
  try {
    return formatDistanceToNow(parseISO(iso), { addSuffix: true })
  } catch {
    return iso
  }
}

/** Minutes until race start */
export function minutesToRace(startTime: string): number | null {
  try {
    const start = parseISO(startTime)
    return differenceInMinutes(start, new Date())
  } catch {
    return null
  }
}

/** Get zone color class */
export function zoneColor(zone: string | undefined): string {
  switch (zone?.toUpperCase()) {
    case 'PRIME': return 'text-chimera-success'
    case 'STRONG': return 'text-chimera-cyan'
    case 'SECONDARY': return 'text-chimera-warning'
    default: return 'text-chimera-muted'
  }
}

/** Get zone bg class */
export function zoneBgColor(zone: string | undefined): string {
  switch (zone?.toUpperCase()) {
    case 'PRIME': return 'bg-chimera-success/10 text-chimera-success border-chimera-success/20'
    case 'STRONG': return 'bg-chimera-cyan/10 text-chimera-cyan border-chimera-cyan/20'
    case 'SECONDARY': return 'bg-chimera-warning/10 text-chimera-warning border-chimera-warning/20'
    default: return 'bg-chimera-bg-card text-chimera-muted'
  }
}

/** Get status badge color */
export function statusColor(status: string): string {
  switch (status?.toUpperCase()) {
    case 'WON':
    case 'MATCHED':
    case 'SUCCESS': return 'text-chimera-success'
    case 'LOST':
    case 'CANCELLED':
    case 'ERROR': return 'text-chimera-error'
    case 'PENDING': return 'text-chimera-warning'
    default: return 'text-chimera-muted'
  }
}

/** Generate unique ID */
export function uid(): string {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
}

/** Clamp number */
export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}

/** Group markets by venue */
export function groupByVenue<T extends { venue?: string }>(items: T[]): Record<string, T[]> {
  return items.reduce((groups, item) => {
    const venue = item.venue || 'Unknown'
    if (!groups[venue]) groups[venue] = []
    groups[venue].push(item)
    return groups
  }, {} as Record<string, T[]>)
}
