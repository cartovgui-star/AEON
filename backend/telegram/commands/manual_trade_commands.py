"""
Manual Trade Commands
/trade  — place a trade manually from Telegram signal
/close  — close a specific open position

Usage:
  /trade BTC LONG           — auto-leverage, PERSONAL account
  /trade BTC LONG 20x       — specify leverage
  /trade ETH SHORT 10x rl   — account shorthand: rl=reallife, p=personal, t5=tier5k, t1=tier1k, t500=tier500
  /close BTC                — close first open BTC position on any account
  /close BTC rl             — close BTC on reallife account

The trade bypasses the H-gate (it's your explicit choice).
It goes through the full paper_trading.open_position() pipeline so it
shows up correctly everywhere: Trading Hub, accounts, PnL analytics.
"""

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Account shorthand map — matches what Carlos types naturally
_ACC_SHORTHANDS = {
    "rl": "REAL_LIFE", "reallife": "REAL_LIFE", "real": "REAL_LIFE", "real_life": "REAL_LIFE",
    "p": "PERSONAL", "personal": "PERSONAL", "per": "PERSONAL",
    "t5": "TIER_5K", "tier5k": "TIER_5K", "5k": "TIER_5K", "t5k": "TIER_5K",
    "t1": "TIER_1K", "tier1k": "TIER_1K", "1k": "TIER_1K", "t1k": "TIER_1K",
    "t500": "TIER_500", "tier500": "TIER_500", "500": "TIER_500",
    "all": "ALL",
}

def _parse_trade_args(parts: list) -> dict:
    """
    Parse /trade args into a dict.
    Input parts: everything after /trade, e.g. ["BTC", "LONG", "20x", "rl"]
    Returns: {symbol, direction, leverage, account_id, error?}
    """
    if len(parts) < 2:
        return {"error": "Need at least: /trade SYMBOL DIRECTION\nExample: /trade BTC LONG 20x"}

    symbol = parts[0].upper()
    if not symbol.endswith("/USDT"):
        symbol = symbol.rstrip("USDT").rstrip("/") + "/USDT"

    direction = parts[1].upper()
    if direction not in ("LONG", "SHORT", "L", "S", "BUY", "SELL"):
        return {"error": f"Direction must be LONG or SHORT, got '{parts[1]}'"}
    if direction in ("L", "BUY"): direction = "LONG"
    if direction in ("S", "SELL"): direction = "SHORT"

    leverage    = 0    # 0 = auto
    account_id  = "PERSONAL"

    for part in parts[2:]:
        p = part.lower().strip()
        # Leverage: "20x", "20X", "20"
        if p.rstrip("x").isdigit():
            leverage = int(p.rstrip("x"))
        elif p in _ACC_SHORTHANDS:
            account_id = _ACC_SHORTHANDS[p]

    return {"symbol": symbol, "direction": direction, "leverage": leverage, "account_id": account_id}


async def handle_trade(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /trade command — opens a manual paper trade."""
    import app_state

    parts = text.strip().split()[1:]  # drop /trade
    parsed = _parse_trade_args(parts)

    if "error" in parsed:
        return (
            f"❌ {parsed['error']}\n\n"
            "📋 *Examples:*\n"
            "`/trade BTC LONG`\n"
            "`/trade ETH SHORT 15x`\n"
            "`/trade SOL LONG 10x rl`  ← reallife account\n"
            "`/trade BTC LONG 20x all` ← all accounts",
            "trading"
        )

    symbol     = parsed["symbol"]
    direction  = parsed["direction"]
    leverage   = parsed["leverage"]
    account_id = parsed["account_id"]

    if not app_state.paper_trading or not app_state.market_intel:
        return "❌ Trading system not ready.", "trading"

    # Live price
    try:
        ticker = await app_state.market_intel.get_ticker(symbol)
        entry_price = float(ticker.get("last") or ticker.get("close") or ticker.get("price") or 0)
    except Exception as e:
        return f"❌ Could not fetch price for {symbol}: {e}", "trading"

    if entry_price <= 0:
        return f"❌ No live price for {symbol}.", "trading"

    # SL/TP
    try:
        from paper_trading import get_dynamic_leverage, calculate_smart_stops
        if leverage == 0:
            leverage = get_dynamic_leverage(symbol, 85, direction)
        stop_loss, take_profit = calculate_smart_stops(entry_price, leverage, direction)
    except Exception as e:
        return f"❌ Could not compute stops: {e}", "trading"

    # Determine accounts to trade
    from paper_trading import ACCOUNTS
    if account_id == "ALL":
        account_ids = list(ACCOUNTS.keys())
    elif account_id not in ACCOUNTS:
        return f"❌ Unknown account '{account_id}'. Use: rl, p, t5, t1, t500, all", "trading"
    else:
        account_ids = [account_id]

    results = []
    failed  = []
    for acc_id in account_ids:
        try:
            res = await app_state.paper_trading.open_position(
                account_id=acc_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=leverage,
                risk_pct=ACCOUNTS[acc_id].get("base_risk_pct", 2.0),
                confidence=90,   # manual = high conviction
                strategy="CARLOS_MANUAL",
            )
            if res and res.get("status") in ("opened", "open") or res.get("trade_id"):
                cfg = ACCOUNTS[acc_id]
                margin = res.get("margin", 0)
                results.append(f"  {cfg.get('emoji','📊')} {cfg.get('name',acc_id)} — margin ${margin:.2f}")
            else:
                reason = res.get("reason", str(res))[:60] if res else "unknown"
                failed.append(f"  ✗ {acc_id}: {reason}")
        except Exception as e:
            failed.append(f"  ✗ {acc_id}: {str(e)[:60]}")

    if not results and failed:
        return f"❌ Trade failed on all accounts:\n" + "\n".join(failed), "trading"

    rr = round(abs(take_profit - entry_price) / max(abs(stop_loss - entry_price), 0.0001), 2)
    dir_emoji = "🟢 LONG" if direction == "LONG" else "🔴 SHORT"

    msg = (
        f"✅ *Manual Trade Opened*\n\n"
        f"📍 {symbol} {dir_emoji} {leverage}x\n"
        f"💵 Entry: ${entry_price:,.4f}\n"
        f"🛑 SL: ${stop_loss:,.4f}\n"
        f"🎯 TP: ${take_profit:,.4f}  (R:R {rr}:1)\n\n"
        f"📂 *Accounts:*\n" + "\n".join(results)
    )
    if failed:
        msg += "\n⚠️ *Skipped:*\n" + "\n".join(failed)

    msg += "\n\n`/close " + symbol.replace("/USDT", "") + "` to close"
    return msg, "trading"


async def handle_trade_close(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """
    /close SYMBOL [account] — close matching open position.
    If no account specified, closes the first match across all accounts.
    """
    import app_state
    from paper_trading import ACCOUNTS

    parts = text.strip().split()[1:]
    if not parts:
        return "Usage: `/close BTC` or `/close ETH rl`", "trading"

    raw_symbol = parts[0].upper()
    symbol = raw_symbol if "/" in raw_symbol else raw_symbol + "/USDT"

    account_id = None
    if len(parts) >= 2:
        short = parts[1].lower()
        account_id = _ACC_SHORTHANDS.get(short)
        if not account_id:
            return f"❌ Unknown account '{parts[1]}'. Use: rl, p, t5, t1, t500", "trading"

    if not app_state.paper_trading:
        return "❌ Paper trading not ready.", "trading"

    try:
        # Find matching open positions
        positions = await app_state.paper_trading.get_open_positions()
        matches = [
            p for p in positions
            if p.get("symbol") == symbol
            and (account_id is None or p.get("account_id") == account_id)
        ]
        if not matches:
            return f"No open {symbol} positions found.", "trading"

        closed = []
        for pos in matches:
            pos_id  = str(pos.get("_id") or pos.get("id", ""))
            acc_id  = pos.get("account_id", "?")
            try:
                # Fetch current price
                ticker = await app_state.market_intel.get_ticker(symbol)
                exit_price = float(ticker.get("last") or ticker.get("close") or 0)
            except Exception:
                exit_price = 0.0

            try:
                res = await app_state.paper_trading.close_position(
                    position_id=pos_id,
                    exit_price=exit_price,
                    close_reason="manual_close",
                )
                pnl = res.get("realized_pnl", 0) if res else 0
                cfg = ACCOUNTS.get(acc_id, {})
                emoji = "🟢" if pnl >= 0 else "🔴"
                closed.append(f"  {cfg.get('emoji','📊')} {cfg.get('name', acc_id)} — {emoji} ${pnl:+.2f}")
            except Exception as e:
                closed.append(f"  ✗ {acc_id}: {str(e)[:60]}")

        return (
            f"✅ *Closed {symbol}*\n\n" + "\n".join(closed),
            "trading"
        )
    except Exception as e:
        return f"❌ Close failed: {e}", "trading"


def route_manual_trade_command(text: str) -> bool:
    """Return True if this command is handled here."""
    cmd = text.lower().split()[0] if text else ""
    return cmd in ("/trade", "/close")


async def handle(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    cmd = text.lower().split()[0] if text else ""
    if cmd == "/trade":
        return await handle_trade(text, chat_id, context)
    if cmd == "/close":
        return await handle_trade_close(text, chat_id, context)
    return None
