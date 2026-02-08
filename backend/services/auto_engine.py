"""
CHIMERA v2 Auto-Betting Engine
Background async task that evaluates markets against active plugins
and places bets automatically via the Betfair REST API.

Key features:
- Reads from Stream API price cache (no HTTP polling)
- Runs as asyncio background task within FastAPI lifespan
- Survives frontend tab close
- State persisted in SQLite auto_session table
- Evaluates all active plugins in priority order (stackable)
- Full decision logging for every evaluation
- STAGING mode: runs full pipeline without placing real bets
- GO LIVE: switch from staging to live without restarting
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from config import config
from services.betfair_client import betfair_client, BetfairAPIError
from services.stream_manager import stream_manager
from services.plugin_loader import plugin_loader
from routers.websocket import broadcast_engine_status, broadcast_engine_activity
from models import PluginResult, BetCandidate
import database as db

logger = logging.getLogger(__name__)

# Engine modes
MODE_STOPPED = "STOPPED"
MODE_STAGING = "STAGING"
MODE_LIVE = "LIVE"
MODE_PAUSED = "PAUSED"


class AutoBettingEngine:
    """
    Background auto-betting engine.

    Modes:
    - STOPPED: Engine not running
    - STAGING: Full evaluation pipeline runs, bets recorded as STAGED
              (no real money). Everything visible in UI.
    - LIVE:   Real bets placed via Betfair API.
    - PAUSED: Engine loop still alive but skips scanning. Resume instantly.

    Flow:
    1. Periodically scan the price cache for eligible markets
    2. For each market, check if already processed / bet placed
    3. Run active plugins in priority order
    4. If STAGING → record simulated bet (source=STAGED)
    5. If LIVE → place real bet via REST API (source=AUTO)
    6. Record everything to SQLite
    7. Broadcast status to frontend via WebSocket
    """

    def __init__(self):
        self._running = False
        self._mode = MODE_STOPPED
        self._task: Optional[asyncio.Task] = None
        self._settings: Dict[str, Any] = {
            "max_liability_per_bet": config.DEFAULT_MAX_LIABILITY_PER_BET,
            "max_daily_exposure": config.DEFAULT_MAX_DAILY_EXPOSURE,
            "daily_stop_loss": config.DEFAULT_DAILY_STOP_LOSS,
            "max_concurrent_bets": config.DEFAULT_MAX_CONCURRENT_BETS,
            "max_bets_per_race": config.DEFAULT_MAX_BETS_PER_RACE,
        }
        self._pre_pause_mode: str = MODE_STAGING  # mode to resume to after pause
        self._scan_interval = 2.0  # seconds between scans
        self._processed_markets: set = set()

        # Runner name + market info caches
        # (Stream API doesn't include runner names in marketDefinition,
        #  so we fetch them once from REST catalogue and cache them)
        self._runner_names: Dict[str, Dict[int, str]] = {}   # market_id → {sel_id → name}
        self._market_meta: Dict[str, Dict[str, Any]] = {}    # market_id → {venue, name, startTime}
        self._catalogue_fetched = False  # True once we've fetched catalogue this session
        self._last_catalogue_fetch: float = 0  # timestamp of last fetch

        self._stats = {
            "scans": 0,
            "evaluations": 0,
            "bets_placed": 0,
            "bets_staged": 0,
            "errors": 0,
            "last_scan": None,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def is_staging(self) -> bool:
        return self._mode == MODE_STAGING

    @property
    def is_live(self) -> bool:
        return self._mode == MODE_LIVE

    @property
    def is_paused(self) -> bool:
        return self._mode == MODE_PAUSED

    @property
    def stats(self) -> dict:
        return {**self._stats, "is_running": self._running, "mode": self._mode}

    def update_settings(self, settings: dict):
        """Update engine settings."""
        self._settings.update(settings)
        logger.info(f"Engine settings updated: {settings}")

    async def start(self, mode: str = MODE_STAGING):
        """Start the auto-betting engine in the given mode."""
        if self._running:
            logger.warning("Engine already running")
            return

        if mode not in (MODE_STAGING, MODE_LIVE):
            mode = MODE_STAGING

        self._mode = mode

        # Reset catalogue caches for fresh start
        self._runner_names.clear()
        self._market_meta.clear()
        self._catalogue_fetched = False
        self._last_catalogue_fetch = 0

        # Load settings from DB
        session = await db.get_auto_session()
        if session.get("settings"):
            self._settings.update(session["settings"])

        # Load processed markets (clear if starting in LIVE mode —
        # we want a fresh evaluation, not leftover staging state)
        if mode == MODE_LIVE:
            self._processed_markets = set()
        else:
            self._processed_markets = set(session.get("processed_markets", []))

        # Reset daily if needed
        await db.reset_auto_session_daily()

        # Seed processed markets from Betfair current orders
        # Prevents double-betting on markets we already have bets on
        await self._seed_from_betfair_orders()

        # Ensure stream is connected — engine needs price data to scan
        if not stream_manager.is_connected and betfair_client.session_token:
            logger.info("Stream not connected — starting before engine scan")
            try:
                await stream_manager.start(betfair_client.session_token)
                logger.info("Stream started for engine")
            except Exception as e:
                logger.warning(f"Stream start failed: {e} — will use REST fallback")

        self._running = True
        self._task = asyncio.create_task(
            self._run_loop(),
            name="auto-betting-engine"
        )

        # Update DB
        await db.update_auto_session({"is_running": 1})

        logger.info(f"Auto-betting engine STARTED in {mode} mode")
        await broadcast_engine_status({
            "is_running": True,
            "mode": mode,
            "message": f"Engine started in {mode} mode",
        })

    async def stop(self):
        """Stop the auto-betting engine."""
        self._running = False
        prev_mode = self._mode
        self._mode = MODE_STOPPED

        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Update DB
        await db.update_auto_session({
            "is_running": 0,
            "processed_markets": list(self._processed_markets),
        })

        logger.info(f"Auto-betting engine STOPPED (was {prev_mode})")
        await broadcast_engine_status({
            "is_running": False,
            "mode": MODE_STOPPED,
            "message": "Engine stopped",
        })

    async def go_live(self):
        """Switch from STAGING to LIVE mode without restarting.

        Clears processed_markets so the engine re-evaluates all markets
        for real bets — staged bets won't block live ones.
        """
        if not self._running:
            logger.warning("Engine not running — cannot go live")
            return False

        if self._mode == MODE_LIVE:
            logger.info("Already in LIVE mode")
            return True

        # Clear processed markets so engine re-scans everything for real bets
        prev_count = len(self._processed_markets)
        self._processed_markets.clear()
        logger.info(f"Cleared {prev_count} processed markets for live re-evaluation")

        self._mode = MODE_LIVE
        logger.info("Engine switched to LIVE mode — real bets will be placed")
        await broadcast_engine_status({
            "is_running": True,
            "mode": MODE_LIVE,
            "message": "Engine switched to LIVE — real bets active",
        })
        await broadcast_engine_activity({
            "type": "mode_change",
            "mode": MODE_LIVE,
            "message": "Switched to LIVE mode",
        })
        return True

    async def go_staging(self):
        """Switch from LIVE back to STAGING mode without restarting."""
        if not self._running:
            logger.warning("Engine not running — cannot switch to staging")
            return False

        if self._mode == MODE_STAGING:
            logger.info("Already in STAGING mode")
            return True

        self._mode = MODE_STAGING
        logger.info("Engine switched to STAGING mode — no real bets")
        await broadcast_engine_status({
            "is_running": True,
            "mode": MODE_STAGING,
            "message": "Engine switched to STAGING — simulated bets only",
        })
        await broadcast_engine_activity({
            "type": "mode_change",
            "mode": MODE_STAGING,
            "message": "Switched to STAGING mode",
        })
        return True

    async def pause(self):
        """Pause the engine — loop stays alive but skips scanning."""
        if not self._running:
            logger.warning("Engine not running — cannot pause")
            return False

        if self._mode == MODE_PAUSED:
            logger.info("Already paused")
            return True

        self._pre_pause_mode = self._mode  # remember so we can resume to same mode
        self._mode = MODE_PAUSED
        logger.info(f"Engine PAUSED (was {self._pre_pause_mode})")
        await broadcast_engine_status({
            "is_running": True,
            "mode": MODE_PAUSED,
            "message": "Engine paused",
        })
        await broadcast_engine_activity({
            "type": "mode_change",
            "mode": MODE_PAUSED,
            "message": "Engine paused",
        })
        return True

    async def resume(self):
        """Resume from PAUSED back to whatever mode was active before."""
        if not self._running:
            logger.warning("Engine not running — cannot resume")
            return False

        if self._mode != MODE_PAUSED:
            logger.info(f"Not paused (mode={self._mode}), nothing to resume")
            return True

        resume_to = getattr(self, "_pre_pause_mode", MODE_STAGING)
        self._mode = resume_to
        logger.info(f"Engine RESUMED to {resume_to} mode")
        await broadcast_engine_status({
            "is_running": True,
            "mode": resume_to,
            "message": f"Engine resumed in {resume_to} mode",
        })
        await broadcast_engine_activity({
            "type": "mode_change",
            "mode": resume_to,
            "message": f"Resumed — {resume_to} mode",
        })
        return True

    async def reload_plugins(self):
        """Reload plugins (called when plugin config changes)."""
        await plugin_loader.reload()
        logger.info("Plugins reloaded by engine")

    # ─────────────────────────────────────────────────────────
    # Main Loop
    # ─────────────────────────────────────────────────────────

    async def _run_loop(self):
        """Main engine loop — scan price cache and evaluate."""
        logger.info("Engine loop started")

        while self._running:
            try:
                if self._mode == MODE_PAUSED:
                    # Paused — skip scanning, just sleep
                    await asyncio.sleep(self._scan_interval)
                    continue

                await self._scan_markets()
                self._stats["scans"] += 1
                self._stats["last_scan"] = datetime.now(timezone.utc).isoformat()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._stats["errors"] += 1
                logger.error(f"Engine scan error: {e}", exc_info=True)

            # Wait before next scan
            await asyncio.sleep(self._scan_interval)

        logger.info("Engine loop ended")

    async def _seed_from_betfair_orders(self):
        """Fetch current orders from Betfair to prevent double-betting.

        On engine start, checks Betfair for any existing matched/pending
        orders and adds those market IDs to _processed_markets so the
        engine won't place duplicate bets.
        """
        if not betfair_client.session_token:
            return

        try:
            result = await betfair_client.list_current_orders()
            orders = result.get("currentOrders", [])
            if not orders:
                logger.info("No existing Betfair orders found")
                return

            seeded = set()
            for order in orders:
                market_id = order.get("marketId")
                if market_id:
                    seeded.add(market_id)
                    self._processed_markets.add(market_id)

            if seeded:
                logger.info(
                    f"Seeded {len(seeded)} markets from Betfair current orders "
                    f"(prevents double-betting)"
                )

        except BetfairAPIError as e:
            logger.warning(f"Failed to fetch current orders: {e.message}")
        except Exception as e:
            logger.error(f"Failed to fetch current orders: {e}", exc_info=True)

    async def _fetch_catalogue_metadata(self):
        """Fetch runner names, venues, and market info from REST catalogue.

        The Betfair Stream API does NOT include runner names in its
        marketDefinition — only selectionId, status, sortPriority.
        So we fetch the catalogue via REST once (and refresh periodically)
        to populate the caches used during scanning.
        """
        if not betfair_client.session_token:
            return

        try:
            catalogue = await betfair_client.list_market_catalogue(max_results=500)
            if not catalogue:
                return

            count = 0
            for cat in catalogue:
                mid = cat.get("marketId")
                if not mid:
                    continue

                # Cache runner names
                if mid not in self._runner_names:
                    self._runner_names[mid] = {}
                for runner in cat.get("runners", []):
                    sel_id = runner.get("selectionId")
                    name = runner.get("runnerName", "Unknown")
                    if sel_id is not None:
                        self._runner_names[mid][sel_id] = name

                # Cache market metadata (venue, name, start time)
                event = cat.get("event", {})
                self._market_meta[mid] = {
                    "venue": event.get("venue", "") or cat.get("venue", ""),
                    "name": cat.get("marketName", ""),
                    "startTime": cat.get("marketStartTime", ""),
                    "countryCode": event.get("countryCode", cat.get("countryCode", "")),
                }
                count += 1

            self._catalogue_fetched = True
            self._last_catalogue_fetch = time.time()
            logger.info(f"Catalogue metadata cached: {count} markets, "
                        f"{sum(len(v) for v in self._runner_names.values())} runners")

        except BetfairAPIError as e:
            logger.warning(f"Catalogue metadata fetch error: {e.message}")
        except Exception as e:
            logger.error(f"Catalogue metadata fetch error: {e}", exc_info=True)

    def _get_runner_name(self, market_id: str, selection_id: int) -> str:
        """Look up a runner name from the cached catalogue data."""
        market_runners = self._runner_names.get(market_id, {})
        return market_runners.get(selection_id, "Unknown")

    def _get_market_meta(self, market_id: str) -> Dict[str, Any]:
        """Look up market metadata (venue, name, startTime) from cache."""
        return self._market_meta.get(market_id, {})

    async def _scan_markets(self):
        """Scan all cached markets and evaluate eligible ones.

        Primary source: Stream API price cache (real-time).
        Fallback: REST API listMarketCatalogue + listMarketBook (every scan).
        """
        cache = stream_manager.price_cache
        markets = cache.get_all_markets()

        # Fetch catalogue metadata (runner names, venues) if not cached yet
        # or refresh every 5 minutes. Stream API doesn't include runner names.
        if not self._catalogue_fetched or (time.time() - self._last_catalogue_fetch > 300):
            await self._fetch_catalogue_metadata()

        if not markets:
            # Stream cache empty — fall back to REST API
            markets = await self._fetch_markets_rest()
            if not markets:
                return

        # Get today's bets and stats
        # In LIVE mode, exclude STAGED bets so they don't count towards
        # per-race limits or concurrent bet caps
        all_today_bets = await db.get_today_bets()
        if self._mode == MODE_LIVE:
            today_bets = [b for b in all_today_bets if b.get("source") != "STAGED"]
        else:
            today_bets = all_today_bets
        today_stats = await db.get_daily_stats()
        daily_pnl = today_stats.get("profit_loss", 0)
        daily_exposure = today_stats.get("exposure", 0)

        # Check daily stop-loss before scanning
        if daily_pnl <= self._settings.get("daily_stop_loss", -25.00):
            return

        # Get active plugins
        active_plugins = await plugin_loader.get_active_plugins()
        if not active_plugins:
            return

        for market_id, market_data in markets.items():
            # Skip if already processed
            if market_id in self._processed_markets:
                continue

            # Skip if not OPEN
            status = market_data.get("status", "")
            if status not in ("OPEN", ""):
                if status in ("CLOSED", "COMPLETE"):
                    self._processed_markets.add(market_id)
                continue

            # Skip in-play
            if market_data.get("inPlay", False):
                continue

            # Check duplicate — already bet on this market?
            # In LIVE mode, ignore STAGED bets so we can place real ones
            has_bet = await db.has_bet_on_market(
                market_id,
                exclude_staged=(self._mode == MODE_LIVE),
            )
            if has_bet:
                self._processed_markets.add(market_id)
                continue

            # Build market info — use cached catalogue metadata for
            # venue/name/startTime since stream doesn't always have these
            market_def = market_data.get("marketDefinition", {})
            meta = self._get_market_meta(market_id)

            # Prefer catalogue metadata, fall back to stream marketDefinition
            market_info = {
                "marketId": market_id,
                "marketName": meta.get("name") or market_def.get("name", ""),
                "venue": meta.get("venue") or market_def.get("venue", ""),
                "countryCode": meta.get("countryCode") or market_def.get("countryCode", ""),
                "marketStartTime": meta.get("startTime") or market_def.get("marketTime", ""),
                "status": status,
                "inPlay": False,
            }

            # Build runners list with live prices
            # Runner names come from REST catalogue cache (stream doesn't include them)
            runners = []
            for sel_id, runner_data in market_data.get("runners", {}).items():
                # Look up runner name from cached catalogue data
                runner_name = self._get_runner_name(market_id, sel_id)

                # Fallback: try stream marketDefinition (rarely has names, but just in case)
                if runner_name == "Unknown":
                    for rd in market_def.get("runners", []):
                        if rd.get("id") == sel_id:
                            runner_name = rd.get("name", rd.get("runnerName", "Unknown"))
                            break

                runners.append({
                    "selectionId": sel_id,
                    "runnerName": runner_name,
                    "atb": runner_data.get("atb", []),
                    "atl": runner_data.get("atl", []),
                    "ltp": runner_data.get("ltp"),
                    "tv": runner_data.get("tv", 0),
                })

            if not runners:
                continue

            # ── Evaluate plugins ──
            self._stats["evaluations"] += 1

            for plugin in active_plugins:
                try:
                    result = plugin.evaluate(
                        runners=runners,
                        market=market_info,
                        daily_pnl=daily_pnl,
                        daily_exposure=daily_exposure,
                        bets_today=today_bets,
                        settings=self._settings,
                    )

                    # Log the decision
                    await self._log_decision(
                        market_info=market_info,
                        plugin=plugin,
                        result=result,
                        runners=runners,
                        daily_pnl=daily_pnl,
                        daily_exposure=daily_exposure,
                        bets_today_count=len(today_bets),
                    )

                    if result.action == "ACCEPT" and result.candidates:
                        candidate = result.candidates[0]

                        if self._mode == MODE_LIVE:
                            # LIVE — place real bet via Betfair API
                            success = await self._place_bet(
                                candidate=candidate,
                                market_info=market_info,
                                plugin=plugin,
                            )
                            if success:
                                self._processed_markets.add(market_id)
                                self._stats["bets_placed"] += 1
                        else:
                            # STAGING — record simulated bet, no real money
                            await self._stage_bet(
                                candidate=candidate,
                                market_info=market_info,
                                plugin=plugin,
                            )
                            self._processed_markets.add(market_id)
                            self._stats["bets_staged"] += 1

                        # Refresh daily stats (exclude staged in LIVE mode)
                        all_today_bets = await db.get_today_bets()
                        if self._mode == MODE_LIVE:
                            today_bets = [b for b in all_today_bets if b.get("source") != "STAGED"]
                        else:
                            today_bets = all_today_bets
                        today_stats = await db.get_daily_stats()
                        daily_pnl = today_stats.get("profit_loss", 0)
                        daily_exposure = today_stats.get("exposure", 0)

                        break  # Don't evaluate more plugins for this market

                    elif result.action == "REJECT":
                        # Rejected — try next plugin in stack
                        continue

                    elif result.action == "SKIP":
                        # Skip — try next plugin
                        continue

                except Exception as e:
                    logger.error(
                        f"Plugin {plugin.get_id()} error on {market_id}: {e}",
                        exc_info=True,
                    )

        # Periodically persist processed markets
        if self._stats["scans"] % 10 == 0:
            await db.update_auto_session({
                "processed_markets": list(self._processed_markets),
            })

    # ─────────────────────────────────────────────────────────
    # REST API Fallback
    # ─────────────────────────────────────────────────────────

    async def _fetch_markets_rest(self) -> dict:
        """Fetch markets + prices via Betfair REST API when stream cache is empty."""
        if not betfair_client.session_token:
            return {}

        try:
            # 1. Get today's market catalogue
            catalogue = await betfair_client.list_market_catalogue(max_results=100)
            if not catalogue:
                return {}

            market_ids = [m["marketId"] for m in catalogue]

            # 2. Get market books with prices (batch of up to 40)
            all_books = []
            for i in range(0, len(market_ids), 40):
                batch = market_ids[i:i+40]
                books = await betfair_client.list_market_book(
                    market_ids=batch,
                    price_projection=["EX_BEST_OFFERS"],
                )
                all_books.extend(books)

            # 3. Build a dict matching the stream cache format
            # so the rest of _scan_markets can work unchanged
            markets = {}
            catalogue_by_id = {m["marketId"]: m for m in catalogue}

            for book in all_books:
                mid = book.get("marketId")
                cat = catalogue_by_id.get(mid, {})
                event = cat.get("event", {})
                venue = event.get("venue", "") or cat.get("venue", "")

                # Build runners dict keyed by selectionId
                runners = {}
                for r in book.get("runners", []):
                    sel_id = r.get("selectionId")
                    ex = r.get("ex", {})
                    # Convert REST format {price,size}[] → stream format [[price,size],...]
                    atb = [[p["price"], p["size"]] for p in ex.get("availableToBack", [])]
                    atl = [[p["price"], p["size"]] for p in ex.get("availableToLay", [])]
                    runners[sel_id] = {
                        "atb": atb,
                        "atl": atl,
                        "ltp": r.get("lastPriceTraded"),
                        "tv": r.get("totalMatched", 0),
                    }

                # Build runner definitions for name lookup
                runner_defs = []
                if mid not in self._runner_names:
                    self._runner_names[mid] = {}
                for cr in cat.get("runners", []):
                    sel_id = cr.get("selectionId")
                    name = cr.get("runnerName", "Unknown")
                    runner_defs.append({
                        "id": sel_id,
                        "name": name,
                    })
                    # Also populate the runner name cache
                    if sel_id is not None:
                        self._runner_names[mid][sel_id] = name

                # Populate market meta cache
                self._market_meta[mid] = {
                    "venue": venue,
                    "name": cat.get("marketName", ""),
                    "startTime": cat.get("marketStartTime", ""),
                    "countryCode": event.get("countryCode", cat.get("countryCode", "")),
                }

                markets[mid] = {
                    "status": book.get("status", "OPEN"),
                    "inPlay": book.get("inplay", False),
                    "runners": runners,
                    "marketDefinition": {
                        "name": cat.get("marketName", ""),
                        "venue": venue,
                        "countryCode": event.get("countryCode", ""),
                        "marketTime": cat.get("marketStartTime", ""),
                        "runners": runner_defs,
                    },
                }

            self._catalogue_fetched = True
            self._last_catalogue_fetch = time.time()
            logger.info(f"REST fallback: fetched {len(markets)} markets with prices")
            return markets

        except BetfairAPIError as e:
            logger.warning(f"REST fallback error: {e.message}")
            return {}
        except Exception as e:
            logger.error(f"REST fallback error: {e}", exc_info=True)
            return {}

    # ─────────────────────────────────────────────────────────
    # Bet Placement
    # ─────────────────────────────────────────────────────────

    async def _place_bet(
        self,
        candidate: BetCandidate,
        market_info: dict,
        plugin: Any,
    ) -> bool:
        """Place a bet via the Betfair REST API and record it."""
        try:
            logger.info(
                f"AUTO BET: {market_info.get('venue', '?')} | "
                f"{candidate.runner_name} | {candidate.odds:.2f} | "
                f"£{candidate.stake:.2f} | {candidate.zone} | "
                f"Plugin: {plugin.get_id()}"
            )

            # Place via REST API
            result = await betfair_client.place_orders(
                market_id=candidate.market_id,
                selection_id=candidate.selection_id,
                odds=candidate.odds,
                stake=candidate.stake,
                side="LAY",
                persistence_type="LAPSE",
            )

            # Extract response details
            status = result.get("status", "FAILURE")
            instruction_reports = result.get("instructionReports", [])
            bet_id = None
            size_matched = 0
            avg_price = 0

            if instruction_reports:
                report = instruction_reports[0]
                bet_id = report.get("betId")
                size_matched = report.get("sizeMatched", 0)
                avg_price = report.get("averagePriceMatched", 0)

            if status == "SUCCESS":
                # Record to database
                bet_data = {
                    "bet_id": bet_id,
                    "market_id": candidate.market_id,
                    "market_name": market_info.get("marketName"),
                    "venue": market_info.get("venue"),
                    "country_code": market_info.get("countryCode"),
                    "race_time": market_info.get("marketStartTime"),
                    "selection_id": candidate.selection_id,
                    "runner_name": candidate.runner_name,
                    "side": "LAY",
                    "stake": candidate.stake,
                    "odds": candidate.odds,
                    "liability": candidate.liability,
                    "zone": candidate.zone,
                    "confidence": candidate.confidence,
                    "rule_id": plugin.get_id(),
                    "persistence_type": "LAPSE",
                    "status": "MATCHED" if size_matched > 0 else "PENDING",
                    "size_matched": size_matched,
                    "size_remaining": candidate.stake - size_matched,
                    "avg_price_matched": avg_price if avg_price else None,
                    "source": "AUTO",
                    "raw_response": json.dumps(result),
                }
                await db.insert_bet(bet_data)

                # Broadcast to frontend
                await broadcast_engine_activity({
                    "type": "bet_placed",
                    "bet_id": bet_id,
                    "market_id": candidate.market_id,
                    "venue": market_info.get("venue"),
                    "runner_name": candidate.runner_name,
                    "odds": candidate.odds,
                    "stake": candidate.stake,
                    "liability": candidate.liability,
                    "zone": candidate.zone,
                    "confidence": candidate.confidence,
                    "plugin": plugin.get_id(),
                    "status": "MATCHED" if size_matched > 0 else "PENDING",
                })

                logger.info(f"AUTO BET PLACED: bet_id={bet_id} status={status}")
                return True

            else:
                # Placement failed
                error_msg = str(instruction_reports[0] if instruction_reports else result)
                logger.warning(f"AUTO BET FAILED: {error_msg}")

                await broadcast_engine_activity({
                    "type": "bet_failed",
                    "market_id": candidate.market_id,
                    "runner_name": candidate.runner_name,
                    "reason": error_msg[:200],
                })
                return False

        except BetfairAPIError as e:
            logger.error(f"Betfair API error placing auto bet: {e.message}")
            self._stats["errors"] += 1
            return False
        except Exception as e:
            logger.error(f"Error placing auto bet: {e}", exc_info=True)
            self._stats["errors"] += 1
            return False

    # ─────────────────────────────────────────────────────────
    # Staged (Simulated) Bet
    # ─────────────────────────────────────────────────────────

    async def _stage_bet(
        self,
        candidate: BetCandidate,
        market_info: dict,
        plugin: Any,
    ):
        """Record a simulated bet — no real money, just logged for review."""
        logger.info(
            f"STAGED BET: {market_info.get('venue', '?')} | "
            f"{candidate.runner_name} | {candidate.odds:.2f} | "
            f"£{candidate.stake:.2f} | {candidate.zone} | "
            f"Plugin: {plugin.get_id()}"
        )

        # Generate a fake staged bet ID
        staged_id = f"STAGED-{int(time.time() * 1000)}"

        bet_data = {
            "bet_id": staged_id,
            "market_id": candidate.market_id,
            "market_name": market_info.get("marketName"),
            "venue": market_info.get("venue"),
            "country_code": market_info.get("countryCode"),
            "race_time": market_info.get("marketStartTime"),
            "selection_id": candidate.selection_id,
            "runner_name": candidate.runner_name,
            "side": "LAY",
            "stake": candidate.stake,
            "odds": candidate.odds,
            "liability": candidate.liability,
            "zone": candidate.zone,
            "confidence": candidate.confidence,
            "rule_id": plugin.get_id(),
            "persistence_type": "LAPSE",
            "status": "STAGED",
            "size_matched": 0,
            "size_remaining": candidate.stake,
            "source": "STAGED",
        }
        await db.insert_bet(bet_data)

        # Broadcast to frontend
        await broadcast_engine_activity({
            "type": "bet_staged",
            "bet_id": staged_id,
            "market_id": candidate.market_id,
            "venue": market_info.get("venue"),
            "runner_name": candidate.runner_name,
            "odds": candidate.odds,
            "stake": candidate.stake,
            "liability": candidate.liability,
            "zone": candidate.zone,
            "confidence": candidate.confidence,
            "plugin": plugin.get_id(),
            "status": "STAGED",
        })

    # ─────────────────────────────────────────────────────────
    # Decision Logging
    # ─────────────────────────────────────────────────────────

    async def _log_decision(
        self,
        market_info: dict,
        plugin: Any,
        result: PluginResult,
        runners: list,
        daily_pnl: float,
        daily_exposure: float,
        bets_today_count: int,
    ):
        """Log every evaluation decision to the database."""
        try:
            # Calculate time to race
            time_to_race = None
            market_time = market_info.get("marketStartTime")
            if market_time:
                try:
                    mt = market_time.replace("Z", "+00:00")
                    start = datetime.fromisoformat(mt)
                    delta = (start - datetime.now(timezone.utc)).total_seconds() / 60
                    time_to_race = max(0, delta)
                except (ValueError, TypeError):
                    pass

            decision = {
                "market_id": market_info.get("marketId"),
                "market_name": market_info.get("marketName"),
                "venue": market_info.get("venue"),
                "race_time": market_info.get("marketStartTime"),
                "plugin_id": plugin.get_id(),
                "action": result.action,
                "reason": result.reason[:500] if result.reason else None,
                "runners_snapshot": runners,
                "candidates": [c.model_dump() for c in result.candidates] if result.candidates else [],
                "daily_pnl": daily_pnl,
                "daily_exposure": daily_exposure,
                "bets_today_count": bets_today_count,
                "time_to_race_minutes": time_to_race,
            }

            await db.insert_decision_log(decision)

        except Exception as e:
            logger.debug(f"Decision log error: {e}")


# Singleton
auto_engine = AutoBettingEngine()
