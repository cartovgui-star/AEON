"""
Quantum-strategy backtester — powers POST /api/researcher/backtest/{name}.

Runs a named research strategy over *real* historical OHLCV (OKX, via
market_intelligence) and reports genuine, reproducible performance:
Sharpe ratio, win rate, max drawdown, total trades, total return.

Design principles:
  • No fabricated numbers. Every metric comes from a walk-forward simulation on
    actual candles, using only information available at bar t to decide bar t+1.
  • Each strategy's rule is a faithful single-symbol echo of the live gate/sizer
    it corresponds to, so the backtest answers "would this logic have paid off?"
  • Pure-ish: needs market_intel for candles; otherwise deterministic.

Strategies implemented:
  hurst_regime         — regime-switched momentum/mean-reversion (mirrors Gate 16)
  von_neumann_entropy  — momentum gated by return-sign dispersion (mirrors Gate 17)
  qubo_position        — momentum baseline, per-bar sized by the QUBO sizer
  <anything else>      — plain N-bar momentum baseline (clearly labelled)
"""

import logging
import math
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

_BARS_PER_YEAR_1H = 24 * 365  # 8760 — annualisation factor for 1h bars


def _sign(x: float) -> int:
    return 1 if x > 0 else -1 if x < 0 else 0


# ── Per-strategy position rules ───────────────────────────────────────────────
# Each returns a position ∈ [-1, 1] for bar t+1, given returns[:t+1] (and prices).

def _pos_momentum(returns: np.ndarray, t: int, lookback: int = 5) -> float:
    if t < lookback:
        return 0.0
    return float(_sign(returns[t - lookback + 1 : t + 1].mean()))


def _pos_hurst(returns: np.ndarray, t: int) -> float:
    """Regime switch via rolling Hurst (R/S) on the trailing window."""
    if t < 60:
        return 0.0
    from hurst_gate import _hurst_rs  # reuse the live gate's estimator
    window = returns[max(0, t - 100) : t + 1]
    H = _hurst_rs(window)
    recent = float(returns[t - 4 : t + 1].mean())
    if H > 0.56:          # momentum regime → follow
        return float(_sign(recent))
    if H < 0.44:          # mean-reversion regime → fade the last bar
        return float(-_sign(returns[t]))
    return 0.0            # random walk → flat


def _pos_von_neumann(returns: np.ndarray, t: int, window: int = 24) -> float:
    """
    Single-symbol echo of the correlation-dispersion gate: trade momentum only
    when the trailing up/down sign distribution is balanced (healthy two-sided
    market, high dispersion). One-sided lockstep → flat.
    """
    if t < window:
        return 0.0
    seg = returns[t - window + 1 : t + 1]
    ups = float((seg > 0).mean())
    ups = min(max(ups, 1e-6), 1 - 1e-6)
    sign_entropy = -(ups * math.log(ups) + (1 - ups) * math.log(1 - ups)) / math.log(2)
    if sign_entropy < 0.65:   # lockstep / one-sided — no idiosyncratic edge
        return 0.0
    return float(_sign(seg.mean()))


def _pos_qubo(returns: np.ndarray, t: int, prices: np.ndarray) -> float:
    """Momentum direction, sized [0,1] each bar by the QUBO sizer using local vol."""
    direction = _pos_momentum(returns, t, lookback=5)
    if direction == 0.0:
        return 0.0
    try:
        from qubo_sizer import compute_qubo_multiplier
        vol = float(np.std(returns[max(0, t - 24) : t + 1])) if t >= 5 else 0.01
        atr_pct = vol * 100.0
        # crude rolling "score": stronger recent trend → higher score
        trend = abs(float(returns[max(0, t - 9) : t + 1].mean())) / (vol + 1e-9)
        score = float(min(100.0, 40.0 + trend * 25.0))
        mult, _ = compute_qubo_multiplier(
            quant_score=score, confidence=70.0, atr_pct=atr_pct, leverage=5.0,
        )
    except Exception:
        mult = 1.0
    return direction * mult


_RULES: Dict[str, str] = {
    "hurst_regime": "regime-switched momentum / mean-reversion via rolling Hurst",
    "von_neumann_entropy": "momentum gated by return-sign dispersion entropy",
    "qubo_position": "momentum baseline sized per-bar by the QUBO annealer",
}


def _position_series(name: str, returns: np.ndarray, prices: np.ndarray) -> np.ndarray:
    n = len(returns)
    pos = np.zeros(n)
    for t in range(n - 1):  # decide pos for bar t+1, realised by returns[t+1]
        if name == "hurst_regime":
            pos[t + 1] = _pos_hurst(returns, t)
        elif name == "von_neumann_entropy":
            pos[t + 1] = _pos_von_neumann(returns, t)
        elif name == "qubo_position":
            pos[t + 1] = _pos_qubo(returns, t, prices)
        else:
            pos[t + 1] = _pos_momentum(returns, t)
    return pos


def _metrics(pos: np.ndarray, returns: np.ndarray) -> Dict:
    """Compute SR / WR / drawdown / trades from a position and return series."""
    strat_ret = pos * returns                      # bar-by-bar strategy return
    active = strat_ret[pos != 0]

    if len(active) == 0:
        return {
            "sharpe_ratio": 0.0, "win_rate": 0.0, "total_trades": 0,
            "max_drawdown": 0.0, "total_return": 0.0, "avg_return_bp": 0.0,
            "exposure": 0.0,
        }

    mean = float(active.mean())
    std = float(active.std(ddof=1)) if len(active) > 1 else 0.0
    sharpe = (mean / std * math.sqrt(_BARS_PER_YEAR_1H)) if std > 0 else 0.0

    wins = int((active > 0).sum())
    win_rate = wins / len(active) * 100.0

    # Equity curve & max drawdown (compounded)
    equity = np.cumprod(1.0 + strat_ret)
    peak = np.maximum.accumulate(equity)
    drawdown = (equity - peak) / peak
    max_dd = float(drawdown.min()) * 100.0

    # A "trade" = a transition into a new nonzero position (sign change or 0→nonzero)
    sign_changes = 0
    prev = 0.0
    for p in pos:
        ps = _sign(p)
        if ps != 0 and ps != _sign(prev):
            sign_changes += 1
        prev = p

    total_return = float(equity[-1] - 1.0) * 100.0

    return {
        "sharpe_ratio": round(float(np.clip(sharpe, -10, 10)), 3),
        "win_rate": round(win_rate, 2),
        "total_trades": sign_changes,
        "max_drawdown": round(max_dd, 2),
        "total_return": round(total_return, 2),
        "avg_return_bp": round(mean * 10000.0, 2),
        "exposure": round(float((pos != 0).mean()) * 100.0, 1),
    }


async def run_backtest(
    name: str,
    market_intel,
    *,
    symbol: str = "BTC/USDT",
    bars: int = 300,
) -> Dict:
    """
    Backtest strategy `name` on `bars` of 1h `symbol` history.
    Returns a result dict (also shaped for storage in qr_backtests).
    Raises ValueError on missing data so the route can return a clean 4xx-style body.
    """
    if market_intel is None:
        raise ValueError("market intelligence unavailable")

    bars = int(max(120, min(bars, 300)))  # OKX 1h cap ≈ 300
    ohlcv = await market_intel.get_ohlcv(symbol, "1h", bars)
    candles = ohlcv.get("candles", []) if isinstance(ohlcv, dict) else []
    closes = [c[4] for c in candles] if candles else []
    if len(closes) < 120:
        raise ValueError(f"insufficient history for {symbol} ({len(closes)} bars)")

    prices = np.asarray(closes, dtype=float)
    returns = np.diff(np.log(prices))
    # Pad returns to align indexing with prices (returns[t] ≈ price move into bar t)
    returns = np.concatenate([[0.0], returns])

    pos = _position_series(name, returns, prices)
    metrics = _metrics(pos, returns)

    return {
        "strategy_name": name,
        "rule": _RULES.get(name, "N-bar momentum baseline (no dedicated rule)"),
        "implemented": name in _RULES,
        "symbol": symbol,
        "timeframe": "1h",
        "bars_tested": len(closes),
        **metrics,
    }
