"""
CHIMERA v2 Market Routes
Market catalogue, market book (REST fallback)
"""

import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from models import MarketFilter, MarketBookRequest
from services.betfair_client import betfair_client, BetfairAPIError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/markets", tags=["markets"])


@router.get("/catalogue")
async def list_market_catalogue(
    max_results: int = Query(default=500, ge=1, le=1000),
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
):
    """Get today's GB/IE WIN horse racing markets."""
    try:
        markets = await betfair_client.list_market_catalogue(
            max_results=max_results,
            from_time=from_time,
            to_time=to_time,
        )

        # Enrich with venue/country extraction
        enriched = []
        for market in markets:
            event = market.get("event", {})
            venue = event.get("venue", "Unknown")
            country_code = event.get("countryCode", "")

            enriched.append({
                "marketId": market.get("marketId"),
                "marketName": market.get("marketName"),
                "marketStartTime": market.get("marketStartTime"),
                "venue": venue,
                "countryCode": country_code,
                "event": event,
                "competition": market.get("competition"),
                "runners": [
                    {
                        "selectionId": r.get("selectionId"),
                        "runnerName": r.get("runnerName"),
                        "metadata": r.get("metadata", {}),
                    }
                    for r in market.get("runners", [])
                ],
            })

        return {"markets": enriched, "count": len(enriched)}

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/book")
async def list_market_book(request: MarketBookRequest):
    """Get market book with prices for specific markets (REST fallback)."""
    try:
        books = await betfair_client.list_market_book(
            market_ids=request.market_ids,
            price_projection=request.price_projection,
            virtualise=request.virtualise,
        )
        return {"markets": books}

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/{market_id}/book")
async def get_single_market_book(market_id: str):
    """Get market book for a single market."""
    try:
        books = await betfair_client.list_market_book(
            market_ids=[market_id],
            price_projection=["EX_BEST_OFFERS"],
        )
        if not books:
            raise HTTPException(status_code=404, detail="Market not found")
        return books[0]

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
