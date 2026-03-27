"""
Paper Trading Weekly Report
Sends a Monday 8am UTC Telegram summary for all paper accounts.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Callable, List

logger = logging.getLogger(__name__)


class PaperWeeklyReport:
    def __init__(self, paper_trading, send_telegram: Callable, chat_ids: List[str]):
        self.paper_trading = paper_trading
        self.send_telegram = send_telegram
        self.chat_ids = chat_ids
        self.is_active = True
        self._last_sent: datetime = None

    async def run_scheduler(self):
        """Check every 15 minutes if it's Monday 08:00 UTC and report hasn't been sent yet today."""
        while self.is_active:
            try:
                now = datetime.now(timezone.utc)
                # Monday = 0, 08:00 UTC
                if now.weekday() == 0 and now.hour == 8:
                    today = now.date()
                    if self._last_sent is None or self._last_sent.date() < today:
                        await self._send_report()
                        self._last_sent = now
            except Exception as e:
                logger.error(f"[PaperWeeklyReport] scheduler error: {e}")
            await asyncio.sleep(900)  # 15 minutes

    async def _send_report(self):
        try:
            summary = await self.paper_trading.get_weekly_summary()

            # Count omega cycle fixes from the last 7 days
            try:
                from datetime import timedelta, timezone
                cutoff = datetime.now(timezone.utc) - timedelta(days=7)
                omega_fixes = await self.paper_trading.db.omega_fixes.count_documents(
                    {"timestamp": {"$gte": cutoff}}
                )
                summary["omega_fixes_week"] = omega_fixes
            except Exception:
                summary["omega_fixes_week"] = 0

            msg = self._format(summary)
            for chat_id in self.chat_ids:
                await self.send_telegram(chat_id, msg)
            await self.paper_trading.reset_weekly_baselines()
            logger.info("[PaperWeeklyReport] Weekly report sent and baselines reset.")
        except Exception as e:
            logger.error(f"[PaperWeeklyReport] send error: {e}")

    def _format(self, summary: dict) -> str:
        rl = summary.get("REAL_LIFE", {})
        tp = summary.get("THE_PROOF", {})
        bm = summary.get("BENCHMARK", {})
        qs = summary.get("quantum_state", {})

        def sign(v):
            return f"+{v:.2f}" if v >= 0 else f"{v:.2f}"

        def pct_sign(v):
            return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"

        lines = [
            "📊 AEON WEEKLY REPORT",
            "──────────────────────",
        ]

        # Real Life
        rl_bal = rl.get("balance", 0)
        rl_pnl = rl.get("weekly_pnl", 0)
        rl_pct = rl.get("weekly_pnl_pct", 0)
        rl_dep = rl.get("total_deposited", 0)
        rl_cross = rl.get("crossover_pct", 0)
        lines.append(
            f"💰 Real Life:  ${rl_bal:,.2f} ({pct_sign(rl_pct)}) | Dep ${rl_dep:,.0f} | "
            f"Crossover {rl_cross:.0f}% there"
        )

        # The Proof
        tp_bal = tp.get("balance", 0)
        tp_pct = tp.get("weekly_pnl_pct", 0)
        tp_target_pct = tp.get("target_pct", 0)
        tp_hit = tp.get("target_hit_at")
        proof_line = f"🎯 The Proof:  ${tp_bal:,.2f} ({pct_sign(tp_pct)}) | 17x target: {tp_target_pct:.1f}% there"
        if tp_hit:
            proof_line += f" 🏆 HIT {tp_hit[:10]}"
        lines.append(proof_line)

        # Benchmark
        bm_bal = bm.get("balance", 0)
        bm_pnl = bm.get("weekly_pnl", 0)
        bm_pct = bm.get("weekly_pnl_pct", 0)
        bm_best = bm.get("best_engine", "N/A")
        lines.append(
            f"📊 Benchmark:  ${bm_bal:,.2f} ({pct_sign(bm_pct)}) | Best engine: {bm_best}"
        )

        # Quantum state + omega fixes count
        h = qs.get("H", 0)
        c = qs.get("C", 0)
        omega_fixes = summary.get("omega_fixes_week", 0)
        lines += [
            "──────────────────────",
            f"H score:    {h:.4f}",
            f"Coherence:  {c:.4f}",
            f"Ω fixes:    {omega_fixes} this week",
            "──────────────────────",
        ]

        return "\n".join(lines)
