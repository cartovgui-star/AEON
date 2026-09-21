import React, { useState, useEffect } from 'react';
import { Power } from 'lucide-react';
import { fetchTradingStats, fetchSystemHealth } from '../services/api';

// Format total_pnl_pct as a percentage (e.g. +12.34%)
const fmt2 = (v) => v != null ? `${Number(v) >= 0 ? '+' : ''}${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}%` : '—';

export default function SlimHeader({ onNavigate }) {
  const [stats, setStats] = useState(null);
  const [health, setHealth] = useState(null);
  const [killConfirm, setKillConfirm] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        const [s, h] = await Promise.allSettled([fetchTradingStats(), fetchSystemHealth()]);
        if (s.status === 'fulfilled') setStats(s.value);
        if (h.status === 'fulfilled') setHealth(h.value);
      } catch {}
    };
    load();
    const iv = setInterval(load, 30000);
    return () => clearInterval(iv);
  }, []);

  const overall = health?.overall || 'unknown';
  const dotColor = overall === 'healthy' ? 'bg-emerald-500' : overall === 'degraded' ? 'bg-amber-500 animate-pulse' : 'bg-zinc-600';

  // Use total_pnl_pct from /api/trading/v2/stats (no daily_pnl field in backend)
  const dailyPnl = stats?.total_pnl_pct ?? null;
  const pnlColor = dailyPnl > 0 ? 'text-[#00E676]' : dailyPnl < 0 ? 'text-[#FF3D57]' : 'text-zinc-400';

  return (
    <div className="sticky top-0 z-40 bg-[#0A0A0F]/95 backdrop-blur-xl border-b border-zinc-800/50 px-4 h-14 flex items-center justify-between">
      {/* Left: AEON logo */}
      <div className="flex items-center gap-2">
        <span className="text-zinc-500 text-xs font-bold tracking-[0.2em] uppercase">AEON</span>
        <div className="w-px h-3 bg-zinc-800" />
        <span className={`text-[10px] font-semibold ${stats?.active ? 'text-emerald-400' : 'text-amber-400'}`}>
          {stats?.active ? 'ACTIVE' : 'PAUSED'}
        </span>
      </div>

      {/* Center: Today's PnL */}
      <button
        onClick={() => onNavigate('command')}
        className="flex flex-col items-center -mt-0.5"
      >
        <div className={`font-mono text-xl font-bold leading-none ${pnlColor}`}>
          {fmt2(dailyPnl)}
        </div>
        <div className="text-[9px] text-zinc-600 uppercase tracking-widest mt-0.5">TOTAL PNL</div>
      </button>

      {/* Right: health + kill */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => onNavigate('settings-v2')}
          className="flex items-center gap-1.5 px-2 py-1 rounded-lg bg-zinc-900/60 border border-zinc-800/50"
        >
          <div className={`w-2 h-2 rounded-full ${dotColor}`} />
          <span className="text-[10px] text-zinc-500 hidden sm:inline capitalize">{overall}</span>
        </button>

        <button
          onClick={() => {
            if (killConfirm) {
              onNavigate('settings-v2');
              setKillConfirm(false);
            } else {
              setKillConfirm(true);
              setTimeout(() => setKillConfirm(false), 3000);
            }
          }}
          className={`p-2 rounded-lg transition-all ${
            killConfirm
              ? 'bg-rose-500/30 text-rose-400 border border-rose-500/40 animate-pulse'
              : 'bg-zinc-900/60 border border-zinc-800/50 text-zinc-500 hover:text-rose-400 hover:border-rose-500/30'
          }`}
          title={killConfirm ? 'Tap again to go to Emergency Stop' : 'Emergency Stop'}
        >
          <Power className="w-3.5 h-3.5" />
        </button>
      </div>
    </div>
  );
}
