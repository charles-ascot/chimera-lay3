"""
CHIMERA v2 History Routes
Bet history, stats, CSV export, analysis, decision log
"""

import csv
import io
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from config import config
import database as db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/history", tags=["history"])


# ─────────────────────────────────────────────────────────────
# Helper: date range from period
# ─────────────────────────────────────────────────────────────

def _resolve_period(period: str, date_from: Optional[str], date_to: Optional[str]):
    """Convert period name to date_from/date_to strings."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")

    if period == "custom" and date_from:
        return date_from, date_to or f"{today}T23:59:59"

    if period == "yesterday":
        yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
        return f"{yesterday}T00:00:00", f"{yesterday}T23:59:59"
    elif period == "week":
        week_ago = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        return f"{week_ago}T00:00:00", f"{today}T23:59:59"
    elif period == "month":
        month_ago = (now - timedelta(days=30)).strftime("%Y-%m-%d")
        return f"{month_ago}T00:00:00", f"{today}T23:59:59"
    elif period == "all":
        return None, None
    else:  # today
        return f"{today}T00:00:00", f"{today}T23:59:59"


# ─────────────────────────────────────────────────────────────
# Bet History
# ─────────────────────────────────────────────────────────────

@router.get("/bets")
async def get_bets(
    period: str = Query(default="today"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    source: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=500, ge=1, le=2000),
    offset: int = Query(default=0, ge=0),
):
    """Get bet history with filters."""
    from_dt, to_dt = _resolve_period(period, date_from, date_to)

    bets = await db.get_bets(
        date_from=from_dt,
        date_to=to_dt,
        source=source,
        status=status,
        limit=limit,
        offset=offset,
    )

    return {"bets": bets, "count": len(bets), "period": period}


# ─────────────────────────────────────────────────────────────
# Stats
# ─────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats(
    period: str = Query(default="today"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Get aggregated stats for a period."""
    from_dt, to_dt = _resolve_period(period, date_from, date_to)

    if period == "today":
        stats = await db.get_daily_stats()
    else:
        from_date = from_dt.split("T")[0] if from_dt else "2020-01-01"
        to_date = to_dt.split("T")[0] if to_dt else datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = await db.get_period_stats(from_date, to_date)

    # Calculate derived metrics
    total_bets = stats.get("total_bets", 0)
    wins = stats.get("wins", 0)
    total_staked = stats.get("total_staked", 0)
    pnl = stats.get("profit_loss", 0)

    stats["win_rate"] = round(wins / total_bets * 100, 1) if total_bets > 0 else 0
    stats["roi"] = round(pnl / total_staked * 100, 1) if total_staked > 0 else 0

    return stats


# ─────────────────────────────────────────────────────────────
# CSV Export
# ─────────────────────────────────────────────────────────────

@router.get("/export")
async def export_csv(
    period: str = Query(default="all"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Export bet history as CSV."""
    from_dt, to_dt = _resolve_period(period, date_from, date_to)
    bets = await db.get_bets(date_from=from_dt, date_to=to_dt, limit=10000)

    if not bets:
        raise HTTPException(status_code=404, detail="No bets found for export")

    # Build CSV
    output = io.StringIO()
    fieldnames = [
        "id", "bet_id", "market_id", "market_name", "venue", "country_code",
        "race_time", "runner_name", "side", "stake", "odds", "liability",
        "zone", "confidence", "rule_id", "status", "result", "profit_loss",
        "placed_at", "settled_at", "source",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for bet in bets:
        writer.writerow(bet)

    output.seek(0)
    filename = f"chimera_bets_{period}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"

    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ─────────────────────────────────────────────────────────────
# Built-in Analysis
# ─────────────────────────────────────────────────────────────

@router.get("/analysis")
async def get_analysis(
    period: str = Query(default="all"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    """Built-in statistical analysis of bet history."""
    from_dt, to_dt = _resolve_period(period, date_from, date_to)
    bets = await db.get_bets(date_from=from_dt, date_to=to_dt, limit=10000)

    if not bets:
        return {"message": "No bets to analyze", "analysis": {}}

    # Zone analysis
    zones = {}
    for bet in bets:
        zone = bet.get("zone") or "UNKNOWN"
        if zone not in zones:
            zones[zone] = {"bets": 0, "wins": 0, "losses": 0, "pnl": 0, "staked": 0}
        zones[zone]["bets"] += 1
        zones[zone]["staked"] += bet.get("stake", 0)
        zones[zone]["pnl"] += bet.get("profit_loss", 0)
        if bet.get("result") == "WON":
            zones[zone]["wins"] += 1
        elif bet.get("result") == "LOST":
            zones[zone]["losses"] += 1

    for zone in zones.values():
        settled = zone["wins"] + zone["losses"]
        zone["win_rate"] = round(zone["wins"] / settled * 100, 1) if settled > 0 else 0
        zone["roi"] = round(zone["pnl"] / zone["staked"] * 100, 1) if zone["staked"] > 0 else 0

    # Venue analysis
    venues = {}
    for bet in bets:
        venue = bet.get("venue") or "Unknown"
        if venue not in venues:
            venues[venue] = {"bets": 0, "wins": 0, "losses": 0, "pnl": 0}
        venues[venue]["bets"] += 1
        venues[venue]["pnl"] += bet.get("profit_loss", 0)
        if bet.get("result") == "WON":
            venues[venue]["wins"] += 1
        elif bet.get("result") == "LOST":
            venues[venue]["losses"] += 1

    for venue in venues.values():
        settled = venue["wins"] + venue["losses"]
        venue["win_rate"] = round(venue["wins"] / settled * 100, 1) if settled > 0 else 0

    # Streak analysis
    streaks = _calculate_streaks(bets)

    # Odds distribution
    odds_buckets = {"2.50-2.99": 0, "3.00-3.49": 0, "3.50-3.99": 0, "4.00-4.49": 0, "4.50+": 0}
    for bet in bets:
        odds = bet.get("odds", 0)
        if odds < 3.0:
            odds_buckets["2.50-2.99"] += 1
        elif odds < 3.5:
            odds_buckets["3.00-3.49"] += 1
        elif odds < 4.0:
            odds_buckets["3.50-3.99"] += 1
        elif odds < 4.5:
            odds_buckets["4.00-4.49"] += 1
        else:
            odds_buckets["4.50+"] += 1

    # P/L over time (daily)
    daily_pnl = {}
    for bet in bets:
        date = bet.get("placed_at", "")[:10]
        if date:
            daily_pnl[date] = daily_pnl.get(date, 0) + bet.get("profit_loss", 0)

    # Cumulative P/L
    cumulative = []
    running = 0
    for date in sorted(daily_pnl.keys()):
        running += daily_pnl[date]
        cumulative.append({"date": date, "daily_pnl": round(daily_pnl[date], 2), "cumulative": round(running, 2)})

    return {
        "total_bets": len(bets),
        "by_zone": zones,
        "by_venue": dict(sorted(venues.items(), key=lambda x: x[1]["bets"], reverse=True)),
        "streaks": streaks,
        "odds_distribution": odds_buckets,
        "pnl_over_time": cumulative,
    }


def _calculate_streaks(bets: list) -> dict:
    """Calculate winning and losing streaks."""
    settled = [b for b in bets if b.get("result") in ("WON", "LOST")]
    settled.sort(key=lambda b: b.get("placed_at", ""))

    max_win = current_win = 0
    max_loss = current_loss = 0

    for bet in settled:
        if bet["result"] == "WON":
            current_win += 1
            current_loss = 0
            max_win = max(max_win, current_win)
        else:
            current_loss += 1
            current_win = 0
            max_loss = max(max_loss, current_loss)

    return {
        "max_winning_streak": max_win,
        "max_losing_streak": max_loss,
        "current_winning_streak": current_win,
        "current_losing_streak": current_loss,
    }


# ─────────────────────────────────────────────────────────────
# AI Analysis (Optional — Claude API)
# ─────────────────────────────────────────────────────────────

@router.post("/ai-analysis")
async def ai_analysis(
    period: str = Query(default="all"),
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    question: Optional[str] = None,
):
    """Send bet data to Claude API for deep analysis."""
    if not config.ANTHROPIC_API_KEY:
        raise HTTPException(
            status_code=400,
            detail="Anthropic API key not configured. Set ANTHROPIC_API_KEY environment variable.",
        )

    from_dt, to_dt = _resolve_period(period, date_from, date_to)
    bets = await db.get_bets(date_from=from_dt, date_to=to_dt, limit=2000)

    if not bets:
        raise HTTPException(status_code=404, detail="No bets to analyze")

    # Build the analysis prompt
    bet_summary = _build_bet_summary(bets)
    prompt = _build_analysis_prompt(bet_summary, question)

    try:
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": config.ANTHROPIC_API_KEY,
                    "content-type": "application/json",
                    "anthropic-version": "2023-06-01",
                },
                json={
                    "model": "claude-sonnet-4-20250514",
                    "max_tokens": 2000,
                    "messages": [{"role": "user", "content": prompt}],
                },
            )
            result = response.json()
            analysis_text = result.get("content", [{}])[0].get("text", "No analysis available")

        return {"analysis": analysis_text, "bets_analyzed": len(bets), "period": period}

    except Exception as e:
        logger.error(f"AI analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


def _build_bet_summary(bets: list) -> str:
    """Build a concise summary of bet data for the AI."""
    total = len(bets)
    settled = [b for b in bets if b.get("result") in ("WON", "LOST")]
    wins = sum(1 for b in settled if b["result"] == "WON")
    losses = sum(1 for b in settled if b["result"] == "LOST")
    pnl = sum(b.get("profit_loss", 0) for b in bets)
    staked = sum(b.get("stake", 0) for b in bets)

    # Zone breakdown
    zone_data = {}
    for b in settled:
        z = b.get("zone", "UNKNOWN")
        if z not in zone_data:
            zone_data[z] = {"w": 0, "l": 0, "pnl": 0}
        zone_data[z]["pnl"] += b.get("profit_loss", 0)
        if b["result"] == "WON":
            zone_data[z]["w"] += 1
        else:
            zone_data[z]["l"] += 1

    lines = [
        f"Total bets: {total}, Settled: {len(settled)}, Wins: {wins}, Losses: {losses}",
        f"P/L: £{pnl:.2f}, Staked: £{staked:.2f}, ROI: {pnl / staked * 100:.1f}%" if staked > 0 else f"P/L: £{pnl:.2f}",
        f"Win rate: {wins / len(settled) * 100:.1f}%" if settled else "No settled bets",
        "",
        "By zone:",
    ]
    for z, d in zone_data.items():
        total_z = d["w"] + d["l"]
        wr = d["w"] / total_z * 100 if total_z > 0 else 0
        lines.append(f"  {z}: {d['w']}W/{d['l']}L ({wr:.0f}%) P/L: £{d['pnl']:.2f}")

    # Recent 20 bets detail
    lines.append("\nRecent bets:")
    for b in bets[:20]:
        lines.append(
            f"  {b.get('placed_at', '')[:16]} | {b.get('venue', '?'):12} | "
            f"{b.get('runner_name', '?'):20} | {b.get('odds', 0):.2f} | "
            f"£{b.get('stake', 0):.2f} | {b.get('zone', '?'):9} | "
            f"{b.get('result', 'PENDING'):5} | £{b.get('profit_loss', 0):+.2f}"
        )

    return "\n".join(lines)


def _build_analysis_prompt(summary: str, question: Optional[str] = None) -> str:
    """Build the prompt for Claude API analysis."""
    base = (
        "You are an expert horse racing lay betting analyst. Analyze the following "
        "betting data from a Betfair Exchange lay betting strategy (Chimera). "
        "The strategy targets horses in the 3.00-4.49 odds range with tiered staking.\n\n"
        f"DATA:\n{summary}\n\n"
    )

    if question:
        base += f"USER QUESTION: {question}\n\n"

    base += (
        "Provide a concise analysis covering:\n"
        "1. Overall performance assessment\n"
        "2. Zone performance comparison (which zones are delivering)\n"
        "3. Any patterns or anomalies you notice\n"
        "4. Risk concerns if any\n"
        "5. Actionable recommendations\n"
        "Keep it practical and data-driven. Use £ for currency."
    )

    return base


# ─────────────────────────────────────────────────────────────
# Decision Log
# ─────────────────────────────────────────────────────────────

@router.get("/decisions")
async def get_decisions(
    market_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """Get auto-betting engine decision log."""
    decisions = await db.get_decision_log(
        market_id=market_id,
        action=action,
        limit=limit,
        offset=offset,
    )
    return {"decisions": decisions, "count": len(decisions)}
