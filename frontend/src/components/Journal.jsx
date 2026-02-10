import React, { useState, useEffect } from 'react';
import { BookOpen, TrendingUp, TrendingDown, Award, Brain, RefreshCw, Plus, X } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Journal() {
  const [stats, setStats] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [recentTrades, setRecentTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('stats');
  const [showLogForm, setShowLogForm] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const statsRes = await fetch(`${API_URL}/api/memory/journal/stats?days=30`);
      const patternsRes = await fetch(`${API_URL}/api/memory/journal/patterns?min_trades=1`);
      const tradesRes = await fetch(`${API_URL}/api/memory/journal/trades?limit=10`);
      
      setStats(await statsRes.json());
      setPatterns(await patternsRes.json());
      setRecentTrades(await tradesRes.json());
    } catch (err) {
      console.error('Failed to fetch:', err);
    }
    setLoading(false);
  };

  return (
    <div className="space-y-4 md:space-y-6" data-testid="journal-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['stats', 'trades'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-md text-xs sm:text-sm font-medium transition-all ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-2">
          <button 
            onClick={() => setShowLogForm(true)}
            className="flex items-center gap-2 px-3 py-2 bg-green-500/20 rounded-lg text-green-400 hover:bg-green-500/30 text-sm"
          >
            <Plus className="w-4 h-4" />
            <span className="hidden sm:inline">Log Trade</span>
          </button>
          <button onClick={fetchData} className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Stats Tab */}
      {activeTab === 'stats' && stats && (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <p className="text-zinc-500 text-xs">Total Trades</p>
              <p className="text-xl sm:text-2xl font-bold text-white">{stats.total_trades || 0}</p>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <p className="text-zinc-500 text-xs">Win Rate</p>
              <p className={`text-xl sm:text-2xl font-bold ${stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.win_rate || 0}%
              </p>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <p className="text-zinc-500 text-xs">Total PnL</p>
              <p className={`text-xl sm:text-2xl font-bold ${stats.total_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.total_pnl_pct >= 0 ? '+' : ''}{stats.total_pnl_pct || 0}%
              </p>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <p className="text-zinc-500 text-xs">Profit Factor</p>
              <p className={`text-xl sm:text-2xl font-bold ${stats.profit_factor >= 1 ? 'text-green-400' : 'text-red-400'}`}>
                {stats.profit_factor || 0}
              </p>
            </div>
          </div>

          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <h3 className="text-white font-medium mb-3">Win/Loss Breakdown</h3>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-zinc-400">Wins</span>
                  <span className="text-green-400">{stats.wins || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Losses</span>
                  <span className="text-red-400">{stats.losses || 0}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Avg Win</span>
                  <span className="text-green-400">+{stats.average_win || 0}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-zinc-400">Avg Loss</span>
                  <span className="text-red-400">-{stats.average_loss || 0}%</span>
                </div>
              </div>
            </div>

            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <h3 className="text-white font-medium mb-3">Best Patterns</h3>
              {patterns && patterns.length > 0 ? (
                <div className="space-y-2">
                  {patterns.slice(0, 3).map((p, i) => (
                    <div key={i} className="bg-zinc-900/50 rounded-lg p-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-white">{p.setup_type || 'Unknown'}</span>
                        <span className="text-green-400">{p.win_rate}% WR</span>
                      </div>
                      <p className="text-zinc-500 text-xs">{p.timeframe} - {p.total_trades} trades</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-zinc-500 text-sm">Log more trades to see patterns</p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Trades Tab */}
      {activeTab === 'trades' && (
        <div className="space-y-3">
          {recentTrades && recentTrades.length > 0 ? (
            recentTrades.map((trade, i) => (
              <div 
                key={trade._id || i}
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  trade.result === 'WIN' ? 'border-green-500/30' : 'border-red-500/30'
                }`}
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.direction}
                    </span>
                    <span className="text-white font-medium">{trade.symbol?.replace('/USDT', '')}</span>
                    <span className="text-zinc-500 text-xs">{trade.timeframe}</span>
                  </div>
                  <span className={`text-lg font-bold ${trade.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {trade.pnl_pct >= 0 ? '+' : ''}{trade.pnl_pct}%
                  </span>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <BookOpen className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No trades logged yet</p>
            </div>
          )}
        </div>
      )}

      {/* Log Trade Modal */}
      {showLogForm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 rounded-xl p-4 sm:p-6 w-full max-w-md border border-zinc-700">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-white font-medium text-lg">Log Trade</h3>
              <button onClick={() => setShowLogForm(false)} className="text-zinc-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <p className="text-zinc-500 text-sm">Trade logging form coming soon...</p>
            <button
              onClick={() => setShowLogForm(false)}
              className="mt-4 w-full px-4 py-2 bg-zinc-800 rounded-lg text-zinc-400"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
