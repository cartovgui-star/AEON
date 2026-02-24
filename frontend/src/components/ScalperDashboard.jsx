import React, { useState, useEffect, useCallback } from 'react';
import {
  Zap, TrendingUp, TrendingDown, Activity, Clock, Target,
  Play, RefreshCw, Settings, Filter, BarChart3, Loader2,
  ArrowUpCircle, ArrowDownCircle, Minus, AlertTriangle
} from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const TIMEFRAMES = ['5m', '15m', '30m'];

function SignalBadge({ signal, strength }) {
  if (signal === 0) {
    return (
      <span className="px-2 py-1 rounded bg-zinc-700 text-zinc-400 text-xs flex items-center gap-1">
        <Minus className="w-3 h-3" /> HOLD
      </span>
    );
  }
  
  const isBuy = signal === 1;
  const strengthBars = '●'.repeat(strength) + '○'.repeat(3 - strength);
  
  return (
    <span className={`px-2 py-1 rounded text-xs flex items-center gap-1 ${
      isBuy ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
    }`}>
      {isBuy ? <ArrowUpCircle className="w-3 h-3" /> : <ArrowDownCircle className="w-3 h-3" />}
      {isBuy ? 'BUY' : 'SELL'}
      <span className="opacity-60 ml-1">{strengthBars}</span>
    </span>
  );
}

function SignalCard({ signal }) {
  if (!signal) return null;
  
  const isBuy = signal.signal === 1;
  const isSell = signal.signal === -1;
  
  return (
    <Card className={`bg-zinc-800/30 border-zinc-700/50 ${
      isBuy ? 'border-l-2 border-l-green-500' : 
      isSell ? 'border-l-2 border-l-red-500' : ''
    }`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-bold text-white">{signal.symbol?.replace('/USDT', '')}</span>
            <span className="text-xs text-zinc-500 px-1.5 py-0.5 bg-zinc-800 rounded">{signal.timeframe}</span>
          </div>
          <SignalBadge signal={signal.signal} strength={signal.strength} />
        </div>
        
        {signal.signal !== 0 && (
          <>
            <p className="text-xs text-zinc-400 mb-2">{signal.reason}</p>
            <div className="grid grid-cols-3 gap-2 text-xs">
              <div>
                <span className="text-zinc-500">Price</span>
                <p className="text-white font-medium">${signal.price?.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-zinc-500">Target</span>
                <p className="text-green-400">${signal.target?.toLocaleString()}</p>
              </div>
              <div>
                <span className="text-zinc-500">Stop</span>
                <p className="text-red-400">${signal.stop_loss?.toLocaleString()}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 mt-2 text-xs text-zinc-500">
              <span>RSI: <span className={signal.rsi > 70 ? 'text-red-400' : signal.rsi < 30 ? 'text-green-400' : 'text-zinc-300'}>{signal.rsi}</span></span>
              <span>Vol: <span className={signal.volume_ratio > 1.5 ? 'text-amber-400' : 'text-zinc-300'}>{signal.volume_ratio}x</span></span>
              <span>ROC: <span className={signal.roc > 0 ? 'text-green-400' : 'text-red-400'}>{signal.roc}%</span></span>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function BacktestResults({ results }) {
  if (!results) return null;
  
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-4 gap-3">
        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
          <p className="text-zinc-500 text-xs">Win Rate</p>
          <p className={`text-xl font-bold ${results.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
            {results.win_rate}%
          </p>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
          <p className="text-zinc-500 text-xs">Total Trades</p>
          <p className="text-xl font-bold text-white">{results.total_trades}</p>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
          <p className="text-zinc-500 text-xs">Total P&L</p>
          <p className={`text-xl font-bold ${results.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {results.total_pnl > 0 ? '+' : ''}{results.total_pnl}%
          </p>
        </div>
        <div className="bg-zinc-800/50 rounded-lg p-3 text-center">
          <p className="text-zinc-500 text-xs">Avg Bars</p>
          <p className="text-xl font-bold text-cyan-400">{results.avg_bars || 0}</p>
        </div>
      </div>
      
      {results.by_symbol && (
        <div className="bg-zinc-800/30 rounded-lg p-3">
          <p className="text-xs text-zinc-400 mb-2">Top Performers</p>
          <div className="space-y-1">
            {results.by_symbol.slice(0, 5).map((sym, idx) => (
              <div key={idx} className="flex items-center justify-between text-xs">
                <span className="text-white">{sym.symbol?.replace('/USDT', '')}</span>
                <div className="flex items-center gap-3">
                  <span className="text-zinc-400">{sym.total_trades} trades</span>
                  <span className={sym.win_rate >= 50 ? 'text-green-400' : 'text-red-400'}>
                    {sym.win_rate}% WR
                  </span>
                  <span className={sym.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                    {sym.total_pnl > 0 ? '+' : ''}{sym.total_pnl}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ScalperDashboard() {
  const [activeTab, setActiveTab] = useState('signals');
  const [timeframe, setTimeframe] = useState('5m');
  const [signals, setSignals] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [status, setStatus] = useState(null);
  const [backtestResult, setBacktestResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/scalper/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error('Scalper status error:', err);
    }
  }, []);

  const scanSignals = useCallback(async () => {
    setScanning(true);
    try {
      const res = await fetch(`${API_URL}/api/scalper/scan?timeframe=${timeframe}`);
      const data = await res.json();
      setSignals(data.signals || []);
    } catch (err) {
      console.error('Scalper scan error:', err);
    } finally {
      setScanning(false);
    }
  }, [timeframe]);

  const fetchOpportunities = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/scalper/opportunities?min_strength=2`);
      const data = await res.json();
      setOpportunities(data.opportunities || []);
    } catch (err) {
      console.error('Opportunities error:', err);
    }
  }, []);

  const runBacktest = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/scalper/backtest/all/${timeframe}?days=7`);
      const data = await res.json();
      setBacktestResult(data);
    } catch (err) {
      console.error('Backtest error:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    if (activeTab === 'signals') {
      scanSignals();
    } else if (activeTab === 'opportunities') {
      fetchOpportunities();
    }
  }, [activeTab, timeframe, scanSignals, fetchOpportunities]);

  return (
    <div className="space-y-6" data-testid="scalper-dashboard">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center">
              <Zap className="w-5 h-5 text-white" />
            </div>
            Aggressive Scalper
          </h1>
          <p className="text-zinc-500 text-sm mt-1">
            High-frequency signals • 5m/15m/30m • All 15 cryptos
          </p>
        </div>
        
        {/* Status Badge */}
        <div className="flex items-center gap-3">
          <span className={`px-3 py-1.5 rounded-full text-sm font-medium ${
            status?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
          }`}>
            {status?.enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
          <span className="text-xs text-zinc-500">
            {status?.active_signals || 0} active signals
          </span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-zinc-800 pb-2">
        {[
          { id: 'signals', label: 'Live Signals', icon: Activity },
          { id: 'opportunities', label: 'Best Opportunities', icon: Target },
          { id: 'backtest', label: 'Backtest', icon: BarChart3 },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id
                ? 'bg-purple-500/20 text-purple-400'
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
        
        {/* Timeframe Selector */}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-zinc-500">Timeframe:</span>
          {TIMEFRAMES.map(tf => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                timeframe === tf
                  ? 'bg-purple-500/20 text-purple-400 border border-purple-500/50'
                  : 'bg-zinc-800 text-zinc-400 border border-zinc-700'
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {activeTab === 'signals' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-400">
              {signals.length} signals found on {timeframe}
            </p>
            <button
              onClick={scanSignals}
              disabled={scanning}
              className="flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm text-zinc-300 transition-all"
            >
              {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Refresh
            </button>
          </div>
          
          {signals.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">
              <Activity className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No active signals on {timeframe}</p>
              <p className="text-xs mt-1">Try a different timeframe or wait for market movement</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {signals.map((sig, idx) => (
                <SignalCard key={idx} signal={sig} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'opportunities' && (
        <div className="space-y-4">
          <p className="text-sm text-zinc-400">
            Top opportunities with strength ≥ 2 across all timeframes
          </p>
          
          {opportunities.length === 0 ? (
            <div className="text-center py-12 text-zinc-500">
              <Target className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>No high-strength opportunities right now</p>
              <p className="text-xs mt-1">Markets are quiet or signals don't meet criteria</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
              {opportunities.map((opp, idx) => (
                <SignalCard key={idx} signal={opp} />
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === 'backtest' && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-zinc-400">
              Backtest scalper strategy on all 15 cryptos ({timeframe}, 7 days)
            </p>
            <button
              onClick={runBacktest}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 rounded-lg text-sm text-purple-400 transition-all"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
              Run Backtest
            </button>
          </div>
          
          {backtestResult ? (
            <BacktestResults results={backtestResult} />
          ) : (
            <div className="text-center py-12 text-zinc-500">
              <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-50" />
              <p>Click "Run Backtest" to test the scalper strategy</p>
            </div>
          )}
        </div>
      )}

      {/* Settings Summary */}
      {status && (
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-xs text-zinc-400 mb-2 flex items-center gap-2">
            <Settings className="w-3 h-3" />
            Scalper Settings
          </p>
          <div className="flex flex-wrap gap-3 text-xs">
            <span className="px-2 py-1 bg-green-500/10 text-green-400 rounded">
              Target: {status.settings_summary?.profit_target}
            </span>
            <span className="px-2 py-1 bg-red-500/10 text-red-400 rounded">
              Stop: {status.settings_summary?.stop_loss}
            </span>
            <span className="px-2 py-1 bg-amber-500/10 text-amber-400 rounded">
              Volume: {status.settings_summary?.volume_threshold}
            </span>
            <span className="px-2 py-1 bg-purple-500/10 text-purple-400 rounded">
              RSI: {status.settings_summary?.rsi_range}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
