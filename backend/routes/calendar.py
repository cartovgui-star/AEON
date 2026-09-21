"""Economic Calendar — curated upcoming macro events with impact rating."""
from fastapi import APIRouter
from datetime import datetime, timezone, timedelta
from typing import List, Dict

router = APIRouter()

# ──────────────────────────────────────────────────────────────────────────
# Real FOMC meeting schedule. Update yearly.
# Format: (year, month, day) of the FINAL day of the 2-day meeting (decision day).
# Time: 18:00 UTC = 2pm ET when standard time, 18:00 UTC = 2pm ET when daylight savings shifts.
# We publish minutes ~3 weeks (21 days) after each meeting.
# ──────────────────────────────────────────────────────────────────────────
FOMC_SCHEDULE = {
    2025: [(1, 29), (3, 19), (5, 7), (6, 18), (7, 30), (9, 17), (10, 29), (12, 10)],
    2026: [(1, 28), (3, 18), (4, 29), (6, 17), (7, 29), (9, 16), (10, 28), (12, 9)],
    2027: [(1, 27), (3, 17), (4, 28), (6, 16), (7, 28), (9, 15), (10, 27), (12, 8)],
}

# ──────────────────────────────────────────────────────────────────────────
# Curated economic calendar.
# Impact: 1=low, 2=medium, 3=high
# Each event has a `next_*` function that returns the next occurrence
# given today's date. Keeps the calendar always fresh without manual
# updates.
# ──────────────────────────────────────────────────────────────────────────


def _next_weekday(year_month_day_template: str, target_weekday: int, week_of_month: int = None, from_date=None) -> datetime:
    """
    Find next occurrence of a weekday in a month-pattern.
    week_of_month=2 means "2nd <target_weekday> of the month".
    If from_date is given, find next occurrence on/after that date.
    """
    today = from_date or datetime.now(timezone.utc).date()
    for delta in range(0, 90):
        candidate = today + timedelta(days=delta)
        if candidate.weekday() != target_weekday:
            continue
        if week_of_month is not None:
            # which week of month is this?
            wom = (candidate.day - 1) // 7 + 1
            if wom != week_of_month:
                continue
        return datetime(candidate.year, candidate.month, candidate.day, 14, 0, 0, tzinfo=timezone.utc)
    return None


def _next_monthly(day_of_month: int, from_date=None) -> datetime:
    """Next occurrence of a specific day of month (skip if already passed)."""
    today = from_date or datetime.now(timezone.utc).date()
    yr, mo = today.year, today.month
    # try this month first
    try:
        candidate = datetime(yr, mo, day_of_month, 13, 30, 0, tzinfo=timezone.utc)
        if candidate.date() >= today:
            return candidate
    except ValueError:
        pass
    # next month
    mo += 1
    if mo > 12: mo = 1; yr += 1
    try:
        return datetime(yr, mo, day_of_month, 13, 30, 0, tzinfo=timezone.utc)
    except ValueError:
        return None


def _next_quarterly_earnings_window(month_offsets, from_date=None) -> datetime:
    """Next big tech earnings cluster: late Jan/Apr/Jul/Oct."""
    today = from_date or datetime.now(timezone.utc).date()
    for delta in range(0, 365):
        c = today + timedelta(days=delta)
        if c.month in month_offsets and 20 <= c.day <= 30 and c.weekday() < 4:
            return datetime(c.year, c.month, c.day, 20, 0, 0, tzinfo=timezone.utc)
    return None


def _build_events() -> List[Dict]:
    """Generate the live calendar from rule-based recurring patterns."""
    now = datetime.now(timezone.utc)
    events = []

    # FOMC meetings — real schedule, plus minutes (~21 days after each meeting)
    for year in [now.year, now.year + 1]:
        schedule = FOMC_SCHEDULE.get(year, [])
        for (mo, day) in schedule:
            try:
                meeting_dt = datetime(year, mo, day, 18, 0, 0, tzinfo=timezone.utc)
            except ValueError:
                continue
            if meeting_dt > now:
                events.append({
                    "name": "FOMC Rate Decision",
                    "category": "FED",
                    "impact": 3,
                    "datetime": meeting_dt.isoformat(),
                    "blurb": "Federal Reserve rate decision + Powell press conference. Highest-impact macro event.",
                })
            # Minutes released 21 days (3 weeks) after meeting at 18:00 UTC
            minutes_dt = meeting_dt + timedelta(days=21)
            if minutes_dt > now:
                events.append({
                    "name": "FOMC Minutes",
                    "category": "FED",
                    "impact": 2,
                    "datetime": minutes_dt.isoformat(),
                    "blurb": "Detailed minutes from prior FOMC meeting. Markets parse for hints on next move.",
                })

    # CPI: ~10th-15th of each month at 13:30 UTC
    cpi = _next_monthly(12)
    if cpi and cpi > now:
        events.append({
            "name": "US CPI Inflation",
            "category": "MACRO",
            "impact": 3,
            "datetime": cpi.isoformat(),
            "blurb": "Headline + core CPI. Drives rate path expectations.",
        })

    # PPI: ~14th-15th of each month
    ppi = _next_monthly(14)
    if ppi and ppi > now:
        events.append({
            "name": "US PPI Producer Prices",
            "category": "MACRO",
            "impact": 2,
            "datetime": ppi.isoformat(),
            "blurb": "Wholesale inflation, leading indicator for CPI.",
        })

    # NFP: first Friday of the month
    nfp = _next_weekday(None, target_weekday=4, week_of_month=1)
    if nfp and nfp > now:
        events.append({
            "name": "US Nonfarm Payrolls",
            "category": "MACRO",
            "impact": 3,
            "datetime": nfp.isoformat(),
            "blurb": "Jobs report. Drives USD + risk asset volatility.",
        })

    # Retail sales: ~15th-17th of month
    retail = _next_monthly(16)
    if retail and retail > now:
        events.append({
            "name": "US Retail Sales",
            "category": "MACRO",
            "impact": 2,
            "datetime": retail.isoformat(),
            "blurb": "Consumer spending pulse.",
        })

    # ECB: every ~6 weeks Thursday
    for monthdelta in range(0, 6):
        target = now + timedelta(days=30 * monthdelta)
        c_year, c_month = target.year, target.month
        # 2nd Thu of target month
        thu_count = 0
        for d in range(31):
            try:
                dt = datetime(c_year, c_month, 1 + d, 12, 15, 0, tzinfo=timezone.utc)
            except ValueError:
                break
            if dt.weekday() == 3:
                thu_count += 1
                if thu_count == 2:
                    if dt > now:
                        events.append({
                            "name": "ECB Rate Decision",
                            "category": "FED",
                            "impact": 2,
                            "datetime": dt.isoformat(),
                            "blurb": "European Central Bank policy. EUR + DXY mover.",
                        })
                    break

    # Big-tech earnings: late Jan, Apr, Jul, Oct
    big_tech_dt = _next_quarterly_earnings_window([1, 4, 7, 10])
    if big_tech_dt and big_tech_dt > now:
        events.append({
            "name": "Big Tech Earnings Cluster",
            "category": "EQUITIES",
            "impact": 2,
            "datetime": big_tech_dt.isoformat(),
            "blurb": "AAPL/MSFT/GOOG/AMZN/META/NVDA earnings window. Spills into crypto.",
        })

    # Jackson Hole: late August (~24th)
    aug_jh = datetime(now.year if now.month <= 8 else now.year + 1, 8, 24, 14, 0, 0, tzinfo=timezone.utc)
    if aug_jh > now and (aug_jh - now).days < 200:
        events.append({
            "name": "Jackson Hole Symposium",
            "category": "FED",
            "impact": 3,
            "datetime": aug_jh.isoformat(),
            "blurb": "Annual Fed symposium. Powell speech historically moves markets significantly.",
        })

    # BTC quarterly options expiry: end of March/Jun/Sep/Dec
    for mo in [3, 6, 9, 12]:
        try:
            yr = now.year if now.month <= mo else now.year + 1
            expiry = datetime(yr, mo, 28, 8, 0, 0, tzinfo=timezone.utc)
            # last Friday of month
            while expiry.weekday() != 4:
                expiry -= timedelta(days=1)
            if expiry > now and (expiry - now).days < 120:
                events.append({
                    "name": "BTC Quarterly Options Expiry",
                    "category": "CRYPTO",
                    "impact": 2,
                    "datetime": expiry.isoformat(),
                    "blurb": "Largest options expiry of the quarter. Max pain dynamics.",
                })
                break
        except ValueError:
            continue

    # Sort by datetime
    events.sort(key=lambda e: e["datetime"])
    return events


@router.get("/calendar/events")
async def api_calendar_events(limit: int = 12):
    """Get upcoming macro/crypto events with impact rating."""
    events = _build_events()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "events": events[:limit],
        "total": len(events),
    }
