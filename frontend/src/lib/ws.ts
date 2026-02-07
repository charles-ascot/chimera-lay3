/**
 * CHIMERA v2 WebSocket Client
 * Connects to backend for live price updates, order changes, and engine status.
 */

type WSMessageHandler = (data: any) => void

interface WSHandlers {
  onPriceUpdate?: WSMessageHandler
  onMarketStatus?: WSMessageHandler
  onOrderUpdate?: WSMessageHandler
  onEngineStatus?: WSMessageHandler
  onEngineActivity?: WSMessageHandler
  onConnected?: () => void
  onDisconnected?: () => void
}

class ChimeraWebSocket {
  private ws: WebSocket | null = null
  private url: string
  private handlers: WSHandlers = {}
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private reconnectDelay = 1000
  private maxReconnectDelay = 30000
  private pingInterval: ReturnType<typeof setInterval> | null = null
  private _isConnected = false
  private _shouldReconnect = true

  constructor() {
    const wsUrl = import.meta.env.VITE_WS_URL || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/prices`
    this.url = wsUrl
  }

  get isConnected(): boolean {
    return this._isConnected
  }

  setHandlers(handlers: WSHandlers) {
    this.handlers = { ...this.handlers, ...handlers }
  }

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return

    this._shouldReconnect = true

    try {
      this.ws = new WebSocket(this.url)

      this.ws.onopen = () => {
        this._isConnected = true
        this.reconnectDelay = 1000
        this.handlers.onConnected?.()
        this._startPing()
      }

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          this._handleMessage(msg)
        } catch (e) {
          console.error('WS parse error:', e)
        }
      }

      this.ws.onclose = () => {
        this._isConnected = false
        this._stopPing()
        this.handlers.onDisconnected?.()

        if (this._shouldReconnect) {
          this._scheduleReconnect()
        }
      }

      this.ws.onerror = (error) => {
        console.error('WS error:', error)
      }
    } catch (e) {
      console.error('WS connection failed:', e)
      if (this._shouldReconnect) {
        this._scheduleReconnect()
      }
    }
  }

  disconnect() {
    this._shouldReconnect = false
    this._stopPing()

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    if (this.ws) {
      this.ws.close()
      this.ws = null
    }

    this._isConnected = false
  }

  private _handleMessage(msg: { type: string; data?: any }) {
    switch (msg.type) {
      case 'price_update':
        this.handlers.onPriceUpdate?.(msg.data)
        break
      case 'market_status':
        this.handlers.onMarketStatus?.(msg.data)
        break
      case 'order_update':
        this.handlers.onOrderUpdate?.(msg.data)
        break
      case 'engine_status':
        this.handlers.onEngineStatus?.(msg.data)
        break
      case 'engine_activity':
        this.handlers.onEngineActivity?.(msg.data)
        break
      case 'connected':
        console.log('WS: Connected to CHIMERA')
        break
      case 'pong':
      case 'heartbeat':
        break
      default:
        console.debug('WS unknown type:', msg.type)
    }
  }

  private _startPing() {
    this._stopPing()
    this.pingInterval = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 10000)
  }

  private _stopPing() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval)
      this.pingInterval = null
    }
  }

  private _scheduleReconnect() {
    if (this.reconnectTimer) return

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
      this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay)
    }, this.reconnectDelay)
  }
}

export const chimeraWS = new ChimeraWebSocket()
export default chimeraWS
