"""
=============================================================
  tcn_neural_engine.py — Engine 9: TCN Neural Engine
=============================================================

  Architecture
  ─────────────
  Input  : 64 × 12 feature window (64 timesteps, 12 features)
  Model  : Temporal Convolutional Network (TCN)
           6 TemporalBlocks — dilations [1, 2, 4, 8, 16, 32]
           Each block: causal conv1d × 2 + BN + ReLU + dropout + residual
  Pool   : Global Average Pooling over time axis
  Output : p̂_{t+1} ∈ [0, 1] — P(next candle is bullish)

  Position Sizing (Deadbanded Volatility Scaled Risk Map)
  ────────────────────────────────────────────────────────
  signal  = 2p̂ − 1                            ∈ [−1, 1]
  g_τ     = 0 if |signal| < 0.15, else signal  (deadband)
  w_{t+1} = clip( (σ* / σ̂) × g_τ, −1, 1 )
  σ*      = 0.02  (2% daily vol target)
  σ̂      = rolling 20-period realised vol of returns

  Signal output
  ─────────────
  w >  0.15 → LONG
  w < −0.15 → SHORT
  else       → NO TRADE

  Quantum Integration (α₉)
  ─────────────────────────
  S₉  = rolling Sharpe of TCN outcomes over last 100 trades
  α₉  = (2p̂ − 1) × S₉
  Then aeon_quantum_state applies: e^(−λδ₉) · 𝟙[ADX>θ] · (1−ρ₉_max)

  Training
  ─────────
  Data   : MEXC BTC/USDT 1h — last 2 years (~17 500 candles)
  Split  : 70 / 15 / 15 walk-forward (chronological)
  Loss   : Binary cross-entropy
  Adam   : lr=0.001, weight_decay=1e-4
  Dropout: 0.2
  Retrain trigger: rolling accuracy < 52% over 200 trades

  Graceful degradation
  ─────────────────────
  If model fails to load → α₉ = 0, system continues without Engine 9.

  Files
  ──────
  Model weights : /backend/models/tcn_neural_engine.pt
  Signal log    : MongoDB collection  tcn_signals
=============================================================
"""

from __future__ import annotations

import asyncio
import logging
import math
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

_HERE        = Path(__file__).resolve().parent          # backend/engines/
_BACKEND     = _HERE.parent                             # backend/
_MODELS_DIR  = _BACKEND / "models"
_WEIGHTS_PATH = _MODELS_DIR / "tcn_neural_engine.pt"

# ─── Hyper-parameters ─────────────────────────────────────────────────────────

WINDOW       = 64
N_FEATURES   = 12
N_CHANNELS   = 64
KERNEL_SIZE  = 3
DROPOUT      = 0.2
DILATIONS    = [1, 2, 4, 8, 16, 32]

SIGMA_STAR   = 0.02    # vol target
DEADBAND_TAU = 0.15    # deadband threshold
W_MIN, W_MAX = -1.0, 1.0

TRAIN_RATIO  = 0.70
VAL_RATIO    = 0.15
BATCH_SIZE   = 128
MAX_EPOCHS   = 50
PATIENCE     = 5       # early stopping epochs
LR           = 1e-3
WEIGHT_DECAY = 1e-4

SHARPE_LOOKBACK  = 100   # trades for S₉ computation
HOURLY_PER_YEAR  = 8760  # sqrt factor for annualised Sharpe
RETRAIN_ACCURACY_FLOOR  = 0.52
RETRAIN_ACCURACY_WINDOW = 200

# ─── PyTorch import (guarded for graceful degradation) ────────────────────────

_TORCH_OK = False
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    _TORCH_OK = True
except ImportError:
    logger.warning("[TCN-9] PyTorch not available — Engine 9 will return α₉=0")


# ─────────────────────────────────────────────────────────────────────────────
# TCN Architecture
# ─────────────────────────────────────────────────────────────────────────────

if _TORCH_OK:

    class _CausalConv1d(nn.Module):
        """Left-padded dilated convolution — strictly causal (no future leakage)."""

        def __init__(self, in_ch: int, out_ch: int, kernel: int, dilation: int):
            super().__init__()
            self._pad  = (kernel - 1) * dilation
            self._conv = nn.Conv1d(
                in_ch, out_ch, kernel,
                dilation=dilation,
                padding=self._pad,
            )

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            out = self._conv(x)
            # Remove right-side future-looking padding to restore causal property
            return out[:, :, : -self._pad] if self._pad > 0 else out


    class _TemporalBlock(nn.Module):
        """
        TCN residual block.

        Conv → BN → ReLU → Dropout → Conv → BN → ReLU → Dropout + skip.
        If in_ch ≠ out_ch a 1×1 conv aligns the residual path.
        """

        def __init__(self, in_ch: int, out_ch: int, kernel: int, dilation: int):
            super().__init__()
            self.conv1 = _CausalConv1d(in_ch,  out_ch, kernel, dilation)
            self.conv2 = _CausalConv1d(out_ch, out_ch, kernel, dilation)
            self.bn1   = nn.BatchNorm1d(out_ch)
            self.bn2   = nn.BatchNorm1d(out_ch)
            self.relu  = nn.ReLU(inplace=True)
            self.drop  = nn.Dropout(DROPOUT)
            self.skip  = nn.Conv1d(in_ch, out_ch, 1) if in_ch != out_ch else None

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            res = x

            out = self.drop(self.relu(self.bn1(self.conv1(x))))
            out = self.drop(self.relu(self.bn2(self.conv2(out))))

            if self.skip is not None:
                res = self.skip(res)

            return self.relu(out + res)


    class TCNModel(nn.Module):
        """
        Full Temporal Convolutional Network.

        Input  : (batch, seq_len, n_features)
        Output : (batch,)  — sigmoid probability ∈ (0, 1)
        """

        def __init__(
            self,
            n_features: int = N_FEATURES,
            n_channels: int = N_CHANNELS,
            kernel_size: int = KERNEL_SIZE,
            dilations: List[int] = DILATIONS,
        ):
            super().__init__()
            blocks: List[nn.Module] = []
            in_ch = n_features
            for d in dilations:
                blocks.append(_TemporalBlock(in_ch, n_channels, kernel_size, d))
                in_ch = n_channels

            self.network = nn.Sequential(*blocks)
            self.fc      = nn.Linear(n_channels, 1)

        def forward(self, x: "torch.Tensor") -> "torch.Tensor":
            # x: (B, T, F) → (B, F, T) for Conv1d
            x = x.permute(0, 2, 1)
            x = self.network(x)          # (B, C, T)
            x = x.mean(dim=2)            # Global Average Pool → (B, C)
            return torch.sigmoid(self.fc(x)).squeeze(-1)   # (B,)


# ─────────────────────────────────────────────────────────────────────────────
# TCN Neural Engine
# ─────────────────────────────────────────────────────────────────────────────


class TCNNeuralEngine:
    """
    Engine 9 — TCN Neural Engine.

    Responsibilities
    ─────────────────
    • Load / save PyTorch weights from /backend/models/
    • Run inference on live OHLCV data → p̂, w, direction
    • Train on historical MEXC BTC/USDT 1h candles
    • Maintain rolling S₉ (Sharpe) and expose α₉ for quantum state
    • Log all signals to MongoDB `tcn_signals` collection
    • Gracefully degrade to α₉=0 on any error

    Usage in server.py
    ───────────────────
    from engines.tcn_neural_engine import get_tcn_engine
    tcn = get_tcn_engine()
    await tcn.initialise(db=db, market_intel=market_intel)
    asyncio.create_task(tcn.run_background_loop())
    """

    ENGINE_LABEL = "tcn_neural"

    def __init__(self):
        self._model: Optional["TCNModel"] = None
        self._device: str = "cpu"
        self._db = None
        self._market_intel = None

        # Live state
        self._p_hat: float = 0.5          # last predicted probability
        self._w: float = 0.0              # last position weight
        self._direction: str = "NO_TRADE" # LONG / SHORT / NO_TRADE
        self._s9_sharpe: float = 0.0      # rolling Sharpe from last 100 trades
        self._alpha9: float = 0.0         # (2p̂−1) × S₉
        self._last_inference_ts: float = 0.0
        self._consecutive_errors: int = 0

        # Realised vol buffer for σ̂ (last 20 returns)
        self._return_buffer: List[float] = []
        self._last_close: float = 0.0

        # Retrain tracking
        self._recent_accuracy: List[float] = []   # 1=correct, 0=wrong

        _MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Initialisation ────────────────────────────────────────────────────────

    async def initialise(self, db=None, market_intel=None):
        """
        Wire dependencies, load weights, run first inference.
        Call from server.py startup.
        """
        self._db           = db
        self._market_intel = market_intel

        if not _TORCH_OK:
            logger.warning("[TCN-9] PyTorch absent — Engine 9 disabled (α₉=0)")
            return

        self._model = TCNModel()
        self._model.to(self._device)

        loaded = self._load_weights()
        if not loaded:
            logger.info(
                "[TCN-9] No saved weights found at %s — will train on first call.",
                _WEIGHTS_PATH,
            )
        else:
            logger.info("[TCN-9] Weights loaded from %s", _WEIGHTS_PATH)

        # Fetch initial S₉ from MongoDB
        await self._refresh_sharpe()
        logger.info("[TCN-9] Engine 9 initialised. S₉=%.4f", self._s9_sharpe)

    # ── Weight I/O ────────────────────────────────────────────────────────────

    def _load_weights(self) -> bool:
        if not _TORCH_OK or self._model is None:
            return False
        if not _WEIGHTS_PATH.exists():
            return False
        try:
            state = torch.load(str(_WEIGHTS_PATH), map_location=self._device, weights_only=True)
            self._model.load_state_dict(state)
            self._model.eval()
            return True
        except Exception as e:
            logger.error("[TCN-9] Weight load failed: %s", e)
            return False

    def _save_weights(self):
        if not _TORCH_OK or self._model is None:
            return
        try:
            torch.save(self._model.state_dict(), str(_WEIGHTS_PATH))
            logger.info("[TCN-9] Weights saved → %s", _WEIGHTS_PATH)
        except Exception as e:
            logger.error("[TCN-9] Weight save failed: %s", e)

    # ── Data fetching ─────────────────────────────────────────────────────────

    async def _fetch_historical_candles(self, limit: int = 2000) -> "pd.DataFrame":
        """
        Fetch up to `limit` BTC/USDT 1h candles from MEXC, paginating if needed.
        Returns a pandas DataFrame with columns [timestamp, open, high, low, close, volume].
        MEXC CCXT allows a maximum of 1000 per request, so we paginate.
        """
        import pandas as pd

        if self._market_intel is None:
            return pd.DataFrame()

        all_frames = []
        fetched     = 0
        chunk       = 1000
        since: Optional[int] = None    # epoch ms

        loop = asyncio.get_running_loop()

        while fetched < limit:
            to_fetch = min(chunk, limit - fetched)
            try:
                kwargs = dict(symbol="BTC/USDT", timeframe="1h", limit=to_fetch)
                if since is not None:
                    kwargs["since"] = since

                raw = await loop.run_in_executor(
                    None,
                    lambda kw=kwargs: self._market_intel.okx_public.fetch_ohlcv(**kw),
                )
                if not raw:
                    break

                frame = pd.DataFrame(
                    raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
                )
                frame["timestamp"] = pd.to_datetime(frame["timestamp"], unit="ms")
                all_frames.append(frame)
                fetched += len(frame)

                if len(frame) < to_fetch:
                    break   # no more data

                # Advance cursor: last timestamp + 1 hour
                last_ts_ms = int(raw[-1][0])
                since      = last_ts_ms + 3_600_000

            except Exception as e:
                logger.error("[TCN-9] Candle fetch error: %s", e)
                break

        if not all_frames:
            return pd.DataFrame()

        import pandas as pd
        df = pd.concat(all_frames, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"]).sort_values("timestamp").reset_index(drop=True)
        logger.info("[TCN-9] Fetched %d candles for training", len(df))
        return df

    async def _fetch_funding_rate(self) -> float:
        """Best-effort MEXC funding rate for BTC/USDT. Returns 0.0 on failure."""
        try:
            if self._market_intel is None:
                return 0.0
            loop = asyncio.get_running_loop()
            funding_data = await loop.run_in_executor(
                None,
                lambda: self._market_intel.okx.fetch_funding_rate("BTC/USDT:USDT"),
            )
            rate = funding_data.get("fundingRate", 0.0) if isinstance(funding_data, dict) else 0.0
            return float(rate) if rate is not None else 0.0
        except Exception:
            return 0.0

    # ── Training ──────────────────────────────────────────────────────────────

    async def train(self) -> Dict:
        """
        Full training run on 2 years of BTC/USDT 1h data.

        Walk-forward split: 70 / 15 / 15 (chronological).
        Returns a summary dict with train/val/test accuracy metrics.
        """
        if not _TORCH_OK:
            return {"error": "PyTorch not available"}

        logger.info("[TCN-9] Starting training run...")

        try:
            from engines.tcn_feature_builder import (
                build_features, build_windows, build_labels, normalize_windows
            )

            # ── 1. Fetch data ──────────────────────────────────────────────────
            # 2 years × 365 × 24 ≈ 17 520 h candles
            df_raw = await self._fetch_historical_candles(limit=17_520)
            if len(df_raw) < WINDOW + 50:
                return {"error": f"Insufficient candles: {len(df_raw)}"}

            funding_rate = await self._fetch_funding_rate()

            # ── 2. Build features ──────────────────────────────────────────────
            df_feat = build_features(df_raw, funding_rate)
            if len(df_feat) < WINDOW + 10:
                return {"error": "Feature build failed — too many NaN rows"}

            # ── 3. Build windows + labels ─────────────────────────────────────
            windows = build_windows(df_feat, WINDOW)  # (N, W, F)
            labels  = build_labels(df_feat, df_raw)   # (N-1,) — last window dropped

            # Align: windows=(N-W+1,) rows, labels=(N-1,) rows — clip both to min
            windows = windows[: len(labels)]
            labels  = labels[: len(windows)]
            windows = normalize_windows(windows)

            N = len(windows)
            if N < 100:
                return {"error": f"Only {N} samples — cannot split 70/15/15"}

            # ── 4. Chronological split ────────────────────────────────────────
            n_train = int(N * TRAIN_RATIO)
            n_val   = int(N * VAL_RATIO)

            X_train = torch.tensor(windows[:n_train],             dtype=torch.float32)
            y_train = torch.tensor(labels[:n_train],              dtype=torch.float32)
            X_val   = torch.tensor(windows[n_train:n_train+n_val],dtype=torch.float32)
            y_val   = torch.tensor(labels[n_train:n_train+n_val], dtype=torch.float32)
            X_test  = torch.tensor(windows[n_train+n_val:],       dtype=torch.float32)
            y_test  = torch.tensor(labels[n_train+n_val:],        dtype=torch.float32)

            logger.info(
                "[TCN-9] Split: train=%d val=%d test=%d",
                len(X_train), len(X_val), len(X_test),
            )

            # ── 5. Model + optimiser ──────────────────────────────────────────
            self._model = TCNModel()
            self._model.to(self._device)
            optimizer   = optim.Adam(
                self._model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY
            )
            criterion   = nn.BCELoss()
            scheduler   = optim.lr_scheduler.ReduceLROnPlateau(
                optimizer, patience=2, factor=0.5
            )

            train_ds     = TensorDataset(X_train, y_train)
            train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True)

            # ── 6. Training loop ───────────────────────────────────────────────
            best_val_loss  = float("inf")
            best_state     = None
            patience_count = 0
            history        = []

            for epoch in range(MAX_EPOCHS):
                self._model.train()
                total_loss, total_correct, total_n = 0.0, 0, 0

                for Xb, yb in train_loader:
                    optimizer.zero_grad()
                    pred = self._model(Xb)
                    loss = criterion(pred, yb)
                    loss.backward()
                    nn.utils.clip_grad_norm_(self._model.parameters(), 1.0)
                    optimizer.step()

                    total_loss    += loss.item() * len(yb)
                    total_correct += ((pred > 0.5).float() == yb).sum().item()
                    total_n       += len(yb)

                train_acc  = total_correct / total_n
                train_loss = total_loss / total_n

                # Validation
                self._model.eval()
                with torch.no_grad():
                    val_pred = self._model(X_val)
                    val_loss = criterion(val_pred, y_val).item()
                    val_acc  = ((val_pred > 0.5).float() == y_val).float().mean().item()

                scheduler.step(val_loss)
                history.append({
                    "epoch": epoch + 1,
                    "train_loss": round(train_loss, 5),
                    "train_acc":  round(train_acc, 4),
                    "val_loss":   round(val_loss, 5),
                    "val_acc":    round(val_acc, 4),
                })

                logger.info(
                    "[TCN-9] Epoch %2d/%d — train_loss=%.4f acc=%.3f | val_loss=%.4f acc=%.3f",
                    epoch + 1, MAX_EPOCHS, train_loss, train_acc, val_loss, val_acc,
                )

                # Early stopping
                if val_loss < best_val_loss:
                    best_val_loss  = val_loss
                    best_state     = {k: v.clone() for k, v in self._model.state_dict().items()}
                    patience_count = 0
                else:
                    patience_count += 1
                    if patience_count >= PATIENCE:
                        logger.info("[TCN-9] Early stopping at epoch %d", epoch + 1)
                        break

            # Restore best checkpoint
            if best_state is not None:
                self._model.load_state_dict(best_state)
            self._model.eval()

            # ── 7. Test set evaluation ─────────────────────────────────────────
            with torch.no_grad():
                test_pred = self._model(X_test)
                test_acc  = ((test_pred > 0.5).float() == y_test).float().mean().item()
                test_loss = criterion(test_pred, y_test).item()

            logger.info(
                "[TCN-9] Training complete — test_acc=%.4f test_loss=%.5f",
                test_acc, test_loss,
            )

            # ── 8. Save weights ────────────────────────────────────────────────
            self._save_weights()

            return {
                "status":    "trained",
                "n_samples": N,
                "n_train":   len(X_train),
                "n_val":     len(X_val),
                "n_test":    len(X_test),
                "test_acc":  round(test_acc, 4),
                "test_loss": round(test_loss, 5),
                "best_val_loss": round(best_val_loss, 5),
                "epochs_run": len(history),
                "history":   history[-5:],   # last 5 epochs
            }

        except Exception as e:
            logger.error("[TCN-9] Training failed: %s", e, exc_info=True)
            return {"error": str(e)}

    # ── Inference ─────────────────────────────────────────────────────────────

    async def run_inference(
        self,
        df: "pd.DataFrame",
        funding_rate: float = 0.0,
    ) -> Dict:
        """
        Run one inference step on the latest OHLCV candles.

        Parameters
        ----------
        df : pd.DataFrame
            Raw OHLCV DataFrame with at least WINDOW + 35 rows.
            Columns: open, high, low, close, volume.
        funding_rate : float
            Current MEXC funding rate. 0.0 if unavailable.

        Returns
        -------
        Dict with keys:
            p_hat     — bullish probability ∈ [0, 1]
            w         — position weight ∈ [−1, 1]
            direction — "LONG" | "SHORT" | "NO_TRADE"
            confidence — 0–100
            alpha9    — TCN's contribution to |Ψ⟩
            s9_sharpe — current rolling Sharpe estimate
        """
        if not _TORCH_OK or self._model is None:
            return self._zero_signal("PyTorch/model unavailable")

        try:
            from engines.tcn_feature_builder import build_inference_window

            window_arr = build_inference_window(df, funding_rate, WINDOW)
            if window_arr is None:
                return self._zero_signal("Insufficient candles for window")

            X = torch.tensor(window_arr, dtype=torch.float32)

            self._model.eval()
            with torch.no_grad():
                p_hat = float(self._model(X).item())

            # Update realised vol buffer
            if not df.empty and len(df) >= 2:
                closes = df["close"].values[-21:].astype(float)
                if len(closes) >= 2:
                    rets = np.log(closes[1:] / (closes[:-1] + 1e-10))
                    self._return_buffer = rets.tolist()[-20:]
                    self._last_close    = float(closes[-1])

            # Position sizing
            sigma_hat = float(np.std(self._return_buffer)) if len(self._return_buffer) >= 2 else SIGMA_STAR
            sigma_hat = max(sigma_hat, 1e-8)

            raw_signal = 2.0 * p_hat - 1.0  # ∈ [−1, 1]

            # Deadband gate g_τ
            gated_signal = raw_signal if abs(raw_signal) >= DEADBAND_TAU else 0.0

            # Volatility-scaled weight
            w = (SIGMA_STAR / sigma_hat) * gated_signal
            w = float(np.clip(w, W_MIN, W_MAX))

            # Direction
            if w > DEADBAND_TAU:
                direction = "LONG"
            elif w < -DEADBAND_TAU:
                direction = "SHORT"
            else:
                direction = "NO_TRADE"

            # α₉ = (2p̂ − 1) × S₉
            alpha9 = raw_signal * self._s9_sharpe

            # Update state
            self._p_hat     = p_hat
            self._w         = w
            self._direction = direction
            self._alpha9    = alpha9
            self._last_inference_ts = time.time()
            self._consecutive_errors = 0

            confidence = abs(p_hat - 0.5) * 200.0   # 0–100

            result = {
                "p_hat":      round(p_hat, 6),
                "w":          round(w, 6),
                "direction":  direction,
                "confidence": round(confidence, 2),
                "alpha9":     round(alpha9, 6),
                "s9_sharpe":  round(self._s9_sharpe, 4),
                "sigma_hat":  round(sigma_hat, 6),
                "timestamp":  datetime.now(timezone.utc).isoformat(),
                "engine":     self.ENGINE_LABEL,
            }

            # Log to MongoDB
            await self._log_signal(result)

            return result

        except Exception as e:
            self._consecutive_errors += 1
            logger.error("[TCN-9] Inference error: %s", e, exc_info=True)
            return self._zero_signal(str(e))

    def _zero_signal(self, reason: str = "") -> Dict:
        """Return the graceful-degradation zero signal."""
        self._alpha9 = 0.0
        return {
            "p_hat":      0.5,
            "w":          0.0,
            "direction":  "NO_TRADE",
            "confidence": 0.0,
            "alpha9":     0.0,
            "s9_sharpe":  0.0,
            "sigma_hat":  SIGMA_STAR,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "engine":     self.ENGINE_LABEL,
            "error":      reason,
        }

    # ── S₉ rolling Sharpe ─────────────────────────────────────────────────────

    async def _refresh_sharpe(self):
        """
        Compute rolling Sharpe S₉ from the last SHARPE_LOOKBACK closed TCN
        signals in MongoDB (those with `outcome_return` field set).

        S₉ = mean(returns) / (std(returns) + ε) × sqrt(HOURLY_PER_YEAR)
        """
        if self._db is None:
            self._s9_sharpe = 0.0
            return

        try:
            cursor = self._db["tcn_signals"].find(
                {"outcome_return": {"$exists": True, "$ne": None}},
                sort=[("timestamp", -1)],
                limit=SHARPE_LOOKBACK,
            )
            docs = await cursor.to_list(length=SHARPE_LOOKBACK)

            if len(docs) < 5:
                self._s9_sharpe = 0.0
                return

            returns = np.array([d["outcome_return"] for d in docs], dtype=float)
            mean_r  = float(np.mean(returns))
            std_r   = float(np.std(returns)) + 1e-8
            sharpe  = mean_r / std_r * math.sqrt(HOURLY_PER_YEAR)
            self._s9_sharpe = float(np.clip(sharpe, -5.0, 5.0))

            logger.debug(
                "[TCN-9] S₉=%.4f (n=%d, μ=%.6f, σ=%.6f)",
                self._s9_sharpe, len(docs), mean_r, std_r,
            )

        except Exception as e:
            logger.debug("[TCN-9] Sharpe refresh failed: %s", e)
            self._s9_sharpe = 0.0

    # ── MongoDB logging ───────────────────────────────────────────────────────

    async def _log_signal(self, result: Dict):
        """Persist TCN signal to MongoDB `tcn_signals` collection."""
        if self._db is None:
            return
        try:
            doc = {
                **result,
                "strategy":       self.ENGINE_LABEL,
                "symbol":         "BTC/USDT",
                "outcome_return": None,   # filled when outcome is known
                "logged_at":      datetime.now(timezone.utc),
            }
            await self._db["tcn_signals"].insert_one(doc)
        except Exception as e:
            logger.debug("[TCN-9] Signal log failed: %s", e)

    async def record_outcome(self, signal_ts: str, outcome_return: float):
        """
        Update a previously logged signal with its realised outcome return.
        Called externally when the trade associated with this signal closes.
        Also updates recent accuracy buffer for retrain trigger.

        Parameters
        ----------
        signal_ts : str
            ISO timestamp of the signal to update (must be unique).
        outcome_return : float
            Realised log return of the trade (positive = win, negative = loss).
        """
        if self._db is None:
            return
        try:
            # Direction at signal time: positive outcome means direction was correct
            doc = await self._db["tcn_signals"].find_one(
                {"timestamp": signal_ts}, projection={"direction": 1, "p_hat": 1}
            )
            if doc:
                # Accuracy: p̂ > 0.5 predicted LONG, outcome > 0 means it went up
                p_hat   = doc.get("p_hat", 0.5)
                correct = (p_hat > 0.5 and outcome_return > 0) or (p_hat <= 0.5 and outcome_return <= 0)
                self._recent_accuracy.append(1.0 if correct else 0.0)
                if len(self._recent_accuracy) > RETRAIN_ACCURACY_WINDOW:
                    self._recent_accuracy.pop(0)

            await self._db["tcn_signals"].update_one(
                {"timestamp": signal_ts},
                {"$set": {"outcome_return": outcome_return}},
            )
            # Refresh Sharpe now that we have new outcome data
            await self._refresh_sharpe()

        except Exception as e:
            logger.debug("[TCN-9] Outcome record failed: %s", e)

    # ── Retrain trigger ───────────────────────────────────────────────────────

    def _should_retrain(self) -> bool:
        """
        Returns True when rolling accuracy over last RETRAIN_ACCURACY_WINDOW
        trades falls below RETRAIN_ACCURACY_FLOOR (default 52%).
        """
        if len(self._recent_accuracy) < RETRAIN_ACCURACY_WINDOW:
            return False
        acc = sum(self._recent_accuracy) / len(self._recent_accuracy)
        if acc < RETRAIN_ACCURACY_FLOOR:
            logger.warning(
                "[TCN-9] Rolling accuracy %.3f < %.3f — triggering retrain",
                acc, RETRAIN_ACCURACY_FLOOR,
            )
            return True
        return False

    # ── Public getters (called by quantum state) ──────────────────────────────

    def get_alpha9(self) -> float:
        """Current α₉ = (2p̂−1) × S₉. Returns 0.0 on degradation."""
        return self._alpha9

    def get_p_hat(self) -> float:
        return self._p_hat

    def get_direction(self) -> str:
        return self._direction

    def get_confidence(self) -> float:
        return abs(self._p_hat - 0.5) * 200.0

    def get_sharpe(self) -> float:
        return self._s9_sharpe

    def is_live(self) -> bool:
        """True if a successful inference was run in the last 2 hours."""
        return (
            _TORCH_OK
            and self._model is not None
            and (time.time() - self._last_inference_ts) < 7200
        )

    def get_vote(self, symbol: str = "BTC/USDT") -> Dict:
        """
        Return binary ensemble vote for a symbol.
        TCN is trained on BTC/USDT only — other symbols return NEUTRAL.
        This is the proper ensemble-voter interface: a clear directional vote
        rather than diluting α₉ into the quantum state vector.
        """
        if symbol not in ("BTC/USDT", "BTCUSDT"):
            return {"vote": "NEUTRAL", "confidence": 0.0, "p_hat": 0.5, "live": False}

        if not self.is_live():
            return {"vote": "NEUTRAL", "confidence": 0.0, "p_hat": self._p_hat, "live": False}

        conf = self.get_confidence()
        if self._direction == "LONG":
            vote = "BULLISH"
        elif self._direction == "SHORT":
            vote = "BEARISH"
        else:
            vote = "NEUTRAL"

        return {
            "vote": vote,
            "confidence": round(conf, 2),
            "p_hat": round(self._p_hat, 4),
            "sharpe": round(self._s9_sharpe, 4),
            "alpha9": round(self._alpha9, 4),
            "live": True,
        }

    def get_all_votes(self) -> Dict[str, Dict]:
        """
        Return vote dict for all symbols this engine covers.
        Currently BTC-only; other symbols return NEUTRAL placeholder.
        """
        return {
            "BTC/USDT": self.get_vote("BTC/USDT"),
        }

    # ── Background loop ───────────────────────────────────────────────────────

    async def run_background_loop(self, interval_seconds: int = 3600):
        """
        Run inference every `interval_seconds` (default 1 hour — aligned with
        the 1h candle timeframe). Also checks retrain trigger after each cycle.

        Wire into server.py startup:
            asyncio.create_task(tcn_engine.run_background_loop())
        """
        logger.info(
            "[TCN-9] Background loop started — inference every %ds", interval_seconds
        )

        while True:
            try:
                # Train first if no weights exist
                if not _WEIGHTS_PATH.exists() and _TORCH_OK:
                    logger.info("[TCN-9] No weights found — initiating training...")
                    result = await self.train()
                    logger.info("[TCN-9] Initial training result: %s", result)

                # Fetch latest candles
                if self._market_intel is not None:
                    # 150 candles: enough for feature warmup (35) + window (64) + buffer
                    loop = asyncio.get_running_loop()
                    df = await loop.run_in_executor(
                        None,
                        lambda: self._market_intel.get_klines_sync(
                            "BTC/USDT", "1h", 150
                        ),
                    )
                    funding = await self._fetch_funding_rate()

                    if df is not None and not df.empty:
                        await self.run_inference(df, funding)

                        logger.info(
                            "[TCN-9] Inference — p̂=%.4f w=%.4f dir=%s α₉=%.4f S₉=%.4f",
                            self._p_hat, self._w, self._direction,
                            self._alpha9, self._s9_sharpe,
                        )

                        # Retrain trigger check
                        if self._should_retrain():
                            logger.info("[TCN-9] Accuracy below floor — retraining...")
                            await self.train()

                # Refresh Sharpe every hour
                await self._refresh_sharpe()

                # Heartbeat for health monitor
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("tcn_neural")
                except Exception:
                    pass

            except Exception as e:
                logger.error("[TCN-9] Background loop error: %s", e, exc_info=True)

            # Sleep in 60s chunks so heartbeat stays fresh throughout long interval
            elapsed = 0
            while elapsed < interval_seconds:
                await asyncio.sleep(60)
                elapsed += 60
                try:
                    from self_healer import self_healer
                    self_healer.heartbeat("tcn_neural")
                except Exception:
                    pass


# ─── Singleton ────────────────────────────────────────────────────────────────

_tcn_engine: Optional[TCNNeuralEngine] = None


def init_tcn_engine() -> TCNNeuralEngine:
    """Create the global Engine 9 singleton. Call once from server.py."""
    global _tcn_engine
    _tcn_engine = TCNNeuralEngine()
    return _tcn_engine


def get_tcn_engine() -> Optional[TCNNeuralEngine]:
    """Return the live singleton. Returns None before init_tcn_engine()."""
    return _tcn_engine


def get_tcn_alpha() -> float:
    """
    Module-level shortcut for aeon_quantum_state.

    Returns α₉ = (2p̂−1) × S₉, or 0.0 if Engine 9 is not initialised.
    This is the raw directional amplitude before drawdown decay / regime gate.
    """
    if _tcn_engine is None:
        return 0.0
    return _tcn_engine.get_alpha9()


def get_tcn_direction_bias() -> float:
    """
    Returns the signed direction signal for Engine 9 correlation matrix.
    LONG → +1, SHORT → −1, NO_TRADE → 0.
    """
    if _tcn_engine is None:
        return 0.0
    d = _tcn_engine.get_direction()
    return 1.0 if d == "LONG" else (-1.0 if d == "SHORT" else 0.0)
