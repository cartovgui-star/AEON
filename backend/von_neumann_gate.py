"""
Von Neumann Entropy Gate — Gate 17 in submit_signal_gated()

Measures market-wide *correlation regime* via the von Neumann entropy of the
return correlation matrix across a basket of major symbols.

  Build C = corr(returns) over an N-symbol basket  (N×N, symmetric, diag=1).
  Its eigenvalues {λᵢ} satisfy Σλᵢ = N  (trace of a correlation matrix = N).
  The normalized matrix ρ = C / N is a valid density matrix:
      eigenvalues  pᵢ = λᵢ / N,   Σpᵢ = 1,   pᵢ ≥ 0.

      S_vn   = −Σ pᵢ ln pᵢ          von Neumann entropy
      S_norm = S_vn / ln(N)         ∈ [0, 1]

Interpretation (random-matrix / econophysics):
  S_norm → 1  : eigenvalues evenly spread → many independent market modes →
                healthy, diversified market. Engine edges are real and local.
  S_norm → 0  : one eigenvalue dominates → every asset moving in lockstep →
                a single macro shock is driving everything (correlation crisis).
                Individual engine edges evaporate; idiosyncratic alpha is gone.

Gate logic:
  S_norm < CRISIS_THRESHOLD (0.45)  → correlation lockstep → REJECT
  0.45 ≤ S_norm < CAUTION (0.55)    → elevated correlation → pass, size penalty
  S_norm ≥ 0.55                     → healthy dispersion → clear pass

This complements the existing gates:
  • Entropy gate  — Shannon entropy of *one* symbol's returns (ranging noise)
  • Hurst gate    — fractal structure of *one* symbol (trend vs mean-revert)
  • Von Neumann   — *cross-asset* correlation structure (systemic crisis)

Graceful degradation: any failure → PASS (never block on missing data).
"""

import logging
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Basket of liquid majors used to estimate the market correlation structure.
# Kept small (8) so the matrix is well-conditioned and the fetch is cheap.
_BASKET: List[str] = [
    "BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT",
    "XRP/USDT", "ADA/USDT", "DOGE/USDT", "AVAX/USDT",
]

# Correlation regime is slow-moving — cache the whole-market reading for 10 min.
_CACHE_TTL = 600
_vn_cache: Dict[str, object] = {"ts": 0.0, "S_norm": None, "detail": {}}

CRISIS_THRESHOLD = 0.45   # below this → hard block (lockstep / systemic shock)
CAUTION_THRESHOLD = 0.55  # below this → pass but apply size penalty


def _von_neumann_entropy(corr: np.ndarray) -> Tuple[float, float, np.ndarray]:
    """
    Return (S_vn, S_norm, eigenvalues) for an N×N correlation matrix.

    ρ = corr / N is the density matrix. Numerical guards:
      • symmetrise to kill tiny asymmetries from pairwise NaN handling
      • clip negative eigenvalues (numerical noise) to 0
      • renormalise pᵢ so Σpᵢ = 1 exactly before the entropy sum
    """
    n = corr.shape[0]
    if n < 2:
        return 0.0, 1.0, np.array([1.0])

    sym = 0.5 * (corr + corr.T)
    eig = np.linalg.eigvalsh(sym)        # ascending, real (Hermitian)
    eig = np.clip(eig, 0.0, None)        # drop numerical-negative eigenvalues

    p = eig / n                          # density-matrix eigenvalues, Σ≈1
    total = float(p.sum())
    if total <= 0:
        return 0.0, 1.0, eig
    p = p / total                        # renormalise after clipping

    p_nz = p[p > 1e-12]
    s_vn = float(-np.sum(p_nz * np.log(p_nz)))
    s_norm = float(s_vn / np.log(n)) if n > 1 else 1.0
    return s_vn, float(np.clip(s_norm, 0.0, 1.0)), eig


async def compute_market_entropy(market_intel) -> Optional[Dict]:
    """
    Fetch 1h returns for the basket, build the correlation matrix, and compute
    normalized von Neumann entropy. Cached 10 min. Returns None on failure.
    """
    now = time.time()
    if _vn_cache["S_norm"] is not None and (now - float(_vn_cache["ts"])) < _CACHE_TTL:
        return _vn_cache["detail"]  # type: ignore[return-value]

    if market_intel is None:
        return None

    try:
        series: List[np.ndarray] = []
        used: List[str] = []
        for sym in _BASKET:
            try:
                ohlcv = await market_intel.get_ohlcv(sym, "1h", 120)
                closes = [c[4] for c in ohlcv.get("candles", [])] if "candles" in ohlcv else []
                if len(closes) >= 60:
                    rets = np.diff(np.log(np.array(closes[-100:], dtype=float)))
                    series.append(rets)
                    used.append(sym)
            except Exception as inner:
                logger.debug(f"[VN GATE] basket fetch failed for {sym}: {inner}")

        if len(series) < 3:
            logger.debug("[VN GATE] insufficient basket coverage (<3 symbols) — skipping")
            return None

        # Align to the shortest series so the matrix is rectangular-clean.
        min_len = min(len(s) for s in series)
        matrix = np.vstack([s[-min_len:] for s in series])  # (N_symbols, T)

        corr = np.corrcoef(matrix)
        if not np.all(np.isfinite(corr)):
            corr = np.nan_to_num(corr, nan=0.0)
            np.fill_diagonal(corr, 1.0)

        s_vn, s_norm, eig = _von_neumann_entropy(corr)

        # Concentration ratio: share of the largest eigenvalue (market-mode weight).
        lambda_max_share = float(eig.max() / eig.sum()) if eig.sum() > 0 else 0.0

        detail = {
            "S_vn": round(s_vn, 4),
            "S_norm": round(s_norm, 4),
            "n_symbols": len(used),
            "symbols": used,
            "lambda_max_share": round(lambda_max_share, 4),
            "regime": (
                "CORRELATION_CRISIS" if s_norm < CRISIS_THRESHOLD
                else "ELEVATED_CORRELATION" if s_norm < CAUTION_THRESHOLD
                else "HEALTHY_DISPERSION"
            ),
            "computed_at": now,
        }
        _vn_cache.update({"ts": now, "S_norm": s_norm, "detail": detail})
        logger.info(
            f"[VN GATE] market S_norm={s_norm:.3f} ({detail['regime']}) "
            f"λ_max share={lambda_max_share:.2f} over {len(used)} symbols"
        )
        return detail
    except Exception as e:
        logger.debug(f"[VN GATE] compute failed: {e}")
        return None


async def check_von_neumann_gate(market_intel) -> Tuple[bool, str, Dict, float]:
    """
    Gate 17: Von Neumann Entropy Gate.

    Returns (passes, reason, detail, size_multiplier).

    • S_norm < 0.45 → REJECT (size_multiplier irrelevant)
    • 0.45 ≤ S_norm < 0.55 → pass with size_multiplier 0.5 (de-risk lockstep)
    • S_norm ≥ 0.55 → clear pass, size_multiplier 1.0

    Always passes (size 1.0) when data is unavailable — never block on missing data.
    """
    detail = await compute_market_entropy(market_intel)
    if detail is None:
        return True, "vn gate skipped (insufficient basket data)", {}, 1.0

    s_norm = float(detail["S_norm"])

    if s_norm < CRISIS_THRESHOLD:
        return (
            False,
            f"VON NEUMANN GATE: S_norm={s_norm:.3f} < {CRISIS_THRESHOLD} — "
            f"market in correlation lockstep ({detail['regime']}), idiosyncratic edge gone",
            detail,
            0.0,
        )

    if s_norm < CAUTION_THRESHOLD:
        return (
            True,
            f"vn gate: S_norm={s_norm:.3f} elevated correlation — pass at half size",
            detail,
            0.5,
        )

    return True, f"vn gate: S_norm={s_norm:.3f} healthy dispersion", detail, 1.0


def get_vn_cache_snapshot() -> Dict:
    """Current von Neumann reading for API/Lab surfacing."""
    detail = _vn_cache.get("detail") or {}
    if not detail:
        return {"available": False}
    age = round(time.time() - float(detail.get("computed_at", 0)))
    return {
        "available": True,
        "S_norm": detail.get("S_norm"),
        "S_vn": detail.get("S_vn"),
        "regime": detail.get("regime"),
        "lambda_max_share": detail.get("lambda_max_share"),
        "n_symbols": detail.get("n_symbols"),
        "symbols": detail.get("symbols"),
        "age_seconds": age,
    }
