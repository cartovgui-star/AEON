import React, { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, RefreshCw, Skull } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const CLOSE_REASON_CONFIG = {
  SL_HIT:       { label: 'SL Hit',       color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/30' },
  LIQUIDATION:  { label: 'Liquidated',   color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/30' },
  TIMEOUT:      { label: 'Timeout',      color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/30' },
  MANUAL:       { label: 'Manual',       color: 'text-zinc-400',   bg: 'bg-zinc-500/10 border-zinc-500/30' },
  TP_HIT:       { label: 'TP Hit',       color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/30' },
};

function closeReasonCfg(reason) {
  const key = (reason || '').toUpperCase().replace(/\s+/g, '_');
  return CLOSE_REASON_CONFIG[key] || { label: reason || '—', color: 'text-zinc-400', bg: 'bg-zinc-500/10 border-zinc-500/30' };
}

function RegimeBadge({ regime }) {
  const colors = {
    STRUCTURED:   'text-green-400 bg-green-500/10 border-green-500/30',
    TRANSITIONAL: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    CHAOTIC:      'text-orange-400 bg-orange-500/10 border-orange-500/30',
    CRISIS:       'text-red-400 bg-red-500/10 border-red-500/30',
  };
  const cls = colors[(regime || '').toUpperCase()] || 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30';
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold ${cls}`}>
      {regime || '—'}
    </span>
  );
}

function TradeRow({ trade }) {
  const [expanded, setExpanded] = useState(false);
  const cfg = closeReasonCfg(trade.close_reason);

  return (
    <>
      <tr
        className="hover:bg-zinc-800/30 cursor-pointer transition-colors border-b border-zinc-800/30"
        onClick={() => setExpanded(!expanded)}
      >
        <td className="px-3 py-2.5 text-xs">
          {expanded
            ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />
            : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
        </td>
        <td className="px-3 py-2.5 text-xs font-medium text-white">
          {trade.symbol?.replace('/USDT', '')}
          <span className={`ml-1.5 text-[10px] ${trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
            {trade.direction}
          </span>
        </td>
        <td className="px-3 py-2.5 text-xs text-zinc-400">{trade.engine || '—'}</td>
        <td className="px-3 py-2.5 text-xs font-mono font-bold text-red-400">
          ${trade.pnl?.toFixed(2)}
        </td>
        <td className="px-3 py-2.5 text-xs">
          <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold ${cfg.bg} ${cfg.color}`}>
            {cfg.label}
          </span>
        </td>
        <td className="px-3 py-2.5 text-xs">
          <RegimeBadge regime={trade.regime_at_entry} />
        </td>
        <td className="px-3 py-2.5 text-xs font-mono text-blue-400">
          {trade.h_value_at_entry !== null && trade.h_value_at_entry !== undefined
            ? Number(trade.h_value_at_entry).toFixed(3)
            : '—'}
        </td>
      </tr>

      {expanded && (
        <tr className="bg-zinc-900/60">
          <td colSpan={7} className="px-4 py-3">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
              <div>
                <p className="text-zinc-600 mb-0.5">Entry Price</p>
                <p className="text-zinc-300 font-mono">${trade.entry_price?.toFixed(4) ?? '—'}</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Exit Price</p>
                <p className="text-zinc-300 font-mono">${trade.exit_price?.toFixed(4) ?? '—'}</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Stop Loss</p>
                <p className="text-orange-400 font-mono">{trade.stop_loss ? `$${Number(trade.stop_loss).toFixed(4)}` : '—'}</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Duration</p>
                <p className="text-zinc-300 font-mono">
                  {trade.duration_min !== null && trade.duration_min !== undefined
                    ? trade.duration_min >= 60
                      ? `${(trade.duration_min / 60).toFixed(1)}h`
                      : `${trade.duration_min}m`
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Closed At</p>
                <p className="text-zinc-400">{trade.closed_at ? new Date(trade.closed_at).toLocaleString() : '—'}</p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Regime at Entry</p>
                <RegimeBadge regime={trade.regime_at_entry} />
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">H-Value at Entry</p>
                <p className="text-blue-400 font-mono">
                  {trade.h_value_at_entry !== null && trade.h_value_at_entry !== undefined
                    ? Number(trade.h_value_at_entry).toFixed(3)
                    : '—'}
                </p>
              </div>
              <div>
                <p className="text-zinc-600 mb-0.5">Close Reason</p>
                <span className={`inline-flex items-center px-1.5 py-0.5 rounded border text-[10px] font-semibold ${closeReasonCfg(trade.close_reason).bg} ${closeReasonCfg(trade.close_reason).color}`}>
                  {closeReasonCfg(trade.close_reason).label}
                </span>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

export default function PostMortemPanel() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/trades/post-mortem?limit=20`);
      if (res.ok) {
        const data = await res.json();
        setTrades(data);
        setLastUpdated(new Date());
      }
    } catch (_) {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Skull className="w-5 h-5 text-red-400" />
          <h2 className="text-base font-semibold text-white">Post-Mortem: Losing Trades</h2>
          <span className="text-xs text-zinc-500">(click row to expand)</span>
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

      {loading && trades.length === 0 ? (
        <div className="flex items-center justify-center py-10 text-zinc-500 text-sm gap-2">
          <RefreshCw className="w-4 h-4 animate-spin" />
          Loading post-mortem data...
        </div>
      ) : trades.length === 0 ? (
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-8 text-center">
          <AlertTriangle className="w-10 h-10 text-zinc-600 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">No losing trades found</p>
          <p className="text-zinc-600 text-xs mt-1">All recent trades were profitable</p>
        </div>
      ) : (
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px]">
              <thead className="bg-zinc-900/80">
                <tr>
                  <th className="px-3 py-2 text-left w-6" />
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Symbol</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Engine</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">PnL</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Reason</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">Regime</th>
                  <th className="px-3 py-2 text-left text-[10px] font-semibold text-zinc-500 uppercase tracking-wider">H Val</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade, i) => (
                  <TradeRow key={`${trade.symbol}-${trade.closed_at}-${i}`} trade={trade} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
