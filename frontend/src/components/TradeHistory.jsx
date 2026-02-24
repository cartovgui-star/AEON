import React, { useState, useEffect } from 'react';
import { 
  TrendingUp, TrendingDown, RefreshCw, X, Target, Shield, Clock, 
  Zap, Brain, ChevronRight, Filter, Download, Eye, AlertTriangle,
  CheckCircle, XCircle, Activity, BarChart3, Percent, DollarSign,
  Scale, Crosshair, TrendingUp as Trend, Info
} from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function TradeHistory() {
  const [trades, setTrades] = useState({ open: [], closed: [] });
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState('all');
  const [selectedTrade, setSelectedTrade] = useState(null);
  const [showLogicBreakdown, setShowLogicBreakdown] = useState(false);
  const [sortBy, setSortBy] = useState('date');
  const [sortOrder, setSortOrder] = useState('desc');

  useEffect(() => {
    fetchTrades();
  }, []);

  const fetchTrades = async () => {
    setLoading(true);
    try {
      const [openRes, closedRes, positionsRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/open`),
        fetch(`${API_URL}/api/trading/v2/closed`),
        fetch(`${API_URL}/api/trading/v2/live-positions`)
      ]);
      const openData = await openRes.json();
      const closedData = await closedRes.json();
      const positionsData = await positionsRes.json();
      
      // Merge open trades with live position data for current prices
      const openWithPrices = (openData.open_trades || []).map(trade => {
        const livePos = (positionsData.positions || []).find(p => p.symbol === trade.symbol);
        return {
          ...trade,
          current_price: livePos?.current_price || trade.entry_price,
          live_pnl: livePos?.pnl_pct || 0
        };
      });
      
      setTrades({
        open: openWithPrices,
        closed: closedData.closed_trades || []
      });
    } catch (err) {
      console.error('Failed to fetch trades:', err);
    }
    setLoading(false);
  };

  const allTrades = [
    ...trades.open.map(t => ({ ...t, status: 'OPEN', sort_date: new Date(t.entry_time) })),
    ...trades.closed.map(t => ({ ...t, status: 'CLOSED', sort_date: new Date(t.exit_time || t.entry_time) }))
  ].sort((a, b) => {
    if (sortBy === 'date') {
      return sortOrder === 'desc' ? b.sort_date - a.sort_date : a.sort_date - b.sort_date;
    }
    if (sortBy === 'pnl') {
      return sortOrder === 'desc' ? (b.pnl_pct || 0) - (a.pnl_pct || 0) : (a.pnl_pct || 0) - (b.pnl_pct || 0);
    }
    if (sortBy === 'symbol') {
      return sortOrder === 'desc' ? b.symbol.localeCompare(a.symbol) : a.symbol.localeCompare(b.symbol);
    }
    return 0;
  });

  const filteredTrades = allTrades.filter(t => {
    if (tab === 'open') return t.status === 'OPEN';
    if (tab === 'closed') return t.status === 'CLOSED';
    if (tab === 'winners') return t.status === 'CLOSED' && (t.pnl_pct || 0) > 0;
    if (tab === 'losers') return t.status === 'CLOSED' && (t.pnl_pct || 0) < 0;
    return true;
  });

  const stats = {
    total: trades.closed.length,
    open: trades.open.length,
    winners: trades.closed.filter(t => (t.pnl_pct || 0) > 0).length,
    losers: trades.closed.filter(t => (t.pnl_pct || 0) < 0).length,
    pnl: trades.closed.reduce((s, t) => s + (t.pnl_pct || 0), 0),
    avgWin: trades.closed.filter(t => (t.pnl_pct || 0) > 0).reduce((s, t) => s + t.pnl_pct, 0) / (trades.closed.filter(t => (t.pnl_pct || 0) > 0).length || 1),
    avgLoss: trades.closed.filter(t => (t.pnl_pct || 0) < 0).reduce((s, t) => s + t.pnl_pct, 0) / (trades.closed.filter(t => (t.pnl_pct || 0) < 0).length || 1),
    winRate: (trades.closed.filter(t => (t.pnl_pct || 0) > 0).length / (trades.closed.length || 1) * 100)
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    const d = new Date(dateStr);
    return d.toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const getTradeStyleColor = (style) => {
    if (style === 'SCALP') return 'bg-purple-500/20 text-purple-400';
    if (style === 'DAY') return 'bg-blue-500/20 text-blue-400';
    return 'bg-yellow-500/20 text-yellow-400';
  };

  return (
    <div className="space-y-6">
      {/* Stats Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-3">
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Total Closed</p>
            <p className="text-2xl font-bold text-white">{stats.total}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Open Now</p>
            <p className="text-2xl font-bold text-orange-400">{stats.open}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Winners</p>
            <p className="text-2xl font-bold text-green-400">{stats.winners}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Losers</p>
            <p className="text-2xl font-bold text-red-400">{stats.losers}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Win Rate</p>
            <p className={`text-2xl font-bold ${stats.winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.winRate.toFixed(1)}%
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Total PnL</p>
            <p className={`text-2xl font-bold ${stats.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {stats.pnl >= 0 ? '+' : ''}{stats.pnl.toFixed(1)}%
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Avg Win</p>
            <p className="text-2xl font-bold text-green-400">+{stats.avgWin.toFixed(1)}%</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <p className="text-zinc-500 text-xs">Avg Loss</p>
            <p className="text-2xl font-bold text-red-400">{stats.avgLoss.toFixed(1)}%</p>
          </CardContent>
        </Card>
      </div>

      {/* Trading Logic Button */}
      <button
        onClick={() => setShowLogicBreakdown(true)}
        className="w-full flex items-center justify-between p-4 bg-gradient-to-r from-orange-500/10 to-yellow-500/10 border border-orange-500/30 rounded-xl hover:border-orange-500/50 transition-all"
        data-testid="show-trading-logic-btn"
      >
        <div className="flex items-center gap-3">
          <Brain className="w-6 h-6 text-orange-400" />
          <div className="text-left">
            <p className="text-white font-medium">How AEON Decides to Trade</p>
            <p className="text-zinc-400 text-sm">View the complete trading logic breakdown</p>
          </div>
        </div>
        <ChevronRight className="w-5 h-5 text-orange-400" />
      </button>

      {/* Filters & Controls */}
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['all', 'open', 'closed', 'winners', 'losers'].map(t => (
            <button 
              key={t} 
              onClick={() => setTab(t)}
              className={`px-3 py-2 rounded-md text-sm font-medium transition-all ${
                tab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-2 ml-auto">
          <select 
            value={sortBy} 
            onChange={(e) => setSortBy(e.target.value)}
            className="bg-zinc-800/50 text-zinc-300 text-sm rounded-lg px-3 py-2 border border-zinc-700"
          >
            <option value="date">Sort by Date</option>
            <option value="pnl">Sort by PnL</option>
            <option value="symbol">Sort by Symbol</option>
          </select>
          <button 
            onClick={() => setSortOrder(sortOrder === 'desc' ? 'asc' : 'desc')}
            className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white border border-zinc-700"
          >
            {sortOrder === 'desc' ? '↓' : '↑'}
          </button>
          <button 
            onClick={fetchTrades} 
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white border border-zinc-700"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Trade Table */}
      <Card className="bg-zinc-800/30 border-zinc-700/50 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px]">
            <thead className="bg-zinc-800/50">
              <tr className="text-left text-xs text-zinc-500 uppercase">
                <th className="px-4 py-3">Trade ID</th>
                <th className="px-4 py-3">Symbol</th>
                <th className="px-4 py-3">Direction</th>
                <th className="px-4 py-3">Style</th>
                <th className="px-4 py-3">Entry</th>
                <th className="px-4 py-3">Leverage</th>
                <th className="px-4 py-3">Confidence</th>
                <th className="px-4 py-3">PnL</th>
                <th className="px-4 py-3">Status</th>
                <th className="px-4 py-3">Date</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-zinc-800">
              {filteredTrades.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-4 py-12 text-center text-zinc-500">
                    {loading ? 'Loading trades...' : 'No trades found'}
                  </td>
                </tr>
              ) : filteredTrades.map((trade, i) => (
                <tr 
                  key={trade.id || i} 
                  className="hover:bg-zinc-800/50 cursor-pointer transition-colors"
                  onClick={() => setSelectedTrade(trade)}
                  data-testid={`trade-row-${trade.id || i}`}
                >
                  <td className="px-4 py-3 text-zinc-400 text-sm font-mono">{trade.id || `#${i+1}`}</td>
                  <td className="px-4 py-3 font-medium text-white">{trade.symbol}</td>
                  <td className="px-4 py-3">
                    <span className={`flex items-center gap-1 ${trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                      {trade.direction === 'LONG' ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
                      {trade.direction}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getTradeStyleColor(trade.trade_type)}`}>
                      {trade.trade_type || 'SWING'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-300">${(trade.entry_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</td>
                  <td className="px-4 py-3 text-orange-400 font-medium">{trade.leverage || 10}x</td>
                  <td className="px-4 py-3">
                    <span className={`text-sm ${(trade.confidence || 0) >= 85 ? 'text-green-400' : (trade.confidence || 0) >= 75 ? 'text-yellow-400' : 'text-zinc-400'}`}>
                      {trade.confidence || 'N/A'}%
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-bold ${(trade.pnl_pct || trade.live_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {(trade.pnl_pct || trade.live_pnl || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || trade.live_pnl || 0).toFixed(2)}%
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium ${
                      trade.status === 'OPEN' ? 'bg-orange-500/20 text-orange-400' : 
                      (trade.pnl_pct || 0) >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.status === 'OPEN' ? 'OPEN' : (trade.pnl_pct || 0) >= 0 ? 'WON' : 'LOST'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-zinc-400 text-sm">{formatDate(trade.entry_time)}</td>
                  <td className="px-4 py-3">
                    <Eye className="w-4 h-4 text-zinc-500 hover:text-white" />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Trade Detail Modal */}
      {selectedTrade && (
        <TradeDetailModal 
          trade={selectedTrade} 
          onClose={() => setSelectedTrade(null)} 
        />
      )}

      {/* Trading Logic Breakdown Modal */}
      {showLogicBreakdown && (
        <TradingLogicModal onClose={() => setShowLogicBreakdown(false)} />
      )}
    </div>
  );
}

// Trade Detail Modal Component
function TradeDetailModal({ trade, onClose }) {
  const pnl = trade.pnl_pct || trade.live_pnl || 0;
  const isOpen = trade.status === 'OPEN';
  
  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div 
        className="bg-zinc-900 rounded-2xl border border-zinc-700 w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800">
          <div className="flex items-center gap-4">
            <div className={`p-3 rounded-xl ${trade.direction === 'LONG' ? 'bg-green-500/20' : 'bg-red-500/20'}`}>
              {trade.direction === 'LONG' ? 
                <TrendingUp className="w-6 h-6 text-green-400" /> : 
                <TrendingDown className="w-6 h-6 text-red-400" />
              }
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{trade.symbol}</h2>
              <div className="flex items-center gap-2 mt-1">
                <span className={`px-2 py-0.5 rounded text-xs ${trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                  {trade.direction}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs ${
                  trade.trade_type === 'SCALP' ? 'bg-purple-500/20 text-purple-400' :
                  trade.trade_type === 'DAY' ? 'bg-blue-500/20 text-blue-400' : 'bg-yellow-500/20 text-yellow-400'
                }`}>
                  {trade.trade_type || 'SWING'}
                </span>
                <span className={`px-2 py-0.5 rounded text-xs ${isOpen ? 'bg-orange-500/20 text-orange-400' : 'bg-zinc-500/20 text-zinc-400'}`}>
                  {isOpen ? 'OPEN' : 'CLOSED'}
                </span>
              </div>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-lg">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        {/* PnL Banner */}
        <div className={`p-6 ${pnl >= 0 ? 'bg-green-500/10' : 'bg-red-500/10'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-400 text-sm">Profit/Loss</p>
              <p className={`text-4xl font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}{pnl.toFixed(2)}%
              </p>
            </div>
            <div className="text-right">
              <p className="text-zinc-400 text-sm">With {trade.leverage || 10}x Leverage</p>
              <p className={`text-2xl font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                {pnl >= 0 ? '+' : ''}{(pnl * (trade.leverage || 10) / 100 * (trade.position_size || 1000)).toFixed(2)} USD
              </p>
            </div>
          </div>
        </div>

        {/* Trade Details Grid */}
        <div className="p-6 space-y-6">
          {/* Price Levels */}
          <div>
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Target className="w-4 h-4 text-orange-400" />
              Price Levels
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Entry Price</p>
                <p className="text-white font-medium">${(trade.entry_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</p>
              </div>
              {isOpen && (
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-xs">Current Price</p>
                  <p className="text-cyan-400 font-medium">${(trade.current_price || trade.entry_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</p>
                </div>
              )}
              {!isOpen && (
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-xs">Exit Price</p>
                  <p className="text-cyan-400 font-medium">${(trade.exit_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</p>
                </div>
              )}
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Stop Loss</p>
                <p className="text-red-400 font-medium">${(trade.stop_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Take Profit</p>
                <p className="text-green-400 font-medium">${(trade.target_price || 0).toLocaleString(undefined, {maximumFractionDigits: 2})}</p>
              </div>
            </div>
          </div>

          {/* Position Details */}
          <div>
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Scale className="w-4 h-4 text-orange-400" />
              Position Details
            </h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Position Size</p>
                <p className="text-white font-medium">${trade.position_size || 1000}</p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Leverage</p>
                <p className="text-orange-400 font-medium">{trade.leverage || 10}x</p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Confidence</p>
                <p className={`font-medium ${(trade.confidence || 0) >= 85 ? 'text-green-400' : 'text-yellow-400'}`}>
                  {trade.confidence || 'N/A'}%
                </p>
              </div>
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Timeframe</p>
                <p className="text-white font-medium">{trade.timeframe || '4h'}</p>
              </div>
            </div>
          </div>

          {/* Trade Timing */}
          <div>
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-400" />
              Timing
            </h3>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-zinc-800/50 rounded-lg p-3">
                <p className="text-zinc-500 text-xs">Entry Time</p>
                <p className="text-white font-medium">{trade.entry_time ? new Date(trade.entry_time).toLocaleString() : 'N/A'}</p>
              </div>
              {!isOpen && (
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-xs">Exit Time</p>
                  <p className="text-white font-medium">{trade.exit_time ? new Date(trade.exit_time).toLocaleString() : 'N/A'}</p>
                </div>
              )}
              {!isOpen && (
                <div className="bg-zinc-800/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-xs">Exit Reason</p>
                  <p className={`font-medium ${trade.exit_reason === 'TARGET' ? 'text-green-400' : trade.exit_reason === 'STOP' ? 'text-red-400' : 'text-yellow-400'}`}>
                    {trade.exit_reason || 'Manual'}
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Confirmations / Why This Trade */}
          <div>
            <h3 className="text-white font-medium mb-3 flex items-center gap-2">
              <Brain className="w-4 h-4 text-orange-400" />
              Why This Trade Was Taken
            </h3>
            <div className="bg-zinc-800/50 rounded-lg p-4">
              {trade.confirmations && trade.confirmations.length > 0 ? (
                <div className="space-y-2">
                  {trade.confirmations.map((conf, i) => (
                    <div key={i} className="flex items-center gap-2">
                      <CheckCircle className="w-4 h-4 text-green-400 flex-shrink-0" />
                      <span className="text-zinc-300 text-sm">{conf}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-zinc-500 text-sm">No confirmation data recorded</p>
              )}
            </div>
          </div>

          {/* Additional Info */}
          {(trade.atr_pct || trade.risk_reward || trade.partial_target) && (
            <div>
              <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-orange-400" />
                Additional Metrics
              </h3>
              <div className="grid grid-cols-3 gap-3">
                {trade.atr_pct && (
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs">ATR %</p>
                    <p className="text-white font-medium">{trade.atr_pct}%</p>
                  </div>
                )}
                {trade.risk_reward && (
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs">Risk:Reward</p>
                    <p className="text-white font-medium">1:{trade.risk_reward}</p>
                  </div>
                )}
                {trade.partial_target && (
                  <div className="bg-zinc-800/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs">Partial Target</p>
                    <p className="text-white font-medium">${trade.partial_target.toLocaleString()}</p>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Position Scaling Info */}
          {(trade.pending_scale_in !== undefined || trade.is_fully_scaled !== undefined) && (
            <div>
              <h3 className="text-white font-medium mb-3 flex items-center gap-2">
                <Scale className="w-4 h-4 text-orange-400" />
                Position Scaling
              </h3>
              <div className="bg-zinc-800/50 rounded-lg p-4">
                <div className="flex items-center gap-2">
                  {trade.is_fully_scaled ? (
                    <>
                      <CheckCircle className="w-4 h-4 text-green-400" />
                      <span className="text-green-400">Fully scaled into position</span>
                    </>
                  ) : trade.pending_scale_in ? (
                    <>
                      <Clock className="w-4 h-4 text-yellow-400" />
                      <span className="text-yellow-400">Awaiting scale-in confirmation (50% position)</span>
                    </>
                  ) : (
                    <>
                      <Info className="w-4 h-4 text-zinc-400" />
                      <span className="text-zinc-400">No scaling applied</span>
                    </>
                  )}
                </div>
                {trade.original_full_size && (
                  <p className="text-zinc-500 text-sm mt-2">
                    Current: ${trade.position_size} / Full: ${trade.original_full_size}
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Trading Logic Breakdown Modal
function TradingLogicModal({ onClose }) {
  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <div 
        className="bg-zinc-900 rounded-2xl border border-zinc-700 w-full max-w-4xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}
        data-testid="trading-logic-modal"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-zinc-800 sticky top-0 bg-zinc-900 z-10">
          <div className="flex items-center gap-3">
            <Brain className="w-8 h-8 text-orange-400" />
            <div>
              <h2 className="text-2xl font-bold text-white">How AEON Decides to Trade</h2>
              <p className="text-zinc-400">Complete breakdown of the trading logic</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 hover:bg-zinc-800 rounded-lg">
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        <div className="p-6 space-y-8">
          {/* Step 1: Confluence Scoring */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">1</span>
              Confluence Scoring System
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <p className="text-zinc-300 mb-4">
                Every potential trade is scored using a weighted confluence system. The bot needs multiple indicators agreeing before taking any trade.
              </p>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-zinc-900/50 rounded-lg p-4 border-l-4 border-blue-500">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-blue-400 font-bold">Core Technicals</span>
                    <span className="text-2xl font-bold text-white">60%</span>
                  </div>
                  <ul className="text-zinc-400 text-sm space-y-1">
                    <li>• RSI (14): &lt;30 buy, &gt;70 sell</li>
                    <li>• MACD crossovers + histogram</li>
                    <li>• Bollinger Band touches</li>
                    <li>• EMA stack (9/21/50)</li>
                    <li>• Stochastic crossovers</li>
                  </ul>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-4 border-l-4 border-purple-500">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-purple-400 font-bold">Market Structure</span>
                    <span className="text-2xl font-bold text-white">20%</span>
                  </div>
                  <ul className="text-zinc-400 text-sm space-y-1">
                    <li>• HH/HL (uptrend)</li>
                    <li>• LL/LH (downtrend)</li>
                    <li>• Break of Structure (BOS)</li>
                    <li>• Change of Character (CHoCH)</li>
                    <li>• Order Blocks</li>
                  </ul>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-4 border-l-4 border-green-500">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-green-400 font-bold">Derivatives</span>
                    <span className="text-2xl font-bold text-white">20%</span>
                  </div>
                  <ul className="text-zinc-400 text-sm space-y-1">
                    <li>• Funding rate extremes</li>
                    <li>• Open Interest changes</li>
                    <li>• Long/Short ratio</li>
                    <li>• CVD (buyer/seller pressure)</li>
                    <li>• Liquidation data</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>

          {/* Step 2: Entry Requirements */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">2</span>
              Entry Requirements (Must ALL Pass)
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 mb-4">
                <p className="text-green-400 font-medium">V2.1 HIGH WIN RATE MODE - All filters active</p>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">200 EMA Trend Filter (FIRST)</p>
                    <p className="text-zinc-400 text-sm">LONG only above 200 EMA, SHORT only below. Skip if within 0.5%</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">ADX &gt; 25 (Trending Market)</p>
                    <p className="text-zinc-400 text-sm">Skip ranging/choppy markets entirely</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Volume &gt; 1.5x Average</p>
                    <p className="text-zinc-400 text-sm">Signal candle must have above-average volume</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">5/5 Confirmations (ALL Agree)</p>
                    <p className="text-zinc-400 text-sm">Tech + SMC + Derivatives + Trend + Volume</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">90%+ Confidence Score</p>
                    <p className="text-zinc-400 text-sm">Raised from 80% for higher quality</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">R:R Minimum 3:1</p>
                    <p className="text-zinc-400 text-sm">Raised from 2:1 for better risk/reward</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">RSI Agrees With Trend</p>
                    <p className="text-zinc-400 text-sm">No counter-trend RSI signals allowed</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <CheckCircle className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Session Filter (SCALP/DAY)</p>
                    <p className="text-zinc-400 text-sm">London (3-12 EST) or NY (8-17 EST) only</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Step 3: Trade Style Selection */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">3</span>
              Dynamic Trade Style Selection
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <p className="text-zinc-300 mb-4">
                Trade style is determined by ATR (Average True Range) volatility percentage:
              </p>
              <div className="grid md:grid-cols-3 gap-4">
                <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Zap className="w-5 h-5 text-purple-400" />
                    <span className="text-purple-400 font-bold">SCALP</span>
                  </div>
                  <p className="text-zinc-300 text-sm mb-2">High Volatility (ATR &gt; 2%)</p>
                  <ul className="text-zinc-400 text-xs space-y-1">
                    <li>• Timeframes: 5m, 15m</li>
                    <li>• Leverage: 50-200x</li>
                    <li>• Hold: Minutes to hours</li>
                  </ul>
                </div>
                <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Activity className="w-5 h-5 text-blue-400" />
                    <span className="text-blue-400 font-bold">DAY</span>
                  </div>
                  <p className="text-zinc-300 text-sm mb-2">Medium Volatility (ATR 1-2%)</p>
                  <ul className="text-zinc-400 text-xs space-y-1">
                    <li>• Timeframes: 1h, 4h</li>
                    <li>• Leverage: 20-75x</li>
                    <li>• Hold: Hours to 24h</li>
                  </ul>
                </div>
                <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Trend className="w-5 h-5 text-yellow-400" />
                    <span className="text-yellow-400 font-bold">SWING</span>
                  </div>
                  <p className="text-zinc-300 text-sm mb-2">Low Volatility (ATR &lt; 1%)</p>
                  <ul className="text-zinc-400 text-xs space-y-1">
                    <li>• Timeframes: 4h, 1d</li>
                    <li>• Leverage: 10-25x</li>
                    <li>• Hold: Days to weeks</li>
                  </ul>
                </div>
              </div>
            </div>
          </section>

          {/* Step 4: Position Sizing */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">4</span>
              Position Sizing (Kelly Criterion)
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <div className="bg-zinc-900/50 rounded-lg p-4 mb-4 font-mono text-center">
                <p className="text-zinc-400 text-sm mb-2">Kelly Formula</p>
                <p className="text-xl text-white">f = (p × b - q) / b</p>
                <p className="text-zinc-500 text-xs mt-2">where p = win prob, q = loss prob, b = win/loss ratio</p>
              </div>
              <div className="grid md:grid-cols-4 gap-4 text-center">
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-400 text-xs">Minimum</p>
                  <p className="text-white font-bold text-xl">$500</p>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-400 text-xs">Base</p>
                  <p className="text-white font-bold text-xl">$1,000</p>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-400 text-xs">Maximum</p>
                  <p className="text-white font-bold text-xl">$2,500</p>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-400 text-xs">Risk/Trade</p>
                  <p className="text-red-400 font-bold text-xl">1% Max</p>
                </div>
              </div>
              <div className="mt-4 p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg">
                <p className="text-cyan-400 font-medium mb-2">Position Scaling (50/50) - V2.1 Improved</p>
                <ul className="text-zinc-300 text-sm space-y-1">
                  <li>• Initial entry: 50% on signal</li>
                  <li>• Scale-in: 50% only when +0.5% profitable (raised from 0.3%)</li>
                  <li>• Timeout: Scale-in cancelled after 2 hours if not triggered</li>
                </ul>
              </div>
            </div>
          </section>

          {/* Step 5: Exit Strategy */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">5</span>
              Exit Strategy (Exit Intelligence)
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <div className="space-y-4">
                <div className="flex items-start gap-3">
                  <Target className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-green-400 font-medium">Take Profit</p>
                    <p className="text-zinc-400 text-sm">Primary target hit (calculated from ATR and R:R ratio)</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Shield className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="text-red-400 font-medium">Stop Loss</p>
                    <p className="text-zinc-400 text-sm">ATR-based stop to limit downside</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <TrendingUp className="w-5 h-5 text-yellow-400 mt-0.5" />
                  <div>
                    <p className="text-yellow-400 font-medium">Trailing Stop</p>
                    <p className="text-zinc-400 text-sm">Moves to breakeven at +1% profit, then trails</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <Activity className="w-5 h-5 text-purple-400 mt-0.5" />
                  <div>
                    <p className="text-purple-400 font-medium">Momentum Exit</p>
                    <p className="text-zinc-400 text-sm">Early exit if RSI diverges while in profit (momentum fading)</p>
                  </div>
                </div>
                <div className="flex items-start gap-3">
                  <DollarSign className="w-5 h-5 text-cyan-400 mt-0.5" />
                  <div>
                    <p className="text-cyan-400 font-medium">Partial Take Profit</p>
                    <p className="text-zinc-400 text-sm">50% closed at partial target, rest runs to full target</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Step 6: Risk Management */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4 flex items-center gap-2">
              <span className="w-8 h-8 rounded-full bg-orange-500 flex items-center justify-center text-white font-bold">6</span>
              Risk Management Rules
            </h3>
            <div className="bg-zinc-800/50 rounded-xl p-6">
              <div className="grid md:grid-cols-2 gap-4">
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <AlertTriangle className="w-5 h-5 text-yellow-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Auto-Blacklist</p>
                    <p className="text-zinc-400 text-sm">Pairs with &lt;30% win rate after 10 trades are blacklisted automatically</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Clock className="w-5 h-5 text-orange-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Loss Cooldown</p>
                    <p className="text-zinc-400 text-sm">4-hour cooldown on a pair after a losing trade</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Crosshair className="w-5 h-5 text-red-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Max 5 Positions</p>
                    <p className="text-zinc-400 text-sm">Reduced from 15 for higher quality focus</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Percent className="w-5 h-5 text-green-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">90%+ Confidence Only</p>
                    <p className="text-zinc-400 text-sm">Raised from 80% - quality over quantity</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Target className="w-5 h-5 text-blue-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">Smart Stop Loss</p>
                    <p className="text-zinc-400 text-sm">Placed at support/resistance levels, bounded 1-2x ATR</p>
                  </div>
                </div>
                <div className="flex items-start gap-3 p-3 bg-zinc-900/50 rounded-lg">
                  <Activity className="w-5 h-5 text-purple-400 mt-0.5" />
                  <div>
                    <p className="text-white font-medium">ADX Trending Filter</p>
                    <p className="text-zinc-400 text-sm">Only trade when ADX &gt; 25 (no ranging markets)</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          {/* Summary Flow */}
          <section>
            <h3 className="text-xl font-bold text-white mb-4">Trade Decision Flow</h3>
            <div className="bg-gradient-to-r from-orange-500/10 to-yellow-500/10 border border-orange-500/30 rounded-xl p-6">
              <div className="flex flex-wrap items-center justify-center gap-2 text-sm">
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Scan 25 Pairs</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Calculate Confluence</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Check 80% Confidence</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Verify R:R 2:1</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Check Blacklist/Cooldown</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Determine Style (ATR)</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-zinc-800 rounded-full text-zinc-300">Calculate Size (Kelly)</span>
                <ChevronRight className="w-4 h-4 text-orange-400" />
                <span className="px-3 py-1 bg-green-500/20 rounded-full text-green-400 font-medium">Execute Trade</span>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
