"""
CHIMERA v2 WebSocket Routes
WebSocket endpoint for frontend to receive live price updates
"""

import asyncio
import json
import logging
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from config import config

logger = logging.getLogger(__name__)
router = APIRouter(tags=["websocket"])

# Connected WebSocket clients
_clients: Set[WebSocket] = set()


async def broadcast(message: dict):
    """Broadcast a message to all connected WebSocket clients."""
    if not _clients:
        return

    data = json.dumps(message)
    disconnected = set()

    for ws in _clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)

    # Clean up disconnected clients
    _clients.difference_update(disconnected)


async def broadcast_price_update(market_id: str, runners: list):
    """Broadcast a price update for a market."""
    await broadcast({
        "type": "price_update",
        "data": {
            "marketId": market_id,
            "runners": runners,
        }
    })


async def broadcast_market_status(market_id: str, status: str, **kwargs):
    """Broadcast a market status change."""
    await broadcast({
        "type": "market_status",
        "data": {
            "marketId": market_id,
            "status": status,
            **kwargs,
        }
    })


async def broadcast_order_update(order_data: dict):
    """Broadcast an order update."""
    await broadcast({
        "type": "order_update",
        "data": order_data,
    })


async def broadcast_engine_status(status: dict):
    """Broadcast auto-betting engine status."""
    await broadcast({
        "type": "engine_status",
        "data": status,
    })


async def broadcast_engine_activity(activity: dict):
    """Broadcast an engine activity event (bet placed, decision made, etc.)."""
    await broadcast({
        "type": "engine_activity",
        "data": activity,
    })


def get_connected_count() -> int:
    """Get the number of connected WebSocket clients."""
    return len(_clients)


@router.websocket("/ws/prices")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for live price updates."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info(f"WebSocket client connected. Total: {len(_clients)}")

    try:
        # Send initial heartbeat
        await websocket.send_json({"type": "connected", "data": {"message": "Connected to CHIMERA"}})

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (pings, subscriptions, etc.)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=config.WS_HEARTBEAT_INTERVAL * 2
                )

                # Handle client messages
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg.get("type") == "subscribe":
                        # Client can subscribe to specific market updates
                        # For now we broadcast all updates to all clients
                        await websocket.send_json({
                            "type": "subscribed",
                            "data": {"message": "Subscribed to all markets"}
                        })
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send heartbeat
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        _clients.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total: {len(_clients)}")
