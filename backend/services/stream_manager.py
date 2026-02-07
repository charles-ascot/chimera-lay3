"""
CHIMERA v2 Stream Manager
Manages Betfair Stream API subscriptions, maintains price cache,
and bridges updates to WebSocket clients.

The price cache is the single source of truth for live prices.
It processes delta updates from the Stream API per the Betfair specification.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import config
from services.stream_client import stream_client
from routers.websocket import (
    broadcast_price_update,
    broadcast_market_status,
    broadcast_order_update,
)
import database as db

logger = logging.getLogger(__name__)


class PriceCache:
    """
    In-memory cache of live market prices.
    Processes delta updates from the Betfair Stream API.

    Structure:
        markets[market_id] = {
            "marketDefinition": { ... },
            "runners": {
                selection_id: {
                    "atb": [[price, size], ...],   # Available to Back
                    "atl": [[price, size], ...],   # Available to Lay
                    "ltp": float,                   # Last Traded Price
                    "tv": float,                    # Total Volume
                    "spn": float,                   # Starting Price Near
                    "spf": float,                   # Starting Price Far
                    "trd": [[price, size], ...],    # Traded (if requested)
                },
            },
            "status": str,              # e.g. OPEN, SUSPENDED, CLOSED
            "inPlay": bool,
            "marketTime": str,          # ISO start time
            "totalMatched": float,
            "lastUpdate": float,        # Timestamp
        }
    """

    def __init__(self):
        self._markets: Dict[str, dict] = {}
        self._update_count = 0

    @property
    def market_count(self) -> int:
        return len(self._markets)

    @property
    def update_count(self) -> int:
        return self._update_count

    def get_market(self, market_id: str) -> Optional[dict]:
        """Get cached market data."""
        return self._markets.get(market_id)

    def get_all_markets(self) -> Dict[str, dict]:
        """Get all cached markets."""
        return self._markets.copy()

    def get_runner_prices(self, market_id: str, selection_id: int) -> Optional[dict]:
        """Get prices for a specific runner."""
        market = self._markets.get(market_id)
        if not market:
            return None
        return market.get("runners", {}).get(selection_id)

    def get_best_lay(self, market_id: str, selection_id: int) -> Optional[float]:
        """Get best available lay price for a runner."""
        runner = self.get_runner_prices(market_id, selection_id)
        if not runner:
            return None
        atl = runner.get("atl", [])
        if atl:
            # atl is sorted by price, best lay = lowest price
            return min(atl, key=lambda x: x[0])[0] if atl else None
        return runner.get("ltp")

    def clear(self):
        """Clear the entire cache."""
        self._markets.clear()
        self._update_count = 0

    # ─────────────────────────────────────────────────────────
    # Delta Processing (per Betfair Stream API spec)
    # ─────────────────────────────────────────────────────────

    def process_market_change(self, market_change: dict) -> dict:
        """
        Process a single market change from MCM message.
        Applies delta updates to the cache.
        Returns the updated market dict.
        """
        market_id = market_change.get("id")
        if not market_id:
            return {}

        # Get or create market entry
        if market_id not in self._markets:
            self._markets[market_id] = {
                "runners": {},
                "status": "OPEN",
                "inPlay": False,
                "lastUpdate": time.time(),
            }

        market = self._markets[market_id]

        # Process image vs delta
        is_image = market_change.get("img", False)
        if is_image:
            # Full image — replace everything
            market["runners"] = {}

        # Market definition
        market_def = market_change.get("marketDefinition")
        if market_def:
            market["marketDefinition"] = market_def
            market["status"] = market_def.get("status", market.get("status", "OPEN"))
            market["inPlay"] = market_def.get("inPlay", False)
            market["marketTime"] = market_def.get("marketTime", "")

            # Map runner info from definition
            for rd in market_def.get("runners", []):
                sel_id = rd.get("id")
                if sel_id and sel_id not in market["runners"]:
                    market["runners"][sel_id] = {
                        "atb": [], "atl": [], "ltp": None, "tv": 0,
                    }

        # Total matched volume
        if "tv" in market_change:
            market["totalMatched"] = market_change["tv"]

        # Runner changes
        for rc in market_change.get("rc", []):
            sel_id = rc.get("id")
            if sel_id is None:
                continue

            if sel_id not in market["runners"]:
                market["runners"][sel_id] = {
                    "atb": [], "atl": [], "ltp": None, "tv": 0,
                }

            runner = market["runners"][sel_id]

            # Full image for this runner
            if is_image or rc.get("img", False):
                runner["atb"] = []
                runner["atl"] = []

            # Available to Back (delta-merge on price level)
            if "atb" in rc:
                runner["atb"] = self._merge_levels(runner["atb"], rc["atb"])
            # Available to Lay (delta-merge on price level)
            if "atl" in rc:
                runner["atl"] = self._merge_levels(runner["atl"], rc["atl"])

            # Best available back/lay (display only — already sorted)
            if "batb" in rc:
                runner["atb"] = self._merge_display_levels(runner.get("batb_display", []), rc["batb"])
                runner["batb_display"] = runner["atb"]
            if "batl" in rc:
                runner["atl"] = self._merge_display_levels(runner.get("batl_display", []), rc["batl"])
                runner["batl_display"] = runner["atl"]

            # Best display levels (position-indexed: [position, price, size])
            if "bdatb" in rc:
                runner["atb"] = self._process_display_available(
                    runner.get("_bdatb", []), rc["bdatb"]
                )
                runner["_bdatb"] = runner["atb"]
            if "bdatl" in rc:
                runner["atl"] = self._process_display_available(
                    runner.get("_bdatl", []), rc["bdatl"]
                )
                runner["_bdatl"] = runner["atl"]

            # Last traded price
            if "ltp" in rc:
                runner["ltp"] = rc["ltp"]

            # Total volume
            if "tv" in rc:
                runner["tv"] = rc["tv"]

            # Starting prices
            if "spn" in rc:
                runner["spn"] = rc["spn"]
            if "spf" in rc:
                runner["spf"] = rc["spf"]

            # Traded volume ladder
            if "trd" in rc:
                runner["trd"] = self._merge_levels(runner.get("trd", []), rc["trd"])

        market["lastUpdate"] = time.time()
        self._update_count += 1

        return market

    @staticmethod
    def _merge_levels(existing: list, updates: list) -> list:
        """
        Merge price-level updates into existing ladder.
        Each entry is [price, size].
        A size of 0 means remove that level.
        """
        # Build dict of existing levels
        levels = {entry[0]: entry[1] for entry in existing}

        # Apply updates
        for update in updates:
            price = update[0]
            size = update[1]
            if size == 0:
                levels.pop(price, None)
            else:
                levels[price] = size

        # Return sorted by price
        return sorted([[p, s] for p, s in levels.items()], key=lambda x: x[0])

    @staticmethod
    def _merge_display_levels(existing: list, updates: list) -> list:
        """
        Merge position-indexed display levels.
        Updates are [position, price, size].
        """
        levels = {entry[0]: entry[1:] for entry in existing} if existing else {}

        for update in updates:
            pos = update[0]
            price = update[1]
            size = update[2]
            if size == 0 and price == 0:
                levels.pop(pos, None)
            else:
                levels[pos] = [price, size]

        # Return as [[price, size], ...] sorted by position
        result = []
        for pos in sorted(levels.keys()):
            result.append(levels[pos])
        return result

    @staticmethod
    def _process_display_available(existing: list, updates: list) -> list:
        """Process bdatb/bdatl display available (position, price, size)."""
        # Same as merge_display_levels
        return PriceCache._merge_display_levels(
            [[i] + v for i, v in enumerate(existing)] if existing else [],
            updates
        )


class StreamManager:
    """
    Manages the Betfair Stream API connection, price cache,
    and WebSocket bridge to the frontend.
    """

    def __init__(self):
        self.price_cache = PriceCache()
        self._listen_task: Optional[asyncio.Task] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._session_token: Optional[str] = None
        self._running = False
        self._reconnect_delay = 1.0  # Start with 1s, exponential backoff
        self._max_reconnect_delay = 60.0

    @property
    def is_connected(self) -> bool:
        return stream_client.connected

    @property
    def stats(self) -> dict:
        return {
            **stream_client.stats,
            "cached_markets": self.price_cache.market_count,
            "total_updates": self.price_cache.update_count,
        }

    async def start(self, session_token: str):
        """Start the stream connection and subscriptions."""
        self._session_token = session_token
        self._running = True

        # Set up callbacks
        stream_client.set_callbacks(
            on_market_change=self._on_market_change,
            on_order_change=self._on_order_change,
            on_connection_change=self._on_connection_change,
        )

        # Connect
        success = await stream_client.connect(session_token)
        if not success:
            logger.error("Failed to connect to stream")
            return False

        # Subscribe to markets and orders
        await stream_client.subscribe_markets()
        await stream_client.subscribe_orders()

        # Start listening
        self._listen_task = asyncio.create_task(
            stream_client.listen(),
            name="stream-listener"
        )

        self._reconnect_delay = 1.0
        logger.info("Stream manager started")
        return True

    async def stop(self):
        """Stop the stream connection."""
        self._running = False

        if self._reconnect_task and not self._reconnect_task.done():
            self._reconnect_task.cancel()

        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass

        await stream_client.disconnect()
        logger.info("Stream manager stopped")

    async def _reconnect(self):
        """Attempt to reconnect with exponential backoff."""
        while self._running:
            logger.info(
                f"Reconnecting in {self._reconnect_delay:.0f}s..."
            )
            await asyncio.sleep(self._reconnect_delay)

            if not self._running:
                break

            try:
                success = await stream_client.connect(self._session_token)
                if success:
                    await stream_client.subscribe_markets()
                    await stream_client.subscribe_orders()
                    self._listen_task = asyncio.create_task(
                        stream_client.listen(),
                        name="stream-listener"
                    )
                    self._reconnect_delay = 1.0
                    logger.info("Reconnected successfully")
                    return
            except Exception as e:
                logger.error(f"Reconnection attempt failed: {e}")

            # Exponential backoff
            self._reconnect_delay = min(
                self._reconnect_delay * 2,
                self._max_reconnect_delay
            )

    # ─────────────────────────────────────────────────────────
    # Callbacks from StreamClient
    # ─────────────────────────────────────────────────────────

    async def _on_market_change(self, msg: dict):
        """Handle market change messages — update cache and broadcast."""
        mc_list = msg.get("mc", [])

        for mc in mc_list:
            market_id = mc.get("id")
            if not market_id:
                continue

            # Update price cache
            market = self.price_cache.process_market_change(mc)

            # Archive raw stream data (if enabled)
            if config.ARCHIVE_ENABLED:
                try:
                    await db.archive_stream_data(
                        market_id=market_id,
                        event_type="price_update",
                        data=mc,
                    )
                except Exception as e:
                    logger.debug(f"Archive error: {e}")

            # Build runner data for WebSocket broadcast
            runners_ws = []
            for sel_id, runner_data in market.get("runners", {}).items():
                runners_ws.append({
                    "selectionId": sel_id,
                    "atb": runner_data.get("atb", [])[:3],  # Top 3 back prices
                    "atl": runner_data.get("atl", [])[:3],  # Top 3 lay prices
                    "ltp": runner_data.get("ltp"),
                    "tv": runner_data.get("tv", 0),
                })

            # Broadcast price update to WebSocket clients
            await broadcast_price_update(market_id, runners_ws)

            # Check for market status changes
            market_def = mc.get("marketDefinition")
            if market_def:
                status = market_def.get("status", "")
                in_play = market_def.get("inPlay", False)
                await broadcast_market_status(
                    market_id,
                    status,
                    inPlay=in_play,
                    marketTime=market_def.get("marketTime", ""),
                )

    async def _on_order_change(self, msg: dict):
        """Handle order change messages — update bet status and broadcast."""
        oc_list = msg.get("oc", [])

        for oc in oc_list:
            market_id = oc.get("id")
            for order_runner in oc.get("orc", []):
                sel_id = order_runner.get("id")
                for order in order_runner.get("uo", []):
                    bet_id = order.get("id")
                    status = order.get("status", "")
                    size_matched = order.get("sm", 0)
                    size_remaining = order.get("sr", 0)
                    price = order.get("p", 0)
                    avg_price = order.get("avp", 0)

                    # Update in database
                    try:
                        updates = {
                            "status": "MATCHED" if size_remaining == 0 else "PENDING",
                            "size_matched": size_matched,
                            "size_remaining": size_remaining,
                            "avg_price_matched": avg_price or price,
                        }
                        if status == "EC":  # Execution Complete
                            updates["status"] = "MATCHED"
                        elif status == "E":  # Executable (still live)
                            updates["status"] = "PENDING" if size_remaining > 0 else "MATCHED"

                        await db.update_bet(bet_id, updates)
                    except Exception as e:
                        logger.error(f"Failed to update bet {bet_id}: {e}")

                    # Broadcast to frontend
                    await broadcast_order_update({
                        "betId": bet_id,
                        "marketId": market_id,
                        "selectionId": sel_id,
                        "status": status,
                        "sizeMatched": size_matched,
                        "sizeRemaining": size_remaining,
                        "price": price,
                        "avgPriceMatched": avg_price,
                    })

    async def _on_connection_change(self, status: str):
        """Handle connection status changes."""
        if status == "disconnected" and self._running:
            logger.warning("Stream disconnected — starting reconnection")
            self._reconnect_task = asyncio.create_task(
                self._reconnect(),
                name="stream-reconnect"
            )


# Singleton
stream_manager = StreamManager()
