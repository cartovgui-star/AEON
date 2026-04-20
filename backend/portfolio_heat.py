"""
Phase 1 — Portfolio heat monitor.

Read-only. Accepts a snapshot of account state and computes heat metrics
used by RiskPolicy. Never writes or modifies any state.

Heat = open margin / current balance.
Tracks total, directional, symbol-level, and cluster/correlation heat.

Note: BTC_ECOSYSTEM mirrors CORRELATION_GROUPS["btc_eco"] in paper_trading.py.
Keep in sync if that list changes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

# Mirrors paper_trading.CORRELATION_GROUPS["btc_eco"]
BTC_ECOSYSTEM: Set[str] = {
    "BTC/USDT", "ETH/USDT", "BNB/USDT", "SOL/USDT",
    "AVAX/USDT", "MATIC/USDT", "ARB/USDT", "OP/USDT",
}

# DeFi correlation cluster (mirrors CORRELATION_GROUPS["defi"])
DEFI_CLUSTER: Set[str] = {
    "UNI/USDT", "AAVE/USDT", "CRV/USDT", "MKR/USDT",
    "COMP/USDT", "SNX/USDT", "SUSHI/USDT",
}

# Heat threshold above which an account is considered overheated
MAX_PORTFOLIO_HEAT: float = 0.30   # 30% of balance in open margin

# Cluster long count that triggers a correlation alert
MAX_CLUSTER_LONGS: int = 3


@dataclass
class HeatReport:
    account_id: str
    balance: float

    # Directional heat (margin / balance)
    total_heat: float = 0.0
    long_heat: float = 0.0
    short_heat: float = 0.0

    # Open symbols (deduplicated)
    open_symbols: List[str] = field(default_factory=list)

    # Symbols with >1 open position
    duplicate_symbols: List[str] = field(default_factory=list)

    # BTC-ecosystem cluster
    cluster_long_count: int = 0
    cluster_short_count: int = 0
    cluster_alert: bool = False    # True if cluster_long_count >= MAX_CLUSTER_LONGS

    # DeFi cluster
    defi_long_count: int = 0
    defi_short_count: int = 0

    # Hard gate flag
    is_overheated: bool = False


class PortfolioHeat:
    """
    Computes heat metrics for one or all accounts.

    Usage:
        ph = PortfolioHeat()
        report = ph.compute("PRO", account_doc)
        all_reports = ph.compute_all(accounts_dict)
    """

    def compute(self, account_id: str, account_data: dict) -> HeatReport:
        """
        Compute heat for a single account.

        account_data: a live paper account document (from paper_trading.accounts).
        """
        positions = account_data.get("positions", [])
        balance = float(account_data.get("balance") or 1.0)
        if balance <= 0:
            balance = 1.0

        open_positions = [p for p in positions if p.get("status") == "open"]

        total_margin: float = 0.0
        long_margin: float = 0.0
        short_margin: float = 0.0
        symbol_list: List[str] = []
        cluster_longs: int = 0
        cluster_shorts: int = 0
        defi_longs: int = 0
        defi_shorts: int = 0

        for pos in open_positions:
            margin = float(pos.get("margin") or 0.0)
            direction = str(pos.get("direction", "")).upper()
            symbol = str(pos.get("symbol", ""))

            total_margin += margin
            symbol_list.append(symbol)

            if direction == "LONG":
                long_margin += margin
                if symbol in BTC_ECOSYSTEM:
                    cluster_longs += 1
                if symbol in DEFI_CLUSTER:
                    defi_longs += 1
            elif direction == "SHORT":
                short_margin += margin
                if symbol in BTC_ECOSYSTEM:
                    cluster_shorts += 1
                if symbol in DEFI_CLUSTER:
                    defi_shorts += 1

        # Symbols appearing more than once
        symbol_set = list(set(symbol_list))
        duplicates = [s for s in symbol_set if symbol_list.count(s) > 1]

        total_heat = total_margin / balance
        long_heat = long_margin / balance
        short_heat = short_margin / balance

        return HeatReport(
            account_id=account_id,
            balance=balance,
            total_heat=round(total_heat, 4),
            long_heat=round(long_heat, 4),
            short_heat=round(short_heat, 4),
            open_symbols=symbol_set,
            duplicate_symbols=duplicates,
            cluster_long_count=cluster_longs,
            cluster_short_count=cluster_shorts,
            cluster_alert=cluster_longs >= MAX_CLUSTER_LONGS,
            defi_long_count=defi_longs,
            defi_short_count=defi_shorts,
            is_overheated=total_heat >= MAX_PORTFOLIO_HEAT,
        )

    def compute_all(self, accounts_data: dict) -> Dict[str, HeatReport]:
        """Compute heat for every account in accounts_data."""
        return {
            account_id: self.compute(account_id, data)
            for account_id, data in accounts_data.items()
        }
