import React, { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Play, TrendingUp, TrendingDown, Check, X,
  Loader2, Trophy, RefreshCw, Settings, Filter, BarChart3,
  Clock, Target, Shield, Zap, Activity, Layers, Sliders
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend, LineChart, Line
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SYMBOLS = [
  { value: 'BTC/USDT', label: 'BTC' },
  { value: 'ETH/USDT', label: 'ETH' },
  { value: 'SOL/USDT', label: 'SOL' },
  { value: 'BNB/USDT', label: 'BNB' },
  { value: 'XRP/USDT', label: 'XRP' },
  { value: 'DOGE/USDT', label: 'DOGE' },
  { value: 'ADA/USDT', label: 'ADA' },
  { value: 'AVAX/USDT', label: 'AVAX' },
];

const TIMEFRAMES = [
  { value: '15m', label: '15 Min' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: '1 Day' },
];

const DAYS_OPTIONS = [7, 14, 30, 60, 90];

const CONFIDENCE_LEVELS = [65, 70, 75, 80, 85, 90];

const TEST_MODES = [
  { id: 'standard', label: 'Standard Test', icon: FlaskConical },
  { id: 'confidence', label: 'Confidence Range', icon: Sliders },
  { id: 'timeframe', label: 'Multi-Timeframe', icon: Layers },
];

const FILTER_COLORS = {
  ema_200: '#f59e0b',
  adx: '#8b5cf6',
  volume: '#06b6d4',
  session: '#22c55e',
  rsi_counter_trend: '#ef4444',
  confidence: '#ec4899',
  rr: '#3b82f6',
};

function StatCard({ label, value, subtitle, color, icon: Icon }) {
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-zinc-500 text-xs uppercase tracking-wider">{label}</span>
        {Icon && <Icon className={`w-4 h-4 ${color || 'text-zinc-400'}`} />}
      </div>
      <p className={`text-2xl font-bold ${color || 'text-white'}`}>{value}</p>
      {subtitle && <p className="text-xs text-zinc-500 mt-1">{subtitle}</p>}
    </div>
  );
}

function WinRateGauge({ winRate, oldWinRate }) {
  const improvement = winRate - oldWinRate;
  const isPositive = improvement > 0;
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4">Win Rate Comparison</h3>
      <div className="flex items-center justify-center gap-8">
        <div className="text-center">
          <p className="text-3xl font-bold text-red-400">{oldWinRate}%</p>
          <p className="text-xs text-zinc-500 mt-1">Old Strategy</p>
        </div>
        <div className="flex items-center">
          <TrendingUp className={`w-8 h-8 ${isPositive ? 'text-green-400' : 'text-red-400'}`} />
        </div>
        <div className="text-center">
          <p className="text-3xl font-bold text-green-400">{winRate}%</p>
          <p className="text-xs text-zinc-500 mt-1">V2.1 Strategy</p>
        </div>
      </div>
      <div className={`mt-4 text-center ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
        <span className="text-lg font-semibold">
          {isPositive ? '+' : ''}{improvement.toFixed(1)}% improvement
        </span>
      </div>
    </div>
  );
}

function FilterEffectivenessChart({ filterBreakdown }) {
  if (!filterBreakdown) return null;
  
  const data = Object.entries(filterBreakdown)
    .filter(([_, value]) => value > 0)
    .map(([key, value]) => ({
      name: key.replace(/_/g, ' ').toUpperCase(),
      value,
      fill: FILTER_COLORS[key] || '#71717a'
    }));
  
  if (data.length === 0) return null;
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <Filter className="w-4 h-4" />
        Filter Effectiveness
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            innerRadius={60}
            outerRadius={90}
            paddingAngle={2}
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.fill} />
            ))}
          </Pie>
          <Legend 
            verticalAlign="bottom" 
            height={36}
            formatter={(value) => <span className="text-xs text-zinc-400">{value}</span>}
          />
          <Tooltip 
            contentStyle={{ 
              background: '#18181b', 
              border: '1px solid #3f3f46', 
              borderRadius: '8px' 
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs">
        {data.map((item) => (
          <div key={item.name} className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.fill }} />
            <span className="text-zinc-400">{item.name}: {item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function SymbolResults({ results }) {
  if (!results || results.length === 0) return null;
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <BarChart3 className="w-4 h-4" />
        Results by Symbol
      </h3>
      <div className="space-y-4">
        {results.map((result, idx) => {
          const trades = result.trades || [];
          const wins = trades.filter(t => t.outcome === 'WIN').length;
          const total = trades.length;
          const winRate = total > 0 ? ((wins / total) * 100).toFixed(1) : 0;
          
          return (
            <div key={idx} className="border-b border-zinc-800 pb-4 last:border-0">
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-white">{result.symbol}</span>
                <span className={`text-sm font-medium ${Number(winRate) >= 50 ? 'text-green-400' : 'text-red-400'}`}>
                  {winRate}% WR
                </span>
              </div>
              <div className="grid grid-cols-4 gap-2 text-xs">
                <div>
                  <span className="text-zinc-500">Candles</span>
                  <p className="text-white">{result.total_candles || 0}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Old Signals</span>
                  <p className="text-orange-400">{result.old_signals || 0}</p>
                </div>
                <div>
                  <span className="text-zinc-500">V2.1 Signals</span>
                  <p className="text-green-400">{result.new_signals || 0}</p>
                </div>
                <div>
                  <span className="text-zinc-500">Trades</span>
                  <p className="text-white">{total} ({wins}W/{total - wins}L)</p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecentTradesTable({ trades }) {
  if (!trades || trades.length === 0) return null;
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <Activity className="w-4 h-4" />
        Recent Simulated Trades
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-zinc-500 border-b border-zinc-800">
              <th className="text-left py-2 px-2">Symbol</th>
              <th className="text-left py-2 px-2">Dir</th>
              <th className="text-right py-2 px-2">Entry</th>
              <th className="text-right py-2 px-2">Stop</th>
              <th className="text-right py-2 px-2">Target</th>
              <th className="text-right py-2 px-2">R:R</th>
              <th className="text-right py-2 px-2">Conf</th>
              <th className="text-center py-2 px-2">Result</th>
            </tr>
          </thead>
          <tbody>
            {trades.slice(0, 15).map((trade, idx) => {
              const isWin = trade.outcome === 'WIN';
              return (
                <tr key={idx} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                  <td className="py-2 px-2 text-zinc-300">{trade.symbol?.replace('/USDT', '') || 'N/A'}</td>
                  <td className="py-2 px-2">
                    <span className={trade.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}>
                      {trade.direction}
                    </span>
                  </td>
                  <td className="text-right py-2 px-2 text-zinc-300">${trade.entry?.toLocaleString()}</td>
                  <td className="text-right py-2 px-2 text-red-400">${trade.stop?.toLocaleString()}</td>
                  <td className="text-right py-2 px-2 text-green-400">${trade.target?.toLocaleString()}</td>
                  <td className="text-right py-2 px-2 text-zinc-300">{trade.rr_ratio?.toFixed(1)}:1</td>
                  <td className="text-right py-2 px-2 text-amber-400">{trade.confidence}%</td>
                  <td className="text-center py-2 px-2">
                    {isWin ? (
                      <span className="px-2 py-1 rounded bg-green-500/20 text-green-400">WIN</span>
                    ) : (
                      <span className="px-2 py-1 rounded bg-red-500/20 text-red-400">LOSS</span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function V21SettingsDisplay({ settings }) {
  if (!settings) return null;
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <Settings className="w-4 h-4" />
        V2.1 HIGH WIN RATE Settings
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
        <div className="flex items-center gap-2">
          <Target className="w-4 h-4 text-amber-400" />
          <span className="text-zinc-400">Min Confidence:</span>
          <span className="text-white font-medium">{settings.min_confidence}%</span>
        </div>
        <div className="flex items-center gap-2">
          <Check className="w-4 h-4 text-green-400" />
          <span className="text-zinc-400">Min Confirmations:</span>
          <span className="text-white font-medium">{settings.min_confirmations}/5</span>
        </div>
        <div className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-blue-400" />
          <span className="text-zinc-400">Min R:R:</span>
          <span className="text-white font-medium">{settings.min_rr_ratio}:1</span>
        </div>
        <div className="flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-purple-400" />
          <span className="text-zinc-400">EMA Zone:</span>
          <span className="text-white font-medium">{settings.ema_no_trade_zone_pct}%</span>
        </div>
        <div className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-cyan-400" />
          <span className="text-zinc-400">Min ADX:</span>
          <span className="text-white font-medium">{settings.min_adx}</span>
        </div>
        <div className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-pink-400" />
          <span className="text-zinc-400">Volume Mult:</span>
          <span className="text-white font-medium">{settings.min_volume_multiplier}x</span>
        </div>
      </div>
    </div>
  );
}

function Recommendations({ recommendations }) {
  if (!recommendations || recommendations.length === 0) return null;
  
  return (
    <div className="bg-zinc-900/50 border border-amber-500/30 rounded-xl p-6">
      <h3 className="text-sm font-medium text-amber-400 mb-4 flex items-center gap-2">
        <Trophy className="w-4 h-4" />
        Recommendations
      </h3>
      <div className="space-y-2">
        {recommendations.map((rec, idx) => (
          <p key={idx} className="text-sm text-zinc-300">{rec}</p>
        ))}
      </div>
    </div>
  );
}

function ConfidenceRangeChart({ results }) {
  if (!results || results.length === 0) return null;
  
  const chartData = results.map(r => ({
    confidence: `${r.confidence_level}%`,
    winRate: r.win_rate,
    trades: r.total_trades
  }));
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <Sliders className="w-4 h-4" />
        Win Rate by Confidence Level
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
          <XAxis dataKey="confidence" stroke="#71717a" fontSize={12} />
          <YAxis stroke="#71717a" fontSize={12} />
          <Tooltip 
            contentStyle={{ 
              background: '#18181b', 
              border: '1px solid #3f3f46', 
              borderRadius: '8px' 
            }}
            formatter={(value, name) => [
              name === 'winRate' ? `${value}%` : value,
              name === 'winRate' ? 'Win Rate' : 'Trades'
            ]}
          />
          <Bar dataKey="winRate" fill="#f59e0b" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {results.map((r, idx) => (
          <div key={idx} className="text-center p-2 bg-zinc-800/50 rounded-lg">
            <p className="text-amber-400 font-bold">{r.confidence_level}%</p>
            <p className="text-xs text-zinc-400">{r.win_rate}% WR | {r.total_trades} trades</p>
          </div>
        ))}
      </div>
    </div>
  );
}

function TimeframeComparisonChart({ results }) {
  if (!results || results.length === 0) return null;
  
  const chartData = results.map(r => ({
    timeframe: r.timeframe,
    winRate: r.win_rate,
    trades: r.total_trades
  }));
  
  return (
    <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-6">
      <h3 className="text-sm font-medium text-zinc-400 mb-4 flex items-center gap-2">
        <Layers className="w-4 h-4" />
        Win Rate by Timeframe
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
          <XAxis dataKey="timeframe" stroke="#71717a" fontSize={12} />
          <YAxis stroke="#71717a" fontSize={12} />
          <Tooltip 
            contentStyle={{ 
              background: '#18181b', 
              border: '1px solid #3f3f46', 
              borderRadius: '8px' 
            }}
            formatter={(value, name) => [
              name === 'winRate' ? `${value}%` : value,
              name === 'winRate' ? 'Win Rate' : 'Trades'
            ]}
          />
          <Bar dataKey="winRate" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
      <div className="mt-4 grid grid-cols-3 gap-2">
        {results.map((r, idx) => (
          <div key={idx} className="text-center p-2 bg-zinc-800/50 rounded-lg">
            <p className="text-purple-400 font-bold">{r.timeframe}</p>
            <p className="text-xs text-zinc-400">{r.win_rate}% WR | {r.total_trades} trades</p>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function BacktestV21() {
  const [selectedSymbols, setSelectedSymbols] = useState(['BTC/USDT', 'ETH/USDT', 'SOL/USDT']);
  const [timeframe, setTimeframe] = useState('1h');
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [polling, setPolling] = useState(false);
  const [testMode, setTestMode] = useState('standard');
  const [confidenceResult, setConfidenceResult] = useState(null);
  const [timeframeResult, setTimeframeResult] = useState(null);

  const toggleSymbol = (symbol) => {
    if (selectedSymbols.includes(symbol)) {
      if (selectedSymbols.length > 1) {
        setSelectedSymbols(selectedSymbols.filter(s => s !== symbol));
      }
    } else {
      setSelectedSymbols([...selectedSymbols, symbol]);
    }
  };

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    
    try {
      if (testMode === 'standard') {
        // Standard backtest
        const response = await fetch(`${API_URL}/api/backtest/v21/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            symbols: selectedSymbols,
            interval: timeframe,
            days: days
          })
        });
        
        const data = await response.json();
        
        if (data.status === 'started' || data.status === 'already_running') {
          setPolling(true);
        }
      } else if (testMode === 'confidence') {
        // Multi-confidence backtest (65-90%)
        const response = await fetch(`${API_URL}/api/backtest/v21/confidence-range?days=${days}`);
        const data = await response.json();
        
        if (data.status === 'success') {
          setConfidenceResult(data);
        } else {
          setError(data.message || 'Confidence range test failed');
        }
        setLoading(false);
      } else if (testMode === 'timeframe') {
        // Multi-timeframe backtest
        const response = await fetch(`${API_URL}/api/backtest/v21/timeframe-comparison?days=${days}&confidence=75`);
        const data = await response.json();
        
        if (data.status === 'success') {
          setTimeframeResult(data);
        } else {
          setError(data.message || 'Timeframe comparison failed');
        }
        setLoading(false);
      }
    } catch (err) {
      setError('Failed to start backtest');
      setLoading(false);
    }
  };

  const checkStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_URL}/api/backtest/v21/status`);
      const data = await response.json();
      setStatus(data);
      
      if (!data.is_running && data.has_result) {
        // Fetch results
        const resultResponse = await fetch(`${API_URL}/api/backtest/v21/result`);
        const resultData = await resultResponse.json();
        
        if (resultData.status === 'success') {
          setResult(resultData.result);
        }
        
        setPolling(false);
        setLoading(false);
      } else if (!data.is_running && data.error) {
        setError(data.error);
        setPolling(false);
        setLoading(false);
      }
    } catch (err) {
      console.error('Status check failed:', err);
    }
  }, []);

  useEffect(() => {
    let interval;
    if (polling) {
      interval = setInterval(checkStatus, 2000);
    }
    return () => clearInterval(interval);
  }, [polling, checkStatus]);

  // Load any existing result on mount
  useEffect(() => {
    const loadExisting = async () => {
      try {
        const response = await fetch(`${API_URL}/api/backtest/v21/result`);
        const data = await response.json();
        if (data.status === 'success') {
          setResult(data.result);
        }
      } catch (err) {
        console.error('Failed to load existing result:', err);
      }
    };
    loadExisting();
  }, []);

  return (
    <div className="space-y-6" data-testid="backtest-v21-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <FlaskConical className="w-5 h-5 text-white" />
            </div>
            V2.1 Strategy Backtest
          </h1>
          <p className="text-zinc-500 text-sm mt-1">
            Test HIGH WIN RATE filters against MEXC historical data
          </p>
        </div>
        {result && (
          <div className="text-right">
            <p className="text-xs text-zinc-500">Last run</p>
            <p className="text-sm text-zinc-400">
              {new Date(result.timestamp).toLocaleString()}
            </p>
          </div>
        )}
      </div>

      {/* Configuration Panel */}
      <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-2xl p-6 space-y-5" data-testid="backtest-v21-config">
        {/* Test Mode Selector */}
        <div>
          <label className="block text-xs text-zinc-400 mb-3">Test Mode</label>
          <div className="flex gap-2">
            {TEST_MODES.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setTestMode(id)}
                data-testid={`test-mode-${id}`}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  testMode === id
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50'
                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600'
                }`}
              >
                <Icon className="w-4 h-4" />
                {label}
              </button>
            ))}
          </div>
          <p className="text-xs text-zinc-500 mt-2">
            {testMode === 'standard' && 'Run standard backtest with current settings'}
            {testMode === 'confidence' && 'Test confidence levels 65-90% to find optimal threshold'}
            {testMode === 'timeframe' && 'Compare performance across 15m, 1h, 4h timeframes'}
          </p>
        </div>

        {/* Symbol Selection (shown for all modes) */}
        <div>
          <label className="block text-xs text-zinc-400 mb-3">Select Symbols (MEXC)</label>
          <div className="flex flex-wrap gap-2">
            {SYMBOLS.map(({ value, label }) => (
              <button
                key={value}
                onClick={() => toggleSymbol(value)}
                data-testid={`symbol-${label.toLowerCase()}`}
                className={`px-4 py-2 rounded-xl text-sm font-medium transition-all ${
                  selectedSymbols.includes(value)
                    ? 'bg-amber-500/20 text-amber-400 border border-amber-500/50'
                    : 'bg-zinc-800 text-zinc-400 border border-zinc-700 hover:border-zinc-600'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        {/* Timeframe & Days (conditional based on mode) */}
        <div className="grid grid-cols-2 gap-4">
          {testMode === 'standard' && (
            <div>
              <label className="block text-xs text-zinc-400 mb-2">Timeframe</label>
              <select
                value={timeframe}
                onChange={(e) => setTimeframe(e.target.value)}
                data-testid="backtest-v21-timeframe"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 focus:outline-none"
              >
                {TIMEFRAMES.map(tf => (
                  <option key={tf.value} value={tf.value}>{tf.label}</option>
                ))}
              </select>
            </div>
          )}
          <div className={testMode !== 'standard' ? 'col-span-2' : ''}>
            <label className="block text-xs text-zinc-400 mb-2">Period</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              data-testid="backtest-v21-days"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 focus:outline-none"
            >
              {DAYS_OPTIONS.map(d => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </div>
        </div>
            <label className="block text-xs text-zinc-400 mb-2">Period</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              data-testid="backtest-v21-days"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-amber-500 focus:outline-none"
            >
              {DAYS_OPTIONS.map(d => (
                <option key={d} value={d}>{d} days</option>
              ))}
            </select>
          </div>
        </div>

        {/* Run Button */}
        <button
          onClick={runBacktest}
          disabled={loading || selectedSymbols.length === 0}
          data-testid="run-backtest-v21-btn"
          className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 disabled:opacity-40 rounded-xl text-white font-semibold transition-all flex items-center justify-center gap-2 shadow-lg shadow-amber-500/20"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Running Backtest... {status?.progress || 0}%
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Run V2.1 Backtest
            </>
          )}
        </button>

        {/* Progress indicator */}
        {loading && status && (
          <div className="w-full bg-zinc-800 rounded-full h-2 overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-amber-500 to-orange-500 transition-all duration-300"
              style={{ width: `${status.progress || 0}%` }}
            />
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm flex items-center gap-2">
          <X className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div className="space-y-6" data-testid="backtest-v21-results">
          {/* Key Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <StatCard
              label="Win Rate"
              value={`${result.win_rate}%`}
              subtitle={`${result.improvement > 0 ? '+' : ''}${result.improvement}% vs old`}
              color={result.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}
              icon={TrendingUp}
            />
            <StatCard
              label="Total Trades"
              value={result.total_trades}
              subtitle={`${result.wins}W / ${result.losses}L`}
              color="text-white"
              icon={Activity}
            />
            <StatCard
              label="Signal Reduction"
              value={`${result.signal_reduction_pct}%`}
              subtitle={`${result.old_signals} → ${result.new_signals}`}
              color="text-cyan-400"
              icon={Filter}
            />
            <StatCard
              label="Data Source"
              value="MEXC"
              subtitle={`${result.days} days, ${result.interval}`}
              color="text-purple-400"
              icon={Clock}
            />
          </div>

          {/* Win Rate Comparison */}
          <WinRateGauge winRate={result.win_rate} oldWinRate={result.old_win_rate} />

          {/* V2.1 Settings Display */}
          <V21SettingsDisplay settings={result.settings} />

          {/* Charts & Details Row */}
          <div className="grid md:grid-cols-2 gap-6">
            <FilterEffectivenessChart filterBreakdown={result.filter_breakdown} />
            <SymbolResults results={result.results_by_symbol} />
          </div>

          {/* Recent Trades */}
          <RecentTradesTable trades={result.recent_trades} />

          {/* Recommendations */}
          <Recommendations recommendations={result.recommendations} />
        </div>
      )}
    </div>
  );
}
