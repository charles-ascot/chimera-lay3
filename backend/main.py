"""
CHIMERA v2 — FastAPI Application
Main entry point with lifespan manager, CORS, and route mounting.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import config
import database as db
from services.betfair_client import betfair_client, BetfairAPIError
from services.stream_manager import stream_manager
from services.plugin_loader import plugin_loader
from services.auto_engine import auto_engine

# Import routers
from routers import auth, markets, orders, account, auto_betting, history, websocket

# ─────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("chimera")


# ─────────────────────────────────────────────────────────────
# Lifespan (startup / shutdown)
# ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown hooks."""
    logger.info("=" * 60)
    logger.info("  CHIMERA v2 Starting...")
    logger.info("=" * 60)

    # 1. Initialize database
    await db.init_db()

    # 2. Reset daily counters if needed
    await db.reset_auto_session_daily()

    # 3. Restore session if available
    session = await db.get_session()
    if session:
        betfair_client.session_token = session["session_token"]
        logger.info("Session restored from database")

        # 4. Start stream connection if session exists
        try:
            await stream_manager.start(session["session_token"])
            logger.info("Stream connection established")
        except Exception as e:
            logger.warning(f"Could not start stream on boot: {e}")

    # 5. Load plugins
    await plugin_loader.load_all()

    # 6. Auto-betting engine
    auto_betting.set_engine(auto_engine)

    # Restore engine state if it was running before restart
    auto_session = await db.get_auto_session()
    if auto_session.get("is_running") and betfair_client.session_token:
        try:
            await auto_engine.start()
            logger.info("Auto-betting engine restored from previous session")
        except Exception as e:
            logger.warning(f"Could not restore auto-betting engine: {e}")

    logger.info("CHIMERA v2 ready")
    logger.info(f"  App Key: {config.BETFAIR_APP_KEY[:8]}...")
    logger.info(f"  Database: {config.DATABASE_PATH}")
    logger.info(f"  Archive: {'enabled' if config.ARCHIVE_ENABLED else 'disabled'}")

    yield

    # Shutdown
    logger.info("CHIMERA v2 shutting down...")
    if auto_engine.is_running:
        await auto_engine.stop()
    await stream_manager.stop()
    await betfair_client.close()
    logger.info("Shutdown complete")


# ─────────────────────────────────────────────────────────────
# FastAPI App
# ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="CHIMERA v2",
    description="Lay betting engine for Betfair Exchange (Horse Racing GB/IE)",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────
# Global Exception Handler
# ─────────────────────────────────────────────────────────────

@app.exception_handler(BetfairAPIError)
async def betfair_error_handler(request: Request, exc: BetfairAPIError):
    """Handle Betfair API errors globally."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "code": exc.error_code,
        },
    )


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)},
    )


# ─────────────────────────────────────────────────────────────
# Mount Routers
# ─────────────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(markets.router)
app.include_router(orders.router)
app.include_router(account.router)
app.include_router(auto_betting.router)
app.include_router(history.router)
app.include_router(websocket.router)


# ─────────────────────────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    """Health check endpoint."""
    session = await db.get_session()
    return {
        "status": "ok",
        "version": "2.0.0",
        "authenticated": bool(session and betfair_client.session_token),
        "stream": stream_manager.stats,
        "ws_clients": websocket.get_connected_count(),
    }


# ─────────────────────────────────────────────────────────────
# Stream Management
# ─────────────────────────────────────────────────────────────

@app.post("/api/stream/start")
async def start_stream():
    """Manually start/restart the stream connection."""
    if not betfair_client.session_token:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})

    if stream_manager.is_connected:
        await stream_manager.stop()

    success = await stream_manager.start(betfair_client.session_token)
    return {"status": "STARTED" if success else "FAILED"}


@app.post("/api/stream/stop")
async def stop_stream():
    """Stop the stream connection."""
    await stream_manager.stop()
    return {"status": "STOPPED"}


@app.get("/api/stream/status")
async def stream_status():
    """Get stream connection status and stats."""
    return stream_manager.stats


@app.get("/api/stream/cache")
async def stream_cache():
    """Get current price cache summary."""
    markets = stream_manager.price_cache.get_all_markets()
    summary = []
    for mid, mdata in markets.items():
        summary.append({
            "marketId": mid,
            "status": mdata.get("status", "UNKNOWN"),
            "inPlay": mdata.get("inPlay", False),
            "runnerCount": len(mdata.get("runners", {})),
            "lastUpdate": mdata.get("lastUpdate"),
        })
    return {"markets": summary, "count": len(summary)}


# ─────────────────────────────────────────────────────────────
# Archive Management
# ─────────────────────────────────────────────────────────────

@app.get("/api/archive/stats")
async def archive_stats():
    """Get archive storage stats."""
    import aiosqlite
    async with aiosqlite.connect(config.DATABASE_PATH) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM stream_archive")
        stream_count = (await cursor.fetchone())[0]
        cursor = await conn.execute("SELECT COUNT(*) FROM decision_log")
        decision_count = (await cursor.fetchone())[0]
    return {
        "stream_records": stream_count,
        "decision_records": decision_count,
        "archive_enabled": config.ARCHIVE_ENABLED,
    }


@app.delete("/api/archive/cleanup")
async def cleanup_archive(days: int = 30):
    """Clean old stream data."""
    await db.cleanup_old_archive(days=days)
    return {"status": "OK", "message": f"Cleaned records older than {days} days"}


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": "CHIMERA v2",
        "description": "Lay betting engine for Betfair Exchange",
        "docs": "/docs",
    }
