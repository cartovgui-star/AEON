import React, { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const REGIME_CONFIG = {
  STRUCTURED:   { color: 'text-blue-400',   bg: 'bg-blue-500/10 border-blue-500/30',   bar: 'bg-blue-500' },
  TRANSITIONAL: { color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30', bar: 'bg-yellow-500' },
  CHAOTIC:      { color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30', bar: 'bg-orange-500' },
  CRISIS:       { color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30',    bar: 'bg-red-500' },
  UNKNOWN:      { color: 'text-zinc-400',   bg: 'bg-zinc-500/10 border-zinc-500/30',  bar: 'bg-zinc-500' },
};

function regimeCfg(regime) {
  return REGIME_CONFIG[(regime || '').toUpperCase()] || REGIME_CONFIG.UNKNOWN;
}

function RegimeCard({ data }) {
  const cfg = regimeCfg(data.regime);
  const winBarWidth = Math.min(100, data.win_rate || 0);
  const pfColor = data.profit_factor >= 2 ? 'text-green-400' : data.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className={`rounded-xl border p-4 ${cfg.bg}`}>
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className={`text-sm font-bold uppercase tracking-wider ${cfg.color}`}>
          {data.regime}
        </span>
        <span className="text-xs text-zinc-500">{data.trade_count} trades</span>
      </div>

      {/* Win Rate Bar */}
      <div className="mb-3">
        <div className="flex justify-between items-center mb-1">
          <span className="text-xs text-zinc-500">Win Rate</span>
          <span className={`text-xs font-bold font-mono ${cfg.color}`}>{data.win_rate}%</span>
        </div>
        <div className="h-1.5 bg-zinc-800/60 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${cfg.bar}`}
            style={{ width: `${winBarWidth}%` }}
          />
        </div>
      </div>

      {/* Stats Row */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <p className="text-zinc-600 mb-0.5">Avg PnL</p>
          <p className={`font-mono font-semibold ${data.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {data.avg_pnl >= 0 ? '+' : ''}${data.avg_pnl?.toFixed(2)}
          </p>
        </div>
        <div>
          <p className="text-zinc-600 mb-0.5">Profit Factor</p>
          <p className={`font-mono font-semibold ${pfColor}`}>
            {data.profit_factor >= 999 ? '∞' : data.profit_factor?.toFixed(2)}
          </p>
        </div>
      </div>
    </div>
  );
}

export default function RegimePerformancePanel() {
  const [regimes, setRegimes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/analytics/regime-performance`);
      if (res.ok) {
        const data = await res.json();
        setRegimes(data);
        setLastUpdated(new Date());
      }
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 120000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-orange-400" />
          <h2 className="text-base font-semibold text-white">Regime vs Performance</h2>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-zinc-600">{lastUpdated.toLocaleTimeString()}</span>
          )}
          <button
            onClick={fetchData}
            className="p-1.5 rounded-lg bg-zinc-800/50 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {loading && regimes.length === 0 ? (
        <div className="flex items-center justify-center py-10 text-zinc-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Loading regime data...
        </div>
      ) : regimes.length === 0 ? (
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6 text-center text-zinc-500 text-sm">
          No regime performance data yet — trades need regime_at_entry field
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Show known regimes first, then any others */}
          {['STRUCTURED', 'TRANSITIONAL', 'CHAOTIC', 'CRISIS'].map((regime) => {
            const data = regimes.find((r) => r.regime === regime);
            if (!data) return null;
            return <RegimeCard key={regime} data={data} />;
          })}
          {/* Any extra regimes not in the canonical list */}
          {regimes
            .filter((r) => !['STRUCTURED', 'TRANSITIONAL', 'CHAOTIC', 'CRISIS'].includes(r.regime))
            .map((data) => (
              <RegimeCard key={data.regime} data={data} />
            ))}
        </div>
      )}
    </div>
  );
}
