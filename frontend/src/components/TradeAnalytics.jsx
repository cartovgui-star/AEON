import React, { useState, useEffect, useMemo } from 'react';
import { 
  TrendingUp, TrendingDown, Activity, Target, Award, Calendar,
  Download, RefreshCw, Zap, Clock, DollarSign, Percent, BarChart3,
  ArrowUpRight, ArrowDownRight, Filter, ChevronDown
} from 'lucide-react';
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Custom tooltip for charts
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-3 shadow-xl">
        <p className="text-zinc-400 text-xs mb-1">{label}</p>
        {payload.map((p, i) => (
          <p key={i} className="text-sm font-medium" style={{ color: p.color }}>
            {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
            {p.name.includes('PnL') || p.name.includes('%') ? '%' : ''}
          </p>
        ))}
      </div>
    );
  }
  return null;
};

export default function TradeAnalytics() {
  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [timeRange, setTimeRange] = useState('7d');
  const [selectedCoin, setSelectedCoin] = useState('all');

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [tradesRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/trades/closed`),
        fetch(`${API_URL}/api/trading/v2/stats`)
      ]);
      
      const tradesData = await tradesRes.json();
      const statsData = await statsRes.json();
      
      setTrades(tradesData.trades || []);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    }
    setLoading(false);
  };

  // Process data for charts
  const chartData = useMemo(() => {
    if (!trades.length) return { pnlCurve: [], byDay: [], byCoin: [], byType: [], filtered: [] };

    // Filter by time range
    const now = new Date();
    const rangeMs = {
      '24h': 24 * 60 * 60 * 1000,
      '7d': 7 * 24 * 60 * 60 * 1000,
      '30d': 30 * 24 * 60 * 60 * 1000,
      'all': Infinity
    }[timeRange];

    let filtered = trades.filter(t => {
      const tradeTime = new Date(t.closed_at || t.timestamp).getTime();
      return (now.getTime() - tradeTime) <= rangeMs;
    });

    if (selectedCoin !== 'all') {
      filtered = filtered.filter(t => t.symbol?.includes(selectedCoin));
    }

    // Sort by time
    filtered.sort((a, b) => new Date(a.closed_at || a.timestamp) - new Date(b.closed_at || b.timestamp));

    // PnL Curve (cumulative)
    let cumPnl = 0;
    const pnlCurve = filtered.map((t, i) => {
      cumPnl += (t.pnl_pct || t.pnl_percentage || 0);
      return {
        trade: i + 1,
        date: new Date(t.closed_at || t.timestamp).toLocaleDateString(),
        pnl: cumPnl,
        individual: t.pnl_pct || t.pnl_percentage || 0
      };
    });

    // Group by day
    const byDayMap = {};
    filtered.forEach(t => {
      const day = new Date(t.closed_at || t.timestamp).toLocaleDateString();
      if (!byDayMap[day]) byDayMap[day] = { day, trades: 0, wins: 0, pnl: 0 };
      byDayMap[day].trades++;
      byDayMap[day].pnl += (t.pnl_pct || t.pnl_percentage || 0);
      if ((t.pnl_pct || t.pnl_percentage || 0) > 0) byDayMap[day].wins++;
    });
    const byDay = Object.values(byDayMap).slice(-14);

    // Group by coin
    const byCoinMap = {};
    filtered.forEach(t => {
      const coin = t.symbol?.replace('/USDT', '').replace('USDT', '') || 'Unknown';
      if (!byCoinMap[coin]) byCoinMap[coin] = { coin, trades: 0, wins: 0, pnl: 0 };
      byCoinMap[coin].trades++;
      byCoinMap[coin].pnl += (t.pnl_pct || t.pnl_percentage || 0);
      if ((t.pnl_pct || t.pnl_percentage || 0) > 0) byCoinMap[coin].wins++;
    });
    const byCoin = Object.values(byCoinMap)
      .sort((a, b) => b.trades - a.trades)
      .slice(0, 10);

    // Group by trade type
    const byTypeMap = { LONG: { type: 'LONG', trades: 0, wins: 0, pnl: 0 }, SHORT: { type: 'SHORT', trades: 0, wins: 0, pnl: 0 } };
    filtered.forEach(t => {
      const type = t.direction || 'LONG';
      if (!byTypeMap[type]) byTypeMap[type] = { type, trades: 0, wins: 0, pnl: 0 };
      byTypeMap[type].trades++;
      byTypeMap[type].pnl += (t.pnl_pct || t.pnl_percentage || 0);
      if ((t.pnl_pct || t.pnl_percentage || 0) > 0) byTypeMap[type].wins++;
    });
    const byType = Object.values(byTypeMap);

    return { pnlCurve, byDay, byCoin, byType, filtered };
  }, [trades, timeRange, selectedCoin]);

  // Calculate additional stats
  const computedStats = useMemo(() => {
    const filtered = chartData.filtered || [];
    if (!filtered.length) return null;

    const wins = filtered.filter(t => (t.pnl_pct || t.pnl_percentage || 0) > 0);
    const losses = filtered.filter(t => (t.pnl_pct || t.pnl_percentage || 0) <= 0);
    
    const avgWin = wins.length ? wins.reduce((s, t) => s + (t.pnl_pct || t.pnl_percentage || 0), 0) / wins.length : 0;
    const avgLoss = losses.length ? Math.abs(losses.reduce((s, t) => s + (t.pnl_pct || t.pnl_percentage || 0), 0) / losses.length) : 0;
    
    const best = filtered.reduce((best, t) => (t.pnl_pct || t.pnl_percentage || 0) > (best.pnl_pct || best.pnl_percentage || 0) ? t : best, filtered[0]);
    const worst = filtered.reduce((worst, t) => (t.pnl_pct || t.pnl_percentage || 0) < (worst.pnl_pct || worst.pnl_percentage || 0) ? t : worst, filtered[0]);

    return {
      totalTrades: filtered.length,
      winRate: (wins.length / filtered.length * 100).toFixed(1),
      avgWin: avgWin.toFixed(2),
      avgLoss: avgLoss.toFixed(2),
      profitFactor: avgLoss ? (avgWin / avgLoss).toFixed(2) : 'N/A',
      best: { symbol: best.symbol, pnl: (best.pnl_pct || best.pnl_percentage || 0).toFixed(2) },
      worst: { symbol: worst.symbol, pnl: (worst.pnl_pct || worst.pnl_percentage || 0).toFixed(2) },
      totalPnl: filtered.reduce((s, t) => s + (t.pnl_pct || t.pnl_percentage || 0), 0).toFixed(2)
    };
  }, [chartData]);

  // Get unique coins for filter
  const uniqueCoins = useMemo(() => {
    const coins = new Set(trades.map(t => t.symbol?.replace('/USDT', '').replace('USDT', '')));
    return ['all', ...Array.from(coins).filter(Boolean).sort()];
  }, [trades]);

  // Export to CSV
  const exportCSV = () => {
    const filtered = chartData.filtered || [];
    if (!filtered.length) return;

    const headers = ['Date', 'Symbol', 'Direction', 'Entry', 'Exit', 'PnL %', 'Leverage', 'Type'];
    const rows = filtered.map(t => [
      new Date(t.closed_at || t.timestamp).toISOString(),
      t.symbol,
      t.direction,
      t.entry_price,
      t.exit_price,
      t.pnl_pct || t.pnl_percentage || 0,
      t.leverage || 1,
      t.trade_type || 'N/A'
    ]);

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aeon_trades_${timeRange}_${new Date().toISOString().split('T')[0]}.csv`;
    a.click();
    URL.revokeObjectURL(url);
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
          <p className="text-zinc-400 text-sm mt-1">Deep dive into your trading performance</p>
        </div>
        
        <div className="flex flex-wrap items-center gap-3">
          {/* Time Range Filter */}
          <div className="relative">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              data-testid="analytics-time-filter"
              className="appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 pr-8 text-white text-sm focus:border-orange-500 focus:outline-none cursor-pointer"
            >
              <option value="24h">Last 24h</option>
              <option value="7d">Last 7 days</option>
              <option value="30d">Last 30 days</option>
              <option value="all">All time</option>
            </select>
            <ChevronDown className="w-4 h-4 text-zinc-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Coin Filter */}
          <div className="relative">
            <select
              value={selectedCoin}
              onChange={(e) => setSelectedCoin(e.target.value)}
              data-testid="analytics-coin-filter"
              className="appearance-none bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2 pr-8 text-white text-sm focus:border-orange-500 focus:outline-none cursor-pointer"
            >
              {uniqueCoins.map(coin => (
                <option key={coin} value={coin}>{coin === 'all' ? 'All Coins' : coin}</option>
              ))}
            </select>
            <Filter className="w-4 h-4 text-zinc-400 absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none" />
          </div>

          {/* Export Button */}
          <button
            onClick={exportCSV}
            data-testid="analytics-export-btn"
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm hover:bg-zinc-700 transition-colors"
          >
            <Download className="w-4 h-4" />
            Export CSV
          </button>

          {/* Refresh Button */}
          <button
            onClick={fetchData}
            data-testid="analytics-refresh-btn"
            className="p-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white hover:bg-zinc-700 transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      {computedStats && (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
          <StatCard 
            icon={Activity} 
            label="Total Trades" 
            value={computedStats.totalTrades} 
            color="orange"
          />
          <StatCard 
            icon={Target} 
            label="Win Rate" 
            value={`${computedStats.winRate}%`} 
            color={parseFloat(computedStats.winRate) >= 50 ? 'green' : 'red'}
          />
          <StatCard 
            icon={TrendingUp} 
            label="Avg Win" 
            value={`+${computedStats.avgWin}%`} 
            color="green"
          />
          <StatCard 
            icon={TrendingDown} 
            label="Avg Loss" 
            value={`-${computedStats.avgLoss}%`} 
            color="red"
          />
          <StatCard 
            icon={Zap} 
            label="Profit Factor" 
            value={computedStats.profitFactor} 
            color="blue"
          />
          <StatCard 
            icon={Award} 
            label="Best Trade" 
            value={`+${computedStats.best.pnl}%`} 
            subtext={computedStats.best.symbol?.replace('/USDT', '')}
            color="green"
          />
          <StatCard 
            icon={ArrowDownRight} 
            label="Worst Trade" 
            value={`${computedStats.worst.pnl}%`} 
            subtext={computedStats.worst.symbol?.replace('/USDT', '')}
            color="red"
          />
          <StatCard 
            icon={DollarSign} 
            label="Total PnL" 
            value={`${parseFloat(computedStats.totalPnl) >= 0 ? '+' : ''}${computedStats.totalPnl}%`} 
            color={parseFloat(computedStats.totalPnl) >= 0 ? 'green' : 'red'}
          />
        </div>
      )}

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* PnL Curve */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4 md:p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-orange-400" />
            Cumulative PnL
          </h3>
          {chartData.pnlCurve.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <AreaChart data={chartData.pnlCurve}>
                <defs>
                  <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#f97316" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#f97316" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="trade" stroke="#9ca3af" fontSize={12} />
                <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={v => `${v}%`} />
                <Tooltip content={<CustomTooltip />} />
                <Area 
                  type="monotone" 
                  dataKey="pnl" 
                  name="Cumulative PnL"
                  stroke="#f97316" 
                  fill="url(#pnlGradient)" 
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-zinc-500">
              No trade data available
            </div>
          )}
        </div>

        {/* Daily Performance */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4 md:p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Calendar className="w-5 h-5 text-orange-400" />
            Daily Performance
          </h3>
          {chartData.byDay.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData.byDay}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="day" stroke="#9ca3af" fontSize={10} angle={-45} textAnchor="end" height={60} />
                <YAxis stroke="#9ca3af" fontSize={12} tickFormatter={v => `${v}%`} />
                <Tooltip content={<CustomTooltip />} />
                <Bar 
                  dataKey="pnl" 
                  name="Daily PnL"
                  radius={[4, 4, 0, 0]}
                >
                  {chartData.byDay.map((entry, index) => (
                    <Cell key={index} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-zinc-500">
              No trade data available
            </div>
          )}
        </div>

        {/* Performance by Coin */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4 md:p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Percent className="w-5 h-5 text-orange-400" />
            Performance by Coin
          </h3>
          {chartData.byCoin.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={chartData.byCoin} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis type="number" stroke="#9ca3af" fontSize={12} tickFormatter={v => `${v}%`} />
                <YAxis type="category" dataKey="coin" stroke="#9ca3af" fontSize={12} width={60} />
                <Tooltip content={<CustomTooltip />} />
                <Bar 
                  dataKey="pnl" 
                  name="Total PnL"
                  radius={[0, 4, 4, 0]}
                >
                  {chartData.byCoin.map((entry, index) => (
                    <Cell key={index} fill={entry.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-zinc-500">
              No trade data available
            </div>
          )}
        </div>

        {/* Long vs Short */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4 md:p-6">
          <h3 className="text-white font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-orange-400" />
            Long vs Short
          </h3>
          {chartData.byType.length > 0 && chartData.byType.some(t => t.trades > 0) ? (
            <div className="flex items-center justify-center h-[250px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={chartData.byType.filter(t => t.trades > 0)}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={90}
                    paddingAngle={5}
                    dataKey="trades"
                    nameKey="type"
                    label={({ type, trades }) => `${type}: ${trades}`}
                    labelLine={false}
                  >
                    <Cell fill="#22c55e" />
                    <Cell fill="#ef4444" />
                  </Pie>
                  <Tooltip content={<CustomTooltip />} />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="h-[250px] flex items-center justify-center text-zinc-500">
              No trade data available
            </div>
          )}
        </div>
      </div>

      {/* Recent Trades Table */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="flex items-center justify-between px-4 md:px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
          <h3 className="text-white font-semibold flex items-center gap-2">
            <Clock className="w-5 h-5 text-orange-400" />
            Recent Trades
          </h3>
          <span className="text-zinc-400 text-sm">{chartData.filtered?.length || 0} trades</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-zinc-900/50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Date</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Coin</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-zinc-400 uppercase">Direction</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">Entry</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">Exit</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">PnL</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-zinc-400 uppercase">Leverage</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-700/50">
              {(chartData.filtered || []).slice(-10).reverse().map((trade, i) => (
                <tr key={i} className="hover:bg-zinc-800/50 transition-colors">
                  <td className="px-4 py-3 text-sm text-zinc-300">
                    {new Date(trade.closed_at || trade.timestamp).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3 text-sm font-medium text-white">
                    {trade.symbol?.replace('/USDT', '').replace('USDT', '')}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      trade.direction === 'LONG' 
                        ? 'bg-green-500/20 text-green-400' 
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.direction === 'LONG' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      {trade.direction}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-300 text-right font-mono">
                    ${trade.entry_price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-300 text-right font-mono">
                    ${trade.exit_price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                  </td>
                  <td className={`px-4 py-3 text-sm text-right font-mono font-medium ${
                    (trade.pnl_pct || trade.pnl_percentage || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {(trade.pnl_pct || trade.pnl_percentage || 0) >= 0 ? '+' : ''}
                    {(trade.pnl_pct || trade.pnl_percentage || 0).toFixed(2)}%
                  </td>
                  <td className="px-4 py-3 text-sm text-zinc-300 text-right">
                    {trade.leverage || 1}x
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {(!chartData.filtered || chartData.filtered.length === 0) && (
            <div className="p-8 text-center text-zinc-500">
              No trades found for the selected filters
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Stat Card Component
function StatCard({ icon: Icon, label, value, subtext, color }) {
  const colorClasses = {
    orange: 'text-orange-400 bg-orange-500/10',
    green: 'text-green-400 bg-green-500/10',
    red: 'text-red-400 bg-red-500/10',
    blue: 'text-blue-400 bg-blue-500/10'
  };

  return (
    <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-3 md:p-4">
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-lg ${colorClasses[color]}`}>
          <Icon className="w-3.5 h-3.5" />
        </div>
        <span className="text-zinc-400 text-xs">{label}</span>
      </div>
      <p className={`text-lg md:text-xl font-bold ${colorClasses[color].split(' ')[0]}`}>{value}</p>
      {subtext && <p className="text-zinc-500 text-xs mt-0.5">{subtext}</p>}
    </div>
  );
}
