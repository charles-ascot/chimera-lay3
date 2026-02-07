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


class AutoBettingEngine:
    """
    Background auto-betting engine.

    Flow:
    1. Periodically scan the price cache for eligible markets
    2. For each market, check if already processed / bet placed
    3. Run active plugins in priority order
    4. If a plugin returns ACCEPT → place bet via REST API
    5. Record everything to SQLite
    6. Broadcast status to frontend via WebSocket
    """

    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._settings: Dict[str, Any] = {
            "max_liability_per_bet": config.DEFAULT_MAX_LIABILITY_PER_BET,
            "max_daily_exposure": config.DEFAULT_MAX_DAILY_EXPOSURE,
            "daily_stop_loss": config.DEFAULT_DAILY_STOP_LOSS,
            "max_concurrent_bets": config.DEFAULT_MAX_CONCURRENT_BETS,
            "max_bets_per_race": config.DEFAULT_MAX_BETS_PER_RACE,
        }
        self._scan_interval = 2.0  # seconds between scans
        self._processed_markets: set = set()
        self._stats = {
            "scans": 0,
            "evaluations": 0,
            "bets_placed": 0,
            "errors": 0,
            "last_scan": None,
        }

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def stats(self) -> dict:
        return {**self._stats, "is_running": self._running}

    def update_settings(self, settings: dict):
        """Update engine settings."""
        self._settings.update(settings)
        logger.info(f"Engine settings updated: {settings}")

    async def start(self):
        """Start the auto-betting engine."""
        if self._running:
            logger.warning("Engine already running")
            return

        # Load settings from DB
        session = await db.get_auto_session()
        if session.get("settings"):
            self._settings.update(session["settings"])

        # Load processed markets
        self._processed_markets = set(session.get("processed_markets", []))

        # Reset daily if needed
        await db.reset_auto_session_daily()

        self._running = True
        self._task = asyncio.create_task(
            self._run_loop(),
            name="auto-betting-engine"
        )

        # Update DB
        await db.update_auto_session({"is_running": 1})

        logger.info("Auto-betting engine STARTED")
        await broadcast_engine_status({"is_running": True, "message": "Engine started"})

    async def stop(self):
        """Stop the auto-betting engine."""
        self._running = False

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

        logger.info("Auto-betting engine STOPPED")
        await broadcast_engine_status({"is_running": False, "message": "Engine stopped"})

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

    async def _scan_markets(self):
        """Scan all cached markets and evaluate eligible ones."""
        cache = stream_manager.price_cache
        markets = cache.get_all_markets()

        if not markets:
            return

        # Get today's bets and stats
        today_bets = await db.get_today_bets()
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
            has_bet = await db.has_bet_on_market(market_id)
            if has_bet:
                self._processed_markets.add(market_id)
                continue

            # Build market info
            market_def = market_data.get("marketDefinition", {})
            market_info = {
                "marketId": market_id,
                "marketName": market_def.get("name", ""),
                "venue": market_def.get("venue", ""),
                "countryCode": market_def.get("countryCode", ""),
                "marketStartTime": market_def.get("marketTime", ""),
                "status": status,
                "inPlay": False,
            }

            # Build runners list with live prices
            runners = []
            for sel_id, runner_data in market_data.get("runners", {}).items():
                # Get runner name from definition
                runner_name = "Unknown"
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
                        # Place the bet!
                        candidate = result.candidates[0]
                        success = await self._place_bet(
                            candidate=candidate,
                            market_info=market_info,
                            plugin=plugin,
                        )

                        if success:
                            self._processed_markets.add(market_id)
                            self._stats["bets_placed"] += 1

                            # Refresh daily stats
                            today_bets = await db.get_today_bets()
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
