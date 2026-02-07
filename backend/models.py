"""
CHIMERA v2 Pydantic Models
Request/response schemas for the API
"""

from datetime import datetime
from typing import Optional, List, Any
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────
# Auth
# ─────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., description="Betfair username")
    password: str = Field(..., description="Betfair password")


class LoginResponse(BaseModel):
    session_token: str
    expires_at: str
    status: str = "SUCCESS"


# ─────────────────────────────────────────────────────────────────
# Markets
# ─────────────────────────────────────────────────────────────────

class MarketFilter(BaseModel):
    event_type_ids: List[str] = Field(default=["7"])
    market_type_codes: List[str] = Field(default=["WIN"])
    country_codes: List[str] = Field(default=["GB", "IE"])
    max_results: int = Field(default=500, ge=1, le=1000)
    from_time: Optional[str] = None
    to_time: Optional[str] = None


class MarketBookRequest(BaseModel):
    market_ids: List[str] = Field(..., min_length=1, max_length=40)
    price_projection: List[str] = Field(default=["EX_BEST_OFFERS"])
    virtualise: bool = Field(default=True)


# ─────────────────────────────────────────────────────────────────
# Orders
# ─────────────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    market_id: str
    selection_id: int
    odds: float = Field(..., gt=1.01, le=1000)
    stake: float = Field(..., gt=0)
    persistence_type: str = Field(default="LAPSE")


class CancelOrderRequest(BaseModel):
    market_id: str
    bet_id: Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# Auto Betting
# ─────────────────────────────────────────────────────────────────

class AutoBettingSettings(BaseModel):
    max_liability_per_bet: float = 9.00
    max_daily_exposure: float = 75.00
    daily_stop_loss: float = -25.00
    max_concurrent_bets: int = 10
    max_bets_per_race: int = 1
    only_pre_race: bool = True
    pre_race_window_minutes: int = 5


class AutoBettingStatus(BaseModel):
    is_running: bool
    active_plugins: List[str]
    daily_exposure: float
    daily_pnl: float
    bets_placed_today: int
    processed_markets_count: int
    settings: AutoBettingSettings


class PluginInfo(BaseModel):
    id: str
    name: str
    version: str
    author: str
    description: str
    enabled: bool
    priority: int
    config: dict
    has_drift_filter: bool = False


class PluginOrderRequest(BaseModel):
    plugin_ids: List[str]


class PluginUpdateRequest(BaseModel):
    enabled: Optional[bool] = None
    priority: Optional[int] = None
    config: Optional[dict] = None


# ─────────────────────────────────────────────────────────────────
# History
# ─────────────────────────────────────────────────────────────────

class BetRecord(BaseModel):
    id: int
    bet_id: Optional[str]
    market_id: str
    market_name: Optional[str]
    venue: Optional[str]
    country_code: Optional[str]
    race_time: Optional[str]
    selection_id: int
    runner_name: Optional[str]
    side: str
    stake: float
    odds: float
    liability: float
    zone: Optional[str]
    confidence: Optional[str]
    rule_id: Optional[str]
    status: str
    result: Optional[str]
    profit_loss: float
    placed_at: str
    settled_at: Optional[str]
    source: str


class StatsResponse(BaseModel):
    total_bets: int
    total_staked: float
    total_liability: float
    profit_loss: float
    wins: int
    losses: int
    pending: int
    exposure: float = 0
    win_rate: float = 0
    roi: float = 0


class HistoryFilterParams(BaseModel):
    period: str = "today"  # today, yesterday, week, month, custom
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    source: Optional[str] = None  # AUTO, MANUAL
    status: Optional[str] = None


# ─────────────────────────────────────────────────────────────────
# Plugin System
# ─────────────────────────────────────────────────────────────────

class BetCandidate(BaseModel):
    """A candidate bet from a plugin evaluation."""
    runner_name: str
    selection_id: int
    market_id: str
    odds: float
    stake: float
    liability: float
    zone: str = ""
    confidence: str = ""
    reason: str = ""


class PluginResult(BaseModel):
    """Result from a plugin evaluation."""
    action: str  # ACCEPT, REJECT, SKIP
    candidates: List[BetCandidate] = []
    analysis: str = ""
    reason: str = ""


# ─────────────────────────────────────────────────────────────────
# WebSocket Messages
# ─────────────────────────────────────────────────────────────────

class WSMessage(BaseModel):
    type: str  # price_update, market_status, order_update, engine_status, heartbeat
    data: Any


# ─────────────────────────────────────────────────────────────────
# Error
# ─────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
