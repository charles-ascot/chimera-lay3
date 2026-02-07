"""
CHIMERA v2 Database
SQLite database for persistent storage of bets, history, settings, and stream data.
"""

import aiosqlite
import json
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from config import config

logger = logging.getLogger(__name__)

DB_PATH = config.DATABASE_PATH

# ─────────────────────────────────────────────────────────────────
# Schema Migrations
# ─────────────────────────────────────────────────────────────────

SCHEMA_SQL = """
-- Session management
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY,
    session_token TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- All bets placed (persistent history)
CREATE TABLE IF NOT EXISTS bets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    bet_id TEXT,
    market_id TEXT NOT NULL,
    market_name TEXT,
    venue TEXT,
    country_code TEXT,
    race_time TEXT,
    selection_id INTEGER NOT NULL,
    runner_name TEXT,
    side TEXT DEFAULT 'LAY',
    stake REAL NOT NULL,
    odds REAL NOT NULL,
    liability REAL NOT NULL,
    zone TEXT,
    confidence TEXT,
    rule_id TEXT,
    persistence_type TEXT DEFAULT 'LAPSE',
    status TEXT DEFAULT 'PENDING',
    result TEXT,
    profit_loss REAL DEFAULT 0,
    size_matched REAL DEFAULT 0,
    size_remaining REAL DEFAULT 0,
    avg_price_matched REAL,
    placed_at TEXT DEFAULT (datetime('now')),
    matched_at TEXT,
    settled_at TEXT,
    source TEXT DEFAULT 'AUTO',
    raw_response TEXT
);

-- Daily P/L tracking
CREATE TABLE IF NOT EXISTS daily_stats (
    date TEXT PRIMARY KEY,
    total_bets INTEGER DEFAULT 0,
    total_staked REAL DEFAULT 0,
    total_liability REAL DEFAULT 0,
    total_returns REAL DEFAULT 0,
    profit_loss REAL DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    pending INTEGER DEFAULT 0,
    exposure REAL DEFAULT 0
);

-- Auto-betting session state (survives reload)
CREATE TABLE IF NOT EXISTS auto_session (
    id INTEGER PRIMARY KEY DEFAULT 1,
    is_running INTEGER DEFAULT 0,
    active_plugins TEXT DEFAULT '[]',
    processed_markets TEXT DEFAULT '[]',
    daily_exposure REAL DEFAULT 0,
    daily_pnl REAL DEFAULT 0,
    bets_placed_today INTEGER DEFAULT 0,
    last_reset_date TEXT,
    settings TEXT DEFAULT '{}',
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Strategy plugins metadata
CREATE TABLE IF NOT EXISTS plugins (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT,
    author TEXT,
    description TEXT,
    config TEXT NOT NULL,
    enabled INTEGER DEFAULT 1,
    priority INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Raw stream data archive
CREATE TABLE IF NOT EXISTS stream_archive (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT,
    event_type TEXT,
    data TEXT NOT NULL,
    captured_at TEXT DEFAULT (datetime('now'))
);

-- Decision log — every engine evaluation with context
CREATE TABLE IF NOT EXISTS decision_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    market_id TEXT NOT NULL,
    market_name TEXT,
    venue TEXT,
    race_time TEXT,
    plugin_id TEXT,
    action TEXT NOT NULL,
    reason TEXT,
    runners_snapshot TEXT,
    candidates TEXT,
    daily_pnl REAL,
    daily_exposure REAL,
    bets_today_count INTEGER,
    time_to_race_minutes REAL,
    created_at TEXT DEFAULT (datetime('now'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_bets_market ON bets(market_id);
CREATE INDEX IF NOT EXISTS idx_bets_date ON bets(placed_at);
CREATE INDEX IF NOT EXISTS idx_bets_status ON bets(status);
CREATE INDEX IF NOT EXISTS idx_bets_result ON bets(result);
CREATE INDEX IF NOT EXISTS idx_stream_market ON stream_archive(market_id);
CREATE INDEX IF NOT EXISTS idx_stream_date ON stream_archive(captured_at);
CREATE INDEX IF NOT EXISTS idx_decision_market ON decision_log(market_id);
CREATE INDEX IF NOT EXISTS idx_decision_date ON decision_log(created_at);
CREATE INDEX IF NOT EXISTS idx_decision_action ON decision_log(action);
"""


# ─────────────────────────────────────────────────────────────────
# Database Connection & Init
# ─────────────────────────────────────────────────────────────────

async def get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    return db


async def init_db():
    """Initialize database with schema."""
    logger.info(f"Initializing database at {DB_PATH}")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA_SQL)
        await db.commit()

        # Ensure auto_session row exists
        cursor = await db.execute("SELECT COUNT(*) FROM auto_session")
        count = (await cursor.fetchone())[0]
        if count == 0:
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            await db.execute(
                "INSERT INTO auto_session (id, last_reset_date) VALUES (1, ?)",
                (today,)
            )
            await db.commit()

    logger.info("Database initialized successfully")


# ─────────────────────────────────────────────────────────────────
# Session Operations
# ─────────────────────────────────────────────────────────────────

async def save_session(token: str, expires_at: str):
    """Save or update the session token."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("DELETE FROM sessions")
        await db.execute(
            "INSERT INTO sessions (id, session_token, expires_at) VALUES (1, ?, ?)",
            (token, expires_at)
        )
        await db.commit()


async def get_session() -> Optional[dict]:
    """Get the current session."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM sessions WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            return dict(row)
    return None


async def clear_session():
    """Clear the session."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM sessions")
        await db.commit()


# ─────────────────────────────────────────────────────────────────
# Bet Operations
# ─────────────────────────────────────────────────────────────────

async def insert_bet(bet_data: dict) -> int:
    """Insert a new bet record. Returns the bet ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        columns = ", ".join(bet_data.keys())
        placeholders = ", ".join(["?"] * len(bet_data))
        cursor = await db.execute(
            f"INSERT INTO bets ({columns}) VALUES ({placeholders})",
            list(bet_data.values())
        )
        await db.commit()
        return cursor.lastrowid


async def update_bet(bet_id: str, updates: dict):
    """Update a bet by bet_id (Betfair ID) or internal ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values())
        # Try bet_id first, then internal id
        await db.execute(
            f"UPDATE bets SET {set_clause} WHERE bet_id = ? OR id = ?",
            values + [bet_id, bet_id]
        )
        await db.commit()


async def get_bets(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    status: Optional[str] = None,
    source: Optional[str] = None,
    limit: int = 500,
    offset: int = 0
) -> list[dict]:
    """Get bets with optional filters."""
    conditions = []
    params = []

    if date_from:
        conditions.append("placed_at >= ?")
        params.append(date_from)
    if date_to:
        conditions.append("placed_at <= ?")
        params.append(date_to)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if source:
        conditions.append("source = ?")
        params.append(source)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT * FROM bets{where} ORDER BY placed_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def get_bets_for_market(market_id: str) -> list[dict]:
    """Get all bets for a specific market."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM bets WHERE market_id = ?", (market_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def has_bet_on_market(market_id: str, exclude_staged: bool = False) -> bool:
    """Check if we already have a bet on this market (for duplicate prevention).

    Args:
        market_id: The market to check
        exclude_staged: If True, ignore STAGED bets (used when in LIVE mode
                       so staged bets don't block real bets)
    """
    async with aiosqlite.connect(DB_PATH) as db:
        if exclude_staged:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bets WHERE market_id = ? AND status != 'CANCELLED' AND source != 'STAGED'",
                (market_id,)
            )
        else:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM bets WHERE market_id = ? AND status != 'CANCELLED'",
                (market_id,)
            )
        count = (await cursor.fetchone())[0]
        return count > 0


async def get_today_bets() -> list[dict]:
    """Get all bets placed today."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return await get_bets(date_from=f"{today}T00:00:00", date_to=f"{today}T23:59:59")


# ─────────────────────────────────────────────────────────────────
# Daily Stats
# ─────────────────────────────────────────────────────────────────

async def get_daily_stats(date: Optional[str] = None) -> dict:
    """Get stats for a specific date (default: today)."""
    if not date:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        # Calculate from bets table for accuracy
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_bets,
                COALESCE(SUM(stake), 0) as total_staked,
                COALESCE(SUM(liability), 0) as total_liability,
                COALESCE(SUM(profit_loss), 0) as profit_loss,
                COALESCE(SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END), 0) as wins,
                COALESCE(SUM(CASE WHEN result = 'LOST' THEN 1 ELSE 0 END), 0) as losses,
                COALESCE(SUM(CASE WHEN result IS NULL OR result = 'PENDING' THEN 1 ELSE 0 END), 0) as pending,
                COALESCE(SUM(CASE WHEN status IN ('PENDING', 'MATCHED') AND result IS NULL THEN liability ELSE 0 END), 0) as exposure
            FROM bets
            WHERE DATE(placed_at) = ?
        """, (date,))
        row = await cursor.fetchone()
        return dict(row) if row else {
            "total_bets": 0, "total_staked": 0, "total_liability": 0,
            "profit_loss": 0, "wins": 0, "losses": 0, "pending": 0, "exposure": 0
        }


async def get_period_stats(date_from: str, date_to: str) -> dict:
    """Get aggregated stats for a date range."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("""
            SELECT
                COUNT(*) as total_bets,
                COALESCE(SUM(stake), 0) as total_staked,
                COALESCE(SUM(liability), 0) as total_liability,
                COALESCE(SUM(profit_loss), 0) as profit_loss,
                COALESCE(SUM(CASE WHEN result = 'WON' THEN 1 ELSE 0 END), 0) as wins,
                COALESCE(SUM(CASE WHEN result = 'LOST' THEN 1 ELSE 0 END), 0) as losses,
                COALESCE(SUM(CASE WHEN result IS NULL OR result = 'PENDING' THEN 1 ELSE 0 END), 0) as pending
            FROM bets
            WHERE DATE(placed_at) >= ? AND DATE(placed_at) <= ?
        """, (date_from, date_to))
        row = await cursor.fetchone()
        return dict(row) if row else {}


# ─────────────────────────────────────────────────────────────────
# Auto Session
# ─────────────────────────────────────────────────────────────────

async def get_auto_session() -> dict:
    """Get the auto-betting session state."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM auto_session WHERE id = 1")
        row = await cursor.fetchone()
        if row:
            result = dict(row)
            result["active_plugins"] = json.loads(result.get("active_plugins", "[]"))
            result["processed_markets"] = json.loads(result.get("processed_markets", "[]"))
            result["settings"] = json.loads(result.get("settings", "{}"))
            return result
        return {}


async def update_auto_session(updates: dict):
    """Update auto-betting session state."""
    # Serialize JSON fields
    serialized = {}
    for k, v in updates.items():
        if k in ("active_plugins", "processed_markets", "settings") and isinstance(v, (list, dict)):
            serialized[k] = json.dumps(v)
        else:
            serialized[k] = v

    serialized["updated_at"] = datetime.now(timezone.utc).isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ", ".join([f"{k} = ?" for k in serialized.keys()])
        await db.execute(
            f"UPDATE auto_session SET {set_clause} WHERE id = 1",
            list(serialized.values())
        )
        await db.commit()


async def reset_auto_session_daily():
    """Reset daily counters if it's a new day."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    session = await get_auto_session()

    if session.get("last_reset_date") != today:
        await update_auto_session({
            "processed_markets": [],
            "daily_exposure": 0,
            "daily_pnl": 0,
            "bets_placed_today": 0,
            "last_reset_date": today,
        })
        logger.info(f"Auto session reset for new day: {today}")


# ─────────────────────────────────────────────────────────────────
# Plugins
# ─────────────────────────────────────────────────────────────────

async def get_plugins() -> list[dict]:
    """Get all registered plugins."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT * FROM plugins ORDER BY priority ASC")
        rows = await cursor.fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["config"] = json.loads(d.get("config", "{}"))
            result.append(d)
        return result


async def upsert_plugin(plugin_data: dict):
    """Insert or update a plugin."""
    config_json = json.dumps(plugin_data.get("config", {}))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO plugins (id, name, version, author, description, config, enabled, priority)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                version = excluded.version,
                config = excluded.config,
                description = excluded.description
        """, (
            plugin_data["id"],
            plugin_data["name"],
            plugin_data.get("version", "1.0.0"),
            plugin_data.get("author", ""),
            plugin_data.get("description", ""),
            config_json,
            plugin_data.get("enabled", 1),
            plugin_data.get("priority", 0),
        ))
        await db.commit()


async def update_plugin(plugin_id: str, updates: dict):
    """Update a plugin's settings."""
    if "config" in updates and isinstance(updates["config"], dict):
        updates["config"] = json.dumps(updates["config"])

    async with aiosqlite.connect(DB_PATH) as db:
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        await db.execute(
            f"UPDATE plugins SET {set_clause} WHERE id = ?",
            list(updates.values()) + [plugin_id]
        )
        await db.commit()


# ─────────────────────────────────────────────────────────────────
# Stream Archive
# ─────────────────────────────────────────────────────────────────

async def archive_stream_data(market_id: str, event_type: str, data: Any):
    """Archive raw stream data for research."""
    if not config.ARCHIVE_ENABLED:
        return

    data_json = json.dumps(data) if not isinstance(data, str) else data
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO stream_archive (market_id, event_type, data) VALUES (?, ?, ?)",
            (market_id, event_type, data_json)
        )
        await db.commit()


async def insert_decision_log(decision: dict):
    """Log an auto-betting engine decision."""
    # Serialize JSON fields
    for key in ("runners_snapshot", "candidates"):
        if key in decision and isinstance(decision[key], (list, dict)):
            decision[key] = json.dumps(decision[key])

    async with aiosqlite.connect(DB_PATH) as db:
        columns = ", ".join(decision.keys())
        placeholders = ", ".join(["?"] * len(decision))
        await db.execute(
            f"INSERT INTO decision_log ({columns}) VALUES ({placeholders})",
            list(decision.values())
        )
        await db.commit()


async def get_decision_log(
    market_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> list[dict]:
    """Get decision log entries."""
    conditions = []
    params = []

    if market_id:
        conditions.append("market_id = ?")
        params.append(market_id)
    if action:
        conditions.append("action = ?")
        params.append(action)

    where = " WHERE " + " AND ".join(conditions) if conditions else ""

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            f"SELECT * FROM decision_log{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset]
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def cleanup_old_archive(days: int = 30):
    """Delete stream archive data older than N days."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM stream_archive WHERE captured_at < datetime('now', ?)",
            (f"-{days} days",)
        )
        await db.commit()
        logger.info(f"Cleaned up {cursor.rowcount} old stream archive records")
