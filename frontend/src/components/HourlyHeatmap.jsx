import React, { useState, useEffect, useCallback } from 'react';
import { Clock, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function winRateColor(winRate, insufficient) {
  if (insufficient) return { bg: 'bg-zinc-800/50', text: 'text-zinc-600', border: 'border-zinc-700/30' };
  if (winRate >= 65) return { bg: 'bg-green-500/30', text: 'text-green-300', border: 'border-green-500/40' };
  if (winRate >= 55) return { bg: 'bg-green-500/15', text: 'text-green-400', border: 'border-green-500/20' };
  if (winRate >= 45) return { bg: 'bg-yellow-500/15', text: 'text-yellow-400', border: 'border-yellow-500/20' };
  if (winRate >= 35) return { bg: 'bg-orange-500/15', text: 'text-orange-400', border: 'border-orange-500/20' };
  return { bg: 'bg-red-500/20', text: 'text-red-400', border: 'border-red-500/30' };
}

function HourCell({ data }) {
  const [hovered, setHovered] = useState(false);
  const { bg, text, border } = winRateColor(data.win_rate, data.insufficient_data);
  const hour = data.hour;
  const label = hour === 0 ? '12am' : hour === 12 ? '12pm' : hour < 12 ? `${hour}am` : `${hour - 12}pm`;

  return (
    <div
      className={`relative rounded-lg border ${bg} ${border} p-2 text-center cursor-default transition-all duration-200 hover:scale-105`}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      <p className="text-[10px] text-zinc-500 mb-0.5">{label}</p>
      {data.insufficient_data ? (
        <p className="text-[10px] text-zinc-700">—</p>
      ) : (
        <p className={`text-xs font-bold font-mono ${text}`}>{data.win_rate}%</p>
      )}

      {/* Tooltip */}
      {hovered && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-20 bg-zinc-900 border border-zinc-700 rounded-lg p-2 shadow-xl min-w-[120px] text-left pointer-events-none">
          <p className="text-xs font-semibold text-white mb-1">{hour}:00 UTC</p>
          {data.insufficient_data ? (
            <p className="text-[11px] text-zinc-500">Insufficient data (&lt;10 trades)</p>
          ) : (
            <>
              <p className="text-[11px] text-zinc-400">Win Rate: <span className={`font-bold ${text}`}>{data.win_rate}%</span></p>
              <p className="text-[11px] text-zinc-400">Trades: <span className="text-white">{data.trade_count}</span></p>
              <p className="text-[11px] text-zinc-400">Avg PnL: <span className={data.avg_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>${data.avg_pnl?.toFixed(2)}</span></p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

export default function HourlyHeatmap() {
  const [heatmap, setHeatmap] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/analytics/hourly-heatmap`);
      if (res.ok) {
        const data = await res.json();
        setHeatmap(data);
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

  const totalTrades = heatmap.reduce((s, h) => s + (h.trade_count || 0), 0);
  const bestHour = heatmap.length > 0
    ? heatmap.filter(h => !h.insufficient_data).sort((a, b) => b.win_rate - a.win_rate)[0]
    : null;

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Clock className="w-5 h-5 text-orange-400" />
          <h2 className="text-base font-semibold text-white">Time-of-Day Performance</h2>
          <span className="text-xs text-zinc-500">(UTC hours)</span>
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

      {/* Legend */}
      <div className="flex items-center gap-4 text-[10px] flex-wrap">
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-green-500/30 border border-green-500/40" /><span className="text-zinc-500">&ge;65% (great)</span></div>
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-green-500/15 border border-green-500/20" /><span className="text-zinc-500">&ge;55% (good)</span></div>
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-yellow-500/15 border border-yellow-500/20" /><span className="text-zinc-500">&ge;45% (neutral)</span></div>
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-red-500/20 border border-red-500/30" /><span className="text-zinc-500">&lt;35% (avoid)</span></div>
        <div className="flex items-center gap-1.5"><div className="w-3 h-3 rounded bg-zinc-800/50 border border-zinc-700/30" /><span className="text-zinc-500">insufficient data</span></div>
      </div>

      {loading && heatmap.length === 0 ? (
        <div className="flex items-center justify-center py-10 text-zinc-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Loading heatmap...
        </div>
      ) : (
        <>
          {/* 24-cell grid */}
          <div className="grid grid-cols-6 sm:grid-cols-8 md:grid-cols-12 gap-1.5">
            {heatmap.map((h) => (
              <HourCell key={h.hour} data={h} />
            ))}
          </div>

          {/* Summary */}
          <div className="bg-zinc-900/30 border border-zinc-800/30 rounded-xl p-3 flex items-center gap-4 text-xs flex-wrap">
            <span className="text-zinc-500">Total trades: <span className="text-white font-mono">{totalTrades}</span></span>
            {bestHour && (
              <span className="text-zinc-500">
                Best hour: <span className="text-green-400 font-mono">{bestHour.hour}:00 UTC</span>
                <span className="text-zinc-600"> ({bestHour.win_rate}% win rate)</span>
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
