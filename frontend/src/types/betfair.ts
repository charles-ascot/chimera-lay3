/** Betfair Exchange API types */

export interface Runner {
  selectionId: number
  runnerName: string
  metadata?: Record<string, string>
  atb?: number[][]  // Available to Back [[price, size], ...]
  atl?: number[][]  // Available to Lay [[price, size], ...]
  ltp?: number | null  // Last Traded Price
  tv?: number  // Total Volume
}

export interface Market {
  marketId: string
  marketName: string
  marketStartTime: string
  venue: string
  countryCode: string
  event?: {
    id?: string
    name?: string
    venue?: string
    countryCode?: string
  }
  competition?: {
    id?: string
    name?: string
  }
  runners: Runner[]
  status?: string
  inPlay?: boolean
  totalMatched?: number
}

export interface MarketBook {
  marketId: string
  status: string
  inplay: boolean
  numberOfActiveRunners: number
  totalMatched: number
  runners: RunnerBook[]
}

export interface RunnerBook {
  selectionId: number
  status: string
  lastPriceTraded?: number
  totalMatched?: number
  ex?: {
    availableToBack: PriceSize[]
    availableToLay: PriceSize[]
    tradedVolume: PriceSize[]
  }
}

export interface PriceSize {
  price: number
  size: number
}

export interface AccountFunds {
  availableToBetBalance: number
  exposure: number
  retainedCommission: number
  exposureLimit: number
  discountRate: number
  pointsBalance: number
  wallet: string
}
