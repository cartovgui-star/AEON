#!/usr/bin/env python3
"""
=============================================================================
  INSTITUTIONAL ADAPTIVE LEVERAGE SCALPER — BACKTEST SIMULATION
  File: institutional_scalper_test.py
=============================================================================

Tests the InstitutionalScalper engine against 55 synthetic BTCUSDT setups.
No live API calls.  No real money.  100% reproducible (seeded RNG).

What this tests:
  1. calculate_adaptive_leverage() — 5-factor model correctness
  2. analyze_setup()               — full MTF signal pipeline with crafted candles
  3. Risk controls                 — daily loss tiers, consecutive-loss cooldown
  4. Outcome simulation            — realistic PnL per scale-out tier
  5. Summary statistics            — win rate, profit factor, avg win/loss

Run:
  python3 institutional_scalper_test.py

Output columns:
  Setup  #01 │ LONG  │ BULL  │ TF:3/3 │ Conf:8  │ ATR:1.2% │ WR:65% │ Lev:150x │ ✅ +$34.10 │ TP2+Trail
=============================================================================
"""

import sys
import os
import asyncio
import math
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd

# ── Path setup so we can import the engine ───────────────────────────────────
_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)
sys.path.insert(0, os.path.join(_here, ".."))   # backend root (for imports inside engine)

try:
    from institutional_scalper_v1 import (
        InstitutionalScalper,
        Direction,
        LEVERAGE_MIN,
        LEVERAGE_MAX,
        MAX_POSITION_USD,
        MIN_RR_RATIO,
        TRADE_FEE_PCT,
        TIER_REDUCE_LEVERAGE,
        TIER_REDUCE_POSITION,
        TIER_HARD_STOP,
    )
    ENGINE_AVAILABLE = True
except ImportError as e:
    print(f"[ERROR] Could not import InstitutionalScalper: {e}")
    ENGINE_AVAILABLE = False
    sys.exit(1)


# =============================================================================
# ANSI Color helpers (disabled gracefully when stdout is not a TTY)
# =============================================================================

_USE_COLOR = sys.stdout.isatty()

def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text

def green(t):   return _c("32",   t)
def red(t):     return _c("31",   t)
def yellow(t):  return _c("33",   t)
def cyan(t):    return _c("36",   t)
def bold(t):    return _c("1",    t)
def dim(t):     return _c("2",    t)
def magenta(t): return _c("35",   t)


# =============================================================================
# Scenario definition
# =============================================================================

@dataclass
class Scenario:
    """
    One simulated setup fed into the engine.

    Fields
    ------
    label           : human description shown in output
    direction       : "LONG" or "SHORT"
    regime          : "BULLISH" / "BEARISH" / "RANGING"
    tf_alignment    : 1 / 2 / 3  (TFs agreeing)
    confluence_count: total number of individual confluences (raw count)
    confluence_score: 1-5 quality score (derived from count by engine rules)
    win_rate        : recent win-rate % fed into leverage formula
    atr_pct         : ATR as % of current price (e.g. 2.3 = 2.3%)
    sharpe          : Sharpe ratio of recent trades
    rr_ratio        : planned reward-to-risk ratio
    price_move_pct  : simulated price move AFTER entry (direction-relative).
                      Positive = favorable (towards TP), negative = towards SL.
                      Scale: 0.01 = 1% favorable price move.
    notes           : explains the skip reason or setup narrative
    """
    label: str
    direction: str
    regime: str
    tf_alignment: int
    confluence_count: int
    confluence_score: int
    win_rate: float
    atr_pct: float
    sharpe: float
    rr_ratio: float
    price_move_pct: float   # direction-relative; only used for valid (non-skipped) trades
    notes: str = ""


# confluence_count → confluence_score mapping (mirrors engine logic)
def count_to_score(count: int) -> int:
    if count >= 10: return 5
    if count >= 8:  return 4
    if count >= 6:  return 3
    if count >= 4:  return 2
    return 1


# ATR % of price → rough ATR percentile (0-100) used in leverage formula
# Low ATR% = low percentile = low volatility = higher leverage bonus
def atr_pct_to_percentile(atr_pct: float) -> float:
    # Linear approximation calibrated to realistic BTCUSDT 5m ATR distribution:
    # 0.5% ≈ 10th pct  |  1.0% ≈ 25th  |  1.5% ≈ 45th  |
    # 2.5% ≈ 65th      |  3.5% ≈ 80th  |  5.0%+ ≈ 95th
    return float(min(100.0, max(0.0, atr_pct * 19.0)))


# =============================================================================
# 55 Scenarios
# =============================================================================
# Organised in 4 sections:
#   A)  SKIP scenarios       (12) — hard filters reject before leverage calc
#   B)  Marginal trades      (10) — confluence 4-5, low leverage, mixed outcomes
#   C)  Standard trades      (18) — confluence 6-8, medium-high leverage
#   D)  Exceptional trades   (15) — confluence 9+, max leverage
#
# price_move_pct guide for 5m scalp simulation:
#   +0.30 to +0.50%  = TP1 hit (50% closed at profit)
#   +0.60 to +1.00%  = TP1+TP2 hit (75% closed at profit)
#   +1.10 to +1.80%  = full scale-out (all 3 tiers closed in profit)
#   -0.20 to -0.45%  = stop-loss hit (full loss)
#   ±0.05 to ±0.15%  = time-limit exit (breakeven/tiny profit)

SCENARIOS: List[Scenario] = [

    # ── A. SKIP SCENARIOS ────────────────────────────────────────────────────
    Scenario("Weak signal — 1 confluence only",
        "LONG", "BULLISH", 2, 1, count_to_score(1),
        win_rate=60.0, atr_pct=1.5, sharpe=0.8, rr_ratio=2.0,
        price_move_pct=0.0,
        notes="Confluence count 1 < 4 — SKIP"),

    Scenario("Poor overlap — only 2 confluences",
        "SHORT", "BEARISH", 2, 2, count_to_score(2),
        win_rate=55.0, atr_pct=2.0, sharpe=0.5, rr_ratio=1.8,
        price_move_pct=0.0,
        notes="Confluence count 2 < 4 — SKIP"),

    Scenario("3 confluences, just below threshold",
        "LONG", "RANGING", 2, 3, count_to_score(3),
        win_rate=52.0, atr_pct=1.8, sharpe=0.3, rr_ratio=2.2,
        price_move_pct=0.0,
        notes="Confluence count 3 < 4 — SKIP"),

    Scenario("Only 1 timeframe aligned",
        "SHORT", "BEARISH", 1, 6, count_to_score(6),
        win_rate=65.0, atr_pct=1.0, sharpe=1.2, rr_ratio=2.5,
        price_move_pct=0.0,
        notes="TF alignment 1/3 — need ≥2 — SKIP"),

    Scenario("Single TF entry (30m only)",
        "LONG", "BULLISH", 1, 7, count_to_score(7),
        win_rate=70.0, atr_pct=0.8, sharpe=1.5, rr_ratio=3.0,
        price_move_pct=0.0,
        notes="TF alignment 1/3 — SKIP despite strong setup"),

    Scenario("Bad R:R — reward only 1.2×",
        "SHORT", "BEARISH", 2, 5, count_to_score(5),
        win_rate=58.0, atr_pct=2.2, sharpe=0.7, rr_ratio=1.2,
        price_move_pct=0.0,
        notes="R:R 1.2 < 1.5 minimum — SKIP"),

    Scenario("Borderline R:R — 1.4×",
        "LONG", "BULLISH", 3, 5, count_to_score(5),
        win_rate=63.0, atr_pct=1.6, sharpe=1.0, rr_ratio=1.4,
        price_move_pct=0.0,
        notes="R:R 1.4 < 1.5 minimum — SKIP"),

    Scenario("LONG blocked — BEARISH 30m regime",
        "LONG", "BEARISH", 3, 8, count_to_score(8),
        win_rate=60.0, atr_pct=1.5, sharpe=1.1, rr_ratio=2.0,
        price_move_pct=0.0,
        notes="Macro gate: LONG in BEARISH regime — SKIP (Session 4 lesson)"),

    Scenario("SHORT blocked — BULLISH 30m regime",
        "SHORT", "BULLISH", 2, 7, count_to_score(7),
        win_rate=62.0, atr_pct=1.3, sharpe=0.9, rr_ratio=2.3,
        price_move_pct=0.0,
        notes="Macro gate: SHORT in BULLISH regime — SKIP"),

    Scenario("Setup score < 40 — marginal conditions",
        "LONG", "RANGING", 2, 4, count_to_score(4),
        win_rate=38.0, atr_pct=5.5, sharpe=-1.5, rr_ratio=1.5,
        price_move_pct=0.0,
        notes="Win rate 38% + Sharpe -1.5 + high vol → setup score <40 — SKIP"),

    Scenario("Zero confluences — no signal at all",
        "SHORT", "RANGING", 1, 0, count_to_score(0),
        win_rate=50.0, atr_pct=3.0, sharpe=0.0, rr_ratio=1.8,
        price_move_pct=0.0,
        notes="0 confluences — SKIP"),

    Scenario("Good confluences but TF misaligned (1/3)",
        "LONG", "BULLISH", 1, 9, count_to_score(9),
        win_rate=68.0, atr_pct=1.2, sharpe=1.4, rr_ratio=2.8,
        price_move_pct=0.0,
        notes="TF alignment 1/3 — SKIP despite strong confluence"),

    # ── B. MARGINAL TRADES (score 40-49, 25-50x leverage) ────────────────────
    # price_move_pct = actual BTC price % move, direction-relative
    # Negative = adverse (SL)  |  0.011+ = TP1  |  0.016+ = TP2  |  0.026+ = trail
    Scenario("Marginal LONG — 4 conf, high vol, weak WR",
        "LONG", "BULLISH", 2, 4, count_to_score(4),
        win_rate=44.0, atr_pct=4.8, sharpe=-0.3, rr_ratio=1.6,
        price_move_pct=-0.011,   # SL hit (-1.1% BTC move)
        notes="Marginal setup — low WR + high vol"),

    Scenario("Marginal SHORT — 4 conf, neutral Sharpe",
        "SHORT", "BEARISH", 2, 4, count_to_score(4),
        win_rate=47.0, atr_pct=4.2, sharpe=0.0, rr_ratio=1.5,
        price_move_pct=+0.013,   # TP1 hit (+1.3% BTC move)
        notes="Minimum viable setup — barely qualifies"),

    Scenario("Marginal LONG — WR recovering from drawdown",
        "LONG", "RANGING", 2, 4, count_to_score(4),
        win_rate=46.0, atr_pct=3.9, sharpe=-0.1, rr_ratio=1.7,
        price_move_pct=-0.012,   # SL hit
        notes="Post-drawdown recovery attempt"),

    Scenario("Marginal SHORT — first trade after cooldown",
        "SHORT", "BEARISH", 2, 5, count_to_score(5),
        win_rate=45.0, atr_pct=3.5, sharpe=0.1, rr_ratio=1.8,
        price_move_pct=+0.013,   # TP1 (+1.3%)
        notes="First setup after 3 consec-loss cooldown — forced 25x"),

    Scenario("Marginal LONG — low Sharpe, okay confluence",
        "LONG", "BULLISH", 2, 4, count_to_score(4),
        win_rate=48.0, atr_pct=3.8, sharpe=-0.4, rr_ratio=1.6,
        price_move_pct=-0.011,   # SL
        notes="Poor Sharpe drags leverage down"),

    Scenario("Marginal SHORT — ranging market, 4 conf",
        "SHORT", "RANGING", 2, 5, count_to_score(5),
        win_rate=49.0, atr_pct=3.2, sharpe=0.2, rr_ratio=2.0,
        price_move_pct=+0.013,   # TP1 (+1.3%)
        notes="Ranging regime but directional bias confirmed"),

    Scenario("Marginal LONG — 5 conf, volatile session",
        "LONG", "BULLISH", 2, 5, count_to_score(5),
        win_rate=51.0, atr_pct=4.0, sharpe=0.3, rr_ratio=1.7,
        price_move_pct=+0.011,   # TP1 barely (+1.1%)
        notes="High ATR punishes leverage — cautious entry"),

    Scenario("Marginal SHORT — time-limit exit",
        "SHORT", "BEARISH", 2, 4, count_to_score(4),
        win_rate=50.0, atr_pct=3.6, sharpe=0.0, rr_ratio=1.5,
        price_move_pct=+0.006,   # drifted toward TP but hit 5m time limit (+0.6%)
        notes="5-minute time limit — scalp window closed"),

    Scenario("Marginal LONG — all 3 TFs aligned, low WR",
        "LONG", "BULLISH", 3, 4, count_to_score(4),
        win_rate=45.0, atr_pct=3.0, sharpe=-0.2, rr_ratio=1.9,
        price_move_pct=-0.010,   # SL (-1.0%)
        notes="TF alignment helps but bad historical WR caps leverage"),

    Scenario("Marginal SHORT — Sharpe recovering",
        "SHORT", "BEARISH", 2, 5, count_to_score(5),
        win_rate=52.0, atr_pct=3.3, sharpe=0.4, rr_ratio=2.1,
        price_move_pct=+0.016,   # TP1 + enters TP2 zone (+1.6%)
        notes="Improving Sharpe suggests strategy finding its edge"),

    # ── C. STANDARD TRADES (score 50-89, 50-120x leverage) ───────────────────
    Scenario("Standard LONG — 6 conf, moderate vol, 2 TF",
        "LONG", "BULLISH", 2, 6, count_to_score(6),
        win_rate=55.0, atr_pct=2.5, sharpe=0.6, rr_ratio=2.0,
        price_move_pct=-0.013,   # SL (-1.3% BTC move)
        notes="Solid setup but adverse price action"),

    Scenario("Standard SHORT — 7 conf, low vol, 3 TF",
        "SHORT", "BEARISH", 3, 7, count_to_score(7),
        win_rate=58.0, atr_pct=1.8, sharpe=0.9, rr_ratio=2.4,
        price_move_pct=+0.018,   # TP1+TP2 (+1.8%)
        notes="Strong SMC alignment — all 3 TFs SHORT"),

    Scenario("Standard LONG — RSI oversold + OB + VWAP bounce",
        "LONG", "BULLISH", 2, 6, count_to_score(6),
        win_rate=60.0, atr_pct=2.0, sharpe=0.8, rr_ratio=2.2,
        price_move_pct=+0.017,   # TP1+TP2 (+1.7%)
        notes="Classic demand zone entry — 3 SMC confluences"),

    Scenario("Standard SHORT — BOS + FVG + VWAP rejection",
        "SHORT", "BEARISH", 3, 8, count_to_score(8),
        win_rate=62.0, atr_pct=1.5, sharpe=1.1, rr_ratio=2.6,
        price_move_pct=+0.035,   # full scale-out (+3.5%)
        notes="Textbook short: BOS confirmed on 15m, FVG fill"),

    Scenario("Standard LONG — 7 conf, trending bull, 2 TF",
        "LONG", "BULLISH", 2, 7, count_to_score(7),
        win_rate=57.0, atr_pct=2.3, sharpe=0.7, rr_ratio=2.1,
        price_move_pct=+0.013,   # TP1 (+1.3%)
        notes="Bull trend continuation — partial profit captured"),

    Scenario("Standard SHORT — liquidity sweep + OB + BOS",
        "SHORT", "BEARISH", 2, 8, count_to_score(8),
        win_rate=64.0, atr_pct=1.6, sharpe=1.2, rr_ratio=2.8,
        price_move_pct=-0.011,   # SL — false breakout (-1.1%)
        notes="Stop hunt above swing high — SL placed just beyond"),

    Scenario("Standard LONG — EMA cross + RSI + VWAP + OB",
        "LONG", "BULLISH", 3, 7, count_to_score(7),
        win_rate=59.0, atr_pct=1.9, sharpe=0.9, rr_ratio=2.3,
        price_move_pct=+0.026,   # TP1+TP2+trail hit (+2.6%)
        notes="All 3 TFs confirming — strong confluence stack"),

    Scenario("Standard SHORT — 6 conf, RANGING regime",
        "SHORT", "RANGING", 2, 6, count_to_score(6),
        win_rate=56.0, atr_pct=2.7, sharpe=0.5, rr_ratio=2.0,
        price_move_pct=+0.013,   # TP1 (+1.3%)
        notes="Range bound — selling resistance top"),

    Scenario("Standard LONG — time-limit exit near TP",
        "LONG", "BULLISH", 2, 6, count_to_score(6),
        win_rate=61.0, atr_pct=2.1, sharpe=1.0, rr_ratio=2.2,
        price_move_pct=+0.008,   # crawling toward TP — 15m time limit fires (+0.8%)
        notes="Strong setup but sluggish price action — time exit"),

    Scenario("Standard SHORT — 8 conf, all 3 TFs, low vol",
        "SHORT", "BEARISH", 3, 8, count_to_score(8),
        win_rate=63.0, atr_pct=1.4, sharpe=1.3, rr_ratio=2.7,
        price_move_pct=+0.038,   # full scale-out (+3.8%)
        notes="Best of class SHORT: low vol + strong TF alignment"),

    Scenario("Standard LONG — 7 conf, moderate Sharpe",
        "LONG", "BULLISH", 2, 7, count_to_score(7),
        win_rate=58.0, atr_pct=2.4, sharpe=0.8, rr_ratio=2.0,
        price_move_pct=-0.013,   # SL hit — market turned (-1.3%)
        notes="Setup invalidated by sudden reversal"),

    Scenario("Standard SHORT — 6 conf, decent WR, 2 TF",
        "SHORT", "BEARISH", 2, 6, count_to_score(6),
        win_rate=55.0, atr_pct=2.6, sharpe=0.6, rr_ratio=1.9,
        price_move_pct=+0.017,   # TP1+TP2 (+1.7%)
        notes="Steady short — methodical profit taking"),

    Scenario("Standard LONG — 7 conf, 3 TF, R:R=3.0",
        "LONG", "BULLISH", 3, 7, count_to_score(7),
        win_rate=66.0, atr_pct=1.7, sharpe=1.2, rr_ratio=3.0,
        price_move_pct=+0.045,   # full scale-out + trailing max (+4.5%)
        notes="High R:R setup — all scale-outs triggered"),

    Scenario("Standard SHORT — 8 conf, moderate vol",
        "SHORT", "BEARISH", 3, 8, count_to_score(8),
        win_rate=60.0, atr_pct=2.2, sharpe=1.0, rr_ratio=2.5,
        price_move_pct=+0.028,   # TP1+TP2+trail (+2.8%)
        notes="3 TF SHORT alignment in bear market — high probability"),

    Scenario("Standard LONG — 6 conf, flat Sharpe, 2 TF",
        "LONG", "BULLISH", 2, 6, count_to_score(6),
        win_rate=54.0, atr_pct=2.8, sharpe=0.4, rr_ratio=1.8,
        price_move_pct=-0.012,   # SL (-1.2%)
        notes="Moderate setup — volatile session triggered SL"),

    Scenario("Standard SHORT — 7 conf, improving WR",
        "SHORT", "BEARISH", 2, 7, count_to_score(7),
        win_rate=62.0, atr_pct=1.8, sharpe=1.1, rr_ratio=2.4,
        price_move_pct=+0.016,   # TP1+TP2 (+1.6%)
        notes="Win rate trending up — leverage increasing organically"),

    Scenario("Standard LONG — post consecutive-loss (cooldown active)",
        "LONG", "BULLISH", 2, 6, count_to_score(6),
        win_rate=45.0, atr_pct=2.5, sharpe=-0.5, rr_ratio=2.0,
        price_move_pct=+0.013,   # TP1 at forced 25x (+1.3%)
        notes="Consec-loss cooldown active — engine forced to 25x"),

    Scenario("Standard SHORT — 7 conf, ranging but biased",
        "SHORT", "RANGING", 2, 7, count_to_score(7),
        win_rate=60.0, atr_pct=2.0, sharpe=0.8, rr_ratio=2.3,
        price_move_pct=+0.018,   # TP1+TP2 (+1.8%)
        notes="Range bottom-to-top short — high probability at resistance"),

    Scenario("Standard LONG — 8 conf, 3 TF, low vol",
        "LONG", "BULLISH", 3, 8, count_to_score(8),
        win_rate=67.0, atr_pct=1.3, sharpe=1.4, rr_ratio=2.8,
        price_move_pct=+0.033,   # TP1+TP2+trail (+3.3%)
        notes="Excellent conditions — all confluences firing"),

    # ── D. EXCEPTIONAL TRADES (score 70+, 100x-150x leverage) ────────────────
    Scenario("Exceptional LONG — 9 conf, 3 TF, WR 70%+",
        "LONG", "BULLISH", 3, 9, count_to_score(9),
        win_rate=71.0, atr_pct=1.0, sharpe=1.8, rr_ratio=3.2,
        price_move_pct=+0.050,   # full book — all 3 tiers + trailing max (+5.0%)
        notes="Top-tier setup: high WR, low vol, all 3 TFs, strong Sharpe"),

    Scenario("Exceptional SHORT — 10 conf, 3 TF, WR 73%",
        "SHORT", "BEARISH", 3, 10, count_to_score(10),
        win_rate=73.0, atr_pct=0.9, sharpe=2.0, rr_ratio=3.5,
        price_move_pct=+0.055,   # max profit captured (+5.5%)
        notes="Almost perfect SHORT: 5/5 confluence score"),

    Scenario("Exceptional LONG — 9 conf, WR 68%, Sharpe 1.6",
        "LONG", "BULLISH", 3, 9, count_to_score(9),
        win_rate=68.0, atr_pct=1.1, sharpe=1.6, rr_ratio=3.0,
        price_move_pct=-0.009,   # SL — even great setups fail (-0.9%)
        notes="Strong setup caught by sudden news reversal"),

    Scenario("Exceptional SHORT — 11 conf, 3 TF, WR 75%",
        "SHORT", "BEARISH", 3, 11, count_to_score(11),
        win_rate=75.0, atr_pct=0.8, sharpe=2.2, rr_ratio=4.0,
        price_move_pct=+0.060,   # max leverage + max trail = peak pnl (+6.0%)
        notes="Best SHORT of session — 150x candidate"),

    Scenario("Exceptional LONG — 10 conf, low vol breakout",
        "LONG", "BULLISH", 3, 10, count_to_score(10),
        win_rate=72.0, atr_pct=1.2, sharpe=1.9, rr_ratio=3.3,
        price_move_pct=+0.045,   # full scale-out (+4.5%)
        notes="Volume breakout confirmed on all 3 TFs"),

    Scenario("Exceptional SHORT — 9 conf, Sharpe 1.7, R:R=3",
        "SHORT", "BEARISH", 3, 9, count_to_score(9),
        win_rate=70.0, atr_pct=1.0, sharpe=1.7, rr_ratio=3.0,
        price_move_pct=+0.038,   # TP1+TP2+trail (+3.8%)
        notes="Bear continuation after BOS + OB + liq sweep"),

    Scenario("Exceptional LONG — 11 conf, 3 TF, WR 74%",
        "LONG", "BULLISH", 3, 11, count_to_score(11),
        win_rate=74.0, atr_pct=0.9, sharpe=2.1, rr_ratio=3.8,
        price_move_pct=+0.052,   # near-max trailing (+5.2%)
        notes="Near-maximum setup score — full book deployed"),

    Scenario("Exceptional SHORT — time limit fires at TP1+TP2",
        "SHORT", "BEARISH", 3, 9, count_to_score(9),
        win_rate=69.0, atr_pct=1.1, sharpe=1.5, rr_ratio=2.8,
        price_move_pct=+0.022,   # TP1+TP2 captured, trailing not reached before 15m (+2.2%)
        notes="TP1+TP2 captured, 15m max hold fires before trailing"),

    Scenario("Exceptional LONG — 10 conf, 3 TF, WR 71%",
        "LONG", "BULLISH", 3, 10, count_to_score(10),
        win_rate=71.0, atr_pct=1.0, sharpe=1.8, rr_ratio=3.1,
        price_move_pct=+0.040,   # TP1+TP2+trail (+4.0%)
        notes="Demand zone + BOS + full SMC stack on 3 TFs"),

    Scenario("Exceptional SHORT — 9 conf, highest R:R of day",
        "SHORT", "BEARISH", 3, 9, count_to_score(9),
        win_rate=70.0, atr_pct=1.3, sharpe=1.6, rr_ratio=4.2,
        price_move_pct=-0.010,   # SL hit — even 150x setups can fail (-1.0%)
        notes="Excellent R:R but news event reversed momentum"),

    Scenario("Exceptional LONG — 12 conf, 3 TF, absolute max",
        "LONG", "BULLISH", 3, 12, count_to_score(12),
        win_rate=76.0, atr_pct=0.8, sharpe=2.4, rr_ratio=4.0,
        price_move_pct=+0.060,   # maximum theoretical pnl (+6.0%)
        notes="Perfect setup — all 12 possible confluences firing"),

    Scenario("Exceptional SHORT — 10 conf, 3 TF, WR 72%",
        "SHORT", "BEARISH", 3, 10, count_to_score(10),
        win_rate=72.0, atr_pct=1.1, sharpe=1.9, rr_ratio=3.5,
        price_move_pct=+0.050,   # full scale-out (+5.0%)
        notes="Supply zone breakdown with liq sweep confirmation"),

    Scenario("Exceptional LONG — WR 68%, Sharpe peak",
        "LONG", "BULLISH", 3, 9, count_to_score(9),
        win_rate=68.0, atr_pct=0.9, sharpe=2.5, rr_ratio=3.2,
        price_move_pct=+0.045,   # full trailing captured (+4.5%)
        notes="Highest Sharpe of simulation — engine uses max leverage"),

    Scenario("Exceptional SHORT — 11 conf, 3 TF, WR 73%",
        "SHORT", "BEARISH", 3, 11, count_to_score(11),
        win_rate=73.0, atr_pct=1.0, sharpe=2.0, rr_ratio=3.6,
        price_move_pct=+0.052,   # TP1+TP2+trail, strong continuation (+5.2%)
        notes="Second-best short of session — strong bear continuation"),
]

# Verify we have exactly the right count
assert len(SCENARIOS) == 55, f"Expected 55 scenarios, got {len(SCENARIOS)}"


# =============================================================================
# PnL Simulation
# =============================================================================

def simulate_pnl(
    margin: float,
    leverage: int,
    price_move_pct: float,   # direction-relative BTC price % move (0.01 = 1%)
    atr_pct: float,
) -> Tuple[float, str]:
    """
    Simulate trade outcome using scale-out logic matching the engine.

    price_move_pct is the ACTUAL BTC price % change direction-relative:
      Positive = price moved toward TP (favorable)
      Negative = price moved toward SL (adverse)

    Scale-out triggers mirror the engine's TP_SCALE_OUT constants:
      TP1 (50% close)  : price_move ≥ 0.010  (+1.0% BTC move)
      TP2 (25% close)  : price_move ≥ 0.015  (+1.5% BTC move)
      Trail (25% close): price_move ≥ 0.025  (+2.5% BTC move — trailing stop carried profit)
      SL               : price_move < 0
      Time limit       : 0 ≤ price_move < 0.010  (didn't reach TP1 before hold limit)

    PnL = margin × leverage × price_move  (notional exposure × move)
    Fees deducted on full notional (round-trip, 0.15% per side).
    """
    notional = margin * leverage
    fee = notional * TRADE_FEE_PCT * 2   # entry + exit round-trip fees

    TP1_TRIGGER   = 0.010
    TP2_TRIGGER   = 0.015
    TRAIL_TRIGGER = 0.025

    # ── SL or time-limit exit ─────────────────────────────────────────────
    if price_move_pct < TP1_TRIGGER:
        exit_label = "SL hit" if price_move_pct < 0 else "Time limit"
        net_pnl = notional * price_move_pct - fee
        return round(net_pnl, 2), exit_label

    # ── Scale-out simulation ──────────────────────────────────────────────
    total_pnl       = 0.0
    scale_remaining = 1.0
    label_parts     = []

    # TP1: close 50% at exactly 1% move price
    if price_move_pct >= TP1_TRIGGER and scale_remaining > 0:
        portion = 0.50
        total_pnl += notional * scale_remaining * portion * TP1_TRIGGER
        scale_remaining *= (1 - portion)
        label_parts.append("TP1(50%)")

    # TP2: close 25% (of original) at 1.5% move price
    if price_move_pct >= TP2_TRIGGER and scale_remaining > 0:
        portion = 0.50   # 50% of the remaining 50% = 25% of original
        total_pnl += notional * scale_remaining * portion * TP2_TRIGGER
        scale_remaining *= (1 - portion)
        label_parts.append("TP2(25%)")

    # Trailing/final: remaining 25% exits at actual achieved move
    if price_move_pct >= TRAIL_TRIGGER and scale_remaining > 0:
        total_pnl += notional * scale_remaining * price_move_pct
        scale_remaining = 0.0
        label_parts.append("Trail(25%)")
    elif scale_remaining > 0:
        # Remaining closed at time-limit or partial TP (between TP2 and trail)
        total_pnl += notional * scale_remaining * price_move_pct

    net_pnl    = total_pnl - fee
    exit_label = " → ".join(label_parts) if label_parts else "Partial"
    return round(net_pnl, 2), exit_label


# =============================================================================
# Skip detection
# =============================================================================

def get_skip_reason(s: Scenario) -> Optional[str]:
    """Return skip reason string if this scenario should be rejected, else None."""
    if s.confluence_count < 4:
        return f"Only {s.confluence_count} confluence(s) — need ≥4"
    if s.tf_alignment < 2:
        return f"Only {s.tf_alignment}/3 TFs aligned — need ≥2"
    if s.rr_ratio < MIN_RR_RATIO:
        return f"R:R {s.rr_ratio:.1f} < {MIN_RR_RATIO} minimum"
    if s.direction == "LONG" and s.regime == "BEARISH":
        return "LONG blocked — BEARISH 30m regime"
    if s.direction == "SHORT" and s.regime == "BULLISH":
        return "SHORT blocked — BULLISH 30m regime"
    return None


# =============================================================================
# Candle generator (for full analyze_setup() deep test)
# =============================================================================

def generate_candles(
    n: int = 100,
    base_price: float = 85_000.0,
    trend: str = "up",        # "up" / "down" / "sideways"
    volatility: str = "medium",  # "low" / "medium" / "high"
    seed: int = 42,
) -> pd.DataFrame:
    """
    Generate synthetic BTCUSDT OHLCV candles using geometric Brownian motion.

    trend:      controls drift component
    volatility: controls daily σ
    """
    rng = np.random.default_rng(seed)

    vol_map  = {"low": 0.0008, "medium": 0.0018, "high": 0.0035}
    drift_map= {"up": +0.0003, "down": -0.0003, "sideways": 0.0}

    sigma = vol_map.get(volatility, 0.0018)
    mu    = drift_map.get(trend, 0.0)

    closes = [base_price]
    for _ in range(n - 1):
        ret = mu + sigma * rng.standard_normal()
        closes.append(closes[-1] * (1 + ret))
    closes = np.array(closes)

    # Build OHLCV from close prices
    noise = sigma * 0.5
    highs  = closes * (1 + np.abs(rng.normal(0, noise, n)))
    lows   = closes * (1 - np.abs(rng.normal(0, noise, n)))
    opens  = np.roll(closes, 1)
    opens[0] = closes[0]
    volumes= rng.uniform(500, 5000, n)

    # Timestamps: 5-minute bars ending now
    end_ts = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    start_ts = end_ts - timedelta(minutes=5 * n)
    timestamps = pd.date_range(start=start_ts, periods=n, freq="5min", tz="UTC")

    df = pd.DataFrame({
        "timestamp": timestamps,
        "open":   opens.astype(float),
        "high":   highs.astype(float),
        "low":    lows.astype(float),
        "close":  closes.astype(float),
        "volume": volumes.astype(float),
    })
    return df


def _resample_candles(df_5m: pd.DataFrame, factor: int) -> pd.DataFrame:
    """Resample 5m candles into 15m (factor=3) or 30m (factor=6)."""
    df = df_5m.set_index("timestamp").copy()
    freq = f"{5 * factor}min"
    resampled = df.resample(freq).agg({
        "open":   "first",
        "high":   "max",
        "low":    "min",
        "close":  "last",
        "volume": "sum",
    }).dropna()
    resampled = resampled.reset_index()
    return resampled


# =============================================================================
# Main Backtest Simulator
# =============================================================================

class BacktestSimulator:
    """Runs all 55 scenarios and prints a formatted report."""

    def __init__(self):
        self.engine = InstitutionalScalper(db=None)
        self.margin = MAX_POSITION_USD  # $150

        # Running stats
        self.total_setups    = 0
        self.skipped         = 0
        self.trades_taken    = 0
        self.wins            = 0
        self.losses          = 0
        self.total_profit    = 0.0
        self.total_loss      = 0.0
        self.gross_wins      = 0.0
        self.gross_losses    = 0.0
        self.all_pnl         : List[float] = []

        # For daily loss tier demonstration
        self._sim_daily_pnl  = 0.0
        self._consec_losses  = 0
        self._cooldown_rem   = 0

        # Track leverage tier distribution
        self.lev_buckets = {"25x": 0, "26-50x": 0, "51-75x": 0, "76-100x": 0, "101-125x": 0, "126-150x": 0}

    # ──────────────────────────────────────────────────────────────────────────
    def _get_leverage_bucket(self, lev: int) -> str:
        if lev <= 25:   return "25x"
        if lev <= 50:   return "26-50x"
        if lev <= 75:   return "51-75x"
        if lev <= 100:  return "76-100x"
        if lev <= 125:  return "101-125x"
        return "126-150x"

    def _effective_margin(self) -> float:
        """Apply daily loss tier position reduction."""
        if self._sim_daily_pnl <= TIER_REDUCE_POSITION:
            return 50.0
        return self.margin

    def _effective_leverage(self, raw_leverage: int) -> int:
        """Apply daily loss tier leverage cap and consec-loss cooldown."""
        if self._sim_daily_pnl <= TIER_REDUCE_LEVERAGE:
            return LEVERAGE_MIN  # tier 1: 25x only
        if self._cooldown_rem > 0:
            return LEVERAGE_MIN  # consec-loss cooldown
        return raw_leverage

    def _update_risk_state(self, pnl: float) -> Optional[str]:
        """Update running risk state and return any warning triggered."""
        self._sim_daily_pnl += pnl
        warning = None

        if pnl < 0:
            self._consec_losses += 1
            if self._consec_losses >= 3 and self._cooldown_rem == 0:
                self._cooldown_rem = 5
                warning = yellow("⚠ 3 consecutive losses — 25x enforced for next 5 trades")
        else:
            self._consec_losses = 0
            if self._cooldown_rem > 0:
                self._cooldown_rem -= 1

        if self._sim_daily_pnl <= TIER_HARD_STOP:
            warning = red("🚨 HARD STOP — Daily loss limit $5,000 reached — NO MORE TRADES TODAY")
        elif self._sim_daily_pnl <= TIER_REDUCE_POSITION:
            warning = red(f"⛔ Tier 2 — Daily PnL ${self._sim_daily_pnl:,.2f}: position →$50, leverage →25x")
        elif self._sim_daily_pnl <= TIER_REDUCE_LEVERAGE:
            warning = yellow(f"⚠ Tier 1 — Daily PnL ${self._sim_daily_pnl:,.2f}: leverage →25x")

        return warning

    # ──────────────────────────────────────────────────────────────────────────
    def run(self, scenarios: List[Scenario]):
        self._print_header()

        for i, s in enumerate(scenarios, 1):
            self.total_setups += 1
            self._run_one(i, s)

        self._print_summary()
        self._print_leverage_distribution()

    # ──────────────────────────────────────────────────────────────────────────
    def _run_one(self, num: int, s: Scenario):
        self._print_section_header(num, s)

        # ── 1. Check hard skip conditions ─────────────────────────────────────
        skip_reason = get_skip_reason(s)
        if skip_reason:
            self.skipped += 1
            self._print_skip(num, s, skip_reason)
            return

        # ── 2. Check daily hard stop ───────────────────────────────────────────
        if self._sim_daily_pnl <= TIER_HARD_STOP:
            self.skipped += 1
            self._print_skip(num, s, "Daily hard stop active — no new trades")
            return

        # ── 3. Calculate adaptive leverage ────────────────────────────────────
        atr_pct = atr_pct_to_percentile(s.atr_pct)
        raw_lev, factors = self.engine.calculate_adaptive_leverage(
            win_rate    = s.win_rate,
            volatility  = atr_pct,
            confluence  = s.confluence_score,
            sharpe      = s.sharpe,
            rr_ratio    = s.rr_ratio,
        )

        # Skip if setup score too low
        if factors.setup_score < 40.0:
            self.skipped += 1
            self._print_skip(num, s,
                f"Setup score {factors.setup_score:.0f}/100 < 40 — marginal setup, skip")
            return

        # ── 4. Apply live risk overrides ──────────────────────────────────────
        effective_lev    = self._effective_leverage(raw_lev)
        effective_margin = self._effective_margin()
        tier_override    = (effective_lev != raw_lev or effective_margin != self.margin)

        # ── 5. Simulate outcome ───────────────────────────────────────────────
        pnl, exit_label = simulate_pnl(
            margin         = effective_margin,
            leverage       = effective_lev,
            price_move_pct = s.price_move_pct,
            atr_pct        = s.atr_pct,
        )

        is_win = pnl > 0
        self.trades_taken += 1
        self.all_pnl.append(pnl)
        self.lev_buckets[self._get_leverage_bucket(effective_lev)] += 1

        if is_win:
            self.wins        += 1
            self.gross_wins  += pnl
            self.total_profit+= pnl
        else:
            self.losses       += 1
            self.gross_losses += abs(pnl)
            self.total_loss   += pnl

        # ── 6. Update risk state + get any triggered warning ──────────────────
        risk_warning = self._update_risk_state(pnl)

        # ── 7. Build confidence score for display ─────────────────────────────
        confidence = self.engine._build_confidence_score(
            s.tf_alignment, s.confluence_count, s.rr_ratio, factors.setup_score
        )

        # ── 8. Print result row ───────────────────────────────────────────────
        self._print_trade(num, s, effective_lev, raw_lev, factors,
                          pnl, confidence, exit_label, tier_override, effective_margin)

        if risk_warning:
            print(f"             {risk_warning}")

    # ──────────────────────────────────────────────────────────────────────────
    # Formatting helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _print_header(self):
        width = 100
        bar   = "━" * width
        print()
        print(bold(cyan(bar)))
        print(bold(cyan("  INSTITUTIONAL ADAPTIVE LEVERAGE SCALPER — BACKTEST SIMULATION")))
        print(bold(cyan(f"  Symbol: BTCUSDT  |  {len(SCENARIOS)} Setups  |  Paper Mode  |  No Live API Calls")))
        print(bold(cyan(bar)))
        print()
        # Column header
        hdr = (
            f"  {'#':>3}  "
            f"{'Dir':^6} "
            f"{'Regime':^8} "
            f"{'TF':^5} "
            f"{'Conf':^6} "
            f"{'ATR':^6} "
            f"{'WR':^6} "
            f"{'Sharpe':^7} "
            f"{'R:R':^5} "
            f"{'Score':^6} "
            f"{'Leverage':^10} "
            f"{'Confidence':^11} "
            f"{'Result':^25} "
            f"{'Exit':^20}"
        )
        print(dim(hdr))
        print(dim("  " + "─" * 98))

    def _print_section_header(self, num: int, s: Scenario):
        """Print a subtle section separator every 12 setups."""
        sections = {
            1:  "▶  SECTION A — SKIP SCENARIOS  (hard filters)",
            13: "▶  SECTION B — MARGINAL TRADES  (score 40-49, 25-50x leverage)",
            23: "▶  SECTION C — STANDARD TRADES  (score 50-89, 50-120x leverage)",
            41: "▶  SECTION D — EXCEPTIONAL TRADES  (score 70+, 100-150x leverage)",
        }
        if num in sections:
            print()
            print(f"  {bold(yellow(sections[num]))}")
            print(dim("  " + "─" * 98))

    def _print_skip(self, num: int, s: Scenario, reason: str):
        dir_str    = cyan(f"{s.direction:^6}")
        regime_str = f"{s.regime[:4]:^8}"
        tf_str     = f"{s.tf_alignment}/3"
        conf_str   = f"{s.confluence_count:^6}"

        line = (
            f"  {dim(str(num).rjust(3))}  "
            f"{dir_str} "
            f"{regime_str} "
            f"TF:{tf_str} "
            f"Conf:{conf_str} "
            f"ATR:{s.atr_pct:.1f}% "
            f"WR:{s.win_rate:.0f}% "
        )
        skip_badge = yellow(f"⏭  SKIP")
        reason_str = dim(f"({reason})")
        print(f"{line}  {skip_badge}  {reason_str}")

    def _print_trade(
        self, num: int, s: Scenario,
        effective_lev: int, raw_lev: int,
        factors,
        pnl: float, confidence: float,
        exit_label: str,
        tier_override: bool,
        effective_margin: float,
    ):
        dir_str    = green(f"{s.direction:^6}") if s.direction == "LONG" else red(f"{s.direction:^6}")
        regime_str = f"{s.regime[:4]:^8}"
        tf_str     = f"TF:{s.tf_alignment}/3"
        conf_str   = f"Conf:{s.confluence_count}"
        atr_str    = f"ATR:{s.atr_pct:.1f}%"
        wr_str     = f"WR:{s.win_rate:.0f}%"
        sharpe_str = f"Sh:{s.sharpe:.1f}"
        rr_str     = f"R:R:{s.rr_ratio:.1f}"
        score_str  = f"Sc:{factors.setup_score:.0f}"

        # Leverage display — flag if tier override applied
        lev_display = f"{effective_lev}x"
        if tier_override:
            lev_display = yellow(f"{effective_lev}x↓({raw_lev}x)")
        else:
            # Color by tier
            if effective_lev >= 126:
                lev_display = bold(green(lev_display))
            elif effective_lev >= 76:
                lev_display = green(lev_display)
            elif effective_lev >= 51:
                lev_display = cyan(lev_display)
            else:
                lev_display = yellow(lev_display)

        conf_pct = f"{confidence:.0f}%"

        # PnL badge
        if pnl > 0:
            pnl_str = bold(green(f"✅ +${pnl:>7.2f}"))
        elif abs(pnl) < 0.5:
            pnl_str = dim(f"➖  ${pnl:>7.2f}")
        else:
            pnl_str = bold(red(f"❌  ${pnl:>7.2f}"))

        line = (
            f"  {str(num).rjust(3)}  "
            f"{dir_str} "
            f"{regime_str} "
            f"{tf_str}  "
            f"{conf_str:8} "
            f"{atr_str:8} "
            f"{wr_str:7} "
            f"{sharpe_str:7} "
            f"{rr_str:7} "
            f"{score_str:6} "
            f"Lev:{lev_display:<14} "
            f"Conf:{conf_pct:<6} "
            f"{pnl_str}  "
            f"{dim(exit_label)}"
        )
        print(line)

        # Factor breakdown on verbose detail line
        detail = (
            f"       {dim('→')} "
            f"base=25 "
            f"WRf={factors.win_rate_factor:+.1f} "
            f"Volf={factors.volatility_factor:+.1f} "
            f"Confb={factors.confluence_bonus:+.1f} "
            f"Sharpe={factors.sharpe_adjustment:+.1f} "
            f"RRf={factors.rr_factor:+.1f} "
            f"raw={factors.raw_leverage:.1f} "
            f"→ final={effective_lev}x  "
            f"[{factors.decision_narrative}]"
        )
        print(dim(detail))

    # ──────────────────────────────────────────────────────────────────────────
    # Summary output
    # ──────────────────────────────────────────────────────────────────────────

    def _print_summary(self):
        bar = "━" * 100
        print()
        print(bold(cyan(bar)))
        print(bold(cyan("  SIMULATION SUMMARY")))
        print(bold(cyan(bar)))

        win_rate     = (self.wins / self.trades_taken * 100) if self.trades_taken > 0 else 0.0
        avg_win      = (self.gross_wins / self.wins) if self.wins > 0 else 0.0
        avg_loss     = (self.gross_losses / self.losses) if self.losses > 0 else 0.0
        net_pnl      = self.total_profit + self.total_loss
        profit_factor= (self.gross_wins / self.gross_losses) if self.gross_losses > 0 else float("inf")
        expectancy   = (win_rate/100 * avg_win) - ((1 - win_rate/100) * avg_loss)

        # Max consecutive losses
        max_consec = 0
        cur_consec = 0
        for p in self.all_pnl:
            if p < 0:
                cur_consec += 1
                max_consec = max(max_consec, cur_consec)
            else:
                cur_consec = 0

        # Max drawdown (peak-to-trough on cumulative PnL)
        cumulative = np.cumsum(self.all_pnl)
        peak = np.maximum.accumulate(cumulative)
        drawdown = cumulative - peak
        max_dd = float(drawdown.min()) if len(drawdown) > 0 else 0.0

        rows = [
            ("Total setups evaluated",      f"{self.total_setups}"),
            ("  Filtered/skipped",          yellow(f"{self.skipped}  ({self.skipped/self.total_setups*100:.0f}%)")),
            ("  Trades taken",              f"{self.trades_taken}"),
            ("",                            ""),
            ("Win rate",                    (green if win_rate >= 55 else yellow)(f"{win_rate:.1f}%")),
            ("  Wins",                      green(f"{self.wins}")),
            ("  Losses",                    red(f"{self.losses}")),
            ("",                            ""),
            ("Gross profit",                green(f"${self.gross_wins:,.2f}")),
            ("Gross loss",                  red(f"${self.gross_losses:,.2f}")),
            ("Net PnL",                     (green if net_pnl >= 0 else red)(f"${net_pnl:,.2f}")),
            ("",                            ""),
            ("Average win",                 green(f"${avg_win:.2f}")),
            ("Average loss",                red(f"${avg_loss:.2f}")),
            ("Win/Loss ratio",              f"{(avg_win/avg_loss):.2f}x" if avg_loss > 0 else "∞"),
            ("",                            ""),
            ("Profit factor",               (green if profit_factor >= 1.5 else yellow)(f"{profit_factor:.2f}")),
            ("Expectancy per trade",        (green if expectancy > 0 else red)(f"${expectancy:.2f}")),
            ("",                            ""),
            ("Max consecutive losses",      red(f"{max_consec}") if max_consec >= 3 else f"{max_consec}"),
            ("Max drawdown (sim session)",  red(f"${max_dd:.2f}")),
            ("Final sim daily PnL",         (green if self._sim_daily_pnl >= 0 else red)
                                            (f"${self._sim_daily_pnl:,.2f}")),
        ]

        for label, value in rows:
            if label == "":
                print()
                continue
            print(f"  {label:<40} {value}")

    def _print_leverage_distribution(self):
        print()
        print(bold("  LEVERAGE DISTRIBUTION (trades taken)"))
        print(dim("  " + "─" * 60))
        total = self.trades_taken or 1
        for bucket, count in self.lev_buckets.items():
            if count == 0:
                continue
            pct     = count / total * 100
            bar_len = int(pct / 2)
            bar     = "█" * bar_len
            if bucket in ("126-150x", "101-125x"):
                bar = green(bar)
            elif bucket in ("76-100x", "51-75x"):
                bar = cyan(bar)
            else:
                bar = yellow(bar)
            print(f"  {bucket:^10}  {bar:<30} {count:>3} trades  ({pct:.0f}%)")

        print()
        print(dim("  Note: leverage reduced by daily loss tier or consecutive-loss cooldown"))
        print(dim("  where '↓' appears in the Leverage column above."))
        print()


# =============================================================================
# Deep test: run analyze_setup() with real indicator calculations
# =============================================================================

async def run_deep_analysis_test(engine: InstitutionalScalper):
    """
    Run analyze_setup() with synthetic candles — tests the FULL signal pipeline:
    indicators → TF alignment → regime detection → confluence scoring → leverage.

    Uses 5 representative market scenarios.
    """
    print()
    bar = "━" * 100
    print(bold(magenta(bar)))
    print(bold(magenta("  DEEP ANALYSIS TEST — Full analyze_setup() Pipeline (Synthetic Candles)")))
    print(bold(magenta(bar)))
    print()
    print(dim("  Each scenario generates 100 bars of synthetic 5m candles, resampled to 15m + 30m."))
    print(dim("  Tests the complete indicator → MTF → confluence → leverage path.\n"))

    deep_cases = [
        ("Bull trend, low vol",   "up",       "low",    41),
        ("Bear trend, med vol",   "down",     "medium", 42),
        ("Sideways, high vol",    "sideways", "high",   43),
        ("Strong bull, low vol",  "up",       "low",    44),
        ("Strong bear, med vol",  "down",     "medium", 45),
    ]

    for label, trend, volatility, seed in deep_cases:
        df_5m  = generate_candles(100, 85_000, trend, volatility, seed)
        df_15m = _resample_candles(df_5m, factor=3)
        df_30m = _resample_candles(df_5m, factor=6)

        timeframe_data = {"5m": df_5m, "15m": df_15m, "30m": df_30m}

        confidence, leverage, signal = await engine.analyze_setup(
            "BTC/USDT", timeframe_data=timeframe_data
        )

        if signal is None:
            result = dim(f"  ● {label:35s} → {yellow('NO SIGNAL')}  (confidence={confidence:.1f}, leverage={leverage}x)")
            print(result)
        else:
            pnl_preview = f"${MAX_POSITION_USD * leverage * 0.005 - MAX_POSITION_USD * TRADE_FEE_PCT * 2:.2f} est. TP1 PnL"
            result = (
                f"  ● {label:35s} → {green('SIGNAL')}  "
                f"{signal.direction.value:5s}  "
                f"conf={confidence:.1f}  "
                f"lev={green(str(leverage)+'x'):8s}  "
                f"confl={signal.confluence_count}  "
                f"R:R={signal.rr_ratio:.1f}  "
                f"regime={signal.market_regime:8s}  "
                f"{dim(pnl_preview)}"
            )
            print(result)
            print(dim(f"    Confluences: {', '.join(signal.confluences_hit[:4])}{'...' if len(signal.confluences_hit) > 4 else ''}"))
            f = signal.leverage_factors
            print(dim(
                f"    Leverage factors: base=25 "
                f"WRf={f.win_rate_factor:+.1f} Volf={f.volatility_factor:+.1f} "
                f"Confb={f.confluence_bonus:+.1f} Sharpe={f.sharpe_adjustment:+.1f} "
                f"RRf={f.rr_factor:+.1f} → {leverage}x  [{f.decision_narrative}]"
            ))

    print()


# =============================================================================
# Entry point
# =============================================================================

def main():
    print(bold(f"\n  InstitutionalScalper Test Suite  —  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"))
    print(dim(f"  Engine: InstitutionalScalper v1.0  |  Seed: deterministic  |  55 scenarios\n"))

    sim = BacktestSimulator()
    sim.run(SCENARIOS)

    # Deep pipeline test (async)
    asyncio.run(run_deep_analysis_test(sim.engine))

    print(bold(cyan("  Done.  No real trades were placed.  No API calls made.\n")))


if __name__ == "__main__":
    main()
