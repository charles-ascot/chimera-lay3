"""
CHIMERA v2 Account Routes
Balance and account statement
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query

from services.betfair_client import betfair_client, BetfairAPIError
import database as db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/account", tags=["account"])


@router.get("/balance")
async def get_balance():
    """Get account funds including balance and exposure."""
    try:
        funds = await betfair_client.get_account_funds()

        # Also get today's stats from our database
        today_stats = await db.get_daily_stats()

        return {
            "balance": funds,
            "today": today_stats,
        }

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)


@router.get("/statement")
async def get_statement(
    from_date: Optional[str] = Query(default=None, description="ISO date string"),
    to_date: Optional[str] = Query(default=None, description="ISO date string"),
    record_count: int = Query(default=100, ge=1, le=500),
):
    """Get account statement from Betfair."""
    try:
        statement = await betfair_client.get_account_statement(
            from_date=from_date,
            to_date=to_date,
            record_count=record_count,
        )
        return statement

    except BetfairAPIError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
