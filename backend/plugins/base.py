"""
CHIMERA v2 Plugin Base Class
Standard interface for all betting strategy plugins.
"""

from abc import ABC, abstractmethod
from typing import Optional
from models import PluginResult


class BasePlugin(ABC):
    """
    Standard interface for all betting strategy plugins.

    Every plugin must:
    1. Have a unique ID
    2. Provide a name and config
    3. Implement evaluate() to assess runners against strategy rules
    4. Return a PluginResult with action (ACCEPT/REJECT/SKIP) and candidates

    Plugins are evaluated in priority order by the auto-betting engine.
    Multiple plugins can be stacked — the engine tries each in order until
    one returns ACCEPT, or all return REJECT/SKIP.
    """

    @abstractmethod
    def get_id(self) -> str:
        """Return unique plugin identifier (e.g. 'marks_rule_1')."""
        ...

    @abstractmethod
    def get_name(self) -> str:
        """Return human-readable name (e.g. 'Mark\\'s Rule Set 1')."""
        ...

    @abstractmethod
    def get_version(self) -> str:
        """Return plugin version string."""
        ...

    @abstractmethod
    def get_author(self) -> str:
        """Return plugin author."""
        ...

    @abstractmethod
    def get_description(self) -> str:
        """Return plugin description."""
        ...

    @abstractmethod
    def get_config(self) -> dict:
        """Return the full plugin configuration."""
        ...

    @abstractmethod
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
        Evaluate a market's runners against this strategy.

        Args:
            runners: List of runner dicts with live prices.
                Each runner has: selectionId, runnerName, atb, atl, ltp, tv
            market: Market info dict with: marketId, marketName, venue,
                countryCode, marketStartTime, status, inPlay
            daily_pnl: Current day's P/L in GBP
            daily_exposure: Current day's total liability exposure
            bets_today: List of bet dicts placed today
            settings: Auto-betting settings (limits, etc.)

        Returns:
            PluginResult with:
                action: 'ACCEPT' if bet should be placed, 'REJECT' if not,
                        'SKIP' if plugin doesn't apply
                candidates: List of BetCandidate objects if ACCEPT
                analysis: Text description of the evaluation
                reason: Short reason for the decision
        """
        ...

    def get_metadata(self) -> dict:
        """Return plugin metadata for registration."""
        return {
            "id": self.get_id(),
            "name": self.get_name(),
            "version": self.get_version(),
            "author": self.get_author(),
            "description": self.get_description(),
            "config": self.get_config(),
        }
