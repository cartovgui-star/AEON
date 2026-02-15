import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TradeHistory() {
  const [trades, setTrades] = useState({ open: [], closed: [] });
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const [openRes, closedRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/open`),
        fetch(`${API_URL}/api/trading/v2/closed`)
      ]);
      const openData = await openRes.json();
      const closedData = await closedRes.json();
      setTrades({
        open: openData.open_trades || [],
        closed: closedData.closed_trades || []
      });
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    }
    setLoading(false);
  };

  const allTrades = [
    ...trades.open.map(t => ({ ...t, status: 'open' })),
    ...trades.closed.map(t => ({ ...t, status: 'closed' }))
  ];

  const filteredTrades = allTrades.filter(t => {
    if (tab === 'open') return t.status === 'open';
    if (tab === 'closed') return t.status === 'closed';
    return true;
  });

  const stats = {
    total: trades.closed.length,
    winners: trades.closed.filter(t => (t.pnl_pct || 0) > 0).length,
    losers: trades.closed.filter(t => (t.pnl_pct || 0) < 0).length,
    pnl: trades.closed.reduce((s, t) => s + (t.pnl_pct || 0), 0)
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Total Trades</p>
          <p className="text-2xl font-bold text-white">{stats.total}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Open</p>
          <p className="text-2xl font-bold text-orange-400">{trades.open.length}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Winners</p>
          <p className="text-2xl font-bold text-green-400">{stats.winners}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Losers</p>
          <p className="text-2xl font-bold text-red-400">{stats.losers}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Total PnL</p>
          <p className={`text-2xl font-bold ${stats.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.pnl >= 0 ? '+' : ''}{stats.pnl.toFixed(2)}%
          </p>
        </div>
      </div>

      <div className="flex items-center gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['all', 'open', 'closed'].map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium ${tab === t ? 'bg-orange-500 text-white' : 'text-zinc-400'}`}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button onClick={fetchTrades} className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="overflow-x-auto">
        <table className="w-full min-w-[500px]">
          <thead className="bg-zinc-800/50">
            <tr className="text-left text-xs text-zinc-500 uppercase">
              <th className="px-4 py-3">Symbol</th>
              <th className="px-4 py-3">Direction</th>
              <th className="px-4 py-3">Entry</th>
              <th className="px-4 py-3">PnL</th>
              <th className="px-4 py-3">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-zinc-800">
            {filteredTrades.length === 0 ? (
              <tr><td colSpan={5} className="px-4 py-8 text-center text-zinc-500">
                {loading ? 'Loading...' : 'No trades yet'}
              </td></tr>
            ) : filteredTrades.map((trade, i) => (
              <tr key={i} className="hover:bg-zinc-800/30">
                <td className="px-4 py-3 font-medium text-white">{trade.symbol}</td>
                <td className="px-4 py-3">
                  <span className={`flex items-center gap-1 ${trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.direction === 'LONG' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                    {trade.direction}
                  </span>
                </td>
                <td className="px-4 py-3 text-zinc-300">${(trade.entry_price || 0).toLocaleString()}</td>
                <td className="px-4 py-3">
                  <span className={`font-medium ${(trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs ${
                    trade.status === 'open' ? 'bg-orange-500/20 text-orange-400' : 
                    (trade.pnl_pct || 0) >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                  }`}>
                    {trade.status === 'open' ? 'Open' : (trade.pnl_pct || 0) >= 0 ? 'Won' : 'Lost'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      </div>
    </div>
  );
}
