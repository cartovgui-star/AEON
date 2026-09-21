"""
AEGIS — AEON's Risk Manager
Monitors the PERSONAL account. Portfolio concentration, drawdown, correlation risk.
Recommendations only apply to the PERSONAL account (tagged with account_scope="PERSONAL").
Does NOT affect sizing. Does NOT affect other accounts.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from team.base import AnalysisResult, MarketSignal, Recommendation, RecType

logger = logging.getLogger(__name__)

PERSONA = (
    "AEON's Risk Manager. You guard the portfolio with discipline — drawdown limits, "
    "concentration risk, correlation exposure. You are the last line of defense. "
    "You speak in 'max drawdown', 'correlated exposure', 'risk budget'. Unemotional. Strict."
)

PERSONAL_ACCOUNT = "PERSONAL"
MAX_DRAWDOWN_PCT  = 15.0   # alert if drawdown > 15% from peak
MAX_CONCENTRATION = 0.40   # alert if one symbol > 40% of open exposure


async def analyze(db) -> AnalysisResult:
    observations: List[str] = []
    raw: Dict[str, Any] = {}
    recommendation: Optional[Recommendation] = None
    risk_flags = 0

    try:
        # ── 1. Load PERSONAL account ─────────────────────────────────────────
        account = await db.paper_accounts.find_one({"_id": PERSONAL_ACCOUNT})
        if not account:
            return AnalysisResult(
                specialist="AEGIS", signal=MarketSignal.NEUTRAL, confidence=20,
                observations=[f"Personal account '{PERSONAL_ACCOUNT}' not found — create it first."]
            )

        balance       = account.get("balance", 0)
        peak          = account.get("peak_balance", balance)
        starting      = account.get("starting_balance", balance)
        positions     = [p for p in account.get("positions", []) if p.get("status") == "open"]
        total_pnl     = account.get("total_pnl", 0)
        wins          = account.get("wins", 0)
        losses        = account.get("losses", 0)
        consec_losses = account.get("consecutive_losses", 0)

        raw.update({"balance": balance, "peak": peak, "starting": starting,
                    "open_positions": len(positions), "total_pnl": total_pnl})

        observations.append(
            f"PERSONAL account: ${balance:,.2f} | Peak: ${peak:,.2f} | "
            f"PnL: ${total_pnl:+,.2f} | {wins}W/{losses}L"
        )

        # ── 2. Drawdown analysis ──────────────────────────────────────────────
        if peak > 0:
            drawdown_pct = (peak - balance) / peak * 100
            raw["drawdown_pct"] = round(drawdown_pct, 2)
            observations.append(f"Drawdown from peak: {drawdown_pct:.1f}%")
            if drawdown_pct > MAX_DRAWDOWN_PCT:
                risk_flags += 2
                observations.append(
                    f"⚠️ DRAWDOWN ALERT: {drawdown_pct:.1f}% from peak ${peak:,.0f}. "
                    f"Exceeds {MAX_DRAWDOWN_PCT}% threshold."
                )
            elif drawdown_pct > MAX_DRAWDOWN_PCT * 0.6:
                risk_flags += 1
                observations.append(f"Drawdown approaching limit ({drawdown_pct:.1f}% of {MAX_DRAWDOWN_PCT}% max).")

        # ── 3. Consecutive losses ─────────────────────────────────────────────
        raw["consecutive_losses"] = consec_losses
        if consec_losses >= 4:
            risk_flags += 2
            observations.append(f"⚠️ {consec_losses} consecutive losses — system may be in adverse regime.")
        elif consec_losses >= 2:
            risk_flags += 1
            observations.append(f"{consec_losses} consecutive losses — caution warranted.")

        # ── 4. Open position concentration ───────────────────────────────────
        if positions:
            total_margin  = sum(p.get("margin", 0) for p in positions)
            symbol_margin: Dict[str, float] = {}
            for p in positions:
                sym    = p.get("symbol", "UNKNOWN")
                margin = p.get("margin", 0)
                symbol_margin[sym] = symbol_margin.get(sym, 0) + margin

            most_concentrated = max(symbol_margin, key=symbol_margin.get)
            conc_pct = symbol_margin[most_concentrated] / total_margin if total_margin > 0 else 0
            raw["concentration"] = {
                "symbol": most_concentrated,
                "pct":    round(conc_pct, 3),
                "total_margin": round(total_margin, 2)
            }
            observations.append(
                f"Open exposure: {len(positions)} positions | "
                f"Top concentration: {most_concentrated} at {conc_pct*100:.0f}%"
            )
            if conc_pct > MAX_CONCENTRATION:
                risk_flags += 1
                observations.append(
                    f"⚠️ CONCENTRATION RISK: {most_concentrated} is {conc_pct*100:.0f}% of open margin."
                )

        # ── 5. Balance health vs starting ────────────────────────────────────
        if starting > 0:
            balance_pct = (balance - starting) / starting * 100
            raw["return_vs_start"] = round(balance_pct, 2)
            observations.append(f"Return vs starting balance: {balance_pct:+.1f}%")

        # ── 6. Signal and recommendation ─────────────────────────────────────
        if risk_flags >= 3:
            signal     = MarketSignal.CAUTION
            confidence = min(85, 60 + risk_flags * 5)
            recommendation = Recommendation(
                type=RecType.RAISE_CONFIDENCE,
                reasoning=(
                    f"PERSONAL account risk flags: {risk_flags} triggered "
                    f"(drawdown {raw.get('drawdown_pct',0):.1f}%, "
                    f"{consec_losses} consecutive losses). "
                    "Raising confidence threshold to protect remaining capital."
                ),
                confidence=0.85,
                params={"min_confidence": 85, "symbol": None,
                        "account_scope": PERSONAL_ACCOUNT},  # AEGIS only
                duration_hours=8,
            )
        elif risk_flags >= 1:
            signal     = MarketSignal.CAUTION
            confidence = 60
        else:
            signal     = MarketSignal.NEUTRAL
            confidence = 55
            observations.append("Risk metrics within acceptable bounds. No action required.")

        return AnalysisResult(
            specialist="AEGIS",
            signal=signal,
            confidence=confidence,
            observations=observations,
            recommendation=recommendation,
            raw_data=raw,
        )

    except Exception as e:
        logger.error(f"[AEGIS] Analysis error: {e}")
        return AnalysisResult(
            specialist="AEGIS", signal=MarketSignal.NEUTRAL, confidence=20,
            observations=["Risk analysis failed — data pipeline error."],
            error=str(e),
        )
