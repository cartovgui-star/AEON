import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Activity, Target, Award, PieChart } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Analytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
    const interval = setInterval(fetchAnalytics, 60000);
    return () => clearInterval(interval);
  }, []);

  const fetchAnalytics = async () => {
    try {
      const [statsRes, closedRes, freeWillRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/trading/v2/closed`),
        fetch(`${API_URL}/api/freewill/stats`)
      ]);
      
      const stats = await statsRes.json();
      const closed = await closedRes.json();
      const freeWill = await freeWillRes.json();
      
      const trades = closed.closed_trades || [];
      const winners = trades.filter(t => (t.pnl_pct || 0) > 0);
      const losers = trades.filter(t => (t.pnl_pct || 0) < 0);
      
      setData({
        ...stats,
        totalTrades: trades.length,
        winCount: winners.length,
        lossCount: losers.length,
        winRate: trades.length > 0 ? (winners.length / trades.length * 100).toFixed(1) : 0,
        totalPnl: trades.reduce((sum, t) => sum + (t.pnl_pct || 0), 0),
        avgWin: winners.length > 0 ? (winners.reduce((s, t) => s + (t.pnl_pct || 0), 0) / winners.length) : 0,
        avgLoss: losers.length > 0 ? (losers.reduce((s, t) => s + (t.pnl_pct || 0), 0) / losers.length) : 0,
        bestTrade: trades.length > 0 ? Math.max(...trades.map(t => t.pnl_pct || 0)) : 0,
        worstTrade: trades.length > 0 ? Math.min(...trades.map(t => t.pnl_pct || 0)) : 0,
        profitFactor: losers.length > 0 && winners.length > 0 
          ? Math.abs(winners.reduce((s, t) => s + (t.pnl_pct || 0), 0) / losers.reduce((s, t) => s + (t.pnl_pct || 0), 0))
          : 0,
        freeWillAlerts: freeWill.alerts_sent_today || 0,
        signalsAnalyzed: stats.total_signals_analyzed || 0,
        trades: trades.slice(-20).reverse()
      });
    } catch (err) {
      console.error('Failed to fetch analytics:', err);
    }
    setLoading(false);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  const pnlColor = (data?.totalPnl || 0) >= 0 ? 'text-green-400' : 'text-red-400';

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-zinc-500 text-sm">Win Rate</p>
              <p className="text-3xl font-bold mt-1 text-green-400">{data?.winRate || 0}%</p>
              <p className="text-xs text-zinc-600 mt-1">{data?.winCount || 0}W / {data?.lossCount || 0}L</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-800">
              <Target className="w-6 h-6 text-green-400" />
            </div>
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-zinc-500 text-sm">Total PnL</p>
              <p className={`text-3xl font-bold mt-1 ${pnlColor}`}>
                {(data?.totalPnl || 0) >= 0 ? '+' : ''}{(data?.totalPnl || 0).toFixed(2)}%
              </p>
              <p className="text-xs text-zinc-600 mt-1">{data?.totalTrades || 0} trades</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-800">
              <TrendingUp className={`w-6 h-6 ${pnlColor}`} />
            </div>
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-zinc-500 text-sm">Profit Factor</p>
              <p className="text-3xl font-bold mt-1 text-orange-400">{(data?.profitFactor || 0).toFixed(2)}</p>
              <p className="text-xs text-zinc-600 mt-1">Gross profit / loss</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-800">
              <Award className="w-6 h-6 text-orange-400" />
            </div>
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-zinc-500 text-sm">Signals Analyzed</p>
              <p className="text-3xl font-bold mt-1 text-blue-400">{(data?.signalsAnalyzed || 0).toLocaleString()}</p>
              <p className="text-xs text-zinc-600 mt-1">By v2 engine</p>
            </div>
            <div className="p-3 rounded-lg bg-zinc-800">
              <Activity className="w-6 h-6 text-blue-400" />
            </div>
          </div>
        </div>
      </div>

      {/* Performance Details */}
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <PieChart className="w-5 h-5 text-orange-400" />
            Performance Breakdown
          </h3>
          
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Average Win</span>
              <span className="text-green-400 font-semibold">+{(data?.avgWin || 0).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Average Loss</span>
              <span className="text-red-400 font-semibold">{(data?.avgLoss || 0).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Best Trade</span>
              <span className="text-green-400 font-semibold">+{(data?.bestTrade || 0).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Worst Trade</span>
              <span className="text-red-400 font-semibold">{(data?.worstTrade || 0).toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-zinc-400">Expectancy</span>
              <span className={`font-semibold ${(data?.expectancy || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {(data?.expectancy || 0) >= 0 ? '+' : ''}{(data?.expectancy || 0).toFixed(2)}%
              </span>
            </div>
          </div>
          
          <div className="mt-6">
            <div className="flex justify-between text-sm text-zinc-500 mb-2">
              <span>Wins: {data?.winCount || 0}</span>
              <span>Losses: {data?.lossCount || 0}</span>
            </div>
            <div className="h-4 bg-zinc-700 rounded-full overflow-hidden flex">
              <div 
                className="h-full bg-green-500 transition-all"
                style={{ width: `${data?.totalTrades > 0 ? (data.winCount / data.totalTrades * 100) : 50}%` }}
              />
              <div 
                className="h-full bg-red-500 transition-all"
                style={{ width: `${data?.totalTrades > 0 ? (data.lossCount / data.totalTrades * 100) : 50}%` }}
              />
            </div>
          </div>
        </div>

        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-orange-400" />
            Recent Trades PnL
          </h3>
          
          {data?.trades?.length > 0 ? (
            <div className="flex items-end gap-1 h-40">
              {data.trades.map((trade, i) => {
                const pnl = trade.pnl_pct || 0;
                const maxPnl = Math.max(...data.trades.map(t => Math.abs(t.pnl_pct || 0)), 5);
                const height = Math.abs(pnl) / maxPnl * 100;
                
                return (
                  <div key={i} className="flex-1 flex flex-col items-center justify-end h-full">
                    <div
                      className={`w-full rounded-t transition-all ${pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ height: `${Math.max(height, 5)}%` }}
                      title={`${trade.symbol}: ${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}%`}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="h-40 flex items-center justify-center text-zinc-500">
              No trades yet
            </div>
          )}
          
          <div className="mt-4 flex justify-between text-xs text-zinc-600">
            <span>Oldest</span>
            <span>Last 20 Trades</span>
            <span>Newest</span>
          </div>
        </div>
      </div>

      {/* System Status */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-6">
        <h3 className="text-lg font-semibold text-white mb-4">System Status</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${data?.active ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <div>
              <p className="text-sm text-white">Auto Trader</p>
              <p className="text-xs text-zinc-500">{data?.active ? 'Active' : 'Paused'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
            <div>
              <p className="text-sm text-white">Free Will</p>
              <p className="text-xs text-zinc-500">{data?.freeWillAlerts || 0} alerts today</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-orange-500" />
            <div>
              <p className="text-sm text-white">Market Regime</p>
              <p className="text-xs text-zinc-500">{data?.market_regime || 'Unknown'}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full bg-blue-500" />
            <div>
              <p className="text-sm text-white">BTC Bias</p>
              <p className="text-xs text-zinc-500">{data?.btc_bias || 'Neutral'}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
