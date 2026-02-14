import React, { useState } from 'react';
import {
  FlaskConical, Play, BarChart3, TrendingUp, TrendingDown,
  Activity, Target, AlertTriangle, Clock, Loader2, ArrowUpRight,
  ArrowDownRight, Trophy, Skull, Minus
} from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LINK', 'DOT'];
const TIMEFRAMES = [
  { value: '15m', label: '15min' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: '1 Day' }
];
const STRATEGIES = [
  { value: 'compare', label: 'Compare All', desc: 'Test all 3 strategies' },
  { value: 'rsi', label: 'RSI Mean Reversion', desc: 'Buy oversold, sell overbought' },
  { value: 'bb', label: 'Bollinger Bands', desc: 'Trade band touches' },
  { value: 'ema', label: 'EMA Crossover', desc: 'Fast/slow EMA cross signals' }
];
const DAYS_OPTIONS = [7, 14, 30, 60, 90];

export default function Backtesting() {
  const [symbol, setSymbol] = useState('BTC');
  const [timeframe, setTimeframe] = useState('1h');
  const [strategy, setStrategy] = useState('compare');
  const [days, setDays] = useState(30);
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Strategy params
  const [rsiOversold, setRsiOversold] = useState(30);
  const [rsiOverbought, setRsiOverbought] = useState(70);
  const [stopPct, setStopPct] = useState(2.0);
  const [targetPct, setTargetPct] = useState(4.0);
  const [emaFast, setEmaFast] = useState(9);
  const [emaSlow, setEmaSlow] = useState(21);

  const runBacktest = async () => {
    setLoading(true);
    setError(null);
    setResults(null);
    try {
      let url;
      if (strategy === 'compare') {
        url = `${API_URL}/api/backtest/compare/${symbol}?timeframe=${timeframe}&days=${days}`;
      } else if (strategy === 'rsi') {
        url = `${API_URL}/api/backtest/rsi/${symbol}?timeframe=${timeframe}&days=${days}&oversold=${rsiOversold}&overbought=${rsiOverbought}&stop_pct=${stopPct}&target_pct=${targetPct}`;
      } else if (strategy === 'bb') {
        url = `${API_URL}/api/backtest/bb/${symbol}?timeframe=${timeframe}&days=${days}&stop_pct=${stopPct}&target_pct=${targetPct}`;
      } else if (strategy === 'ema') {
        url = `${API_URL}/api/backtest/ema/${symbol}?timeframe=${timeframe}&days=${days}&fast=${emaFast}&slow=${emaSlow}&stop_pct=${stopPct}`;
      }
      const res = await fetch(url);
      const data = await res.json();

      if (strategy === 'compare') {
        setResults({ type: 'compare', data });
      } else {
        setResults({ type: 'single', data });
      }
    } catch (err) {
      setError('Failed to run backtest. Try again.');
      console.error('Backtest error:', err);
    }
    setLoading(false);
  };

  // Build equity curve from trades
  const getEquityCurve = (trades) => {
    if (!trades?.length) return [];
    let cumPnl = 0;
    return trades.map((t, i) => {
      cumPnl += t.pnl_pct || 0;
      return { trade: i + 1, pnl: parseFloat(cumPnl.toFixed(2)), result: t.result };
    });
  };

  const renderStrategyResult = (data, highlight = false) => {
    if (!data || data.error) {
      return (
        <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-6 text-center">
          <p className="text-zinc-500 text-sm">{data?.error || 'No data'}</p>
        </div>
      );
    }

    const equityCurve = getEquityCurve(data.trades || []);
    const isProfit = (data.total_pnl_pct || 0) >= 0;

    return (
      <div className={`bg-zinc-800/30 border rounded-2xl overflow-hidden ${
        highlight ? 'border-orange-500/40 ring-1 ring-orange-500/20' : 'border-zinc-700/50'
      }`}>
        {/* Strategy Header */}
        <div className={`px-6 py-4 border-b ${highlight ? 'border-orange-500/20 bg-orange-500/5' : 'border-zinc-800'}`}>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-white flex items-center gap-2">
                {data.strategy}
                {highlight && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 font-medium">
                    BEST
                  </span>
                )}
              </h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                {data.symbol?.replace('/USDT', '')} / {data.timeframe}
              </p>
            </div>
            <div className={`text-right ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
              <p className="text-xl font-bold">{isProfit ? '+' : ''}{data.total_pnl_pct}%</p>
              <p className="text-xs opacity-70">Total PnL</p>
            </div>
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-px bg-zinc-800/50">
          <StatBox label="Trades" value={data.total_trades} />
          <StatBox label="Win Rate" value={`${data.win_rate}%`} color={data.win_rate >= 50 ? 'text-green-400' : 'text-red-400'} />
          <StatBox label="Profit Factor" value={data.profit_factor} color={data.profit_factor >= 1 ? 'text-green-400' : 'text-red-400'} />
          <StatBox label="Max DD" value={`-${data.max_drawdown_pct}%`} color="text-red-400" />
        </div>

        <div className="grid grid-cols-4 gap-px bg-zinc-800/50">
          <StatBox label="Avg Win" value={`+${data.avg_win_pct}%`} color="text-green-400" />
          <StatBox label="Avg Loss" value={`${data.avg_loss_pct}%`} color="text-red-400" />
          <StatBox label="Best" value={`+${data.best_trade_pct}%`} color="text-green-400" />
          <StatBox label="Worst" value={`${data.worst_trade_pct}%`} color="text-red-400" />
        </div>

        {/* Equity Curve */}
        {equityCurve.length > 1 && (
          <div className="px-4 pt-4 pb-2">
            <p className="text-xs text-zinc-500 mb-2 px-2">Equity Curve (Cumulative PnL %)</p>
            <ResponsiveContainer width="100%" height={140}>
              <AreaChart data={equityCurve}>
                <defs>
                  <linearGradient id={`grad-${data.strategy}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={isProfit ? '#22c55e' : '#ef4444'} stopOpacity={0.3} />
                    <stop offset="100%" stopColor={isProfit ? '#22c55e' : '#ef4444'} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="trade" tick={{ fill: '#71717a', fontSize: 10 }} />
                <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={v => `${v}%`} />
                <Tooltip
                  contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: '8px' }}
                  labelStyle={{ color: '#a1a1aa' }}
                  formatter={(v) => [`${v}%`, 'PnL']}
                />
                <Area
                  type="monotone"
                  dataKey="pnl"
                  stroke={isProfit ? '#22c55e' : '#ef4444'}
                  fill={`url(#grad-${data.strategy})`}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Recent Trades */}
        {data.trades?.length > 0 && (
          <div className="px-4 pb-4">
            <p className="text-xs text-zinc-500 mb-2 px-2">Recent Trades (last {data.trades.length})</p>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-zinc-500 border-b border-zinc-800">
                    <th className="text-left py-2 px-2">Dir</th>
                    <th className="text-right py-2 px-2">Entry</th>
                    <th className="text-right py-2 px-2">Exit</th>
                    <th className="text-right py-2 px-2">PnL</th>
                    <th className="text-right py-2 px-2">Result</th>
                    <th className="text-right py-2 px-2">Bars</th>
                  </tr>
                </thead>
                <tbody>
                  {data.trades.map((t, i) => (
                    <tr key={i} className="border-b border-zinc-800/50 hover:bg-zinc-800/30">
                      <td className="py-1.5 px-2">
                        <span className={`flex items-center gap-1 ${t.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>
                          {t.direction === 'LONG' ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                          {t.direction}
                        </span>
                      </td>
                      <td className="text-right py-1.5 px-2 text-zinc-300">${t.entry?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                      <td className="text-right py-1.5 px-2 text-zinc-300">${t.exit?.toLocaleString(undefined, { maximumFractionDigits: 2 })}</td>
                      <td className={`text-right py-1.5 px-2 font-medium ${t.pnl_pct >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {t.pnl_pct >= 0 ? '+' : ''}{t.pnl_pct?.toFixed(2)}%
                      </td>
                      <td className="text-right py-1.5 px-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                          t.result === 'TARGET' ? 'bg-green-500/20 text-green-400' :
                          t.result === 'STOP' ? 'bg-red-500/20 text-red-400' :
                          'bg-zinc-700 text-zinc-400'
                        }`}>
                          {t.result}
                        </span>
                      </td>
                      <td className="text-right py-1.5 px-2 text-zinc-500">{t.bars_held}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="space-y-6" data-testid="backtesting-page">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-white flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center">
            <FlaskConical className="w-5 h-5 text-white" />
          </div>
          Strategy Backtesting
        </h1>
        <p className="text-zinc-500 text-sm mt-1">Test trading strategies against historical MEXC data</p>
      </div>

      {/* Config Panel */}
      <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-2xl p-6 space-y-5" data-testid="backtest-config">
        {/* Row 1: Symbol, Timeframe, Days */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-zinc-400 mb-2">Symbol</label>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              data-testid="backtest-symbol"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
            >
              {SYMBOLS.map(s => <option key={s} value={s}>{s}/USDT</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-400 mb-2">Timeframe</label>
            <select
              value={timeframe}
              onChange={(e) => setTimeframe(e.target.value)}
              data-testid="backtest-timeframe"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
            >
              {TIMEFRAMES.map(tf => <option key={tf.value} value={tf.value}>{tf.label}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-400 mb-2">Period</label>
            <select
              value={days}
              onChange={(e) => setDays(parseInt(e.target.value))}
              data-testid="backtest-days"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
            >
              {DAYS_OPTIONS.map(d => <option key={d} value={d}>{d} days</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-zinc-400 mb-2">Strategy</label>
            <select
              value={strategy}
              onChange={(e) => setStrategy(e.target.value)}
              data-testid="backtest-strategy"
              className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
            >
              {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        </div>

        {/* Strategy-specific params */}
        {strategy !== 'compare' && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 pt-2 border-t border-zinc-800">
            {strategy === 'rsi' && (
              <>
                <div>
                  <label className="block text-xs text-zinc-400 mb-2">RSI Oversold</label>
                  <input type="number" value={rsiOversold} onChange={(e) => setRsiOversold(parseInt(e.target.value))}
                    data-testid="param-rsi-oversold"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-2">RSI Overbought</label>
                  <input type="number" value={rsiOverbought} onChange={(e) => setRsiOverbought(parseInt(e.target.value))}
                    data-testid="param-rsi-overbought"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
                </div>
              </>
            )}
            {strategy === 'ema' && (
              <>
                <div>
                  <label className="block text-xs text-zinc-400 mb-2">Fast EMA</label>
                  <input type="number" value={emaFast} onChange={(e) => setEmaFast(parseInt(e.target.value))}
                    data-testid="param-ema-fast"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
                </div>
                <div>
                  <label className="block text-xs text-zinc-400 mb-2">Slow EMA</label>
                  <input type="number" value={emaSlow} onChange={(e) => setEmaSlow(parseInt(e.target.value))}
                    data-testid="param-ema-slow"
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
                </div>
              </>
            )}
            <div>
              <label className="block text-xs text-zinc-400 mb-2">Stop Loss %</label>
              <input type="number" step="0.5" value={stopPct} onChange={(e) => setStopPct(parseFloat(e.target.value))}
                data-testid="param-stop-pct"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
            </div>
            {strategy !== 'ema' && (
              <div>
                <label className="block text-xs text-zinc-400 mb-2">Take Profit %</label>
                <input type="number" step="0.5" value={targetPct} onChange={(e) => setTargetPct(parseFloat(e.target.value))}
                  data-testid="param-target-pct"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none" />
              </div>
            )}
          </div>
        )}

        {/* Run Button */}
        <button
          onClick={runBacktest}
          disabled={loading}
          data-testid="run-backtest-btn"
          className="w-full py-3.5 bg-gradient-to-r from-violet-500 to-purple-600 hover:from-violet-600 hover:to-purple-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-white font-semibold transition-all flex items-center justify-center gap-2 shadow-lg shadow-violet-500/20"
        >
          {loading ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Running Backtest...
            </>
          ) : (
            <>
              <Play className="w-5 h-5" />
              Run Backtest
            </>
          )}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
          {error}
        </div>
      )}

      {/* Results */}
      {results?.type === 'compare' && results.data && (
        <div className="space-y-4" data-testid="backtest-results">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-400" />
              Strategy Comparison
            </h2>
            <span className="text-xs text-zinc-500">
              {results.data.symbol?.replace('/USDT', '')} / {results.data.timeframe} / {results.data.days}d
            </span>
          </div>

          {/* Winner Banner */}
          {results.data.best_strategy && results.data.best_strategy !== 'None' && (
            <div className="bg-gradient-to-r from-amber-500/10 to-orange-500/10 border border-amber-500/30 rounded-xl p-4 flex items-center gap-3">
              <Trophy className="w-6 h-6 text-amber-400 flex-shrink-0" />
              <p className="text-sm text-amber-200">
                Best strategy: <span className="font-semibold text-white">{results.data.best_strategy}</span>
                <span className="text-zinc-400 ml-1">(highest profit factor)</span>
              </p>
            </div>
          )}

          <div className="space-y-4">
            {results.data.strategies?.map((s, i) => (
              <div key={i}>
                {renderStrategyResult(s, s.strategy === results.data.best_strategy)}
              </div>
            ))}
          </div>
        </div>
      )}

      {results?.type === 'single' && results.data && (
        <div className="space-y-4" data-testid="backtest-results">
          <h2 className="text-lg font-semibold text-white">Results</h2>
          {renderStrategyResult(results.data, true)}
        </div>
      )}
    </div>
  );
}

function StatBox({ label, value, color = 'text-white' }) {
  return (
    <div className="bg-zinc-900/50 p-3 text-center">
      <p className="text-[10px] text-zinc-500 mb-0.5">{label}</p>
      <p className={`text-sm font-bold ${color}`}>{value}</p>
    </div>
  );
}
