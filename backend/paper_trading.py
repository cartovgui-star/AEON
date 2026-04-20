"""
AEON REALISTIC PAPER TRADING SYSTEM
Inspired by MEXC Demo Trading

Features:
- Two accounts: PRO ($50K) and STARTER ($1.5K)
- Liquidation prices
- Leverage, margin, position sizing
- Cross/Isolated margin modes
- Add margin to positions
- Auto-reload on liquidation
"""

import asyncio
import logging
import traceback
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# ── Telegram notifier (set via set_telegram_notifier after init) ──────────────
_telegram_send_fn = None
_telegram_chat_ids: set = set()

def set_telegram_notifier(send_fn, chat_ids):
    """Called from server.py after everything is initialized."""
    global _telegram_send_fn, _telegram_chat_ids
    _telegram_send_fn = send_fn
    _telegram_chat_ids = chat_ids

async def _notify(msg: str):
    """Send msg to all registered chat IDs. Fire-and-forget, never raises."""
    if not _telegram_send_fn or not _telegram_chat_ids:
        return
    for cid in _telegram_chat_ids:
        try:
            await _telegram_send_fn(cid, msg, parse_mode="Markdown")
        except Exception as e:
            logger.warning(f"Paper trade Telegram notify failed: {e}")

# Round-trip trading fee (entry + exit taker fees, realistic for MEXC)
# 0.20% per side = 0.40% round-trip.
# Includes 0.05% funding drag buffer (avg 8h funding ~0.01-0.05%, charged per hold period).
# Higher than raw taker fee (0.15%) to simulate realistic fill + spread cost.
TRADE_FEE_PCT = 0.0020

# Average hold duration used to estimate funding drag when closing
# Used in realized PnL commentary only — actual fill uses TRADE_FEE_PCT
FUNDING_RATE_PER_8H = 0.0001  # 0.01% per 8h — typical BTC perpetual funding

# Max auto-reloads allowed per calendar month per account
MAX_MONTHLY_RELOADS = 3

# Account configurations
ACCOUNTS = {
    "PRO": {
        "name": "PRO Account",
        "starting_balance": 50000.0,
        "emoji": "👑",
        "base_risk_pct": 2.0,
        "use_quantum_sizing": False,
        "notify_telegram": True,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 20,
        "daily_trade_cap": 8,
    },
    "STARTER": {
        "name": "Starter Account",
        "starting_balance": 1500.0,
        "emoji": "🌱",
        "base_risk_pct": 2.0,
        "use_quantum_sizing": False,
        "notify_telegram": False,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 20,
        "daily_trade_cap": 8,
    },
    "REAL_LIFE": {
        "name": "Real Life",
        "starting_balance": 700.0,
        "emoji": "💰",
        "base_risk_pct": 3.0,
        "use_quantum_sizing": True,
        "quantum_floor": 0.35,
        "notify_telegram": True,
        "auto_deposit_usd": 700.0,
        "auto_deposit_days": 7,
        "target_balance": None,
        "max_leverage": 20,
        "daily_trade_cap": 8,
    },
    "THE_PROOF": {
        "name": "The Proof",
        "starting_balance": 40.0,
        "emoji": "🎯",
        "base_risk_pct": 5.0,
        "use_quantum_sizing": True,
        "quantum_floor": 0.35,
        "notify_telegram": True,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": 680.0,
        "target_multiplier": 17.0,
        "max_leverage": 20,
        "daily_trade_cap": 8,
    },
    "BENCHMARK": {
        "name": "Benchmark",
        "starting_balance": 50000.0,
        "emoji": "📊",
        "base_risk_pct": 2.0,
        "use_quantum_sizing": False,
        "notify_telegram": False,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 20,
        "daily_trade_cap": 8,
    },
    # ── Phase 1: Tiered paper accounts ───────────────────────────────────────
    # Conservative profiles for testing risk policy behavior at different
    # balance tiers. Tighter leverage and concurrent position limits as
    # balance decreases. Telegram disabled — observation only for Phase 1.
    "TIER_5K": {
        "name": "Tier 5K",
        "starting_balance": 5000.0,
        "emoji": "🔵",
        "base_risk_pct": 2.0,
        "use_quantum_sizing": False,
        "notify_telegram": False,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 15,
        "daily_trade_cap": 8,
    },
    "TIER_1K": {
        "name": "Tier 1K",
        "starting_balance": 1000.0,
        "emoji": "🟡",
        "base_risk_pct": 2.0,
        "use_quantum_sizing": False,
        "notify_telegram": False,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 10,
        "daily_trade_cap": 6,
    },
    "TIER_500": {
        "name": "Tier 500",
        "starting_balance": 500.0,
        "emoji": "🟠",
        "base_risk_pct": 1.5,
        "use_quantum_sizing": False,
        "notify_telegram": False,
        "auto_deposit_usd": 0.0,
        "auto_deposit_days": None,
        "target_balance": None,
        "max_leverage": 5,
        "daily_trade_cap": 5,
    },
}

# Accounts that receive engine signals (all except none)
_TRADING_ACCOUNTS = list(ACCOUNTS.keys())

# Correlation groups — max 1 LONG and 1 SHORT open per group at a time
CORRELATION_GROUPS = {
    "btc_eco": ["BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT", "AVAX/USDT", "MATIC/USDT", "ARB/USDT", "OP/USDT"],
    "defi":    ["UNI/USDT", "AAVE/USDT", "CRV/USDT", "MKR/USDT", "COMP/USDT", "SNX/USDT", "SUSHI/USDT"],
    "layer1":  ["ADA/USDT", "DOT/USDT", "ATOM/USDT", "NEAR/USDT", "FTM/USDT", "ALGO/USDT"],
    "meme":    ["DOGE/USDT", "SHIB/USDT", "PEPE/USDT", "FLOKI/USDT", "BONK/USDT"],
}

def get_correlation_group(symbol: str) -> Optional[str]:
    for group_name, symbols in CORRELATION_GROUPS.items():
        if symbol in symbols:
            return group_name
    return None

# Default leverage by asset - NO RESTRICTIONS, use what's best
def get_dynamic_leverage(symbol: str, confidence: int, direction: str, volatility: str = "medium") -> int:
    """
    SMART LEVERAGE SELECTION
    
    Bot chooses optimal leverage based on:
    - Coin volatility profile
    - Signal confidence level
    - Current market volatility
    
    Higher confidence + Lower volatility = Higher leverage
    Lower confidence + Higher volatility = Lower leverage
    """
    coin = symbol.split("/")[0] if "/" in symbol else symbol

    # Base leverage ranges by coin (min, max)
    # NOTE: Caps reduced significantly — data showed 28/64 (44%) of closed trades
    # were liquidations at avg 50x leverage. Lower leverage = stay in trade.
    COIN_LEVERAGE = {
        "BTC": (5, 20),
        "ETH": (5, 15),
        "SOL": (3, 12),
        "BNB": (3, 12),
        "XRP": (3, 10),
        "DOGE": (3, 8),
        "ADA": (3, 10),
        "AVAX": (3, 12),
        "LINK": (3, 12),
        "DOT": (3, 10),
    }

    min_lev, max_lev = COIN_LEVERAGE.get(coin, (10, 30))

    # Volatility adjustment
    if volatility == "high":
        min_lev = max(5, min_lev // 2)
        max_lev = max(10, max_lev // 2)
    elif volatility == "low":
        min_lev = int(min_lev * 1.2)
        max_lev = int(max_lev * 1.2)

    # Deterministic confidence-based selection: scale within range
    conf_clamped = max(0, min(100, confidence))
    conf_normalized = (conf_clamped - 60) / 40.0  # 60 = baseline, 100 = max
    conf_normalized = max(0.0, min(1.0, conf_normalized))
    leverage = int(min_lev + (max_lev - min_lev) * conf_normalized)

    # Final bounds — hard cap at 20x
    return min(20, max(2, leverage))



def calculate_smart_stops(entry_price: float, leverage: int, direction: str) -> tuple:
    """
    SMART STOP LOSS & TAKE PROFIT

    Key insight: Higher leverage = TIGHTER stops (in % of price).
    Liquidation distance = 1/leverage. SL must sit well inside that.

    Formula: sl_pct = base_sl / sqrt(leverage)
    - At  1x: SL =10.0%  TP =25.0%  R:R = 2.5:1
    - At  4x: SL = 5.0%  TP =12.5%  R:R = 2.5:1
    - At 10x: SL = 3.2%  TP = 7.9%  R:R = 2.5:1
    - At 20x: SL = 2.2%  TP = 5.6%  R:R = 2.5:1  (liq @ 5% — SL fires first ✓)

    R:R floor enforced at 2.5:1 to ensure positive expectancy after fees/slippage.

    Returns: (stop_loss, take_profit)
    """
    import math

    # Base SL/TP at 1x leverage
    base_sl_pct = 0.10   # 10% base SL
    base_tp_pct = 0.25   # 25% base TP → R:R = 2.5:1 (was 1.5:1)

    leverage_factor = math.sqrt(leverage)

    sl_pct = base_sl_pct / leverage_factor
    tp_pct = base_tp_pct / leverage_factor

    # Hard floors: never stop out on noise, never let TP be unreachable
    sl_pct = max(0.008, sl_pct)   # min 0.8%
    tp_pct = max(0.020, tp_pct)   # min 2.0%

    # Hard ceiling: SL must be within 85% of ACTUAL liq distance.
    # Actual liq distance = 1/leverage - MMR (not just 1/leverage).
    # Old formula used 1/leverage × 0.80 which ignored MMR, causing SL to land
    # beyond the liquidation price at high leverage (e.g. 80x: 1.0% ceiling vs 0.75% actual liq dist).
    _mmr_ss = 0.005
    actual_liq_dist = max(0.001, (1.0 / leverage) - _mmr_ss)
    sl_pct = min(sl_pct, actual_liq_dist * 0.85)

    # Enforce 2.5:1 R:R floor regardless of other clipping
    tp_pct = max(tp_pct, sl_pct * 2.5)

    if direction == "LONG":
        stop_loss   = entry_price * (1 - sl_pct)
        take_profit = entry_price * (1 + tp_pct)
    else:  # SHORT
        stop_loss   = entry_price * (1 + sl_pct)
        take_profit = entry_price * (1 - tp_pct)

    return round(stop_loss, 4), round(take_profit, 4)



def calculate_liquidation_price(
    entry_price: float,
    leverage: int,
    direction: str,
    margin_type: str = "isolated",
    maintenance_margin_rate: float = 0.005  # 0.5% maintenance margin
) -> float:
    """
    Calculate liquidation price for a position
    
    For LONG: Liq Price = Entry * (1 - 1/Leverage + MMR)
    For SHORT: Liq Price = Entry * (1 + 1/Leverage - MMR)
    """
    if direction == "LONG":
        liq_price = entry_price * (1 - (1 / leverage) + maintenance_margin_rate)
    else:  # SHORT
        liq_price = entry_price * (1 + (1 / leverage) - maintenance_margin_rate)
    
    return round(liq_price, 2)


def calculate_position_size(
    balance: float,
    risk_pct: float,
    entry_price: float,
    stop_loss: float,
    leverage: int
) -> Dict:
    """
    Calculate position size based on fixed-risk model.

    Formula (corrected):
        notional = risk_amount / sl_distance_pct
        margin   = notional / leverage

    The old formula multiplied by leverage a second time, making positions
    too large. Now notional is derived purely from risk/sl_distance, and
    leverage only affects how much margin backs that notional.

    Slippage buffer: sl_distance is widened by 0.6% to account for
    MEXC stop-market fills executing slightly below/above the trigger
    price (empirical average slippage on volatile altcoins).
    """

    # Maximum margin per trade: 5% of balance (allows ~12 concurrent positions)
    max_margin_pct = 5.0
    max_margin = balance * (max_margin_pct / 100)

    risk_amount = balance * (risk_pct / 100)

    if entry_price <= 0:
        entry_price = 1e-8

    # Raw SL distance
    raw_sl_dist_pct = abs(entry_price - stop_loss) / entry_price * 100
    # Add slippage buffer so position is sized for real-world fills, not theoretical
    SLIPPAGE_BUFFER_PCT = 0.60   # 0.6% added to SL distance (MEXC taker slippage)
    sl_distance_pct = raw_sl_dist_pct + SLIPPAGE_BUFFER_PCT

    # Notional = risk_amount / sl_distance  (leverage scales margin, not notional)
    if sl_distance_pct > 0:
        position_size_usd = risk_amount / (sl_distance_pct / 100)
    else:
        position_size_usd = max_margin * leverage  # fallback

    # Margin = notional / leverage
    margin_required = position_size_usd / leverage

    # Cap at 5% of balance
    if margin_required > max_margin:
        margin_required = max_margin
        position_size_usd = margin_required * leverage

    quantity = position_size_usd / entry_price
    margin_required = max(margin_required, 1.0)

    return {
        "position_size_usd": round(position_size_usd, 4),
        "margin_required": round(margin_required, 4),
        "quantity": round(quantity, 8),
        "leverage": leverage,
        "risk_amount": round(risk_amount, 4)
    }


class PaperTradingSystem:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.accounts: Dict[str, Dict] = {}
        self._quantum_engine = None

    def set_quantum_engine(self, qe):
        """Wire in quantum state engine for position sizing."""
        self._quantum_engine = qe

    def _get_quantum_multiplier(self, acc_id: str) -> float:
        """
        Returns position multiplier from quantum state.
        Uses account's quantum_floor as minimum so trades always happen
        while data accumulates.
        """
        floor = ACCOUNTS.get(acc_id, {}).get("quantum_floor", 0.35)
        try:
            if self._quantum_engine is None:
                return floor
            state = self._quantum_engine.get_state()
            if state is None:
                return floor
            mult = float(state.get("position_multiplier", 0.0))
            return max(mult, floor)
        except Exception:
            return floor

    def _acc_label(self, account_id: str) -> str:
        cfg = ACCOUNTS.get(account_id, {})
        return f"{cfg.get('emoji', '📊')} {cfg.get('name', account_id)}"

    async def initialize(self):
        """Initialize or load paper trading accounts"""
        now = datetime.now(timezone.utc)
        for acc_id, config in ACCOUNTS.items():
            account = await self.db.paper_accounts.find_one({"_id": acc_id})

            if not account:
                # Build new account doc
                account = {
                    "_id": acc_id,
                    "name": config["name"],
                    "emoji": config["emoji"],
                    "balance": config["starting_balance"],
                    "starting_balance": config["starting_balance"],
                    "total_pnl": 0.0,
                    "total_trades": 0,
                    "wins": 0,
                    "losses": 0,
                    "reloads": 0,
                    "monthly_reloads": 0,
                    "reload_month": now.strftime("%Y-%m"),
                    "created_at": now,
                    "positions": [],
                    "consecutive_losses": 0,
                    "peak_balance": config["starting_balance"],
                    "circuit_breaker_active": False,
                    "circuit_breaker_until": None,
                    # Deposit tracking
                    "total_deposited": config["starting_balance"],
                    "deposit_history": [{"amount": config["starting_balance"], "deposited_at": now, "balance_after": config["starting_balance"], "note": "initial"}],
                    "next_deposit_at": (now + timedelta(days=config["auto_deposit_days"])) if config.get("auto_deposit_days") else None,
                    # Target tracking
                    "target_balance": config.get("target_balance"),
                    "target_hit_at": None,
                    # Weekly PnL baseline (reset every Monday)
                    "week_start_balance": config["starting_balance"],
                    "week_start_at": now,
                }
                await self.db.paper_accounts.insert_one(account)
                logger.info(f"[Paper] Created account {acc_id} — ${config['starting_balance']:,.0f}")
            else:
                # Patch any missing fields on existing accounts
                patch = {}
                if "total_deposited" not in account:
                    patch["total_deposited"] = account.get("starting_balance", config["starting_balance"])
                if "deposit_history" not in account:
                    patch["deposit_history"] = []
                if "next_deposit_at" not in account and config.get("auto_deposit_days"):
                    patch["next_deposit_at"] = now + timedelta(days=config["auto_deposit_days"])
                if "target_balance" not in account:
                    patch["target_balance"] = config.get("target_balance")
                if "target_hit_at" not in account:
                    patch["target_hit_at"] = None
                if "week_start_balance" not in account:
                    patch["week_start_balance"] = account.get("balance", config["starting_balance"])
                    patch["week_start_at"] = now
                if patch:
                    await self.db.paper_accounts.update_one({"_id": acc_id}, {"$set": patch})

            self.accounts[acc_id] = account

        logger.info(f"[Paper] Initialized accounts: {list(self.accounts.keys())}")

    async def auto_deposit_loop(self):
        """Background loop: runs every hour, deposits $700 to REAL_LIFE every 7 days."""
        while True:
            try:
                await asyncio.sleep(3600)
                now = datetime.now(timezone.utc)
                for acc_id, config in ACCOUNTS.items():
                    if not config.get("auto_deposit_usd"):
                        continue
                    account = await self.get_account(acc_id)
                    if not account:
                        continue
                    next_dep = account.get("next_deposit_at")
                    if next_dep is None:
                        continue
                    if isinstance(next_dep, str):
                        next_dep = datetime.fromisoformat(next_dep.replace("Z", "+00:00"))
                    # Motor returns naive datetimes from MongoDB — make timezone-aware
                    if isinstance(next_dep, datetime) and next_dep.tzinfo is None:
                        next_dep = next_dep.replace(tzinfo=timezone.utc)
                    if now >= next_dep:
                        dep_amount = config["auto_deposit_usd"]
                        new_balance = account["balance"] + dep_amount
                        new_total = account.get("total_deposited", account["starting_balance"]) + dep_amount
                        new_next = now + timedelta(days=config["auto_deposit_days"])
                        entry = {"amount": dep_amount, "deposited_at": now, "balance_after": new_balance, "note": "auto_weekly"}
                        await self.db.paper_accounts.update_one(
                            {"_id": acc_id},
                            {
                                "$inc": {"balance": dep_amount},
                                "$set": {"total_deposited": new_total, "next_deposit_at": new_next},
                                "$push": {"deposit_history": entry},
                            }
                        )
                        await self.db.paper_events.insert_one({"type": "auto_deposit", "account_id": acc_id, "amount": dep_amount, "new_balance": new_balance, "timestamp": now})
                        logger.info(f"[Paper] Auto-deposited ${dep_amount:,.0f} to {acc_id}. New balance: ${new_balance:,.0f}")
                        if config.get("notify_telegram"):
                            asyncio.create_task(_notify(
                                f"💰 Auto-Deposit · Real Life\n\n"
                                f"Deposited  ${dep_amount:,.0f}\n"
                                f"Balance    ${new_balance:,.0f}\n"
                                f"Total in   ${new_total:,.0f}\n"
                                f"Next dep   {new_next.strftime('%b %d')}"
                            ))
            except Exception as e:
                logger.error(f"[Paper] auto_deposit_loop error: {e}")

    async def get_weekly_summary(self) -> Dict:
        """Return weekly PnL stats for all 5 accounts."""
        result = {}
        for acc_id in ACCOUNTS:
            account = await self.get_account(acc_id)
            if not account:
                continue
            config = ACCOUNTS[acc_id]
            balance = account.get("balance", 0)
            week_start = account.get("week_start_balance", account.get("starting_balance", 0))
            weekly_pnl = balance - week_start
            weekly_pct = (weekly_pnl / week_start * 100) if week_start > 0 else 0
            total_dep = account.get("total_deposited", account.get("starting_balance", 0))
            target = config.get("target_balance")
            target_pct = (balance / target * 100) if target else None
            crossover_pct = (weekly_pnl / config.get("auto_deposit_usd", 1) * 100) if config.get("auto_deposit_usd") else None
            result[acc_id] = {
                "balance": round(balance, 2),
                "week_start_balance": round(week_start, 2),
                "weekly_pnl": round(weekly_pnl, 2),
                "weekly_pnl_pct": round(weekly_pct, 2),
                "total_deposited": round(total_dep, 2),
                "target_balance": target,
                "target_pct": round(target_pct, 1) if target_pct else None,
                "target_hit_at": account.get("target_hit_at"),
                "crossover_pct": round(crossover_pct, 1) if crossover_pct else None,
                "total_trades": account.get("total_trades", 0),
                "win_rate": round(account.get("wins", 0) / max(account.get("total_trades", 1), 1) * 100, 1),
            }

        # Attach quantum state snapshot if available
        if self._quantum_engine is not None:
            try:
                snap = self._quantum_engine.get_current_state()
                result["quantum_state"] = {
                    "H": round(snap.H, 4),
                    "C": round(snap.C, 4),
                }
            except Exception:
                result["quantum_state"] = {}

        # Best engine for BENCHMARK — highest win-rate among closed trades this week
        try:
            from datetime import timezone as _tz
            cutoff = datetime.now(timezone.utc) - timedelta(days=7)
            engine_wins: Dict[str, list] = {}
            bm_trades = await self.db.paper_trades.find({
                "account_id": "BENCHMARK",
                "status": {"$in": ["closed", "profit", "stopped", "liquidated"]},
                "closed_at": {"$gte": cutoff},
            }).to_list(500)
            for t in bm_trades:
                eng = t.get("strategy", "unknown")
                if eng not in engine_wins:
                    engine_wins[eng] = []
                engine_wins[eng].append((t.get("realized_pnl") or 0) > 0)
            if engine_wins:
                best = max(engine_wins, key=lambda e: sum(engine_wins[e]) / max(len(engine_wins[e]), 1))
                result.setdefault("BENCHMARK", {})["best_engine"] = best
        except Exception:
            pass

        return result

    async def reset_weekly_baselines(self):
        """Called every Monday after report is sent. Resets week_start_balance."""
        now = datetime.now(timezone.utc)
        for acc_id in ACCOUNTS:
            account = await self.get_account(acc_id)
            if not account:
                continue
            await self.db.paper_accounts.update_one(
                {"_id": acc_id},
                {"$set": {"week_start_balance": account.get("balance", 0), "week_start_at": now}}
            )
    
    async def get_account(self, account_id: str) -> Optional[Dict]:
        """Get account by ID"""
        account = await self.db.paper_accounts.find_one({"_id": account_id})
        return account
    
    async def get_all_accounts(self) -> List[Dict]:
        """Get all accounts"""
        accounts = await self.db.paper_accounts.find().to_list(10)
        return accounts
    
    async def open_position(
        self,
        account_id: str,
        symbol: str,
        direction: str,
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        leverage: int = None,
        margin_type: str = "cross",
        risk_pct: float = 2.0,
        signal_data: Dict = None,
        confidence: int = 80,
        strategy: str = "unknown"
    ) -> Dict:
        """Open a new position with full details"""

        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}

        # ── Circuit Breaker ────────────────────────────────────────────────────
        if account.get("circuit_breaker_active"):
            until = account.get("circuit_breaker_until")
            if until:
                # Check if cooldown expired
                try:
                    until_dt = datetime.fromisoformat(until.replace("Z", "+00:00")) if isinstance(until, str) else until
                    if isinstance(until_dt, datetime) and until_dt.tzinfo is None:
                        until_dt = until_dt.replace(tzinfo=timezone.utc)
                    if datetime.now(timezone.utc) < until_dt:
                        return {"error": f"Circuit breaker active — trading halted until {until}"}
                    else:
                        # Auto-reset
                        await self.db.paper_accounts.update_one(
                            {"_id": account_id},
                            {"$set": {"circuit_breaker_active": False, "circuit_breaker_until": None, "consecutive_losses": 0}}
                        )
                        account["circuit_breaker_active"] = False
                except Exception:
                    pass
            else:
                return {"error": "Circuit breaker active — trading halted due to drawdown"}


        # ORIA: apply spread-adjusted entry price for realistic paper simulation
        # Longs pay the ask (slightly higher); shorts hit the bid (slightly lower).
        try:
            from oria_layer import get_edge_filter as _get_ef
            _ef = _get_ef()
            if _ef is not None:
                entry_price = _ef.spread_adjusted_entry(symbol, direction, entry_price)
        except Exception:
            pass

        # Get dynamic leverage based on confidence if not specified
        if leverage is None:
            leverage = get_dynamic_leverage(symbol, confidence, direction)

        # Use smart stops only when no valid stop/target was provided by the caller
        smart_sl, smart_tp = calculate_smart_stops(entry_price, leverage, direction)
        if not stop_loss or stop_loss == 0:
            stop_loss = smart_sl
        if not take_profit or take_profit == 0:
            take_profit = smart_tp

        # Calculate position sizing
        sizing = calculate_position_size(
            balance=account["balance"],
            risk_pct=risk_pct,
            entry_price=entry_price,
            stop_loss=stop_loss,
            leverage=leverage
        )

        # ── Dynamic Sizing: reduce after consecutive losses ────────────────────
        consec_losses = account.get("consecutive_losses", 0)
        if consec_losses >= 3:
            sizing_mult = 0.4
        elif consec_losses == 2:
            sizing_mult = 0.7
        else:
            sizing_mult = 1.0
        if sizing_mult < 1.0:
            sizing["margin_required"] = round(sizing["margin_required"] * sizing_mult, 2)
            sizing["position_size_usd"] = round(sizing["position_size_usd"] * sizing_mult, 2)
            logger.info(f"Dynamic sizing: {consec_losses} consecutive losses → {sizing_mult:.0%} size")

        # Check if we have enough balance (cap total margin at 60% of starting balance)
        starting = account.get("starting_balance", account["balance"])
        max_total_margin = starting * 0.60
        current_margin = sum(p.get("margin", 0) for p in account.get("positions", []) if p.get("status") == "open")
        if current_margin + sizing["margin_required"] > max_total_margin:
            return {"error": f"Margin cap: using ${current_margin:.0f}/${max_total_margin:.0f} (60% of ${starting:.0f})"}
        if sizing["margin_required"] > account["balance"]:
            return {"error": f"Insufficient balance. Need ${sizing['margin_required']:.2f}, have ${account['balance']:.2f}"}
        
        # Calculate liquidation price
        liq_price = calculate_liquidation_price(
            entry_price=entry_price,
            leverage=leverage,
            direction=direction,
            margin_type=margin_type
        )
        
        # ── LEVERAGE REDUCTION: stop must fit within liquidation distance ─────────
        # If stop_distance > 85% of liquidation distance, reduce leverage so the
        # liquidation is safely beyond the stop. This prevents the stop being
        # unreachable (price hits liq before SL fires) — the root cause of the
        # INJ/USDT liquidation chain (2026-03-22, -$4,207 across 5 accounts).
        _stop_dist_pct = abs(stop_loss - entry_price) / entry_price if entry_price and stop_loss else 0
        _mmr = 0.005  # maintenance margin rate used in liquidation calculation
        if _stop_dist_pct > 0:
            # Maximum safe leverage: lev = 1 / (stop_dist / 0.85 + mmr)
            # Ensures liq is at least 15% further than stop from entry.
            _max_safe_lev = int(1.0 / (_stop_dist_pct / 0.85 + _mmr))
            if leverage > _max_safe_lev:
                if _max_safe_lev >= 3:
                    _old_lev = leverage
                    leverage = _max_safe_lev
                    # Recompute liquidation price and sizing for new leverage
                    liq_price = calculate_liquidation_price(entry_price, leverage, direction, margin_type)
                    sizing = calculate_position_size(
                        balance=account["balance"],
                        risk_pct=risk_pct,
                        entry_price=entry_price,
                        stop_loss=stop_loss,
                        leverage=leverage
                    )
                    if sizing_mult < 1.0:
                        sizing["margin_required"] = round(sizing["margin_required"] * sizing_mult, 2)
                        sizing["position_size_usd"] = round(sizing["position_size_usd"] * sizing_mult, 2)
                    logger.warning(
                        f"LEVERAGE REDUCED: {symbol} {direction} — stop {_stop_dist_pct*100:.2f}% "
                        f"would exceed liq distance at {_old_lev}x. "
                        f"Leverage {_old_lev}x → {leverage}x (liq now {abs(liq_price-entry_price)/entry_price*100:.2f}% from entry)"
                    )
                else:
                    logger.warning(
                        f"REJECTED: {symbol} {direction} {leverage}x — stop {_stop_dist_pct*100:.2f}% "
                        f"exceeds liq at any safe leverage (max_safe={_max_safe_lev}x < 3x minimum)"
                    )
                    return {
                        "error": f"REJECTED: stop_loss ({_stop_dist_pct*100:.2f}%) too wide for safe leverage "
                                 f"— max safe leverage {_max_safe_lev}x"
                    }

        # ── SL / liq safety guard ──────────────────────────────────────────────
        # Ensure the stop loss is placed safely outside the liquidation zone.
        # For LONG: SL must be above liq_price. For SHORT: SL must be below liq_price.
        # If not, widen the SL to maintain at least a 0.5% buffer beyond liq.
        # This prevents the poll-gap problem where liq fires before SL.
        _sl_buffer = entry_price * 0.005   # 0.5% buffer
        if direction == "LONG":
            _min_sl = round(liq_price + _sl_buffer, 8)
            if stop_loss and stop_loss < _min_sl:
                logger.warning(
                    f"SL ${stop_loss} is inside liq zone (liq=${liq_price}) for {symbol} "
                    f"LONG {leverage}x — widening SL to ${_min_sl}"
                )
                stop_loss = _min_sl
        else:  # SHORT
            _max_sl = round(liq_price - _sl_buffer, 8)
            if stop_loss and stop_loss > _max_sl:
                logger.warning(
                    f"SL ${stop_loss} is inside liq zone (liq=${liq_price}) for {symbol} "
                    f"SHORT {leverage}x — widening SL to ${_max_sl}"
                )
                stop_loss = _max_sl

        # Apply entry slippage/fee (taker fee on open)
        # LONG pays slightly more, SHORT receives slightly less
        if direction == "LONG":
            effective_entry = round(entry_price * (1 + TRADE_FEE_PCT), 8)
        else:
            effective_entry = round(entry_price * (1 - TRADE_FEE_PCT), 8)

        # Calculate R:R ratio using effective entry
        risk = abs(effective_entry - stop_loss)
        reward = abs(take_profit - effective_entry)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0

        # ── Three-level partial TP targets ─────────────────────────────────────
        # tp1 = 1:1 R:R (close 33%), tp2 = 2:1 R:R (close 33%), tp3 = original TP
        risk_per_unit = abs(effective_entry - stop_loss)
        if direction == "LONG":
            tp1 = round(effective_entry + risk_per_unit * 1.0, 4)
            tp2 = round(effective_entry + risk_per_unit * 2.0, 4)
        else:
            tp1 = round(effective_entry - risk_per_unit * 1.0, 4)
            tp2 = round(effective_entry - risk_per_unit * 2.0, 4)
        tp3 = take_profit

        # Create position
        position = {
            "id": f"{symbol}_{datetime.now().timestamp()}",
            "symbol": symbol,
            "direction": direction,
            "entry_price": effective_entry,
            "current_price": effective_entry,
            "stop_loss": stop_loss,
            "original_stop_loss": stop_loss,
            "take_profit": take_profit,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,
            "tp1_hit": False,
            "tp2_hit": False,
            "trail_active": False,
            "trail_stop": None,
            "trail_pct": 1.5,
            "cumulative_partial_pnl": 0.0,
            "remaining_margin_pct": 1.0,
            "liquidation_price": liq_price,
            "leverage": leverage,
            "margin_type": margin_type,
            "margin": sizing["margin_required"],
            "initial_margin": sizing["margin_required"],
            "position_size_usd": sizing["position_size_usd"],
            "quantity": sizing["quantity"],
            "unrealized_pnl": 0.0,
            "unrealized_pnl_pct": 0.0,
            "rr_ratio": rr_ratio,
            "status": "open",
            "opened_at": datetime.now(timezone.utc),
            "signal_data": signal_data or {},
            "strategy": strategy
        }
        
        # Atomically deduct margin and add position only if:
        # 1. Balance is still sufficient, AND
        # 2. No open position already exists for this symbol (prevents race-condition duplicates)
        margin = sizing["margin_required"]
        result = await self.db.paper_accounts.update_one(
            {
                "_id": account_id,
                "balance": {"$gte": margin},
                "positions": {"$not": {"$elemMatch": {"symbol": symbol, "status": "open"}}}
            },
            {
                "$inc": {"balance": -margin},
                "$push": {"positions": position}
            }
        )
        if result.matched_count == 0:
            # Could be insufficient balance OR duplicate position
            account_fresh = await self.get_account(account_id)
            has_dup = any(p["symbol"] == symbol and p["status"] == "open"
                          for p in (account_fresh or {}).get("positions", []))
            if has_dup:
                return {"error": f"Already have open position for {symbol}"}
            return {"error": f"Insufficient balance (concurrent trade may have used it)"}
        new_balance = account["balance"] - margin
        
        # Store in trade history
        await self.db.paper_trades.insert_one({
            **position,
            "account_id": account_id,
            "account_name": account["name"]
        })
        
        logger.info(f"Opened {direction} on {symbol} @ ${entry_price} | Leverage: {leverage}x | Margin: ${sizing['margin_required']:.2f} | Liq: ${liq_price:.2f}")

        emoji = "🟢" if direction == "LONG" else "🔴"
        if ACCOUNTS.get(account_id, {}).get("notify_telegram"):
            asyncio.create_task(_notify(
                f"{emoji} Trade Opened · {symbol}\n\n"
                f"Account    {self._acc_label(account_id)}\n"
                f"Direction  {direction}  {leverage}x\n"
                f"Entry      ${effective_entry:,.2f}\n"
                f"Target     ${take_profit:,.2f}\n"
                f"Stop       ${stop_loss:,.2f}\n"
                f"Liq        ${liq_price:,.2f}\n"
                f"R:R        {rr_ratio}\n"
                f"Margin     ${sizing['margin_required']:,.0f}\n\n"
                f"{strategy} · {confidence}%"
            ))

        return {
            "success": True,
            "position": position,
            "account_balance": new_balance
        }
    
    def _apply_partial_close(self, pos: dict, close_pct: float, exit_price: float) -> dict:
        """
        Close `close_pct` fraction of position (e.g. 0.333).
        Mutates pos in-place. Returns partial close info dict.
        """
        partial_margin = pos["margin"] * close_pct
        partial_size = pos["position_size_usd"] * close_pct

        if pos["direction"] == "LONG":
            eff_exit = exit_price * (1 - TRADE_FEE_PCT)
            pnl_pct = ((eff_exit - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
        else:
            eff_exit = exit_price * (1 + TRADE_FEE_PCT)
            pnl_pct = ((pos["entry_price"] - eff_exit) / pos["entry_price"]) * 100 * pos["leverage"]

        partial_pnl = round(partial_margin * (pnl_pct / 100), 2)

        # Reduce remaining position
        pos["margin"] = round(pos["margin"] - partial_margin, 2)
        pos["position_size_usd"] = round(pos["position_size_usd"] - partial_size, 2)
        pos["quantity"] = round(pos.get("quantity", 0) * (1 - close_pct), 8)
        pos["cumulative_partial_pnl"] = round(pos.get("cumulative_partial_pnl", 0) + partial_pnl, 2)
        pos["remaining_margin_pct"] = round(pos.get("remaining_margin_pct", 1.0) - close_pct, 3)

        return {
            "partial_pnl": partial_pnl,
            "partial_margin": round(partial_margin, 2),
            "eff_exit": round(eff_exit, 8),
            "pnl_pct": round(pnl_pct, 2),
            "close_pct": close_pct,
        }

    async def update_position_price(self, account_id: str, symbol: str, current_price: float) -> Optional[Dict]:
        """Update position with current price and check for liquidation/TP/SL/partials/trailing"""

        account = await self.get_account(account_id)
        if not account:
            return None

        positions = account.get("positions", [])
        updated_positions = []
        closed_position = None
        partial_events = []  # list of (partial_pnl, partial_margin_returned, telegram_msg)

        acc_label = self._acc_label(account_id)
        _should_notify = ACCOUNTS.get(account_id, {}).get("notify_telegram", False)

        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                pos["current_price"] = current_price

                # Calculate unrealized PnL
                if pos["direction"] == "LONG":
                    pnl_pct = ((current_price - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
                else:
                    pnl_pct = ((pos["entry_price"] - current_price) / pos["entry_price"]) * 100 * pos["leverage"]

                pos["unrealized_pnl_pct"] = round(pnl_pct, 2)
                pos["unrealized_pnl"] = round(pos["margin"] * (pnl_pct / 100), 2)

                direction = pos["direction"]
                entry_p = pos["entry_price"]
                lev = pos["leverage"]
                sym = pos["symbol"]

                # ── 1. STOP LOSS CHECK ─────────────────────────────────────────
                # SL is checked FIRST. In paper trading the price poll is every
                # 30s — price can gap through the SL and reach liq in one interval.
                # The correct behaviour is to honour the SL price (as an exchange
                # would fill a stop market order) rather than marking the trade as
                # a liquidation just because the polled price is at or below liq.
                if direction == "LONG" and current_price <= pos["stop_loss"]:
                    eff_exit = pos["stop_loss"] * (1 - TRADE_FEE_PCT)
                    sl_pnl_pct = ((eff_exit - entry_p) / entry_p) * 100 * lev
                    pos["status"] = "stopped"
                    pos["exit_price"] = round(eff_exit, 8)
                    pos["realized_pnl"] = round(pos["margin"] * (sl_pnl_pct / 100) + pos.get("cumulative_partial_pnl", 0), 2)
                    pos["closed_at"] = datetime.now(timezone.utc)
                    pos["close_reason"] = "stop_loss"
                    closed_position = pos

                elif direction == "SHORT" and current_price >= pos["stop_loss"]:
                    eff_exit = pos["stop_loss"] * (1 + TRADE_FEE_PCT)
                    sl_pnl_pct = ((entry_p - eff_exit) / entry_p) * 100 * lev
                    pos["status"] = "stopped"
                    pos["exit_price"] = round(eff_exit, 8)
                    pos["realized_pnl"] = round(pos["margin"] * (sl_pnl_pct / 100) + pos.get("cumulative_partial_pnl", 0), 2)
                    pos["closed_at"] = datetime.now(timezone.utc)
                    pos["close_reason"] = "stop_loss"
                    closed_position = pos

                # ── 2. LIQUIDATION CHECK ───────────────────────────────────────
                # Only reached if stop loss did NOT fire — true liquidation
                # (no SL set, or SL is below liq for LONG / above liq for SHORT)
                elif direction == "LONG" and current_price <= pos["liquidation_price"]:
                    pos["status"] = "liquidated"
                    pos["exit_price"] = pos["liquidation_price"]
                    pos["realized_pnl"] = round(-pos["margin"] + pos.get("cumulative_partial_pnl", 0), 2)
                    pos["closed_at"] = datetime.now(timezone.utc)
                    pos["close_reason"] = "liquidation"
                    closed_position = pos
                    logger.warning(f"LIQUIDATED: {sym} LONG @ ${pos['liquidation_price']}")

                elif direction == "SHORT" and current_price >= pos["liquidation_price"]:
                    pos["status"] = "liquidated"
                    pos["exit_price"] = pos["liquidation_price"]
                    pos["realized_pnl"] = round(-pos["margin"] + pos.get("cumulative_partial_pnl", 0), 2)
                    pos["closed_at"] = datetime.now(timezone.utc)
                    pos["close_reason"] = "liquidation"
                    closed_position = pos
                    logger.warning(f"LIQUIDATED: {sym} SHORT @ ${pos['liquidation_price']}")

                # ── 3. TRAILING STOP CHECK ─────────────────────────────────────
                elif pos.get("trail_active") and pos.get("trail_stop"):
                    trail_stop = pos["trail_stop"]
                    trail_pct = pos.get("trail_pct", 1.5)
                    trail_hit = False

                    if direction == "LONG":
                        # Update trail upward
                        new_trail = current_price * (1 - trail_pct / 100)
                        if new_trail > trail_stop:
                            pos["trail_stop"] = round(new_trail, 4)
                        # Check if hit
                        if current_price <= trail_stop:
                            trail_hit = True
                    else:  # SHORT
                        # Update trail downward
                        new_trail = current_price * (1 + trail_pct / 100)
                        if new_trail < trail_stop:
                            pos["trail_stop"] = round(new_trail, 4)
                        if current_price >= trail_stop:
                            trail_hit = True

                    if trail_hit:
                        if direction == "LONG":
                            eff_exit = trail_stop * (1 - TRADE_FEE_PCT)
                            final_pnl_pct = ((eff_exit - entry_p) / entry_p) * 100 * lev
                        else:
                            eff_exit = trail_stop * (1 + TRADE_FEE_PCT)
                            final_pnl_pct = ((entry_p - eff_exit) / entry_p) * 100 * lev
                        partial_cumulative = pos.get("cumulative_partial_pnl", 0)
                        remaining_pnl = round(pos["margin"] * (final_pnl_pct / 100), 2)
                        total_pnl = round(remaining_pnl + partial_cumulative, 2)
                        pos["status"] = "profit"
                        pos["exit_price"] = round(eff_exit, 8)
                        pos["realized_pnl"] = total_pnl
                        pos["closed_at"] = datetime.now(timezone.utc)
                        pos["close_reason"] = "trailing_stop"
                        closed_position = pos
                        logger.info(f"TRAILING STOP: {sym} {direction} @ ${eff_exit:.4f} | Total PnL ${total_pnl:.2f}")

                else:
                    # ── 4. TP1: 1:1 R:R — close 33%, move SL to +25% risk lock-in ─
                    tp1 = pos.get("tp1")
                    if tp1 and not pos.get("tp1_hit"):
                        tp1_hit = (direction == "LONG" and current_price >= tp1) or \
                                  (direction == "SHORT" and current_price <= tp1)
                        if tp1_hit:
                            info = self._apply_partial_close(pos, 0.333, current_price)
                            pos["tp1_hit"] = True
                            # Lock in 25% of original risk as guaranteed profit
                            # (not exact break-even — gives remaining 67% room to breathe)
                            orig_sl = pos.get("original_stop_loss", entry_p)
                            original_risk = abs(entry_p - orig_sl)
                            if direction == "LONG":
                                new_sl = round(entry_p + 0.25 * original_risk, 8)
                            else:
                                new_sl = round(entry_p - 0.25 * original_risk, 8)
                            pos["stop_loss"] = new_sl
                            tg_msg = (
                                f"TP1 Hit · {sym} {direction}\n\n"
                                f"+${info['partial_pnl']:,.0f} locked\n"
                                f"SL → ${new_sl:,.4f} (+25% risk) · 67% still riding"
                                if _should_notify else None
                            )
                            partial_events.append((
                                info["partial_pnl"],
                                info["partial_margin"],
                                tg_msg,
                            ))
                            logger.info(f"TP1 HIT: {sym} {direction} | Partial PnL ${info['partial_pnl']:.2f} | SL → ${new_sl:.4f} (25% risk locked)")

                    # ── 4b. 2R trailing mechanism — activates when profit > 2x risk ─
                    if pos.get("tp1_hit") and not pos.get("tp2_hit") and not pos.get("trail_active"):
                        orig_sl = pos.get("original_stop_loss", entry_p)
                        original_risk = abs(entry_p - orig_sl)
                        if original_risk > 0:
                            if direction == "LONG":
                                unrealized_profit = current_price - entry_p
                                if unrealized_profit > 2 * original_risk:
                                    trail_sl = round(current_price - 0.75 * original_risk, 8)
                                    if trail_sl > pos["stop_loss"]:
                                        pos["stop_loss"] = trail_sl
                                        logger.debug(f"2R TRAIL [{sym}]: SL ratcheted to ${trail_sl:.4f}")
                            else:
                                unrealized_profit = entry_p - current_price
                                if unrealized_profit > 2 * original_risk:
                                    trail_sl = round(current_price + 0.75 * original_risk, 8)
                                    if trail_sl < pos["stop_loss"]:
                                        pos["stop_loss"] = trail_sl
                                        logger.debug(f"2R TRAIL [{sym}]: SL ratcheted to ${trail_sl:.4f}")

                    # ── 4c. Auto-activate trailing stop when profit ≥ 1× original risk ─
                    # Ensures winning trades are protected even if TP2 is never reached.
                    if not pos.get("trail_active"):
                        _orig_sl_at = pos.get("original_stop_loss", entry_p)
                        _orig_risk = abs(entry_p - _orig_sl_at)
                        if _orig_risk > 0:
                            _unrealized = (current_price - entry_p) if direction == "LONG" else (entry_p - current_price)
                            if _unrealized >= _orig_risk:
                                _trail_pct = pos.get("trail_pct", 1.5)
                                pos["trail_active"] = True
                                if direction == "LONG":
                                    pos["trail_stop"] = round(current_price * (1 - _trail_pct / 100), 4)
                                else:
                                    pos["trail_stop"] = round(current_price * (1 + _trail_pct / 100), 4)
                                logger.info(
                                    f"TRAIL AUTO-ACTIVATED: {sym} {direction} | "
                                    f"profit={_unrealized:.2f} ≥ 1×risk={_orig_risk:.2f} | "
                                    f"trail_stop={pos['trail_stop']:.4f}"
                                )

                    # ── 5. TP2: 2:1 R:R — close another 33%, activate trailing ─
                    tp2 = pos.get("tp2")
                    if tp2 and pos.get("tp1_hit") and not pos.get("tp2_hit"):
                        tp2_hit = (direction == "LONG" and current_price >= tp2) or \
                                  (direction == "SHORT" and current_price <= tp2)
                        if tp2_hit:
                            info = self._apply_partial_close(pos, 0.50, current_price)  # 50% of remaining = ~33% of original
                            pos["tp2_hit"] = True
                            pos["trail_active"] = True
                            trail_pct = pos.get("trail_pct", 1.5)
                            if direction == "LONG":
                                pos["trail_stop"] = round(current_price * (1 - trail_pct / 100), 4)
                            else:
                                pos["trail_stop"] = round(current_price * (1 + trail_pct / 100), 4)
                            tg_msg = (
                                f"TP2 Hit · {sym} {direction}\n\n"
                                f"+${info['partial_pnl']:,.0f} locked\n"
                                f"Trail stop ${pos['trail_stop']:,.2f} · 34% still riding"
                                if _should_notify else None
                            )
                            partial_events.append((
                                info["partial_pnl"],
                                info["partial_margin"],
                                tg_msg,
                            ))
                            logger.info(f"TP2 HIT: {sym} {direction} | Partial PnL ${info['partial_pnl']:.2f} | Trail activated")

                    # ── 6. TP3: Full close of remaining portion ────────────────
                    tp3 = pos.get("tp3") or pos.get("take_profit")
                    if tp3:
                        tp3_hit = (direction == "LONG" and current_price >= tp3) or \
                                  (direction == "SHORT" and current_price <= tp3)
                        if tp3_hit:
                            if direction == "LONG":
                                eff_exit = tp3 * (1 - TRADE_FEE_PCT)
                                final_pnl_pct = ((eff_exit - entry_p) / entry_p) * 100 * lev
                            else:
                                eff_exit = tp3 * (1 + TRADE_FEE_PCT)
                                final_pnl_pct = ((entry_p - eff_exit) / entry_p) * 100 * lev
                            partial_cumulative = pos.get("cumulative_partial_pnl", 0)
                            remaining_pnl = round(pos["margin"] * (final_pnl_pct / 100), 2)
                            total_pnl = round(remaining_pnl + partial_cumulative, 2)
                            pos["status"] = "profit"
                            pos["exit_price"] = round(eff_exit, 8)
                            pos["realized_pnl"] = total_pnl
                            pos["closed_at"] = datetime.now(timezone.utc)
                            pos["close_reason"] = "take_profit"
                            closed_position = pos

            updated_positions.append(pos)

        # ── Handle partial close events (TP1/TP2) ─────────────────────────────
        if partial_events and not closed_position:
            total_partial_pnl = sum(e[0] for e in partial_events)
            total_partial_margin = sum(e[1] for e in partial_events)
            # Return partial margin + PnL to balance, update positions
            await self.db.paper_accounts.update_one(
                {"_id": account_id},
                {
                    "$inc": {"balance": total_partial_margin + total_partial_pnl},
                    "$set": {"positions": updated_positions},
                }
            )
            # Record partial close events
            for pnl_amt, margin_amt, tg_msg in partial_events:
                if tg_msg:
                    asyncio.create_task(_notify(tg_msg))
                try:
                    await self.db.paper_trades.insert_one({
                        "type": "partial_close",
                        "account_id": account_id,
                        "symbol": symbol,
                        "partial_pnl": pnl_amt,
                        "partial_margin_returned": margin_amt,
                        "timestamp": datetime.now(timezone.utc),
                    })
                except Exception:
                    pass
            return None  # Position still open

        # ── Handle full position close ─────────────────────────────────────────
        if closed_position:
            open_positions = [p for p in updated_positions if p["status"] == "open"]

            pnl = closed_position.get("realized_pnl", 0)
            margin_return = closed_position["margin"] + pnl
            new_balance = account["balance"] + max(0, margin_return)

            is_win = pnl > 0

            # Update consecutive losses and circuit breaker
            new_peak = max(account.get("peak_balance", 0), new_balance)
            drawdown_pct = (new_peak - new_balance) / new_peak * 100 if new_peak > 0 else 0

            extra_set = {"peak_balance": new_peak}
            extra_inc = {"consecutive_losses": 0 if is_win else 1}

            if not is_win:
                new_consec = account.get("consecutive_losses", 0) + 1
                if new_consec >= 3:
                    logger.info(f"Dynamic sizing engaged for {account_id}: {new_consec} consecutive losses")

            # Circuit breaker: halt if drawdown > 20% from peak
            if drawdown_pct > 20 and not account.get("circuit_breaker_active"):
                extra_set["circuit_breaker_active"] = True
                extra_set["circuit_breaker_until"] = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
                if _should_notify:
                    asyncio.create_task(_notify(
                        f"Warning · Circuit Breaker Active\n\n"
                        f"{drawdown_pct:.0f}% drawdown from peak. Trading paused 24 hours.\n"
                        f"Action: All new positions blocked. Balance ${new_balance:,.0f}"
                    ))

            if is_win:
                extra_set["consecutive_losses"] = 0
                extra_inc = {}

            await self.db.paper_accounts.update_one(
                {"_id": account_id},
                {
                    "$set": {
                        "balance": new_balance,
                        "positions": open_positions,
                        **extra_set,
                    },
                    "$inc": {
                        "total_pnl": pnl,
                        "total_trades": 1,
                        "wins": 1 if is_win else 0,
                        "losses": 0 if is_win else 1,
                        **extra_inc,
                    }
                }
            )

            # Check for auto-reload
            starting = ACCOUNTS.get(account_id, {}).get("starting_balance", 1000)
            min_balance = starting * 0.05
            if new_balance < min_balance:
                logger.warning(f"⚠️ {account_id} balance ${new_balance:.2f} below threshold ${min_balance:.2f} - AUTO RELOADING!")
                await self.reload_account(account_id)
                if self.db is not None:
                    await self.db.paper_events.insert_one({
                        "type": "auto_reload",
                        "account_id": account_id,
                        "old_balance": new_balance,
                        "new_balance": starting,
                        "reason": "balance_below_threshold",
                        "timestamp": datetime.now(timezone.utc)
                    })

            # Store closed trade
            closed_position["account_id"] = account_id
            closed_position["status"] = "closed"
            # close_price mirrors exit_price for consistent analytics (RR calculation)
            if "exit_price" in closed_position and "close_price" not in closed_position:
                closed_position["close_price"] = closed_position["exit_price"]
            await self.db.paper_trades.update_one(
                {"id": closed_position.get("id")},
                {"$set": closed_position},
                upsert=True
            )
            logger.info(f"📚 Stored closed trade {closed_position.get('symbol')} for learning engine")

            # Telegram close notification — check per-account setting
            if _should_notify:
                reason = closed_position.get("close_reason", "closed")
                exit_p = closed_position.get("exit_price", 0)
                strat = closed_position.get("strategy", "unknown")
                initial_margin = closed_position.get("initial_margin", closed_position.get("margin", 0))
                pnl_pct = (pnl / initial_margin * 100) if initial_margin > 0 else 0
                lev = closed_position.get("leverage", 1)
                direction = closed_position.get("direction", "")
                entry_p_disp = closed_position.get("entry_price", 0)
                pnl_sign = "+" if pnl >= 0 else ""
                if reason == "liquidation":
                    msg = (
                        f"Trade Closed · {symbol}\n\n"
                        f"Direction   {direction}  {lev}x\n"
                        f"Result      Liquidated\n"
                        f"Loss        ${abs(pnl):,.0f}\n"
                        f"Balance     ${new_balance:,.0f}\n\n"
                        f"{strat}"
                    )
                elif reason == "take_profit":
                    partials = " +TP1+TP2" if closed_position.get("tp2_hit") else (" +TP1" if closed_position.get("tp1_hit") else "")
                    msg = (
                        f"Trade Closed · {symbol}\n\n"
                        f"Direction   {direction}  {lev}x{partials}\n"
                        f"Result      Win   {pnl_sign}{pnl_pct:.0f}%\n"
                        f"PnL         {pnl_sign}${pnl:,.0f}\n"
                        f"Balance     ${new_balance:,.0f}\n\n"
                        f"{strat}"
                    )
                elif reason == "stop_loss":
                    be = " (break-even)" if closed_position.get("tp1_hit") else ""
                    msg = (
                        f"Trade Closed · {symbol}\n\n"
                        f"Direction   {direction}  {lev}x\n"
                        f"Result      Stop Loss{be}   {pnl_sign}{pnl_pct:.0f}%\n"
                        f"PnL         ${pnl:,.0f}\n"
                        f"Balance     ${new_balance:,.0f}\n\n"
                        f"{strat}"
                    )
                elif reason == "trailing_stop":
                    msg = (
                        f"Trade Closed · {symbol}\n\n"
                        f"Direction   {direction}  {lev}x\n"
                        f"Result      Trail Stop   {pnl_sign}{pnl_pct:.0f}%\n"
                        f"PnL         {pnl_sign}${pnl:,.0f}\n"
                        f"Balance     ${new_balance:,.0f}\n\n"
                        f"{strat}"
                    )
                else:
                    msg = None
                if msg:
                    asyncio.create_task(_notify(msg))

        else:
            # Just update positions (trail stop moved, etc.)
            await self.db.paper_accounts.update_one(
                {"_id": account_id},
                {"$set": {"positions": updated_positions}}
            )

        return closed_position
    
    async def add_margin(self, account_id: str, symbol: str, amount: float) -> Dict:
        """Add margin to an existing position"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        if amount > account["balance"]:
            return {"error": f"Insufficient balance. Have ${account['balance']:.2f}"}
        
        positions = account.get("positions", [])
        position_found = False
        
        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                position_found = True
                
                # Add margin
                pos["margin"] += amount
                
                # Recalculate liquidation price with new margin
                # More margin = further liquidation price
                effective_leverage = pos["position_size_usd"] / pos["margin"]
                pos["liquidation_price"] = calculate_liquidation_price(
                    entry_price=pos["entry_price"],
                    leverage=int(effective_leverage),
                    direction=pos["direction"],
                    margin_type=pos["margin_type"]
                )
                
                break
        
        if not position_found:
            return {"error": f"No open position for {symbol}"}
        
        # Update account
        new_balance = account["balance"] - amount
        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balance": new_balance,
                    "positions": positions
                }
            }
        )
        
        return {
            "success": True,
            "added_margin": amount,
            "new_balance": new_balance,
            "new_liq_price": pos["liquidation_price"]
        }
    
    async def close_position(self, account_id: str, symbol: str, exit_price: float) -> Dict:
        """Manually close a position"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        positions = account.get("positions", [])
        closed_pos = None
        open_positions = []
        
        for pos in positions:
            if pos["symbol"] == symbol and pos["status"] == "open":
                # Apply exit slippage/fee (taker fee on close)
                if pos["direction"] == "LONG":
                    effective_exit = exit_price * (1 - TRADE_FEE_PCT)
                    pnl_pct = ((effective_exit - pos["entry_price"]) / pos["entry_price"]) * 100 * pos["leverage"]
                else:
                    effective_exit = exit_price * (1 + TRADE_FEE_PCT)
                    pnl_pct = ((pos["entry_price"] - effective_exit) / pos["entry_price"]) * 100 * pos["leverage"]

                pos["status"] = "closed"
                pos["exit_price"] = round(effective_exit, 8)
                pos["realized_pnl"] = round(pos["margin"] * (pnl_pct / 100), 2)
                pos["closed_at"] = datetime.now(timezone.utc)
                closed_pos = pos
            else:
                if pos["status"] == "open":
                    open_positions.append(pos)
        
        if not closed_pos:
            return {"error": f"No open position for {symbol}"}
        
        pnl = closed_pos["realized_pnl"]
        margin_return = max(0, closed_pos["margin"] + pnl)
        is_win = pnl > 0

        # Use $inc for balance (atomic) and $pull to remove the closed position
        await self.db.paper_accounts.update_one(
            {"_id": account_id, "positions.id": closed_pos["id"]},
            {
                "$inc": {
                    "balance": margin_return,
                    "total_pnl": pnl,
                    "total_trades": 1,
                    "wins": 1 if is_win else 0,
                    "losses": 0 if is_win else 1
                },
                "$pull": {"positions": {"id": closed_pos["id"]}}
            }
        )

        # Persist close event to trade history
        await self.db.paper_trades.update_one(
            {"id": closed_pos["id"]},
            {"$set": {
                "status": "closed",
                "exit_price": exit_price,
                "close_price": exit_price,
                "realized_pnl": pnl,
                "closed_at": closed_pos["closed_at"]
            }}
        )

        new_balance = account["balance"] + margin_return

        # Telegram manual-close notification
        pnl_pct = (pnl / closed_pos["margin"] * 100) if closed_pos.get("margin", 0) > 0 else 0
        acc_label = ACCOUNTS.get(account_id, {}).get("name", account_id)
        pnl_sign = "+" if pnl >= 0 else ""
        pnl_emoji = "✅" if pnl >= 0 else "❌"
        asyncio.create_task(_notify(
            f"Trade Closed · {symbol}\n\n"
            f"Direction  {closed_pos.get('direction', '')}\n"
            f"Result     {'Win' if pnl >= 0 else 'Loss'}   {pnl_sign}{pnl_pct:.0f}%\n"
            f"PnL        {pnl_sign}${pnl:,.0f}\n"
            f"Balance    ${new_balance:,.0f}\n\n"
            f"{acc_label} account"
        ))

        return {
            "success": True,
            "position": closed_pos,
            "pnl": pnl,
            "new_balance": new_balance
        }

    async def reload_account(self, account_id: str) -> Dict:
        """Reload account to starting balance (capped at MAX_MONTHLY_RELOADS per month)"""

        config = ACCOUNTS.get(account_id)
        if not config:
            return {"error": "Account not found"}

        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}

        # Enforce monthly reload cap
        current_month = datetime.now(timezone.utc).strftime("%Y-%m")
        stored_month = account.get("reload_month", "")
        monthly_reloads = account.get("monthly_reloads", 0) if stored_month == current_month else 0

        if monthly_reloads >= MAX_MONTHLY_RELOADS:
            logger.warning(
                f"🚫 {account_id} reload BLOCKED — {monthly_reloads}/{MAX_MONTHLY_RELOADS} "
                f"reloads used this month ({current_month})"
            )
            return {
                "error": f"Monthly reload cap reached ({MAX_MONTHLY_RELOADS}/month). "
                         f"Capital discipline enforced — wait until next month.",
                "monthly_reloads": monthly_reloads,
                "cap": MAX_MONTHLY_RELOADS
            }

        # Reset counter if new month, then increment
        if stored_month != current_month:
            monthly_reloads = 0

        await self.db.paper_accounts.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "balance": config["starting_balance"],
                    "available_balance": config["starting_balance"],
                    "positions": [],
                    "monthly_reloads": monthly_reloads + 1,
                    "reload_month": current_month,
                    # Reset session stats so UI shows fresh state after reload
                    "wins": 0,
                    "losses": 0,
                    "total_trades": 0,
                    "total_pnl": 0.0,
                    "daily_pnl": 0.0,
                    "unrealized_pnl": 0.0,
                    "margin_used": 0.0,
                    "open_positions": 0,
                },
                "$inc": {"reloads": 1}
            }
        )

        logger.info(
            f"Reloaded {account_id} to ${config['starting_balance']} "
            f"({monthly_reloads + 1}/{MAX_MONTHLY_RELOADS} reloads this month)"
        )

        return {
            "success": True,
            "account": account_id,
            "new_balance": config["starting_balance"],
            "monthly_reloads": monthly_reloads + 1,
            "cap": MAX_MONTHLY_RELOADS
        }
    
    async def get_account_summary(self, account_id: str) -> Dict:
        """Get detailed account summary"""
        
        account = await self.get_account(account_id)
        if not account:
            return {"error": "Account not found"}
        
        config = ACCOUNTS.get(account_id, {})
        positions = account.get("positions", [])
        open_positions = [p for p in positions if p["status"] == "open"]
        
        # Calculate total unrealized PnL
        total_unrealized = sum(p.get("unrealized_pnl", 0) for p in open_positions)
        total_margin_used = sum(p.get("margin", 0) for p in open_positions)
        
        # Win rate
        total_trades = account.get("total_trades", 0)
        wins = account.get("wins", 0)
        win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
        
        return {
            "account_id": account_id,
            "name": account.get("name"),
            "emoji": config.get("emoji", "💰"),
            "balance": account.get("balance", 0),
            "starting_balance": account.get("starting_balance", 0),
            "available_balance": account.get("balance", 0),  # balance already has margin deducted on open
            "total_pnl": account.get("total_pnl", 0),
            "unrealized_pnl": total_unrealized,
            "margin_used": total_margin_used,
            "open_positions": len(open_positions),
            "total_trades": total_trades,
            "wins": wins,
            "losses": account.get("losses", 0),
            "win_rate": round(win_rate, 1),
            "reloads": account.get("reloads", 0),
            "positions": open_positions
        }
    
    async def route_signal_to_accounts(
        self,
        signal: Dict,
        engine_name: str = "unknown"
    ) -> List[Dict]:
        """
        Route a trading signal to ALL paper accounts.

        Flow (Phase 2):
          1. Build TradeCandidate from signal + StressMonitor state
          2. Pre-fetch all accounts; RiskPolicy evaluates per-account decisions
             — approved_leverage is capped to account profile max_leverage
          3. For each account: check policy decision, then existing dedup/conflict
             — all skip reasons recorded with outcome_type in results
          4. open_position called with enforced leverage; executed_size_multiplier
             computed from actual filled margin vs full-risk sizing
          5. Fire-and-forget TradeJournal log with full candidate + results

        Risk % per account is determined by ACCOUNTS config + quantum state multiplier.
        Existing dedup/conflict logic is authoritative and runs after RiskPolicy.
        """
        results = []

        symbol = signal.get("symbol")
        direction = signal.get("direction")
        entry_price = signal.get("entry_price")
        stop_loss = signal.get("stop_loss")
        take_profit = signal.get("take_profit")
        confidence = signal.get("confidence", 80)
        signal_risk_pct = signal.get("risk_pct", 2.0)

        if not all([symbol, direction, entry_price, stop_loss, take_profit]):
            logger.warning(f"Invalid signal from {engine_name}: missing required fields")
            return results

        # ── Phase 1: Build TradeCandidate ─────────────────────────────────────
        try:
            from candidate_trade import TradeCandidate
            from oria_layer import get_stress_monitor
            import app_state as _state

            stress_level = 0.0
            stress_multiplier = 1.0
            _sm = get_stress_monitor()
            if _sm is not None:
                stress_level = float(_sm.stress_score)
                stress_multiplier, _ = _sm.get_size_multiplier()

            candidate = TradeCandidate(
                symbol=symbol,
                direction=str(direction).upper(),
                engine=engine_name,
                confidence=float(confidence),
                confluences=int(signal.get("confirmations_count", 0)),
                requested_leverage=int(signal.get("leverage", 10)),
                entry_price=float(entry_price),
                stop_loss=float(stop_loss),
                take_profit=float(take_profit),
                strategy=signal.get("strategy", engine_name),
                stress_level=stress_level,
                stress_multiplier=stress_multiplier,
                gate_passed=True,
            )

            # Pre-fetch all accounts for RiskPolicy evaluation
            _all_accounts = {}
            for _aid in ACCOUNTS:
                _acc = await self.get_account(_aid)
                if _acc:
                    _all_accounts[_aid] = {**_acc, "_config": ACCOUNTS[_aid]}

            # Evaluate RiskPolicy if wired up (advisory mode in Phase 1)
            _policy_decisions = {}
            if hasattr(_state, "risk_policy") and _state.risk_policy is not None:
                try:
                    _policy_decisions = _state.risk_policy.evaluate(
                        candidate, _all_accounts, stress_level, stress_multiplier
                    )
                    candidate.account_decisions = _policy_decisions
                except Exception as _pe:
                    logger.warning(f"[route_signal] RiskPolicy.evaluate error: {_pe}")

        except Exception as _ce:
            candidate = None
            _policy_decisions = {}
            logger.warning(f"[route_signal] TradeCandidate build error: {_ce}")

        _today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        for acc_id, config in ACCOUNTS.items():
            account = await self.get_account(acc_id)
            if not account:
                continue

            # ── Phase 2: RiskPolicy hard gate (REJECT → skip, advisory → proceed) ──
            _decision = _policy_decisions.get(acc_id)
            if _decision and _decision.verdict == "REJECT":
                logger.info(
                    f"[RiskPolicy] {acc_id} REJECTED {symbol} {direction}: "
                    + "; ".join(_decision.rejection_reasons)
                )
                results.append({
                    "account": acc_id,
                    "success": False,
                    "outcome_type": "policy_reject",
                    "reasons": _decision.rejection_reasons,
                })
                continue

            # Skip if already have this symbol open (same direction)
            if any(p["symbol"] == symbol and p["status"] == "open" for p in account.get("positions", [])):
                logger.info(f"[{acc_id}] Already have {symbol} open — skipping")
                results.append({"account": acc_id, "success": False, "outcome_type": "same_symbol_skip"})
                continue

            # ── FIX #12: Signal conflict resolution (opposite direction check) ─
            _opposite_dir = "SHORT" if direction == "LONG" else "LONG"
            _conflict = await self.db.paper_trades.find_one({
                "account_id": acc_id,
                "symbol": symbol,
                "status": "open",
                "direction": _opposite_dir,
            })
            if _conflict:
                logger.info(
                    f"CONFLICT BLOCKED: {symbol} {direction} on {acc_id} "
                    f"— opposite {_opposite_dir} already open (engine: {_conflict.get('engine', 'unknown')})"
                )
                results.append({
                    "account": acc_id,
                    "success": False,
                    "outcome_type": "conflict_skip",
                    "conflicting_engine": _conflict.get("engine", "unknown"),
                })
                continue

            # ── FIX #3: Deduplication lock (10-second window) ────────────────
            _dedup_since = datetime.now(timezone.utc) - timedelta(seconds=10)
            _dup = await self.db.paper_trades.find_one({
                "account_id": acc_id,
                "symbol": symbol,
                "direction": direction,
                "opened_at": {"$gte": _dedup_since}
            })
            if _dup:
                logger.info(
                    f"DEDUP BLOCKED: {symbol} {direction} on {acc_id} "
                    f"— duplicate within 10s window"
                )
                results.append({"account": acc_id, "success": False, "outcome_type": "dedup_skip"})
                continue

            # ── FIX #4: Daily trade cap ───────────────────────────────────────
            _today_count = await self.db.paper_trades.count_documents({
                "account_id": acc_id,
                "opened_at": {"$gte": _today_start}
            })
            _daily_cap = config.get("daily_trade_cap", 8)
            if _today_count >= _daily_cap:
                logger.info(
                    f"DAILY CAP: {acc_id} at {_today_count}/{_daily_cap} trades today "
                    f"— {symbol} {direction} signal skipped"
                )
                results.append({
                    "account": acc_id,
                    "success": False,
                    "outcome_type": "daily_cap_skip",
                    "count": _today_count,
                    "cap": _daily_cap,
                })
                continue

            # Compute risk % for this account
            base_risk = config.get("base_risk_pct", 2.0)
            if config.get("use_quantum_sizing"):
                q_mult = self._get_quantum_multiplier(acc_id)
                adj_risk = base_risk * q_mult
            else:
                if acc_id == "PRO":
                    adj_risk = min(signal_risk_pct * 1.5, 5.0)
                else:
                    adj_risk = base_risk

            # Phase 2: use approved_leverage from RiskPolicy (capped per account profile)
            # Falls back to signal leverage if no decision available.
            _enforced_leverage = (
                _decision.approved_leverage
                if _decision is not None and _decision.approved_leverage > 0
                else int(signal.get("leverage", 10))
            )

            result = await self.open_position(
                account_id=acc_id,
                symbol=symbol,
                direction=direction,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                leverage=_enforced_leverage,
                margin_type="cross",
                risk_pct=adj_risk,
                confidence=confidence,
                strategy=engine_name,
                signal_data={
                    "engine": engine_name,
                    "confidence": confidence,
                    "confirmations": signal.get("confirmations", []),
                    "timeframe": signal.get("timeframe", "4h"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "unified_trade_id": signal.get("unified_trade_id"),
                }
            )

            if "error" not in result:
                pos = result.get("position", {})
                logger.info(f"📊 [{acc_id}] {direction} {symbol} @ ${entry_price:,.2f} | "
                            f"{pos.get('leverage')}x | Margin ${pos.get('margin', 0):,.2f} | Engine {engine_name}")

                # Phase 2: compute true executed_size_multiplier from actual filled margin
                _actual_margin = float(pos.get("margin") or 0.0)
                _exec_size_mult = _decision.approved_size_multiplier if _decision else 1.0
                if _actual_margin > 0:
                    try:
                        _full_sz = calculate_position_size(
                            balance=account["balance"],
                            risk_pct=adj_risk,
                            entry_price=float(entry_price),
                            stop_loss=float(stop_loss),
                            leverage=int(pos.get("leverage") or _enforced_leverage),
                        )
                        _full_margin = float(_full_sz.get("margin_required") or 0.0)
                        if _full_margin > 0:
                            _exec_size_mult = round(_actual_margin / _full_margin, 4)
                    except Exception:
                        pass

                if _decision is not None:
                    _decision.executed_leverage = pos.get("leverage")
                    _decision.executed_size_multiplier = _exec_size_mult

                results.append({
                    "account": acc_id,
                    "success": True,
                    "outcome_type": "opened",
                    "position": pos,
                })
            else:
                logger.warning(f"[{acc_id}] Failed {symbol}: {result['error']}")
                results.append({
                    "account": acc_id,
                    "success": False,
                    "outcome_type": "open_failed",
                    "error": result["error"],
                })

        # ── Phase 1: Journal log (fire-and-forget, never blocks routing) ─────
        try:
            import app_state as _state
            if candidate is not None and hasattr(_state, "trade_journal") and _state.trade_journal is not None:
                candidate.routed_at = datetime.now(timezone.utc)
                candidate.route_results = results
                _state.trade_journal.log(candidate)
        except Exception as _je:
            logger.debug(f"[route_signal] TradeJournal log error: {_je}")

        return results
    
    async def update_all_positions(self, price_data: Dict[str, float]) -> List[Dict]:
        """
        Update all positions across all accounts with current prices
        Returns list of any closed positions (liquidated, stopped, profit)
        """
        closed = []
        
        for acc_id in ACCOUNTS:
            account = await self.get_account(acc_id)
            if not account:
                continue

            for pos in account.get("positions", []):
                if pos["status"] != "open":
                    continue
                
                symbol = pos["symbol"]
                if symbol in price_data:
                    result = await self.update_position_price(acc_id, symbol, price_data[symbol])
                    if result:  # Position was closed
                        closed.append({
                            "account": acc_id,
                            "position": result
                        })
        
        return closed
    
    async def check_account_health(self) -> Dict:
        """
        Periodic health check - auto-reload accounts that are critically low
        Returns status of all accounts
        """
        status = {"reloaded": [], "healthy": [], "low_balance": []}
        
        for acc_id, config in ACCOUNTS.items():
            account = await self.get_account(acc_id)
            if not account:
                continue

            balance = account.get("balance", 0)
            starting = config.get("starting_balance", 1000)
            auto_reload = acc_id in ("PRO", "STARTER")

            # Check if critically low (< 5% of starting) — only auto-reload simulation accounts
            if auto_reload and balance < starting * 0.05:
                logger.warning(f"🔄 Auto-reloading {acc_id} - Balance: ${balance:.2f}")
                await self.reload_account(acc_id)
                status["reloaded"].append({
                    "account_id": acc_id,
                    "old_balance": balance,
                    "new_balance": starting
                })
            elif balance < starting * 0.20:
                status["low_balance"].append({
                    "account_id": acc_id,
                    "balance": balance,
                    "pct_remaining": round((balance / starting) * 100, 1)
                })
            else:
                status["healthy"].append({
                    "account_id": acc_id,
                    "balance": balance,
                    "pct_remaining": round((balance / starting) * 100, 1)
                })
        
        return status


# Global instance
paper_trading: PaperTradingSystem = None

async def init_paper_trading(db: AsyncIOMotorDatabase) -> PaperTradingSystem:
    global paper_trading
    paper_trading = PaperTradingSystem(db)
    await paper_trading.initialize()
    return paper_trading


async def route_engine_signal(signal: Dict, engine: str) -> List[Dict]:
    """Helper function to route signals from any engine"""
    global paper_trading
    if paper_trading:
        return await paper_trading.route_signal_to_accounts(signal, engine)
    return []


async def paper_account_health_loop(interval: int = 300):
    """
    Background task that checks account health every 5 minutes
    and auto-reloads accounts that are critically low
    """
    global paper_trading
    
    while True:
        try:
            if paper_trading:
                status = await paper_trading.check_account_health()
                if status.get("reloaded"):
                    logger.info(f"♻️ Auto-reloaded accounts: {[a['account_id'] for a in status['reloaded']]}")

            from self_healer import self_healer
            self_healer.heartbeat("paper_health")
        except Exception as e:
            logger.error(f"Account health check error: {e}")

        await asyncio.sleep(interval)



async def paper_price_update_loop(market_intel, interval: int = 30):
    """
    Background task that updates all position prices every 30 seconds
    This triggers TP/SL/liquidation checks and closes positions accordingly
    """
    global paper_trading
    
    logger.info(f"📊 Paper Trading Price Update Loop started - checking every {interval}s")
    
    while True:
        try:
            if paper_trading and market_intel:
                # Get all unique symbols from open positions across ALL accounts
                # (was previously limited to PRO+STARTER, missing REAL_LIFE/THE_PROOF/BENCHMARK)
                symbols = set()
                for acc_id in ACCOUNTS:
                    account = await paper_trading.get_account(acc_id)
                    if account:
                        for pos in account.get("positions", []):
                            if pos.get("status") == "open":
                                symbols.add(pos.get("symbol"))
                
                if symbols:
                    logger.debug(f"📊 Updating prices for {len(symbols)} symbols: {list(symbols)[:5]}...")
                    
                    # Fetch current prices
                    price_data = {}
                    for symbol in symbols:
                        try:
                            ticker = await market_intel.get_ticker(symbol)
                            price = ticker.get("price") or ticker.get("last")
                            if ticker and price:
                                price_data[symbol] = price
                        except Exception as e:
                            pass  # Skip symbols that fail
                    
                    # Update positions with new prices
                    if price_data:
                        logger.debug(f"📊 Got prices for {len(price_data)} symbols")
                        closed = await paper_trading.update_all_positions(price_data)
                        
                        if closed:
                            notified_ids = set()  # avoid double-counting PRO+STARTER
                            for result in closed:
                                pos = result.get("position", {})
                                reason = pos.get("close_reason", "unknown")
                                pnl = pos.get("realized_pnl", 0)
                                symbol = pos.get("symbol", "?")
                                acc = result.get("account", "?")

                                emoji = "🎯" if reason == "take_profit" else "🛑" if reason == "stop_loss" else "💀"
                                logger.info(f"{emoji} [{acc}] Closed {symbol} ({reason}) | PnL: ${pnl:,.2f}")

                                # Notify engine manager so win rates track correctly
                                unified_id = pos.get("signal_data", {}).get("unified_trade_id")
                                if unified_id and unified_id not in notified_ids:
                                    notified_ids.add(unified_id)
                                    try:
                                        from aeon_engine_system import get_engine_manager
                                        mgr = get_engine_manager()
                                        exit_price = pos.get("current_price") or pos.get("entry_price", 0)
                                        mgr.close_trade_by_id(unified_id, exit_price, pnl)
                                        logger.info(f"📊 Engine manager notified: trade {unified_id} closed PnL ${pnl:.2f}")
                                    except Exception as em_err:
                                        logger.warning(f"Engine manager notify failed: {em_err}")
                
            from self_healer import self_healer
            self_healer.heartbeat("paper_price_update")
        except Exception as e:
            logger.error(f"Price update loop error: {e}\n{traceback.format_exc()}")

        await asyncio.sleep(interval)
