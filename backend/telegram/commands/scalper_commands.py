"""
Institutional Scalper Telegram Commands
Commands: /scalper, /scalper scan, /scalper on/off, /scalper leverage, /scalper trades, /scalper risk
"""
import logging
from typing import Tuple, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# /scalper  — full engine status dashboard
# ---------------------------------------------------------------------------

async def handle_scalper_status(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scalper — show full engine status"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.\n\nCheck server logs — it may still be starting up.", "scalper"

        lev_info = engine.get_adaptive_leverage()
        factors  = lev_info.get("factors", {})
        daily_pnl = lev_info.get("daily_pnl", 0.0)
        active_count = lev_info.get("active_trades", 0)
        consec = lev_info.get("consec_losses", 0)
        cooldown = lev_info.get("cooldown_remaining", 0)

        # Determine risk tier label
        if daily_pnl <= -5000:
            risk_tier = "HARD STOP — no trading today"
        elif daily_pnl <= -4000:
            risk_tier = "Tier 2 — 25x max, $50 position"
        elif daily_pnl <= -2500:
            risk_tier = "Tier 1 — 25x max leverage"
        else:
            risk_tier = "Normal"

        # Win rate from last 20 trades
        win_rate = factors.get("win_rate", 50.0)

        response = f"""INSTITUTIONAL SCALPER v1

Status: {"ACTIVE" if engine.active else "PAUSED"}
Exchange: MEXC BTCUSDT Perpetual

LIVE SNAPSHOT
Active Trades: {active_count}/5
Daily PnL: ${daily_pnl:+.2f}
Risk Tier: {risk_tier}
Win Rate (last 20): {win_rate:.1f}%
Consec Losses: {consec}{"  (cooldown: " + str(cooldown) + " trades)" if cooldown > 0 else ""}

AI LEVERAGE DECISION
Recommended: {lev_info.get("recommended_leverage", 25)}x
Setup Score: {factors.get("setup_score", 0):.1f}/100
Narrative: {factors.get("decision_narrative", "—")}

FACTOR BREAKDOWN
Base leverage:    25x
Win rate factor:  +{factors.get("win_rate_factor", 0):.1f}
Volatility adj:   +{factors.get("volatility_factor", 0):.1f}
Confluence bonus: +{factors.get("confluence_bonus", 0):.1f}
Sharpe adj:       {factors.get("sharpe_adjustment", 0):+.1f}
R:R factor:       +{factors.get("rr_factor", 0):.1f}
Raw total:        {factors.get("raw_leverage", 25):.1f}x → clamped to {lev_info.get("recommended_leverage", 25)}x

HARD RISK LIMITS
-$2,500 → 25x cap
-$4,000 → 25x + $50 position
-$5,000 → STOP all trading

Commands:
/scalper scan — force analysis now
/scalper leverage — detailed leverage breakdown
/scalper trades — open + recent closed trades
/scalper risk — risk dashboard
/scalper on — start engine
/scalper off — pause engine"""

        return response, "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_status error: {e}", exc_info=True)
        return f"Error fetching scalper status: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# /scalper scan  — run one analysis cycle right now
# ---------------------------------------------------------------------------

async def handle_scalper_scan(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scalper scan — trigger an immediate setup analysis"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.", "scalper"

        if not engine.active:
            return "Engine is paused. Use /scalper on to start it first.", "scalper"

        if not engine.check_daily_limits():
            daily_pnl = engine.track_daily_loss()
            return f"Daily hard stop active (PnL: ${daily_pnl:+.2f}). No scanning until UTC midnight.", "scalper"

        # Run analysis
        confidence, leverage, signal = await engine.analyze_setup("BTC/USDT")

        if signal is None:
            daily_pnl = engine.track_daily_loss()
            return f"""SCALPER SCAN — NO SIGNAL

No valid setup found at this moment.

Possible reasons:
- Fewer than 2 timeframes aligned (need 5m/15m/30m consensus)
- Less than 4 confluences hit
- R:R below 1.5:1
- Market regime conflict (LONG blocked in BEARISH, etc.)

Daily PnL: ${daily_pnl:+.2f}
Active trades: {len(engine.active_trades)}/5

Run again in 30-60 seconds.""", "scalper"

        f = signal.leverage_factors
        direction_label = "LONG" if signal.direction.value == "LONG" else "SHORT"

        response = f"""SCALPER SCAN — SIGNAL FOUND

Direction: {direction_label}
Confidence: {confidence:.1f}%
Leverage: {leverage}x
Setup Score: {f.setup_score:.1f}/100

ENTRY LEVELS
Entry: ${signal.entry_price:,.2f}
Stop Loss: ${signal.stop_loss:,.2f}
Take Profit: ${signal.take_profit:,.2f}
R:R Ratio: {signal.rr_ratio:.2f}:1

TIMEFRAME ALIGNMENT
Aligned: {signal.timeframe_alignment}/3 timeframes
Regime: {signal.market_regime}

CONFLUENCES HIT ({signal.confluence_count} total)
"""
        for c in signal.confluences_hit:
            response += f"- {c}\n"

        response += f"""
AI LEVERAGE FACTORS
Win Rate: {f.win_rate:.1f}% (+{f.win_rate_factor:.1f})
Volatility (ATR%ile): {f.atr_percentile:.0f} (+{f.volatility_factor:.1f})
Confluence Score: {f.confluence_score}/5 (+{f.confluence_bonus:.1f})
Sharpe: {f.sharpe_ratio:.2f} ({f.sharpe_adjustment:+.1f})
R:R bonus: +{f.rr_factor:.1f}
Final: {leverage}x

{f.decision_narrative}

Note: Trade executes automatically on next loop tick if this signal passes all checks."""

        return response, "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_scan error: {e}", exc_info=True)
        return f"Scan error: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# /scalper leverage  — standalone leverage model breakdown
# ---------------------------------------------------------------------------

async def handle_scalper_leverage(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scalper leverage — show current AI leverage decision in detail"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.", "scalper"

        info    = engine.get_adaptive_leverage()
        factors = info.get("factors", {})
        lev     = info.get("recommended_leverage", 25)
        score   = factors.get("setup_score", 0)

        response = f"""ADAPTIVE LEVERAGE MODEL

Current Recommendation: {lev}x
Setup Quality Score: {score:.1f}/100
Decision: {factors.get("decision_narrative", "—")}

HOW IT WAS CALCULATED

Base leverage:          25x
+ Win rate factor:      +{factors.get("win_rate_factor", 0):.2f}
  (win_rate={factors.get("win_rate", 50):.1f}% — above 50% earns leverage)

+ Volatility factor:    +{factors.get("volatility_factor", 0):.2f}
  (ATR percentile={factors.get("atr_percentile", 50):.0f} — low vol = more leverage)

+ Confluence bonus:     +{factors.get("confluence_bonus", 0):.2f}
  (score {factors.get("confluence_score", 1)}/5 × 15)

+ Sharpe adjustment:    {factors.get("sharpe_adjustment", 0):+.2f}
  (Sharpe={factors.get("sharpe_ratio", 0):.3f} — negative penalises leverage)

+ R:R factor:           +{factors.get("rr_factor", 0):.2f}
  (bonus for R:R above 1.5 minimum)

Raw total:              {factors.get("raw_leverage", 25):.2f}x
Clamped [25–150]:       {lev}x

LEVERAGE TIERS (setup score → max allowed)
≥ 90   Exceptional → 150x
70–89  Good        → 75–100x
50–69  Okay        → 50–75x
40–49  Marginal    → 25–50x
< 40   Skip        → don't trade

Risk overrides (always win):
3 consecutive losses → 25x for next 5 trades
Daily PnL ≤ -$2,500  → 25x hard cap
Daily PnL ≤ -$5,000  → no trading at all"""

        return response, "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_leverage error: {e}", exc_info=True)
        return f"Error: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# /scalper trades  — open positions + recent closed trades
# ---------------------------------------------------------------------------

async def handle_scalper_trades(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scalper trades — show open trades and recent history"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.", "scalper"

        now = datetime.now(timezone.utc)

        # ---- Open trades ----
        if engine.active_trades:
            response = f"OPEN TRADES ({len(engine.active_trades)}/5)\n\n"
            for tid, trade in engine.active_trades.items():
                elapsed_secs = (now - trade.open_time).total_seconds()
                elapsed_str  = f"{int(elapsed_secs // 60)}m {int(elapsed_secs % 60)}s"
                time_left    = max(0, trade.max_hold_secs - elapsed_secs)
                tl_str       = f"{int(time_left // 60)}m {int(time_left % 60)}s"

                response += f"""{trade.direction.value} {trade.symbol}
Trade ID: {tid}
Entry: ${trade.entry_price:,.2f}
Stop Loss: ${trade.stop_loss:,.2f}
Take Profit: ${trade.take_profit:,.2f}
Leverage: {trade.leverage}x
Size: ${trade.position_size_usd:.2f} (scale: {trade.scale_factor:.0%})
Elapsed: {elapsed_str} | Time left: {tl_str}
TP1 hit: {"Yes" if trade.tp1_hit else "No"}  |  TP2 hit: {"Yes" if trade.tp2_hit else "No"}
Trailing: {"Active" if trade.trailing_stop_active else "Not yet"}

"""
        else:
            response = "OPEN TRADES\nNo open trades right now.\n\n"

        # ---- Recent closed trades (last 5) ----
        closed = [t for t in engine.trade_history if t.get("state") == "CLOSED"][-5:]
        if closed:
            response += f"RECENT CLOSED TRADES (last {len(closed)})\n\n"
            for t in reversed(closed):
                pnl   = t.get("pnl_usd", 0)
                pct   = t.get("pnl_pct", 0)
                win   = t.get("is_win", False)
                symbol = t.get("symbol", "BTC/USDT").replace("/", "")
                response += f"""{"WIN" if win else "LOSS"}  {t.get("direction", "?")} {symbol}
Entry: ${t.get("entry_price", 0):,.2f}  Exit: ${t.get("exit_price", 0):,.2f}
PnL: ${pnl:+.2f} ({pct:+.2f}%)
Leverage: {t.get("leverage", "?")}x  |  Reason: {t.get("exit_reason", "?")}
Held: {t.get("hold_duration_secs", 0):.0f}s  |  Score: {t.get("setup_score", 0):.0f}/100

"""
        else:
            response += "RECENT CLOSED TRADES\nNo completed trades yet.\n"

        # ---- Summary line ----
        wins  = sum(1 for t in engine.trade_history if t.get("is_win"))
        total = len(engine.trade_history)
        wr    = (wins / total * 100) if total > 0 else 0
        response += f"Overall: {wins}/{total} wins ({wr:.1f}%) | Daily PnL: ${engine.track_daily_loss():+.2f}"

        return response, "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_trades error: {e}", exc_info=True)
        return f"Error: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# /scalper risk  — risk management dashboard
# ---------------------------------------------------------------------------

async def handle_scalper_risk(text: str, chat_id: int, context: dict) -> Tuple[str, str]:
    """Handle /scalper risk — full risk controls dashboard"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.", "scalper"

        daily_pnl = engine.track_daily_loss()
        consec    = engine._consec_losses
        cooldown  = engine._consec_loss_cooldown_remaining
        can_trade = engine.check_daily_limits()

        # Loss tier state
        if daily_pnl <= -5000:
            tier_status = "HARD STOP — ALL TRADING HALTED"
        elif daily_pnl <= -4000:
            tier_status = "Tier 2 — 25x only, max $50 position"
        elif daily_pnl <= -2500:
            tier_status = "Tier 1 — 25x leverage cap active"
        else:
            tier_status = "Normal — full adaptive leverage"

        # Progress bars toward each threshold
        def pct_to_bar(current_loss: float, limit: float) -> str:
            if limit == 0:
                return "████████████ 100%"
            ratio = min(abs(current_loss) / abs(limit), 1.0)
            filled = int(ratio * 10)
            return f"{'█' * filled}{'░' * (10 - filled)} {ratio * 100:.0f}%"

        response = f"""RISK DASHBOARD

Trading Allowed: {"YES" if can_trade else "NO — HARD STOP ACTIVE"}

DAILY LOSS TIERS
Current PnL: ${daily_pnl:+.2f}

Tier 1 (-$2,500): {pct_to_bar(daily_pnl, -2500)}
  → 25x leverage cap

Tier 2 (-$4,000): {pct_to_bar(daily_pnl, -4000)}
  → 25x + position reduced to $50

Hard Stop (-$5,000): {pct_to_bar(daily_pnl, -5000)}
  → Stop all trading

Active Status: {tier_status}

CONSECUTIVE LOSS DISCIPLINE
Consecutive losses: {consec}/3
Cooldown (25x forced): {cooldown} trades remaining
  (Triggers after 3 losses in a row → 5 trade cooldown)

POSITION LIMITS
Max position size: $150 (normal) / $50 (tier 2)
Max concurrent: 5 total, 3 per symbol
Max hold: 5 min (5m scalp) / 15 min (15m setup)

SCALE-OUT PLAN
50% closed at +1.0% profit (TP1)
25% closed at +1.5% profit (TP2)
25% trailing stop (0.5% ATR trail)

ENTRY GATE (all must pass)
- 2 or 3 timeframes aligned (5m/15m/30m)
- 4+ confluences across sets A/B/C
- R:R ≥ 1.5:1
- Regime match (no LONG in BEARISH, no SHORT in BULLISH)
- Setup score ≥ 40/100"""

        return response, "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_risk error: {e}", exc_info=True)
        return f"Error: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# /scalper on | /scalper off  — toggle the engine
# ---------------------------------------------------------------------------

async def handle_scalper_toggle(
    text: str, chat_id: int, context: dict, enabled: bool
) -> Tuple[str, str]:
    """Handle /scalper on and /scalper off"""
    import app_state

    try:
        engine = app_state.institutional_scalper
        if not engine:
            return "Institutional Scalper not initialized.", "scalper"

        engine.active = enabled

        if enabled:
            daily_pnl = engine.track_daily_loss()
            can_trade = engine.check_daily_limits()
            if not can_trade:
                return f"""Scalper enabled but daily hard stop is active.

Daily PnL: ${daily_pnl:+.2f} (limit: -$5,000)

Engine will resume automatically at UTC midnight.""", "scalper"

            return f"""INSTITUTIONAL SCALPER ENABLED

Running on MEXC BTCUSDT Perpetual
Scan interval: every 30 seconds

Active settings:
- Leverage: 25x–150x (AI-adaptive)
- Position size: up to $150
- Timeframes: 5m / 15m / 30m
- Min confluences: 4 required
- Min R:R: 1.5:1

Daily PnL so far: ${daily_pnl:+.2f}

Use /scalper scan to trigger an immediate analysis.""", "scalper"

        else:
            active_count = len(engine.active_trades)
            note = f"\n\n{active_count} open trade(s) will continue to be managed until closed." if active_count > 0 else ""
            return f"""INSTITUTIONAL SCALPER PAUSED

No new trades will be opened.
Existing trades remain managed (SL/TP/trailing still active).{note}

Use /scalper on to resume.""", "scalper"

    except Exception as e:
        logger.error(f"handle_scalper_toggle error: {e}", exc_info=True)
        return f"Error: {str(e)}", "scalper"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

async def route_scalper_command(text: str, chat_id: int, context: dict) -> Optional[Tuple[str, str]]:
    """Route /scalper commands"""
    text_lower = text.lower().strip()

    if text_lower == "/scalper":
        return await handle_scalper_status(text, chat_id, context)
    elif text_lower == "/scalper scan":
        return await handle_scalper_scan(text, chat_id, context)
    elif text_lower == "/scalper leverage":
        return await handle_scalper_leverage(text, chat_id, context)
    elif text_lower == "/scalper trades":
        return await handle_scalper_trades(text, chat_id, context)
    elif text_lower == "/scalper risk":
        return await handle_scalper_risk(text, chat_id, context)
    elif text_lower == "/scalper on":
        return await handle_scalper_toggle(text, chat_id, context, enabled=True)
    elif text_lower == "/scalper off":
        return await handle_scalper_toggle(text, chat_id, context, enabled=False)

    return None
