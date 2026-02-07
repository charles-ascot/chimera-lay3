"""
CHIMERA v2 Order Routes
Place, cancel, list current orders
"""

import json
import logging
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query

from models import PlaceOrderRequest, CancelOrderRequest
from services.betfair_client import betfair_client, BetfairAPIError
import database as db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.post("/place")
async def place_order(request: PlaceOrderRequest):
    """Place a manual lay bet."""
    try:
        # Calculate liability
        liability = round(request.stake * (request.odds - 1), 2)

        # Place via Betfair REST API
        result = await betfair_client.place_orders(
            market_id=request.market_id,
            selection_id=request.selection_id,
            odds=request.odds,
            stake=request.stake,
            side="LAY",
            persistence_type=request.persistence_type,
        )

        # Extract bet details from response
        instruction_reports = result.get("instructionReports", [])
        bet_id = None
        status = result.get("status", "FAILURE")

        if instruction_reports:
            report = instruction_reports[0]
            bet_id = report.get("betId")
            size_matched = report.get("sizeMatched", 0)
            avg_price = report.get("averagePriceMatched", 0)

            # Record the bet in our database
            bet_data = {
                "bet_id": bet_id,
                "market_id": request.market_id,
                "selection_id": request.selection_id,
                "stake": request.stake,
                "odds": request.odds,
                "liability": liability,
                "persistence_type": request.persistence_type,
                "status": "MATCHED" if size_matched > 0 else "PENDING",
                "size_matched": size_matched,
                "size_remaining": request.stake - size_matched,
                "avg_price_matched": avg_price if avg_price else None,
                "source": "MANUAL",
                "raw_response": json.dumps(result),
            }
            await db.insert_bet(bet_data)

        logger.info(
            f"Manual bet placed: market={request.market_id} "
            f"sel={request.selection_id} odds={request.odds} "
            f"stake=£{request.stake} bet_id={bet_id} status={status}"
        )

        return {
            "status": status,
            "bet_id": bet_id,
            "market_id": request.market_id,
            "liability": liability,
            "instruction_reports": instruction_reports,
        }

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.post("/cancel")
async def cancel_order(request: CancelOrderRequest):
    """Cancel an unmatched order."""
    try:
        result = await betfair_client.cancel_orders(
            market_id=request.market_id,
            bet_id=request.bet_id,
        )

        # Update bet status in our database
        if request.bet_id:
            await db.update_bet(request.bet_id, {"status": "CANCELLED"})

        logger.info(
            f"Order cancelled: market={request.market_id} bet_id={request.bet_id}"
        )

        return result

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/current")
async def list_current_orders(
    market_ids: Optional[str] = Query(default=None, description="Comma-separated market IDs"),
):
    """List current unmatched/matched orders."""
    try:
        market_id_list = market_ids.split(",") if market_ids else None
        result = await betfair_client.list_current_orders(market_ids=market_id_list)
        return result

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
