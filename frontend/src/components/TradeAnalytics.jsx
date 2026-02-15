import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, TrendingDown, Activity, Target, Award, Calendar,
  Download, RefreshCw, Zap, Clock, DollarSign, BarChart3,
  ArrowUpRight, ArrowDownRight, ChevronDown
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TradeAnalytics() {
  const [trades, setTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('7d');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/trades/closed`);
      const data = await res.json();
      setTrades(data.trades || []);
    } catch (err) {
      console.error('Failed to fetch:', err);
    }
    setLoading(false);
  };

  // Filter trades by time
  const getFilteredTrades = () => {
    const now = Date.now();
    const ranges = { '24h': 86400000, '7d': 604800000, '30d': 2592000000, 'all': Infinity };
    return trades.filter(t => (now - new Date(t.closed_at || t.timestamp).getTime()) <= ranges[timeRange]);
  };

  const filtered = getFilteredTrades();
  
  // Calculate stats
  const wins = filtered.filter(t => (t.pnl_pct || 0) > 0);
  const totalPnl = filtered.reduce((s, t) => s + (t.pnl_pct || 0), 0);
  const winRate = filtered.length ? ((wins.length / filtered.length) * 100).toFixed(1) : 0;

  // PnL curve data
  let cumPnl = 0;
  const pnlData = filtered
    .sort((a, b) => new Date(a.closed_at || a.timestamp) - new Date(b.closed_at || b.timestamp))
    .map((t, i) => {
      cumPnl += (t.pnl_pct || 0);
      return { trade: i + 1, pnl: cumPnl };
    });

  // Export CSV from backend
  const exportCSV = () => {
    window.open(`${API_URL}/api/trades/export`, '_blank');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-orange-400" />
            Trade Analytics
          </h1>
          <p className="text-zinc-400 text-sm mt-1">Performance insights</p>
        </div>
        
        <div className="flex items-center gap-3">
          <select
            value={timeRange}
            onChange={(e) => setTimeRange(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 text-white text-sm"
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
            <option value="all">All time</option>
          </select>
          <button onClick={exportCSV} className="flex items-center gap-2 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm hover:bg-zinc-700">
            <Download className="w-4 h-4" /> Export
          </button>
          <button onClick={fetchData} className="p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white hover:bg-zinc-700">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard icon={Activity} label="Trades" value={filtered.length} color="orange" />
        <StatCard icon={Target} label="Win Rate" value={`${winRate}%`} color={parseFloat(winRate) >= 50 ? 'green' : 'red'} />
        <StatCard icon={DollarSign} label="Total PnL" value={`${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}%`} color={totalPnl >= 0 ? 'green' : 'red'} />
        <StatCard icon={Zap} label="Wins" value={wins.length} color="green" />
      </div>

      {/* PnL Chart */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
        <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
          <TrendingUp className="w-5 h-5 text-orange-400" />
          Cumulative PnL
        </h3>
        {pnlData.length > 0 ? (
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={pnlData}>
              <defs>
                <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="trade" stroke="#9ca3af" fontSize={12} />
              <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={v => `${v}%`} />
              <Tooltip contentStyle={{ background: '#18181b', border: '1px solid #3f3f46' }} />
              <Area type="monotone" dataKey="pnl" stroke="#f97316" fill="url(#pnlGrad)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[250px] flex items-center justify-center text-zinc-500">No data</div>
        )}
      </div>

      {/* Recent Trades */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5 text-orange-400" />
            Recent Trades ({filtered.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px]">
            <thead className="bg-zinc-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Coin</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Side</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">Entry</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">Exit</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">PnL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700/50">
              {filtered.slice(-10).reverse().map((t, i) => (
                <tr key={i} className="hover:bg-zinc-800/50">
                  <td className="px-4 py-3 text-sm text-zinc-300">{new Date(t.closed_at || t.timestamp).toLocaleDateString()}</td>
                  <td className="px-4 py-3 text-sm font-medium text-white">{t.symbol?.replace('/USDT', '')}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${t.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                      {t.direction === 'LONG' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {t.direction}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-300 text-right font-mono">${t.entry_price?.toFixed(2)}</td>
                  <td className="px-4 py-3 text-sm text-zinc-300 text-right font-mono">${t.exit_price?.toFixed(2)}</td>
                  <td className={`px-4 py-3 text-sm text-right font-mono font-medium ${(t.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(t.pnl_pct || 0) >= 0 ? '+' : ''}{(t.pnl_pct || 0).toFixed(2)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {!filtered.length && <div className="p-8 text-center text-zinc-500">No trades found</div>}
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon: Icon, label, value, color }) {
  const colors = { orange: 'text-orange-400 bg-orange-500/10', green: 'text-green-400 bg-green-500/10', red: 'text-red-400 bg-red-500/10' };
  return (
    <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg ${colors[color]}`}><Icon className="w-4 h-4" /></div>
        <span className="text-zinc-400 text-xs">{label}</span>
      </div>
      <p className={`text-xl font-bold ${colors[color].split(' ')[0]}`}>{value}</p>
    </div>
  );
}
