"""
CHIMERA v2 — Mark's Rule Set 1 Plugin
Lay betting strategy targeting 3.00-4.49 odds range.

Rules:
  1. Odds Filter: Only accept 3.00 ≤ odds ≤ 4.49
  2. Tiered Staking: PRIME (3.50-3.99) £3, STRONG (3.00-3.49) £2, SECONDARY (4.00-4.49) £2
  3. Time Filter: >420min = half stake
  4. Drift Filter (OPTIONAL toggle): Monitor odds drift post-placement

Risk Management:
  - Max £9 liability per bet
  - Max £75 daily exposure
  - Max -£25 daily stop-loss
  - Max 1 bet per race
  - Max 10 concurrent open bets
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

from plugins.base import BasePlugin
from models import PluginResult, BetCandidate

logger = logging.getLogger(__name__)

# Load config from JSON
_config_path = os.path.join(os.path.dirname(__file__), "marks_rule_1.json")


class MarksRule1Plugin(BasePlugin):
    """Mark's Rule Set 1 — Chimera Lay Mid-Range Contenders."""

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """Load strategy config from JSON file."""
        try:
            with open(_config_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Config file not found: {_config_path}, using defaults")
            return self._default_config()

    @staticmethod
    def _default_config() -> dict:
        """Fallback default config if JSON file is missing."""
        return {
            "strategy": {
                "name": "Chimera Lay Mid-Range Contenders",
                "version": "1.1.0",
            },
            "rules": {
                "rule_1_odds_filter": {
                    "enabled": True,
                    "conditions": {"min_odds": 3.00, "max_odds": 4.49},
                    "zones": {
                        "prime": {"min": 3.50, "max": 3.99},
                        "strong": {"min": 3.00, "max": 3.49},
                        "secondary": {"min": 4.00, "max": 4.49},
                    },
                },
                "rule_2_tiered_staking": {
                    "enabled": True,
                    "tiers": [
                        {"name": "PRIME", "condition": "odds >= 3.50 AND odds <= 3.99", "stake": 3.00},
                        {"name": "STRONG", "condition": "odds >= 3.00 AND odds <= 3.49", "stake": 2.00},
                        {"name": "SECONDARY", "condition": "odds >= 4.00 AND odds <= 4.49", "stake": 2.00},
                    ],
                },
                "rule_3_time_filter": {
                    "enabled": True,
                    "adjustments": [
                        {"condition": "time_to_race_minutes <= 120", "stake_modifier": 1.0},
                        {"condition": "time_to_race_minutes > 120 AND time_to_race_minutes <= 420", "stake_modifier": 1.0},
                        {"condition": "time_to_race_minutes > 420", "stake_modifier": 0.5},
                    ],
                },
                "rule_4_drift_filter": {
                    "enabled": False,
                    "conditions": {
                        "warning_threshold_percent": -5.0,
                        "alert_threshold_percent": -10.0,
                        "critical_threshold_percent": -20.0,
                    },
                },
            },
            "risk_management": {
                "liability": {"max_per_bet": 9.00, "max_daily_exposure": 75.00},
                "stop_loss": {"daily_limit": -25.00},
                "bet_limits": {"max_bets_per_race": 1, "max_concurrent_open_bets": 10},
            },
        }

    # ─────────────────────────────────────────────────────────
    # Plugin Interface
    # ─────────────────────────────────────────────────────────

    def get_id(self) -> str:
        return "marks_rule_1"

    def get_name(self) -> str:
        return "Mark's Rule Set 1"

    def get_version(self) -> str:
        return self._config.get("strategy", {}).get("version", "1.1.0")

    def get_author(self) -> str:
        return self._config.get("strategy", {}).get("author", "Cape Berkshire Ltd")

    def get_description(self) -> str:
        return self._config.get("strategy", {}).get(
            "description",
            "Lay betting strategy targeting market inefficiency in the 3.00-4.49 odds range"
        )

    def get_config(self) -> dict:
        return self._config

    # ─────────────────────────────────────────────────────────
    # Core Evaluation
    # ─────────────────────────────────────────────────────────

    def evaluate(
        self,
        runners: list[dict],
        market: dict,
        daily_pnl: float,
        daily_exposure: float,
        bets_today: list[dict],
        settings: dict,
    ) -> PluginResult:
        """
        Evaluate all runners in a market against Mark's Rule Set 1.

        Returns ACCEPT with candidates if any runners qualify,
        REJECT with reason if none do, SKIP if market is not suitable.
        """
        market_id = market.get("marketId", "")
        market_name = market.get("marketName", "")
        venue = market.get("venue", "")

        # ── Pre-checks ──

        # Skip in-play markets
        if market.get("inPlay", False):
            return PluginResult(
                action="SKIP",
                reason="Market is in-play",
            )

        # Skip if market is not OPEN
        if market.get("status", "") not in ("OPEN", ""):
            return PluginResult(
                action="SKIP",
                reason=f"Market status: {market.get('status')}",
            )

        # Check daily stop-loss
        stop_loss = settings.get("daily_stop_loss", -25.00)
        if daily_pnl <= stop_loss:
            return PluginResult(
                action="REJECT",
                reason=f"Daily stop-loss triggered (P/L: £{daily_pnl:.2f})",
            )

        # Check if already bet on this race
        race_bet_ids = [b.get("market_id") for b in bets_today if b.get("status") != "CANCELLED"]
        max_bets_per_race = settings.get("max_bets_per_race", 1)
        current_race_bets = sum(1 for bid in race_bet_ids if bid == market_id)
        if current_race_bets >= max_bets_per_race:
            return PluginResult(
                action="REJECT",
                reason=f"Already have {current_race_bets} bet(s) on this race",
            )

        # Check max concurrent bets
        max_concurrent = settings.get("max_concurrent_bets", 10)
        open_bets = [b for b in bets_today if b.get("status") in ("PENDING", "MATCHED") and not b.get("result")]
        if len(open_bets) >= max_concurrent:
            return PluginResult(
                action="REJECT",
                reason=f"Max concurrent bets reached ({max_concurrent})",
            )

        # Calculate time to race
        time_to_race_mins = self._calc_time_to_race(market)

        # ── Evaluate each runner ──

        candidates = []
        rejection_reasons = []

        for runner in runners:
            result = self._evaluate_runner(
                runner=runner,
                market_id=market_id,
                daily_exposure=daily_exposure,
                time_to_race_mins=time_to_race_mins,
                settings=settings,
            )
            if result:
                candidates.append(result)
            else:
                # Track why runners were rejected (for analysis)
                odds = self._get_lay_odds(runner)
                if odds:
                    rejection_reasons.append(
                        f"{runner.get('runnerName', '?')} @ {odds:.2f}"
                    )

        if candidates:
            # Sort by confidence (PRIME first, then STRONG, then SECONDARY)
            zone_priority = {"PRIME": 0, "STRONG": 1, "SECONDARY": 2}
            candidates.sort(key=lambda c: zone_priority.get(c.zone, 99))

            # Take the best candidate (1 per race)
            best = candidates[0]
            return PluginResult(
                action="ACCEPT",
                candidates=[best],
                analysis=f"Found {len(candidates)} qualifying runner(s) in {venue}. "
                          f"Best: {best.runner_name} @ {best.odds:.2f} ({best.zone})",
                reason=f"{best.zone} zone: {best.runner_name} @ {best.odds:.2f}",
            )
        else:
            return PluginResult(
                action="REJECT",
                reason=f"No runners in qualifying odds range ({len(rejection_reasons)} evaluated)",
                analysis=f"Rejected runners: {', '.join(rejection_reasons[:5])}" if rejection_reasons else "No eligible runners",
            )

    def _evaluate_runner(
        self,
        runner: dict,
        market_id: str,
        daily_exposure: float,
        time_to_race_mins: Optional[float],
        settings: dict,
    ) -> Optional[BetCandidate]:
        """
        Evaluate a single runner against all rules.
        Returns a BetCandidate if it passes, None if rejected.
        """
        runner_name = runner.get("runnerName", "Unknown")
        selection_id = runner.get("selectionId")
        odds = self._get_lay_odds(runner)

        if odds is None or selection_id is None:
            return None

        # ── Rule 1: Odds Filter ──
        rules = self._config.get("rules", {})
        odds_rule = rules.get("rule_1_odds_filter", {})
        if odds_rule.get("enabled", True):
            min_odds = odds_rule.get("conditions", {}).get("min_odds", 3.00)
            max_odds = odds_rule.get("conditions", {}).get("max_odds", 4.49)

            if odds < min_odds or odds > max_odds:
                return None

        # ── Rule 2: Determine zone and stake ──
        zone, stake = self._determine_zone_and_stake(odds)
        if zone is None:
            return None

        # ── Rule 3: Time filter (adjust stake) ──
        # >420 min to race = half stake (Betfair accepts £1 minimum)
        # PRIME £3 → £1.50, STRONG £2 → £1, SECONDARY £2 → £1
        time_rule = rules.get("rule_3_time_filter", {})
        if time_rule.get("enabled", True) and time_to_race_mins is not None:
            if time_to_race_mins > 420:
                stake = stake * 0.5

        # Round stake
        stake = round(stake, 2)

        # ── Calculate liability ──
        liability = round(stake * (odds - 1), 2)

        # ── Risk checks ──
        max_liability = settings.get("max_liability_per_bet", 9.00)
        if liability > max_liability:
            return None

        max_daily = settings.get("max_daily_exposure", 75.00)
        if daily_exposure + liability > max_daily:
            return None

        # ── Build candidate ──
        confidence = "HIGH" if zone == "PRIME" else ("MEDIUM-HIGH" if zone == "STRONG" else "MEDIUM")

        return BetCandidate(
            runner_name=runner_name,
            selection_id=selection_id,
            market_id=market_id,
            odds=odds,
            stake=stake,
            liability=liability,
            zone=zone,
            confidence=confidence,
            reason=f"{zone} zone @ {odds:.2f}, stake £{stake:.2f}, liability £{liability:.2f}",
        )

    def _determine_zone_and_stake(self, odds: float) -> tuple[Optional[str], float]:
        """Determine the zone and base stake for given odds."""
        tiers = (
            self._config
            .get("rules", {})
            .get("rule_2_tiered_staking", {})
            .get("tiers", [])
        )

        if tiers:
            for tier in tiers:
                name = tier.get("name", "")
                base_stake = tier.get("stake", 0)

                if name == "PRIME" and 3.50 <= odds <= 3.99:
                    return "PRIME", base_stake
                elif name == "STRONG" and 3.00 <= odds <= 3.49:
                    return "STRONG", base_stake
                elif name == "SECONDARY" and 4.00 <= odds <= 4.49:
                    return "SECONDARY", base_stake
        else:
            # Defaults if config is missing
            if 3.50 <= odds <= 3.99:
                return "PRIME", 3.00
            elif 3.00 <= odds <= 3.49:
                return "STRONG", 2.00
            elif 4.00 <= odds <= 4.49:
                return "SECONDARY", 2.00

        return None, 0

    @staticmethod
    def _get_lay_odds(runner: dict) -> Optional[float]:
        """Get the best available lay odds for a runner."""
        atl = runner.get("atl", [])
        if atl:
            # Best lay = lowest price in the atl ladder
            return min(atl, key=lambda x: x[0])[0]

        # Fallback to LTP
        ltp = runner.get("ltp")
        return ltp

    @staticmethod
    def _calc_time_to_race(market: dict) -> Optional[float]:
        """Calculate minutes until race start."""
        market_time = market.get("marketStartTime") or market.get("marketTime")
        if not market_time:
            return None

        try:
            if isinstance(market_time, str):
                # Handle various ISO formats
                market_time = market_time.replace("Z", "+00:00")
                start = datetime.fromisoformat(market_time)
            else:
                return None

            now = datetime.now(timezone.utc)
            delta = (start - now).total_seconds() / 60
            return max(0, delta)
        except (ValueError, TypeError):
            return None
