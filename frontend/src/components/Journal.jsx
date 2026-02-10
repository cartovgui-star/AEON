import React, { useState, useEffect, useCallback } from 'react';
import { BookOpen, TrendingUp, TrendingDown, Award, AlertTriangle, Brain, RefreshCw, Plus } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Journal() {
  const [stats, setStats] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [insights, setInsights] = useState(null);
  const [recentTrades, setRecentTrades] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('stats');
  const [showLogForm, setShowLogForm] = useState(false);
  const [tradeForm, setTradeForm] = useState({
    symbol: 'BTC/USDT',
    direction: 'LONG',
    entry_price: '',
    exit_price: '',
    pnl_pct: '',
    strategy: 'breakout',
    timeframe: '4h',
    setup_type: 'range_breakout',
    confidence: 75,
    notes: ''
  });

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, patternsRes, insightsRes, tradesRes] = await Promise.all([
        fetch(`${API_URL}/api/memory/journal/stats?days=30`),
        fetch(`${API_URL}/api/memory/journal/patterns?min_trades=1`),
        fetch(`${API_URL}/api/memory/insights`),
        fetch(`${API_URL}/api/memory/journal/trades?limit=10`)
      ]);
      
      setStats(await statsRes.json());
      setPatterns(await patternsRes.json());
      setInsights(await insightsRes.json());
      setRecentTrades(await tradesRes.json());
    } catch (err) {
      console.error('Failed to fetch journal data:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleLogTrade = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${API_URL}/api/memory/journal/log`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ...tradeForm,
          entry_price: parseFloat(tradeForm.entry_price),
          exit_price: parseFloat(tradeForm.exit_price),
          pnl_pct: parseFloat(tradeForm.pnl_pct)
        })
      });
      
      if (res.ok) {
        setShowLogForm(false);
        setTradeForm({
          symbol: 'BTC/USDT',
          direction: 'LONG',
          entry_price: '',
          exit_price: '',
          pnl_pct: '',
          strategy: 'breakout',
          timeframe: '4h',
          setup_type: 'range_breakout',
          confidence: 75,
          notes: ''
        });
        fetchData();
      }
    } catch (err) {
      console.error('Failed to log trade:', err);
    }
  };

  const generateInsights = async () => {
    try {
      const res = await fetch(`${API_URL}/api/memory/insights/generate`, { method: 'POST' });
      const data = await res.json();
      setInsights(data);
    } catch (err) {
      console.error('Failed to generate insights:', err);
    }
  };

  return (
    <div className="space-y-4 md:space-y-6" data-testid="journal-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['stats', 'trades', 'insights'].map(t => (
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
          {/* Stats Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 sm:gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs">Total Trades</p>
                  <p className="text-xl sm:text-2xl font-bold text-white">{stats.total_trades || 0}</p>
                </div>
                <BookOpen className="w-6 h-6 sm:w-8 sm:h-8 text-blue-400" />
              </div>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs">Win Rate</p>
                  <p className={`text-xl sm:text-2xl font-bold ${stats.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                    {stats.win_rate || 0}%
                  </p>
                </div>
                <Award className="w-6 h-6 sm:w-8 sm:h-8 text-yellow-400" />
              </div>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs">Total PnL</p>
                  <p className={`text-xl sm:text-2xl font-bold ${stats.total_pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {stats.total_pnl_pct >= 0 ? '+' : ''}{stats.total_pnl_pct || 0}%
                  </p>
                </div>
                {stats.total_pnl_pct >= 0 ? 
                  <TrendingUp className="w-6 h-6 sm:w-8 sm:h-8 text-green-400" /> :
                  <TrendingDown className="w-6 h-6 sm:w-8 sm:h-8 text-red-400" />
                }
              </div>
            </div>
            
            <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs">Profit Factor</p>
                  <p className={`text-xl sm:text-2xl font-bold ${stats.profit_factor >= 1 ? 'text-green-400' : 'text-red-400'}`}>
                    {stats.profit_factor || 0}
                  </p>
                </div>
                <Brain className="w-6 h-6 sm:w-8 sm:h-8 text-purple-400" />
              </div>
            </div>
          </div>

          {/* Win/Loss Breakdown */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <h3 className="text-white font-medium mb-3">Win/Loss Breakdown</h3>
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Wins</span>
                  <span className="text-green-400 font-medium">{stats.wins || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Losses</span>
                  <span className="text-red-400 font-medium">{stats.losses || 0}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Avg Win</span>
                  <span className="text-green-400 font-medium">+{stats.average_win || 0}%</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-zinc-400">Avg Loss</span>
                  <span className="text-red-400 font-medium">-{stats.average_loss || 0}%</span>
                </div>
              </div>
            </div>

            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <h3 className="text-white font-medium mb-3">Best Patterns</h3>
              {patterns && patterns.length > 0 ? (
                <div className="space-y-2">
                  {patterns.slice(0, 3).map((p, i) => (
                    <div key={i} className="bg-zinc-900/50 rounded-lg p-2 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="text-white">{p.setup_type || 'Unknown'}</span>
                        <span className="text-green-400">{p.win_rate}% WR</span>
                      </div>
                      <p className="text-zinc-500 text-xs">{p.timeframe} • {p.total_trades} trades</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-zinc-500 text-sm">Log more trades to see patterns</p>
              )}
            </div>
          </div>

          {/* Best/Worst Trade */}
          {(stats.best_trade || stats.worst_trade) && (
            <div className="grid md:grid-cols-2 gap-4">
              {stats.best_trade && (
                <div className="bg-green-500/10 rounded-xl p-4 border border-green-500/30">
                  <h3 className="text-green-400 font-medium mb-2">🏆 Best Trade</h3>
                  <p className="text-white text-lg font-bold">{stats.best_trade.symbol?.replace('/USDT', '')}</p>
                  <p className="text-green-400">+{stats.best_trade.pnl_pct}%</p>
                  <p className="text-zinc-500 text-xs">{stats.best_trade.strategy}</p>
                </div>
              )}
              {stats.worst_trade && (
                <div className="bg-red-500/10 rounded-xl p-4 border border-red-500/30">
                  <h3 className="text-red-400 font-medium mb-2">💀 Worst Trade</h3>
                  <p className="text-white text-lg font-bold">{stats.worst_trade.symbol?.replace('/USDT', '')}</p>
                  <p className="text-red-400">{stats.worst_trade.pnl_pct}%</p>
                  <p className="text-zinc-500 text-xs">{stats.worst_trade.strategy}</p>
                </div>
              )}
            </div>
          )}
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
                <div className="flex flex-wrap gap-4 mt-2 text-sm text-zinc-400">
                  <span>Entry: ${trade.entry_price?.toLocaleString()}</span>
                  <span>Exit: ${trade.exit_price?.toLocaleString()}</span>
                  <span>Strategy: {trade.strategy}</span>
                </div>
                {trade.notes && (
                  <p className="text-zinc-500 text-xs mt-2 italic">{trade.notes}</p>
                )}
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <BookOpen className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No trades logged yet</p>
              <button 
                onClick={() => setShowLogForm(true)}
                className="mt-3 px-4 py-2 bg-orange-500/20 rounded-lg text-orange-400 text-sm"
              >
                Log your first trade
              </button>
            </div>
          )}
        </div>
      )}

      {/* Insights Tab */}
      {activeTab === 'insights' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-medium">AI Trading Insights</h3>
            <button 
              onClick={generateInsights}
              className="flex items-center gap-2 px-3 py-2 bg-purple-500/20 rounded-lg text-purple-400 text-sm"
            >
              <Brain className="w-4 h-4" />
              Generate New
            </button>
          </div>
          
          {insights?.insights && insights.insights.length > 0 ? (
            <div className="space-y-3">
              {insights.insights.map((insight, i) => (
                <div 
                  key={i}
                  className={`rounded-xl p-4 border ${
                    insight.type === 'POSITIVE' ? 'bg-green-500/10 border-green-500/30' :
                    insight.type === 'WARNING' ? 'bg-yellow-500/10 border-yellow-500/30' :
                    'bg-blue-500/10 border-blue-500/30'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    {insight.type === 'POSITIVE' ? (
                      <TrendingUp className="w-5 h-5 text-green-400 flex-shrink-0 mt-0.5" />
                    ) : insight.type === 'WARNING' ? (
                      <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                    ) : (
                      <Brain className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
                    )}
                    <p className="text-zinc-300 text-sm">{insight.message}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No insights available</p>
              <p className="text-zinc-600 text-sm">Log more trades to generate insights</p>
            </div>
          )}
        </div>
      )}

      {/* Log Trade Modal */}
      {showLogForm && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 rounded-xl p-4 sm:p-6 w-full max-w-md max-h-[90vh] overflow-y-auto border border-zinc-700">
            <h3 className="text-white font-medium text-lg mb-4">Log Trade</h3>
            <form onSubmit={handleLogTrade} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 text-xs">Symbol</label>
                  <select
                    value={tradeForm.symbol}
                    onChange={(e) => setTradeForm({...tradeForm, symbol: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    {['BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 text-xs">Direction</label>
                  <select
                    value={tradeForm.direction}
                    onChange={(e) => setTradeForm({...tradeForm, direction: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    <option value="LONG">LONG</option>
                    <option value="SHORT">SHORT</option>
                  </select>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 text-xs">Entry Price</label>
                  <input
                    type="number"
                    value={tradeForm.entry_price}
                    onChange={(e) => setTradeForm({...tradeForm, entry_price: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                    placeholder="65000"
                    required
                  />
                </div>
                <div>
                  <label className="text-zinc-400 text-xs">Exit Price</label>
                  <input
                    type="number"
                    value={tradeForm.exit_price}
                    onChange={(e) => setTradeForm({...tradeForm, exit_price: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                    placeholder="67000"
                    required
                  />
                </div>
              </div>
              
              <div>
                <label className="text-zinc-400 text-xs">PnL %</label>
                <input
                  type="number"
                  step="0.01"
                  value={tradeForm.pnl_pct}
                  onChange={(e) => setTradeForm({...tradeForm, pnl_pct: e.target.value})}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="3.5"
                  required
                />
              </div>
              
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-zinc-400 text-xs">Strategy</label>
                  <select
                    value={tradeForm.strategy}
                    onChange={(e) => setTradeForm({...tradeForm, strategy: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    {['breakout', 'pullback', 'reversal', 'smc', 'scalp'].map(s => (
                      <option key={s} value={s}>{s}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="text-zinc-400 text-xs">Timeframe</label>
                  <select
                    value={tradeForm.timeframe}
                    onChange={(e) => setTradeForm({...tradeForm, timeframe: e.target.value})}
                    className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    {['15m', '1h', '4h', '1d'].map(tf => (
                      <option key={tf} value={tf}>{tf}</option>
                    ))}
                  </select>
                </div>
              </div>
              
              <div>
                <label className="text-zinc-400 text-xs">Notes (optional)</label>
                <textarea
                  value={tradeForm.notes}
                  onChange={(e) => setTradeForm({...tradeForm, notes: e.target.value})}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
                  rows={2}
                  placeholder="Trade notes..."
                />
              </div>
              
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => setShowLogForm(false)}
                  className="flex-1 px-4 py-2 bg-zinc-800 rounded-lg text-zinc-400"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-orange-500 rounded-lg text-white font-medium"
                >
                  Log Trade
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
