"""
CHIMERA v2 Configuration
Environment variables and application settings
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    """Application configuration from environment variables."""

    # Betfair API
    BETFAIR_APP_KEY: str = os.getenv("BETFAIR_APP_KEY", "HTPjf4PpMGLksswf")
    BETFAIR_LOGIN_URL: str = "https://identitysso.betfair.com/api/login"
    BETFAIR_KEEPALIVE_URL: str = "https://identitysso.betfair.com/api/keepAlive"
    BETFAIR_LOGOUT_URL: str = "https://identitysso.betfair.com/api/logout"
    BETFAIR_API_URL: str = "https://api.betfair.com/exchange/betting/json-rpc/v1"
    BETFAIR_ACCOUNT_URL: str = "https://api.betfair.com/exchange/account/json-rpc/v1"

    # Betfair Stream API
    STREAM_HOST: str = "stream-api.betfair.com"
    STREAM_PORT: int = 443

    # Market filters (GB & IE horse racing WIN only)
    EVENT_TYPE_IDS: list = field(default_factory=lambda: ["7"])  # Horse Racing
    COUNTRY_CODES: list = field(default_factory=lambda: ["GB", "IE"])
    MARKET_TYPES: list = field(default_factory=lambda: ["WIN"])

    # Session
    SESSION_TIMEOUT_HOURS: int = 12

    # Rate limiting
    RATE_LIMIT_REQUESTS: int = 5
    RATE_LIMIT_WINDOW: float = 1.0

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "chimera.db")

    # Auto-betting defaults
    DEFAULT_MAX_LIABILITY_PER_BET: float = 9.00
    DEFAULT_MAX_DAILY_EXPOSURE: float = 75.00
    DEFAULT_DAILY_STOP_LOSS: float = -25.00
    DEFAULT_MAX_CONCURRENT_BETS: int = 999
    DEFAULT_MAX_BETS_PER_RACE: int = 1

    # Stream data archive
    ARCHIVE_ENABLED: bool = True
    ARCHIVE_RETENTION_DAYS: int = 30

    # WebSocket
    WS_HEARTBEAT_INTERVAL: int = 5  # seconds

    # CORS origins
    CORS_ORIGINS: list = field(default_factory=lambda: [
        "http://localhost:5173",
        "http://localhost:3000",
        "https://*.pages.dev",
        "https://chimera-lay.pages.dev",
        "https://lay3.thync.online",
        "https://*.thync.online",
    ])

    # Claude API (optional, for AI analysis)
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY", None)


config = Config()
