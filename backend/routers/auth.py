"""
CHIMERA v2 Auth Routes
Login, logout, keepAlive, session status
"""

import logging
from fastapi import APIRouter, HTTPException

from models import LoginRequest, LoginResponse, ErrorResponse
from services.betfair_client import betfair_client, BetfairAPIError
from services.stream_manager import stream_manager
import database as db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Authenticate with Betfair."""
    try:
        result = await betfair_client.login(request.username, request.password)

        # Persist session to DB
        await db.save_session(
            token=result["session_token"],
            expires_at=result["expires_at"],
        )

        logger.info(f"Login successful, status: {result['status']}")

        # Start stream connection
        try:
            await stream_manager.start(result["session_token"])
            logger.info("Stream started after login")
        except Exception as e:
            logger.warning(f"Stream start failed after login: {e}")

        return LoginResponse(
            session_token=result["session_token"],
            expires_at=result["expires_at"],
            status=result["status"],
        )

    except BetfairAPIError as e:
        logger.warning(f"Login failed: {e.message}")
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/logout")
async def logout():
    """Logout and clear session."""
    try:
        # Stop stream before logout
        await stream_manager.stop()

        result = await betfair_client.logout()
        await db.clear_session()
        logger.info("Logout successful")
        return {"status": "SUCCESS", "message": "Logged out"}
    except BetfairAPIError as e:
        # Still clear local session even if Betfair call fails
        await db.clear_session()
        betfair_client.session_token = None
        return {"status": "SUCCESS", "message": "Logged out (local)"}


@router.post("/keepalive")
async def keep_alive():
    """Extend session lifetime."""
    try:
        result = await betfair_client.keep_alive()

        # Update session in DB
        if result.get("token"):
            await db.save_session(
                token=result["token"],
                expires_at=result["expires_at"],
            )

        return result

    except BetfairAPIError as e:
        if e.status_code == 401:
            await db.clear_session()
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/session")
async def get_session():
    """Check current session status."""
    session = await db.get_session()
    if session and betfair_client.session_token:
        return {
            "authenticated": True,
            "expires_at": session["expires_at"],
        }
    return {"authenticated": False}


@router.post("/restore")
async def restore_session():
    """Restore session from database (e.g. after page reload)."""
    session = await db.get_session()
    if not session:
        return {"authenticated": False, "message": "No saved session"}

    # Set the token on the client
    betfair_client.session_token = session["session_token"]

    # Verify it's still valid with a keepalive
    try:
        result = await betfair_client.keep_alive(session["session_token"])
        if result.get("token"):
            await db.save_session(
                token=result["token"],
                expires_at=result["expires_at"],
            )
            betfair_client.session_token = result["token"]

        # Ensure stream is connected (it may have failed at boot or disconnected)
        active_token = betfair_client.session_token
        if not stream_manager.is_connected and active_token:
            try:
                logger.info("Stream not connected — starting on session restore")
                await stream_manager.start(active_token)
                logger.info("Stream started after session restore")
            except Exception as e:
                logger.warning(f"Stream start failed on restore: {e}")

        return {
            "authenticated": True,
            "expires_at": result.get("expires_at", session["expires_at"]),
            "stream_connected": stream_manager.is_connected,
        }
    except BetfairAPIError:
        await db.clear_session()
        betfair_client.session_token = None
        return {"authenticated": False, "message": "Session expired"}
