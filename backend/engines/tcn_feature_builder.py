"""
=============================================================
  tcn_feature_builder.py — Engine 9 Feature Pipeline
=============================================================

  Extracts 12 engineered features from raw OHLCV candle data
  for the TCN Neural Engine.

  Features per candle:
    1.  Returns           — close-to-close pct change
    2.  Log Returns       — log(close_t / close_{t-1})
    3.  HL Range Norm     — (high - low) / close
    4.  Volume Delta      — (vol - rolling_avg) / rolling_avg
    5.  RSI(14)           — normalised to [0, 1]
    6.  MACD Signal       — signal line normalised by close
    7.  BB Position       — (close - lower) / (upper - lower)
    8.  ATR Norm          — ATR(14) / close
    9.  EMA Ratio         — (EMA9/EMA21) − 1
    10. Body Ratio        — |body| / (high - low)
    11. Realized Vol      — 20-period std of log returns
    12. Funding Rate      — MEXC perpetual funding rate (0 if unavailable)

  Constants:
    WINDOW     = 64   (timesteps per sample)
    N_FEATURES = 12
=============================================================
"""

import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

WINDOW     = 64
N_FEATURES = 12

_FEATURE_COLS = [
    "f_returns",
    "f_log_returns",
    "f_hl_range",
    "f_vol_delta",
    "f_rsi",
    "f_macd_signal",
    "f_bb_pos",
    "f_atr_norm",
    "f_ema_ratio",
    "f_body_ratio",
    "f_realized_vol",
    "f_funding_rate",
]


# ─── Feature construction ─────────────────────────────────────────────────────


def build_features(df: pd.DataFrame, funding_rate: float = 0.0) -> pd.DataFrame:
    """
    Compute all 12 features from a raw OHLCV DataFrame.

    Parameters
    ----------
    df : pd.DataFrame
        Must contain columns: open, high, low, close, volume.
        Index should be monotonically increasing (time-ordered).
    funding_rate : float
        Current MEXC perpetual funding rate. Broadcast as a constant
        feature across all rows. Defaults to 0.0 when unavailable.

    Returns
    -------
    pd.DataFrame
        Columns are the 12 feature names. NaN rows are dropped.
        Minimum useful output requires ~35 rows input (warmup for EMA26/ATR/BB).
    """
    if df.empty or len(df) < 30:
        return pd.DataFrame(columns=_FEATURE_COLS)

    d = df.copy()
    d = d.sort_index()

    close  = d["close"].astype(float)
    high   = d["high"].astype(float)
    low    = d["low"].astype(float)
    vol    = d["volume"].astype(float)
    open_  = d["open"].astype(float)

    # ── 1. Returns ────────────────────────────────────────────────────────────
    d["f_returns"] = close.pct_change()

    # ── 2. Log returns ────────────────────────────────────────────────────────
    d["f_log_returns"] = np.log(close / close.shift(1))

    # ── 3. High-Low range normalised by close ────────────────────────────────
    d["f_hl_range"] = (high - low) / close.clip(lower=1e-10)

    # ── 4. Volume delta vs 20-period rolling average ─────────────────────────
    vol_ma = vol.rolling(20).mean()
    d["f_vol_delta"] = (vol - vol_ma) / (vol_ma + 1e-10)

    # ── 5. RSI(14) normalised to [0, 1] ──────────────────────────────────────
    delta = close.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rs    = gain / (loss + 1e-10)
    d["f_rsi"] = (100.0 - (100.0 / (1.0 + rs))) / 100.0

    # ── 6. MACD signal line normalised by close ───────────────────────────────
    ema12  = close.ewm(span=12, adjust=False).mean()
    ema26  = close.ewm(span=26, adjust=False).mean()
    macd   = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()
    d["f_macd_signal"] = signal / close.clip(lower=1e-10)

    # ── 7. Bollinger Band position (0 = at lower, 1 = at upper) ──────────────
    sma20  = close.rolling(20).mean()
    std20  = close.rolling(20).std()
    upper  = sma20 + 2.0 * std20
    lower  = sma20 - 2.0 * std20
    band_w = (upper - lower).clip(lower=1e-10)
    d["f_bb_pos"] = ((close - lower) / band_w).clip(0.0, 1.0)

    # ── 8. ATR(14) normalised by close ───────────────────────────────────────
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    d["f_atr_norm"] = atr / close.clip(lower=1e-10)

    # ── 9. EMA9 / EMA21 ratio − 1 (centred at 0) ─────────────────────────────
    ema9  = close.ewm(span=9,  adjust=False).mean()
    ema21 = close.ewm(span=21, adjust=False).mean()
    d["f_ema_ratio"] = (ema9 / ema21.clip(lower=1e-10)) - 1.0

    # ── 10. Candle body ratio — |body| / wick range ───────────────────────────
    body = (close - open_).abs()
    wick = (high - low).clip(lower=1e-10)
    d["f_body_ratio"] = body / wick

    # ── 11. Rolling 20-period realised volatility (std of log returns) ────────
    d["f_realized_vol"] = d["f_log_returns"].rolling(20).std()

    # ── 12. Funding rate (scalar broadcast) ───────────────────────────────────
    d["f_funding_rate"] = float(funding_rate)

    # ── Finalise ─────────────────────────────────────────────────────────────
    feat = d[_FEATURE_COLS].copy()
    feat = feat.replace([np.inf, -np.inf], np.nan)
    feat = feat.dropna()

    return feat


# ─── Window builder ───────────────────────────────────────────────────────────


def build_windows(df_features: pd.DataFrame, window: int = WINDOW) -> np.ndarray:
    """
    Slice the feature DataFrame into overlapping sliding windows.

    Returns
    -------
    np.ndarray  shape (N, window, N_FEATURES) dtype float32
        Each row is one input sample. Returns empty array when there
        are fewer rows than the window size.
    """
    arr = df_features.values.astype(np.float32)
    n   = len(arr)

    if n < window:
        logger.warning("[TCN-FB] Not enough rows (%d) for window=%d", n, window)
        return np.empty((0, window, N_FEATURES), dtype=np.float32)

    indices = np.arange(n - window + 1)
    windows = np.stack([arr[i : i + window] for i in indices])   # (N, W, F)
    return windows


def build_labels(df_features: pd.DataFrame, df_raw: pd.DataFrame) -> np.ndarray:
    """
    Binary label aligned to each window's last candle.

    Label = 1 if the next candle's close > current close, else 0.
    The last entry has no future candle and is excluded → labels.shape[0]
    equals windows.shape[0] - 1 when using the same window count.

    Parameters
    ----------
    df_features : pd.DataFrame
        Feature DataFrame (same index as the trimmed/normalised slice).
    df_raw : pd.DataFrame
        Raw OHLCV DataFrame aligned to df_features.index for close prices.

    Returns
    -------
    np.ndarray  shape (M,) dtype float32
        M = len(df_features) - 1  (last window has no future label).
    """
    close = df_raw["close"].reindex(df_features.index).astype(float)
    future_up = (close.shift(-1) > close).astype(np.float32)
    return future_up.values[:-1]   # drop last (NaN label)


# ─── Normalisation ────────────────────────────────────────────────────────────


def normalize_windows(windows: np.ndarray) -> np.ndarray:
    """
    Z-score normalise each window independently across the time axis.

    Per-window normalisation prevents data leakage between samples and
    makes the model robust to absolute price levels.

    Parameters
    ----------
    windows : np.ndarray  shape (N, W, F)

    Returns
    -------
    np.ndarray  shape (N, W, F)
    """
    mean = windows.mean(axis=1, keepdims=True)   # (N, 1, F)
    std  = windows.std(axis=1, keepdims=True) + 1e-8
    return (windows - mean) / std


# ─── Convenience: build a single inference window ─────────────────────────────


def build_inference_window(
    df: pd.DataFrame,
    funding_rate: float = 0.0,
    window: int = WINDOW,
) -> np.ndarray:
    """
    Full pipeline: OHLCV DataFrame → normalised (1, window, N_FEATURES) tensor.

    Returns None when there are insufficient candles.
    """
    feat = build_features(df, funding_rate)
    if len(feat) < window:
        return None

    # Use the last `window` rows for inference
    last_rows = feat.iloc[-window:]
    w = last_rows.values.astype(np.float32)[np.newaxis, ...]   # (1, W, F)
    w = normalize_windows(w)
    return w
