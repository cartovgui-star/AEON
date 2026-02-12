import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, TrendingUp, TrendingDown, DollarSign, Target, 
  AlertTriangle, Play, Pause, RefreshCw, X, Settings2, Zap
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Trading() {
  const [stats, setStats] = useState(null);
  const [openTrades, setOpenTrades] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('positions');
  const [confidence, setConfidence] = useState(75);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, openRes, closedRes, oppsRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/trading/v2/open`),
        fetch(`${API_URL}/api/trading/v2/closed`),
        fetch(`${API_URL}/api/trading/opportunities`)
      ]);
      
      // Check response status
      if (!statsRes.ok) console.error('Stats fetch failed:', statsRes.status);
      if (!openRes.ok) console.error('Open trades fetch failed:', openRes.status);
      
      const statsData = await statsRes.json();
      const openData = await openRes.json();
      const closedData = await closedRes.json();
      const oppsData = await oppsRes.json();
      
      console.log('Trading data loaded:', { stats: statsData?.active, open: openData?.total_open });
      
      setStats(statsData);
      setOpenTrades(openData.open_trades || []);
      setClosedTrades(closedData.closed_trades || []);
      setOpportunities(oppsData || []);
      setConfidence(statsData.min_confidence || 75);
    } catch (err) {
      console.error('Failed to fetch trading data:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleTrading = async () => {
    try {
      const newState = !stats?.active;
      await fetch(`${API_URL}/api/trading/toggle?active=${newState}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  };

  const updateConfidence = async (val) => {
    try {
      await fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${val}`, { method: 'POST' });
      setConfidence(val);
    } catch (err) {
      console.error('Update confidence failed:', err);
    }
  };

  const closeTrade = async (symbol) => {
    try {
      const cleanSymbol = symbol.replace('/USDT', '');
      await fetch(`${API_URL}/api/trading/v2/close/${cleanSymbol}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Close trade failed:', err);
    }
  };

  return (
    <div className="space-y-4 md:space-y-6" data-testid="trading-page">
      {/* Header Stats */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-500 text-xs">Status</p>
              <p className={`text-lg sm:text-xl font-bold ${stats?.active ? 'text-green-400' : 'text-red-400'}`}>
                {stats?.active ? 'ACTIVE' : 'PAUSED'}
              </p>
            </div>
            <button 
              onClick={toggleTrading}
              className={`p-2 rounded-lg ${stats?.active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}
            >
              {stats?.active ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Open Trades</p>
          <p className="text-lg sm:text-xl font-bold text-white">{stats?.open_trades || 0}</p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Win Rate</p>
          <p className={`text-lg sm:text-xl font-bold ${(stats?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
            {stats?.win_rate || 0}%
          </p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Total PnL</p>
          <p className={`text-lg sm:text-xl font-bold ${(stats?.total_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(stats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(stats?.total_pnl_pct || 0).toFixed(2)}%
          </p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Trades</p>
          <p className="text-lg sm:text-xl font-bold text-white">
            {stats?.wins || 0}W / {stats?.losses || 0}L
          </p>
        </div>
      </div>

      {/* Market Conditions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-zinc-800/30 rounded-xl p-3 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Market Regime</p>
          <p className={`font-medium ${
            stats?.market_regime === 'TRENDING' ? 'text-green-400' :
            stats?.market_regime === 'VOLATILE' ? 'text-orange-400' : 'text-zinc-400'
          }`}>{stats?.market_regime || 'UNKNOWN'}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-3 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">BTC Bias</p>
          <p className={`font-medium ${
            stats?.btc_bias === 'BULLISH' ? 'text-green-400' :
            stats?.btc_bias === 'BEARISH' ? 'text-red-400' : 'text-zinc-400'
          }`}>{stats?.btc_bias || 'NEUTRAL'}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-3 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Fear & Greed</p>
          <p className={`font-medium ${
            (stats?.fear_greed || 50) < 30 ? 'text-red-400' :
            (stats?.fear_greed || 50) > 70 ? 'text-green-400' : 'text-orange-400'
          }`}>{stats?.fear_greed || 50}</p>
        </div>
        <div className="bg-zinc-800/30 rounded-xl p-3 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Session</p>
          <p className="font-medium text-white">{stats?.current_session || 'UNKNOWN'}</p>
        </div>
      </div>

      {/* Confidence Slider */}
      <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-orange-400" />
            <span className="text-white text-sm font-medium">Min Confidence</span>
          </div>
          <span className="text-orange-400 font-bold">{confidence}%</span>
        </div>
        <input
          type="range"
          min="60"
          max="95"
          value={confidence}
          onChange={(e) => setConfidence(parseInt(e.target.value))}
          onMouseUp={(e) => updateConfidence(parseInt(e.target.value))}
          onTouchEnd={(e) => updateConfidence(parseInt(e.target.value))}
          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
        />
        <div className="flex justify-between text-xs text-zinc-500 mt-1">
          <span>More trades (60%)</span>
          <span>Elite only (95%)</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['positions', 'opportunities', 'history'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button onClick={fetchData} className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Open Positions Tab */}
      {activeTab === 'positions' && (
        <div className="space-y-3">
          {openTrades.length > 0 ? (
            openTrades.map((trade, i) => (
              <div key={i} className={`bg-zinc-800/30 rounded-xl p-4 border ${
                trade.direction === 'LONG' ? 'border-green-500/30' : 'border-red-500/30'
              }`}>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.direction}
                    </span>
                    <span className="text-white font-medium text-lg">{trade.symbol?.replace('/USDT', '')}</span>
                  </div>
                  <button 
                    onClick={() => closeTrade(trade.symbol)}
                    className="p-2 bg-red-500/20 rounded-lg text-red-400 hover:bg-red-500/30"
                    title="Close Position"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                  <div>
                    <p className="text-zinc-500 text-xs">Entry</p>
                    <p className="text-white">${trade.entry_price?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 text-xs">Stop Loss</p>
                    <p className="text-red-400">${trade.stop_loss?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 text-xs">Take Profit</p>
                    <p className="text-green-400">${trade.take_profit?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 text-xs">Confidence</p>
                    <p className="text-orange-400">{trade.confidence}%</p>
                  </div>
                </div>
                {trade.reason && (
                  <p className="text-zinc-500 text-xs mt-2 border-t border-zinc-700/50 pt-2">{trade.reason}</p>
                )}
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No open positions</p>
              <p className="text-zinc-600 text-sm">Aeon is scanning for opportunities...</p>
            </div>
          )}
        </div>
      )}

      {/* Opportunities Tab */}
      {activeTab === 'opportunities' && (
        <div className="space-y-3">
          {opportunities.length > 0 ? (
            opportunities.map((opp, i) => (
              <div key={i} className={`bg-zinc-800/30 rounded-xl p-4 border ${
                opp.direction === 'LONG' ? 'border-green-500/30' : 'border-red-500/30'
              }`}>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Zap className={`w-5 h-5 ${opp.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`} />
                    <span className="text-white font-medium">{opp.symbol?.replace('/USDT', '')}</span>
                    <span className={`text-xs ${opp.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                      {opp.direction}
                    </span>
                  </div>
                  <span className="text-orange-400 font-bold">{opp.confidence}%</span>
                </div>
                <p className="text-zinc-400 text-sm">{opp.reason}</p>
                <div className="flex gap-4 mt-2 text-xs text-zinc-500">
                  <span>Entry: ${opp.entry?.toLocaleString()}</span>
                  <span>Target: ${opp.target?.toLocaleString()}</span>
                  <span>{opp.confirmations} confirmations</span>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Target className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No opportunities right now</p>
              <p className="text-zinc-600 text-sm">Try lowering the confidence threshold or wait for better setups</p>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-3">
          {closedTrades.length > 0 ? (
            closedTrades.slice().reverse().map((trade, i) => (
              <div key={i} className={`bg-zinc-800/30 rounded-xl p-4 border ${
                (trade.pnl_pct || 0) >= 0 ? 'border-green-500/30' : 'border-red-500/30'
              }`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>{trade.direction}</span>
                    <span className="text-white font-medium">{trade.symbol?.replace('/USDT', '')}</span>
                  </div>
                  <span className={`text-lg font-bold ${(trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                  </span>
                </div>
                <div className="flex gap-4 mt-2 text-xs text-zinc-500">
                  <span>Entry: ${trade.entry_price?.toLocaleString()}</span>
                  <span>Exit: ${trade.exit_price?.toLocaleString()}</span>
                  <span>{trade.exit_reason}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <DollarSign className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No trade history yet</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
