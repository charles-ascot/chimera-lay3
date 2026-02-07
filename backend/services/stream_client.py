"""
CHIMERA v2 Betfair Stream API Client
SSL socket connection to stream-api.betfair.com:443 for real-time price updates.

Protocol:
- CRLF-delimited JSON messages over SSL
- Authentication → Subscribe → Receive deltas
- Heartbeat mechanism for connection health
- Delta-based price cache updates
"""

import asyncio
import json
import logging
import ssl
import time
from typing import Optional, Callable, Awaitable, Any

from config import config

logger = logging.getLogger(__name__)

# Message IDs for correlation
_msg_id_counter = 0


def _next_id() -> int:
    global _msg_id_counter
    _msg_id_counter += 1
    return _msg_id_counter


class StreamClient:
    """Async SSL socket client for Betfair Stream API."""

    def __init__(self):
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._authenticated = False
        self._running = False

        # Reconnection state
        self._initial_clk: Optional[str] = None
        self._clk: Optional[str] = None

        # Subscriptions
        self._market_sub_id: Optional[int] = None
        self._order_sub_id: Optional[int] = None

        # Callbacks
        self._on_market_change: Optional[Callable] = None
        self._on_order_change: Optional[Callable] = None
        self._on_connection_change: Optional[Callable] = None

        # Stats
        self._messages_received = 0
        self._last_heartbeat: Optional[float] = None
        self._connect_time: Optional[float] = None

    @property
    def connected(self) -> bool:
        return self._connected and self._writer is not None

    @property
    def authenticated(self) -> bool:
        return self._authenticated

    @property
    def stats(self) -> dict:
        return {
            "connected": self._connected,
            "authenticated": self._authenticated,
            "messages_received": self._messages_received,
            "last_heartbeat": self._last_heartbeat,
            "uptime_seconds": time.time() - self._connect_time if self._connect_time else 0,
        }

    def set_callbacks(
        self,
        on_market_change: Optional[Callable] = None,
        on_order_change: Optional[Callable] = None,
        on_connection_change: Optional[Callable] = None,
    ):
        """Set callback functions for stream events."""
        self._on_market_change = on_market_change
        self._on_order_change = on_order_change
        self._on_connection_change = on_connection_change

    # ─────────────────────────────────────────────────────────
    # Connection
    # ─────────────────────────────────────────────────────────

    async def connect(self, session_token: str) -> bool:
        """Connect and authenticate with the Betfair Stream API."""
        try:
            logger.info(f"Connecting to {config.STREAM_HOST}:{config.STREAM_PORT}...")

            # Create SSL context
            ssl_context = ssl.create_default_context()

            self._reader, self._writer = await asyncio.open_connection(
                config.STREAM_HOST,
                config.STREAM_PORT,
                ssl=ssl_context,
            )

            self._connected = True
            self._connect_time = time.time()

            # Read the connection message
            conn_msg = await self._read_line()
            if conn_msg and conn_msg.get("op") == "connection":
                connection_id = conn_msg.get("connectionId")
                logger.info(f"Stream connected. Connection ID: {connection_id}")
            else:
                logger.error(f"Unexpected connection message: {conn_msg}")
                await self.disconnect()
                return False

            # Authenticate
            auth_msg = {
                "op": "authentication",
                "id": _next_id(),
                "appKey": config.BETFAIR_APP_KEY,
                "session": session_token,
            }
            await self._send(auth_msg)

            # Read auth response
            auth_response = await self._read_line()
            if auth_response and auth_response.get("statusCode") == "SUCCESS":
                self._authenticated = True
                logger.info("Stream authenticated successfully")
                if self._on_connection_change:
                    await self._on_connection_change("connected")
                return True
            else:
                error = auth_response.get("errorMessage", "Unknown") if auth_response else "No response"
                logger.error(f"Stream authentication failed: {error}")
                await self.disconnect()
                return False

        except Exception as e:
            logger.error(f"Stream connection failed: {e}")
            self._connected = False
            self._authenticated = False
            return False

    async def disconnect(self):
        """Disconnect from the stream."""
        self._running = False
        self._connected = False
        self._authenticated = False

        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None
            self._reader = None

        logger.info("Stream disconnected")
        if self._on_connection_change:
            try:
                await self._on_connection_change("disconnected")
            except Exception:
                pass

    # ─────────────────────────────────────────────────────────
    # Subscriptions
    # ─────────────────────────────────────────────────────────

    async def subscribe_markets(
        self,
        event_type_ids: list = None,
        country_codes: list = None,
        market_types: list = None,
    ):
        """Subscribe to market price updates for GB/IE horse racing WIN markets."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated — connect first")

        sub_id = _next_id()
        self._market_sub_id = sub_id

        market_filter = {
            "eventTypeIds": event_type_ids or config.EVENT_TYPE_IDS,
            "countryCodes": country_codes or config.COUNTRY_CODES,
            "marketTypes": market_types or config.MARKET_TYPES,
            "turnInPlayEnabled": True,
        }

        market_data_filter = {
            "fields": [
                "EX_BEST_OFFERS_DISP",
                "EX_LTP",
                "EX_MARKET_DEF",
                "EX_TRADED_VOL",
            ],
            "ladderLevels": 3,
        }

        msg = {
            "op": "marketSubscription",
            "id": sub_id,
            "marketFilter": market_filter,
            "marketDataFilter": market_data_filter,
        }

        # If reconnecting, include clk for delta recovery
        if self._initial_clk:
            msg["initialClk"] = self._initial_clk
        if self._clk:
            msg["clk"] = self._clk

        await self._send(msg)
        logger.info(f"Market subscription sent (id={sub_id})")

    async def subscribe_orders(self):
        """Subscribe to order updates (real-time order status)."""
        if not self._authenticated:
            raise RuntimeError("Not authenticated — connect first")

        sub_id = _next_id()
        self._order_sub_id = sub_id

        msg = {
            "op": "orderSubscription",
            "id": sub_id,
            "orderProjection": ["ALL"],
            "includeOverallPosition": True,
        }

        await self._send(msg)
        logger.info(f"Order subscription sent (id={sub_id})")

    # ─────────────────────────────────────────────────────────
    # Message Processing Loop
    # ─────────────────────────────────────────────────────────

    async def listen(self):
        """Main listening loop — reads and processes stream messages."""
        self._running = True
        logger.info("Stream listener started")

        while self._running and self._connected:
            try:
                msg = await self._read_line()
                if msg is None:
                    logger.warning("Stream connection lost (null read)")
                    break

                self._messages_received += 1
                op = msg.get("op")

                if op == "mcm":
                    # Market Change Message
                    await self._handle_market_change(msg)
                elif op == "ocm":
                    # Order Change Message
                    await self._handle_order_change(msg)
                elif op == "connection":
                    # Re-connection message
                    logger.info(f"Re-connection: {msg.get('connectionId')}")
                elif op == "status":
                    # Status message (subscription result or error)
                    await self._handle_status(msg)
                else:
                    # Heartbeat or unknown
                    if "ct" in msg and msg["ct"] == "HEARTBEAT":
                        self._last_heartbeat = time.time()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Stream listener error: {e}")
                if not self._connected:
                    break
                await asyncio.sleep(0.5)

        self._running = False
        logger.info("Stream listener stopped")

    async def _handle_market_change(self, msg: dict):
        """Handle market change message (mcm)."""
        # Update clk tokens for reconnection
        if "initialClk" in msg:
            self._initial_clk = msg["initialClk"]
        if "clk" in msg:
            self._clk = msg["clk"]

        # Track heartbeat
        ct = msg.get("ct")
        if ct == "HEARTBEAT":
            self._last_heartbeat = time.time()
            return

        # Forward to callback
        if self._on_market_change:
            try:
                await self._on_market_change(msg)
            except Exception as e:
                logger.error(f"Market change callback error: {e}")

    async def _handle_order_change(self, msg: dict):
        """Handle order change message (ocm)."""
        if self._on_order_change:
            try:
                await self._on_order_change(msg)
            except Exception as e:
                logger.error(f"Order change callback error: {e}")

    async def _handle_status(self, msg: dict):
        """Handle status messages from subscriptions."""
        status_code = msg.get("statusCode")
        error_code = msg.get("errorCode")
        error_message = msg.get("errorMessage")
        sub_id = msg.get("id")

        if status_code == "SUCCESS":
            logger.info(f"Subscription {sub_id} confirmed")
        else:
            logger.error(
                f"Subscription {sub_id} error: {error_code} — {error_message}"
            )

    # ─────────────────────────────────────────────────────────
    # Low-level I/O
    # ─────────────────────────────────────────────────────────

    async def _send(self, msg: dict):
        """Send a CRLF-delimited JSON message."""
        if not self._writer:
            raise RuntimeError("Not connected")

        data = json.dumps(msg) + "\r\n"
        self._writer.write(data.encode("utf-8"))
        await self._writer.drain()
        logger.debug(f"Stream TX: {msg.get('op', '?')} (id={msg.get('id', '-')})")

    async def _read_line(self, timeout: float = 30.0) -> Optional[dict]:
        """Read a single CRLF-delimited JSON message."""
        if not self._reader:
            return None

        try:
            line = await asyncio.wait_for(
                self._reader.readline(),
                timeout=timeout
            )
            if not line:
                return None

            return json.loads(line.decode("utf-8").strip())

        except asyncio.TimeoutError:
            logger.warning("Stream read timeout")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Stream JSON decode error: {e}")
            return None


# Singleton
stream_client = StreamClient()
