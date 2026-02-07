"""
CHIMERA v2 Auto-Betting Routes
Engine start/stop, status, settings, plugins
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException

from models import (
    AutoBettingSettings,
    AutoBettingStatus,
    PluginInfo,
    PluginUpdateRequest,
    PluginOrderRequest,
)
import database as db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auto", tags=["auto-betting"])

# Reference to the engine — set by main.py at startup
_engine = None


def set_engine(engine):
    """Set the auto-betting engine reference (called from main.py)."""
    global _engine
    _engine = engine


@router.post("/start")
async def start_engine(mode: str = "STAGING"):
    """Start the auto-betting engine. Mode: STAGING (default) or LIVE."""
    if _engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    if _engine.is_running:
        return {"status": "ALREADY_RUNNING", "mode": _engine.mode, "message": "Engine is already running"}

    await _engine.start(mode=mode.upper())

    return {"status": "STARTED", "mode": _engine.mode, "message": f"Engine started in {_engine.mode} mode"}


@router.post("/stop")
async def stop_engine():
    """Stop the auto-betting engine."""
    if _engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    if not _engine.is_running:
        return {"status": "ALREADY_STOPPED", "message": "Engine is not running"}

    await _engine.stop()

    return {"status": "STOPPED", "mode": "STOPPED", "message": "Auto-betting engine stopped"}


@router.post("/go-live")
async def go_live():
    """Switch engine from STAGING to LIVE mode (real bets)."""
    if _engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    if not _engine.is_running:
        raise HTTPException(status_code=400, detail="Engine is not running. Start it first.")

    success = await _engine.go_live()
    return {"status": "LIVE" if success else "FAILED", "mode": _engine.mode}


@router.post("/go-staging")
async def go_staging():
    """Switch engine from LIVE back to STAGING mode (simulated bets)."""
    if _engine is None:
        raise HTTPException(status_code=500, detail="Engine not initialized")

    if not _engine.is_running:
        raise HTTPException(status_code=400, detail="Engine is not running. Start it first.")

    success = await _engine.go_staging()
    return {"status": "STAGING" if success else "FAILED", "mode": _engine.mode}


@router.get("/status")
async def get_status():
    """Get auto-betting engine status and session stats."""
    session = await db.get_auto_session()
    today_stats = await db.get_daily_stats()

    is_running = _engine.is_running if _engine else False
    mode = _engine.mode if _engine else "STOPPED"

    return {
        "is_running": is_running,
        "mode": mode,
        "active_plugins": session.get("active_plugins", []),
        "daily_exposure": today_stats.get("exposure", 0),
        "daily_pnl": today_stats.get("profit_loss", 0),
        "bets_placed_today": today_stats.get("total_bets", 0),
        "processed_markets_count": len(session.get("processed_markets", [])),
        "settings": session.get("settings", {}),
        "wins_today": today_stats.get("wins", 0),
        "losses_today": today_stats.get("losses", 0),
        "pending_today": today_stats.get("pending", 0),
        "total_staked_today": today_stats.get("total_staked", 0),
    }


@router.get("/bets")
async def get_auto_bets(limit: int = 50, offset: int = 0, source: Optional[str] = None):
    """Get list of auto/staged bets. Source filter: AUTO, STAGED, or None for both."""
    if source:
        bets = await db.get_bets(source=source, limit=limit, offset=offset)
    else:
        # Return both AUTO and STAGED bets
        auto = await db.get_bets(source="AUTO", limit=limit, offset=offset)
        staged = await db.get_bets(source="STAGED", limit=limit, offset=offset)
        bets = sorted(auto + staged, key=lambda b: b.get("placed_at", ""), reverse=True)[:limit]
    return {"bets": bets, "count": len(bets)}


@router.put("/settings")
async def update_settings(settings: AutoBettingSettings):
    """Update auto-betting risk/stake settings."""
    settings_dict = settings.model_dump()
    await db.update_auto_session({"settings": settings_dict})

    if _engine:
        _engine.update_settings(settings_dict)

    logger.info(f"Auto-betting settings updated: {settings_dict}")
    return {"status": "UPDATED", "settings": settings_dict}


# ─────────────────────────────────────────────────────────────
# Plugins
# ─────────────────────────────────────────────────────────────

@router.get("/plugins")
async def list_plugins():
    """List all available strategy plugins."""
    plugins = await db.get_plugins()
    return {"plugins": plugins}


@router.put("/plugins/{plugin_id}")
async def update_plugin(plugin_id: str, update: PluginUpdateRequest):
    """Enable/disable/configure a plugin."""
    updates = {}
    if update.enabled is not None:
        updates["enabled"] = 1 if update.enabled else 0
    if update.priority is not None:
        updates["priority"] = update.priority
    if update.config is not None:
        updates["config"] = update.config

    if not updates:
        raise HTTPException(status_code=400, detail="No updates provided")

    await db.update_plugin(plugin_id, updates)

    # Update active plugins list in auto_session
    plugins = await db.get_plugins()
    active_ids = [p["id"] for p in plugins if p.get("enabled")]
    await db.update_auto_session({"active_plugins": active_ids})

    if _engine:
        await _engine.reload_plugins()

    logger.info(f"Plugin {plugin_id} updated: {updates}")
    return {"status": "UPDATED", "plugin_id": plugin_id}


@router.put("/plugins/order")
async def set_plugin_order(request: PluginOrderRequest):
    """Set the evaluation order of plugins."""
    for i, plugin_id in enumerate(request.plugin_ids):
        await db.update_plugin(plugin_id, {"priority": i})

    if _engine:
        await _engine.reload_plugins()

    return {"status": "UPDATED", "order": request.plugin_ids}
