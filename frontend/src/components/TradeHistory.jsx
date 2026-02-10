import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Filter, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TradeHistory() {
  const [trades, setTrades] = useState({ open: [], closed: [] });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('all');
  const [sortBy, setSortBy] = useState('date');
  const [sortDir, setSortDir] = useState('desc');
  const [filter, setFilter] = useState('');

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

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 30000);
    return () => clearInterval(interval);
  }, []);

  const allTrades = [
    ...trades.open.map(t => ({ ...t, status: 'open' })),
    ...trades.closed.map(t => ({ ...t, status: 'closed' }))
  ];

  const filteredTrades = allTrades
    .filter(t => {
      if (activeTab === 'open') return t.status === 'open';
      if (activeTab === 'closed') return t.status === 'closed';
      if (activeTab === 'winners') return t.status === 'closed' && (t.pnl_pct || 0) > 0;
      if (activeTab === 'losers') return t.status === 'closed' && (t.pnl_pct || 0) < 0;
      return true;
    })
    .filter(t => !filter || t.symbol?.toLowerCase().includes(filter.toLowerCase()))
    .sort((a, b) => {
      let aVal, bVal;
      if (sortBy === 'date') {
        aVal = new Date(a.opened_at || a.closed_at || 0);
        bVal = new Date(b.opened_at || b.closed_at || 0);
      } else if (sortBy === 'pnl') {
        aVal = a.pnl_pct || 0;
        bVal = b.pnl_pct || 0;
      } else if (sortBy === 'symbol') {
        aVal = a.symbol || '';
        bVal = b.symbol || '';
      } else if (sortBy === 'confidence') {
        aVal = a.confidence || 0;
        bVal = b.confidence || 0;
      }
      return sortDir === 'asc' ? (aVal > bVal ? 1 : -1) : (aVal < bVal ? 1 : -1);
    });

  const stats = {
    totalTrades: trades.closed.length,
    winners: trades.closed.filter(t => (t.pnl_pct || 0) > 0).length,
    losers: trades.closed.filter(t => (t.pnl_pct || 0) < 0).length,
    totalPnl: trades.closed.reduce((sum, t) => sum + (t.pnl_pct || 0), 0),
    avgWin: trades.closed.filter(t => (t.pnl_pct || 0) > 0).reduce((sum, t, _, arr) => sum + (t.pnl_pct || 0) / arr.length, 0),
    avgLoss: trades.closed.filter(t => (t.pnl_pct || 0) < 0).reduce((sum, t, _, arr) => sum + (t.pnl_pct || 0) / arr.length, 0)
  };

  const SortHeader = ({ label, value }) => (
    <button
      onClick={() => {
        if (sortBy === value) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
        else { setSortBy(value); setSortDir('desc'); }
      }}
      className="flex items-center gap-1 hover:text-orange-400 transition-colors"
    >
      {label}
      {sortBy === value && (sortDir === 'asc' ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />)}
    </button>
  );

  return (
    <div className="space-y-6">
      {/* Stats Summary */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Total Trades</p>
          <p className="text-2xl font-bold text-white">{stats.totalTrades}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Open</p>
          <p className="text-2xl font-bold text-orange-400">{trades.open.length}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Winners</p>
          <p className="text-2xl font-bold text-green-400">{stats.winners}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Losers</p>
          <p className="text-2xl font-bold text-red-400">{stats.losers}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Win Rate</p>
          <p className="text-2xl font-bold text-white">
            {stats.totalTrades > 0 ? Math.round((stats.winners / stats.totalTrades) * 100) : 0}%
          </p>
        </div>
        <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Total PnL</p>
          <p className={`text-2xl font-bold ${stats.totalPnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {stats.totalPnl >= 0 ? '+' : ''}{stats.totalPnl.toFixed(2)}%
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['all', 'open', 'closed', 'winners', 'losers'].map(tab => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === tab 
                  ? 'bg-orange-500 text-white' 
                  : 'text-zinc-400 hover:text-white'
              }`}
            >
              {tab.charAt(0).toUpperCase() + tab.slice(1)}
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-2 bg-zinc-800/50 rounded-lg px-3 py-2">
          <Filter className="w-4 h-4 text-zinc-500" />
          <input
            type="text"
            placeholder="Filter by symbol..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="bg-transparent border-none outline-none text-sm text-white placeholder-zinc-500 w-40"
          />
        </div>

        <button
          onClick={fetchTrades}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Trades Table */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-zinc-800/50">
              <tr className="text-left text-xs text-zinc-500 uppercase">
                <th className="px-4 py-3"><SortHeader label="Symbol" value="symbol" /></th>
                <th className="px-4 py-3">Direction</th>
                <th className="px-4 py-3">Entry</th>
                <th className="px-4 py-3">Exit/Current</th>
                <th className="px-4 py-3"><SortHeader label="PnL" value="pnl" /></th>
                <th className="px-4 py-3"><SortHeader label="Confidence" value="confidence" /></th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3"><SortHeader label="Date" value="date" /></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-8 text-center text-zinc-500">
                    {loading ? 'Loading trades...' : 'No trades found'}
                  </td>
                </tr>
              ) : (
                filteredTrades.map((trade, i) => (
                  <tr key={i} className="hover:bg-zinc-800/30 transition-colors">
                    <td className="px-4 py-3">
                      <span className="font-medium text-white">{trade.symbol}</span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`flex items-center gap-1 ${
                        trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        {trade.direction === 'LONG' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                        {trade.direction}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-300">
                      ${(trade.entry_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-zinc-300">
                      ${(trade.exit_price || trade.current_price || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`font-medium ${(trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="w-16 h-2 bg-zinc-700 rounded-full overflow-hidden">
                          <div 
                            className="h-full bg-gradient-to-r from-orange-500 to-amber-500"
                            style={{ width: `${trade.confidence || 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-400">{trade.confidence || 0}%</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                        trade.status === 'open' 
                          ? 'bg-orange-500/20 text-orange-400' 
                          : (trade.pnl_pct || 0) >= 0 
                            ? 'bg-green-500/20 text-green-400' 
                            : 'bg-red-500/20 text-red-400'
                      }`}>
                        {trade.status === 'open' ? 'Open' : (trade.pnl_pct || 0) >= 0 ? 'Won' : 'Lost'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-zinc-500 text-sm">
                      {new Date(trade.opened_at || trade.closed_at || Date.now()).toLocaleDateString()}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
