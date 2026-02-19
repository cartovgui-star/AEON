import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, TrendingUp, TrendingDown, DollarSign, Target, 
  Play, Pause, RefreshCw, X, Settings2, Zap, Radio, BarChart3
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Simple PnL Chart Component
const PnLChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-zinc-500 text-sm">
        No trade history yet
      </div>
    );
  }

  const maxPnl = Math.max(...data.map(d => d.cumulative_pnl), 0);
  const minPnl = Math.min(...data.map(d => d.cumulative_pnl), 0);
  const range = Math.max(maxPnl - minPnl, 1);
  const height = 120;
  const width = 100;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1 || 1)) * width;
    const y = height - ((d.cumulative_pnl - minPnl) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  const isPositive = data[data.length - 1]?.cumulative_pnl >= 0;

  return (
    <div className="relative h-32">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
        {/* Zero line */}
        <line 
          x1="0" 
          y1={height - ((0 - minPnl) / range) * height} 
          x2={width} 
          y2={height - ((0 - minPnl) / range) * height} 
          stroke="#52525b" 
          strokeWidth="0.5" 
          strokeDasharray="2,2"
        />
        {/* PnL line */}
        <polyline
          fill="none"
          stroke={isPositive ? "#22c55e" : "#ef4444"}
          strokeWidth="2"
          points={points}
        />
        {/* Area fill */}
        <polygon
          fill={isPositive ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)"}
          points={`0,${height} ${points} ${width},${height}`}
        />
      </svg>
      {/* Labels */}
      <div className="absolute top-0 right-0 text-xs text-zinc-500">
        {maxPnl > 0 && `+${maxPnl.toFixed(1)}%`}
      </div>
      <div className="absolute bottom-0 right-0 text-xs text-zinc-500">
        {minPnl < 0 && `${minPnl.toFixed(1)}%`}
      </div>
    </div>
  );
};

export default function Trading() {
  const [stats, setStats] = useState(null);
  const [livePositions, setLivePositions] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [pnlHistory, setPnlHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('positions');
  const [confidence, setConfidence] = useState(70);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [showPositionModal, setShowPositionModal] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch critical data first (fast endpoints)
      const [statsRes, liveRes, closedRes, historyRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/trading/v2/live-positions`),
        fetch(`${API_URL}/api/trading/v2/closed`),
        fetch(`${API_URL}/api/trading/v2/pnl-history`)
      ]);
      
      const statsData = await statsRes.json();
      const liveData = await liveRes.json();
      const closedData = await closedRes.json();
      const historyData = await historyRes.json();
      
      // Update state with critical data immediately
      setStats(statsData);
      setLivePositions(liveData.positions || []);
      setClosedTrades(closedData.closed_trades || []);
      setPnlHistory(historyData.history || []);
      setConfidence(statsData.min_confidence || 70);
      setLoading(false);
      
      // Fetch opportunities in background (slow endpoint - can take 30-50s)
      fetch(`${API_URL}/api/trading/opportunities`)
        .then(res => res.json())
        .then(oppsData => {
          setOpportunities(Array.isArray(oppsData) ? oppsData : []);
        })
        .catch(() => {
          setOpportunities([]);
        });
        
    } catch (err) {
      console.error('Failed to fetch trading data:', err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // Refresh every 15s for live data
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

  // Calculate total live PnL
  const totalLivePnl = livePositions.reduce((sum, p) => sum + (p.pnl_pct || 0), 0);

  return (
    <div className="space-y-4 md:space-y-6" data-testid="trading-page">
      {/* Live Data Banner */}
      <div className="flex items-center gap-2 px-3 py-2 bg-green-500/10 border border-green-500/20 rounded-lg">
        <Radio className="w-4 h-4 text-green-400 animate-pulse" />
        <span className="text-green-400 text-sm font-medium">Live MEXC Data</span>
        <span className="text-zinc-400 text-xs ml-auto">Paper Trading Mode</span>
      </div>

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
              data-testid="toggle-trading-btn"
              className={`p-2 rounded-lg transition-all ${stats?.active ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-red-500/20 text-red-400 hover:bg-red-500/30'}`}
            >
              {stats?.active ? <Pause className="w-5 h-5" /> : <Play className="w-5 h-5" />}
            </button>
          </div>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Open Positions</p>
          <p className="text-lg sm:text-xl font-bold text-white">{livePositions.length}</p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Live PnL</p>
          <p className={`text-lg sm:text-xl font-bold ${totalLivePnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {totalLivePnl >= 0 ? '+' : ''}{totalLivePnl.toFixed(2)}%
          </p>
          <p className={`text-xs ${totalLivePnl >= 0 ? 'text-green-400/60' : 'text-red-400/60'}`}>
            {totalLivePnl >= 0 ? '+' : ''}${(totalLivePnl * 10).toFixed(2)} USD
          </p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Win Rate</p>
          <p className={`text-lg sm:text-xl font-bold ${(stats?.win_rate || 0) >= 50 ? 'text-green-400' : 'text-orange-400'}`}>
            {stats?.win_rate || 0}%
          </p>
        </div>

        <div className="bg-zinc-800/30 rounded-xl p-3 sm:p-4 border border-zinc-700/50 col-span-2 md:col-span-1">
          <p className="text-zinc-500 text-xs">Total Trades</p>
          <p className="text-lg sm:text-xl font-bold text-white">
            <span className="text-green-400">{stats?.wins || 0}W</span>
            <span className="text-zinc-500 mx-1">/</span>
            <span className="text-red-400">{stats?.losses || 0}L</span>
          </p>
        </div>
      </div>

      {/* PnL Chart */}
      <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-orange-400" />
            <span className="text-white text-sm font-medium">Performance</span>
          </div>
          <span className={`text-sm font-bold ${(stats?.total_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {(stats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(stats?.total_pnl_pct || 0).toFixed(2)}% Total
          </span>
        </div>
        <PnLChart data={pnlHistory} />
      </div>

      {/* Market Conditions */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-zinc-800/30 rounded-xl p-3 border border-zinc-700/50">
          <p className="text-zinc-500 text-xs">Market Regime</p>
          <p className={`font-medium ${
            stats?.market_regime === 'TRENDING_UP' || stats?.market_regime === 'TRENDING_DOWN' ? 'text-green-400' :
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
          data-testid="confidence-slider"
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
            <button 
              key={t} 
              onClick={() => setActiveTab(t)}
              data-testid={`tab-${t}`}
              className={`px-3 py-1.5 rounded-md text-xs sm:text-sm font-medium transition-all ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button 
          onClick={fetchData} 
          data-testid="refresh-btn"
          className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Live Positions Tab */}
      {activeTab === 'positions' && (
        <div className="space-y-3" data-testid="positions-list">
          {livePositions.length > 0 ? (
            livePositions.map((position, i) => {
              // Calculate USD PnL with leverage
              const positionSize = position.position_size || 1000;
              const leverage = position.leverage || 10;
              const pnlWithLeverage = position.pnl_pct * leverage;
              const pnlUsd = (pnlWithLeverage / 100) * positionSize;
              const tradeType = position.trade_type || 
                (position.timeframe === '15m' || position.timeframe === '5m' ? 'SCALP' : 
                 position.timeframe === '1h' ? 'DAY' : 'SWING');
              const margin = positionSize / leverage;
              
              return (
                <div 
                  key={position.id || i} 
                  data-testid={`position-${position.symbol?.replace('/USDT', '')}`}
                  onClick={() => {
                    setSelectedPosition(position);
                    setShowPositionModal(true);
                  }}
                  className={`bg-zinc-800/30 rounded-xl p-4 border cursor-pointer hover:border-opacity-60 transition-all ${
                    position.direction === 'LONG' ? 'border-green-500/30 hover:border-green-500/50' : 'border-red-500/30 hover:border-red-500/50'
                  }`}
                >
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-1 rounded text-xs font-bold ${
                        position.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {position.direction}
                      </span>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        tradeType === 'SCALP' ? 'bg-purple-500/20 text-purple-400' :
                        tradeType === 'DAY' ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {tradeType}
                      </span>
                      <span className="px-2 py-1 rounded text-xs font-bold bg-orange-500/20 text-orange-400">
                        {leverage}x
                      </span>
                      <span className="text-white font-medium text-lg">{position.symbol?.replace('/USDT', '')}</span>
                    </div>
                    {/* Live PnL Display */}
                    <div className="flex items-center gap-4">
                      <div className="text-right">
                        <p className={`text-lg font-bold ${pnlWithLeverage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {pnlWithLeverage >= 0 ? '+' : ''}{pnlWithLeverage.toFixed(2)}%
                        </p>
                        <p className={`text-sm ${pnlUsd >= 0 ? 'text-green-400/70' : 'text-red-400/70'}`}>
                          {pnlUsd >= 0 ? '+' : ''}${pnlUsd.toFixed(2)} USD
                        </p>
                      </div>
                      <button 
                        onClick={(e) => {
                          e.stopPropagation();
                          closeTrade(position.symbol);
                        }}
                        className="p-2 bg-red-500/20 rounded-lg text-red-400 hover:bg-red-500/30 transition-all"
                        title="Close Position"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-7 gap-3 text-sm">
                    <div>
                      <p className="text-zinc-500 text-xs">Entry</p>
                      <p className="text-white">${position.entry_price?.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Current</p>
                      <p className={position.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}>
                        ${position.current_price?.toLocaleString()}
                      </p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Stop Loss</p>
                      <p className="text-red-400">${position.stop_price?.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Target</p>
                      <p className="text-green-400">${position.target_price?.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Confidence</p>
                      <p className="text-orange-400">{position.confidence}%</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Size</p>
                      <p className="text-white">${positionSize.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-zinc-500 text-xs">Margin</p>
                      <p className="text-cyan-400 font-medium">${margin.toFixed(2)}</p>
                    </div>
                  </div>
                  {position.confirmations && position.confirmations.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-zinc-700/50">
                      <p className="text-zinc-500 text-xs">
                        {position.confirmations.slice(0, 3).join(' • ')}
                      </p>
                    </div>
                  )}
                </div>
              );
            })
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No open positions</p>
              <p className="text-zinc-600 text-sm">Aeon is scanning MEXC for opportunities...</p>
            </div>
          )}
        </div>
      )}

      {/* Opportunities Tab */}
      {activeTab === 'opportunities' && (
        <div className="space-y-3" data-testid="opportunities-list">
          {opportunities.length > 0 ? (
            opportunities.slice(0, 10).map((opp, i) => (
              <div 
                key={i} 
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  opp.direction === 'LONG' ? 'border-green-500/30' : 'border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Zap className={`w-5 h-5 ${opp.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`} />
                    <span className="text-white font-medium">{opp.symbol?.replace('/USDT', '')}</span>
                    <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                      opp.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {opp.direction}
                    </span>
                  </div>
                  <span className="text-orange-400 font-bold">{opp.confidence}%</span>
                </div>
                <div className="grid grid-cols-3 gap-4 mt-2 text-xs">
                  <div>
                    <span className="text-zinc-500">Entry:</span>
                    <span className="text-white ml-1">${opp.entry?.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Target:</span>
                    <span className="text-green-400 ml-1">${opp.target?.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Stop:</span>
                    <span className="text-red-400 ml-1">${opp.stop?.toLocaleString()}</span>
                  </div>
                </div>
                
                {/* Reasoning */}
                {opp.reasoning && (
                  <div className="mt-3 p-2 bg-zinc-900/60 rounded-lg border border-zinc-700/50">
                    <p className="text-xs text-zinc-400 font-semibold mb-1">Why {opp.direction}:</p>
                    <p className="text-xs text-zinc-300">{opp.reasoning}</p>
                  </div>
                )}
                
                {/* Confirmations */}
                {opp.confirmations && opp.confirmations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {opp.confirmations.slice(0, 4).map((conf, idx) => (
                      <span key={idx} className="text-xs px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20">
                        ✓ {conf}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Target className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No opportunities right now</p>
              <p className="text-zinc-600 text-sm">Lower confidence threshold or wait for setups</p>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-3" data-testid="history-list">
          {closedTrades.length > 0 ? (
            closedTrades.slice().reverse().map((trade, i) => (
              <div 
                key={i} 
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  (trade.pnl_pct || 0) >= 0 ? 'border-green-500/30' : 'border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>{trade.direction}</span>
                    <span className="text-white font-medium">{trade.symbol?.replace('/USDT', '')}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      (trade.pnl_pct || 0) >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.exit_reason}
                    </span>
                  </div>
                  <span className={`text-lg font-bold ${(trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-2 text-xs text-zinc-500">
                  <div>Entry: ${trade.entry_price?.toLocaleString()}</div>
                  <div>Exit: ${trade.exit_price?.toLocaleString()}</div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <DollarSign className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No trade history yet</p>
              <p className="text-zinc-600 text-sm">Completed trades will appear here</p>
            </div>
          )}
        </div>
      )}

      {/* Position Details Modal */}
      {showPositionModal && selectedPosition && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4" onClick={() => setShowPositionModal(false)}>
          <div className="bg-gradient-to-br from-zinc-900 to-zinc-800 border border-zinc-700 rounded-2xl max-w-2xl w-full shadow-2xl max-h-[90vh] overflow-hidden" onClick={(e) => e.stopPropagation()}>
            {/* Modal Header */}
            <div className={`px-6 py-4 border-b flex items-center justify-between ${
              selectedPosition.direction === 'LONG' ? 'border-green-500/30 bg-green-500/5' : 'border-red-500/30 bg-red-500/5'
            }`}>
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-xl ${
                  selectedPosition.direction === 'LONG' ? 'bg-green-500/20' : 'bg-red-500/20'
                }`}>
                  {selectedPosition.direction === 'LONG' ? (
                    <TrendingUp className="w-6 h-6 text-green-400" />
                  ) : (
                    <TrendingDown className="w-6 h-6 text-red-400" />
                  )}
                </div>
                <div>
                  <h3 className="text-white font-bold text-xl">{selectedPosition.symbol?.replace('/USDT', '')}</h3>
                  <p className="text-zinc-400 text-sm">{selectedPosition.timeframe} • {selectedPosition.trade_type || 'SWING'} Trade</p>
                </div>
                <span className={`px-3 py-1 rounded-lg font-bold ${
                  selectedPosition.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                }`}>
                  {selectedPosition.direction}
                </span>
              </div>
              <button onClick={() => setShowPositionModal(false)} className="p-2 hover:bg-zinc-700 rounded-lg text-zinc-400 hover:text-white transition-colors">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
              {/* PnL Overview */}
              <div className={`p-4 rounded-xl border ${
                (selectedPosition.pnl_pct || 0) >= 0 ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
              }`}>
                <p className="text-zinc-400 text-xs mb-1">Current P&L</p>
                <div className="flex items-baseline gap-3">
                  <span className={`text-3xl font-bold ${
                    (selectedPosition.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {((selectedPosition.pnl_pct || 0) * (selectedPosition.leverage || 10)) >= 0 ? '+' : ''}
                    {((selectedPosition.pnl_pct || 0) * (selectedPosition.leverage || 10)).toFixed(2)}%
                  </span>
                  <span className={`text-xl ${
                    (selectedPosition.pnl_pct || 0) >= 0 ? 'text-green-400/70' : 'text-red-400/70'
                  }`}>
                    ${(((selectedPosition.pnl_pct || 0) * (selectedPosition.leverage || 10) / 100) * (selectedPosition.position_size || 1000)).toFixed(2)} USD
                  </span>
                </div>
              </div>

              {/* Position Details Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-800/50 rounded-lg p-4">
                  <p className="text-zinc-500 text-xs mb-1">Entry Price</p>
                  <p className="text-white font-semibold text-lg">${selectedPosition.entry_price?.toLocaleString()}</p>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-4">
                  <p className="text-zinc-500 text-xs mb-1">Current Price</p>
                  <p className="text-white font-semibold text-lg">${selectedPosition.current_price?.toLocaleString()}</p>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-4">
                  <p className="text-zinc-500 text-xs mb-1">Position Size</p>
                  <p className="text-white font-semibold">${(selectedPosition.position_size || 1000).toLocaleString()}</p>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-4">
                  <p className="text-zinc-500 text-xs mb-1">Leverage</p>
                  <p className="text-orange-400 font-semibold">{selectedPosition.leverage || 10}x</p>
                </div>
                <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-4">
                  <p className="text-cyan-400 text-xs mb-1 font-semibold">Margin Used</p>
                  <p className="text-white font-bold text-lg">${((selectedPosition.position_size || 1000) / (selectedPosition.leverage || 10)).toFixed(2)}</p>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-4">
                  <p className="text-zinc-500 text-xs mb-1">Confidence</p>
                  <p className="text-orange-400 font-semibold">{selectedPosition.confidence || 85}%</p>
                </div>
              </div>

              {/* Targets & Stop Loss */}
              <div className="space-y-2">
                <h4 className="text-white font-semibold text-sm">Exit Strategy</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
                    <p className="text-green-400 text-xs mb-1">Take Profit</p>
                    <p className="text-white font-semibold">${selectedPosition.target_price?.toLocaleString()}</p>
                  </div>
                  <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    <p className="text-red-400 text-xs mb-1">Stop Loss</p>
                    <p className="text-white font-semibold">${selectedPosition.stop_price?.toLocaleString()}</p>
                  </div>
                </div>
                {selectedPosition.trail_stop && (
                  <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                    <p className="text-amber-400 text-xs mb-1">Trailing Stop Active</p>
                    <p className="text-white text-sm">{selectedPosition.trail_pct}% trailing</p>
                  </div>
                )}
              </div>

              {/* Confirmations */}
              {selectedPosition.confirmations && selectedPosition.confirmations.length > 0 && (
                <div>
                  <h4 className="text-white font-semibold text-sm mb-2">Trade Confirmations</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedPosition.confirmations.slice(0, 6).map((conf, idx) => (
                      <span key={idx} className="px-3 py-1.5 bg-cyan-500/10 text-cyan-400 rounded-lg text-sm border border-cyan-500/20">
                        ✓ {conf}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Time Held */}
              <div className="bg-zinc-800/50 rounded-lg p-4">
                <p className="text-zinc-500 text-xs mb-1">Time in Position</p>
                <p className="text-white font-semibold">
                  {selectedPosition.entry_time ? 
                    Math.floor((new Date() - new Date(selectedPosition.entry_time)) / (1000 * 60 * 60)) + ' hours' 
                    : 'N/A'}
                </p>
              </div>

              {/* Action Buttons */}
              <div className="flex gap-3">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    closeTrade(selectedPosition.symbol);
                    setShowPositionModal(false);
                  }}
                  data-testid="modal-close-position-btn"
                  className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-all"
                >
                  Close Position
                </button>
                <button
                  onClick={() => setShowPositionModal(false)}
                  data-testid="modal-back-btn"
                  className="px-6 py-3 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg font-medium transition-all"
                >
                  Back
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
