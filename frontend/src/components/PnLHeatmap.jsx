import React, { useState, useEffect } from 'react';
import { RefreshCw, BarChart3 } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const HOURS = Array.from({ length: 24 }, (_, i) => i);

export default function PnLHeatmap() {
  const [heatmap, setHeatmap] = useState({});   // { symbol: { hour: { pnl, count } } }
  const [symbols, setSymbols] = useState([]);
  const [loading, setLoading] = useState(true);
  const [maxAbs, setMaxAbs] = useState(1);
  const [metric, setMetric] = useState('pnl'); // 'pnl' | 'winrate'

  useEffect(() => {
    fetchData();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/trading/v2/closed`);
      const data = await res.json();
      const trades = data.closed_trades || [];

      const map = {};
      trades.forEach(t => {
        if (!t.exit_time) return;
        const sym = (t.symbol || '').replace('/USDT', '');
        if (!sym) return;
        const hour = new Date(t.exit_time).getUTCHours();
        const pnl = t.pnl_pct || 0;
        if (!map[sym]) map[sym] = {};
        if (!map[sym][hour]) map[sym][hour] = { pnl: 0, count: 0, wins: 0 };
        map[sym][hour].pnl += pnl;
        map[sym][hour].count += 1;
        if (pnl > 0) map[sym][hour].wins += 1;
      });

      // Only keep symbols with ≥3 trades
      const filtered = Object.fromEntries(
        Object.entries(map).filter(([, hours]) =>
          Object.values(hours).reduce((s, h) => s + h.count, 0) >= 3
        )
      );

      const syms = Object.keys(filtered).sort();
      setSymbols(syms);
      setHeatmap(filtered);

      // Compute max absolute pnl for color scale
      let ma = 0.01;
      syms.forEach(s => {
        HOURS.forEach(h => {
          const v = filtered[s]?.[h];
          if (v) ma = Math.max(ma, Math.abs(metric === 'winrate' ? (v.wins / v.count * 100 - 50) : v.pnl));
        });
      });
      setMaxAbs(ma);
    } catch (err) {
      console.error('PnL heatmap fetch failed:', err);
    }
    setLoading(false);
  };

  const getColor = (v) => {
    if (!v || v.count === 0) return 'bg-zinc-800/30';
    const raw = metric === 'winrate'
      ? (v.wins / v.count * 100) - 50   // centered at 50%
      : v.pnl;
    const intensity = Math.min(1, Math.abs(raw) / maxAbs);
    if (raw > 0) {
      if (intensity > 0.7) return 'bg-emerald-500/70';
      if (intensity > 0.4) return 'bg-emerald-500/45';
      return 'bg-emerald-500/20';
    } else {
      if (intensity > 0.7) return 'bg-rose-500/70';
      if (intensity > 0.4) return 'bg-rose-500/45';
      return 'bg-rose-500/20';
    }
  };

  const getTooltip = (sym, h) => {
    const v = heatmap[sym]?.[h];
    if (!v || v.count === 0) return `${sym} ${h}:00 UTC — no trades`;
    const wr = ((v.wins / v.count) * 100).toFixed(0);
    return `${sym} ${h}:00 UTC\nPnL: ${v.pnl >= 0 ? '+' : ''}${v.pnl.toFixed(1)}%\nTrades: ${v.count} | Win rate: ${wr}%`;
  };

  if (loading) {
    return (
      <Card className="bg-zinc-800/30 border-zinc-700/50">
        <CardContent className="flex items-center justify-center py-12 gap-3 text-zinc-500">
          <RefreshCw className="w-5 h-5 animate-spin" />
          Building heatmap...
        </CardContent>
      </Card>
    );
  }

  if (symbols.length === 0) {
    return (
      <Card className="bg-zinc-800/30 border-zinc-700/50">
        <CardContent className="py-12 text-center text-zinc-500">
          Not enough closed trades to build a heatmap yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-orange-500/20 border border-orange-500/30 flex items-center justify-center">
            <BarChart3 className="w-5 h-5 text-orange-400" />
          </div>
          <div>
            <h2 className="text-white font-bold text-lg">PnL Heatmap</h2>
            <p className="text-zinc-500 text-xs">Per-symbol performance by hour (UTC)</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex bg-zinc-800/50 rounded-lg p-1">
            {['pnl', 'winrate'].map(m => (
              <button
                key={m}
                onClick={() => setMetric(m)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  metric === m ? 'bg-orange-500/20 text-orange-400' : 'text-zinc-400 hover:text-white'
                }`}
              >
                {m === 'pnl' ? 'PnL %' : 'Win Rate'}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="overflow-x-auto">
        <div className="min-w-[700px]">
          {/* Hour labels */}
          <div className="flex items-center mb-1 pl-16">
            {HOURS.map(h => (
              <div key={h} className="flex-1 text-center text-xs text-zinc-600 font-mono">
                {h % 4 === 0 ? `${h}h` : ''}
              </div>
            ))}
          </div>

          {/* Rows */}
          {symbols.map(sym => (
            <div key={sym} className="flex items-center mb-0.5">
              <div className="w-14 text-right pr-2 text-xs text-zinc-400 font-medium flex-shrink-0">
                {sym}
              </div>
              {HOURS.map(h => {
                const v = heatmap[sym]?.[h];
                return (
                  <div
                    key={h}
                    className={`flex-1 h-6 mx-px rounded-sm cursor-default ${getColor(v)}`}
                    title={getTooltip(sym, h)}
                  >
                    {v && v.count > 0 && (
                      <span className="text-[9px] font-mono text-white/70 leading-6 flex items-center justify-center h-full">
                        {v.count > 1 ? v.count : ''}
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          ))}
        </div>
      </div>

      {/* Legend */}
      <div className="flex items-center gap-6 text-xs text-zinc-500">
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm bg-emerald-500/70" />
          <span>Strong {metric === 'winrate' ? 'win rate' : 'profit'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm bg-rose-500/70" />
          <span>Strong {metric === 'winrate' ? 'loss rate' : 'loss'}</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-4 h-4 rounded-sm bg-zinc-800/30 border border-zinc-700/50" />
          <span>No data</span>
        </div>
        <span className="ml-auto text-zinc-600">Numbers = trade count per cell</span>
      </div>
    </div>
  );
}
