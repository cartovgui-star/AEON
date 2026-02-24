import React, { useState, useEffect, useCallback } from 'react';
import {
  X, FlaskConical, Play, TrendingUp, Loader2, Filter, Trophy,
  Check, Shield, Zap, Target
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function BacktestV21Modal({ isOpen, onClose }) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [status, setStatus] = useState(null);
  const [polling, setPolling] = useState(false);

  const runQuickBacktest = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_URL}/api/backtest/v21/compare?days=30&interval=1h`);
      const data = await response.json();
      
      if (data.status === 'success') {
        setResult(data);
      } else {
        setError(data.message || 'Backtest failed');
      }
    } catch (err) {
      setError('Failed to run backtest');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && !result && !loading) {
      // Load existing result if available
      const loadExisting = async () => {
        try {
          const response = await fetch(`${API_URL}/api/backtest/v21/result`);
          const data = await response.json();
          if (data.status === 'success') {
            setResult({
              status: 'success',
              aggregate: {
                total_trades: data.result.total_trades,
                wins: data.result.wins,
                losses: data.result.losses,
                win_rate: data.result.win_rate,
                old_win_rate: data.result.old_win_rate,
                improvement: data.result.improvement,
                signal_reduction_pct: data.result.signal_reduction_pct
              },
              filter_effectiveness: data.result.filter_breakdown,
              by_symbol: data.result.results_by_symbol?.map(r => ({
                symbol: r.symbol,
                win_rate: r.trades?.length > 0 
                  ? ((r.trades.filter(t => t.outcome === 'WIN').length / r.trades.length) * 100).toFixed(1)
                  : 0,
                trades: r.trades?.length || 0,
                v21_signals: r.new_signals || 0
              })),
              recommendations: data.result.recommendations,
              timestamp: data.result.timestamp
            });
          }
        } catch (err) {
          console.error('Failed to load existing result:', err);
        }
      };
      loadExisting();
    }
  }, [isOpen, result, loading]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div 
        className="bg-zinc-900 border border-zinc-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto shadow-2xl"
        data-testid="backtest-v21-modal"
      >
        {/* Header */}
        <div className="sticky top-0 bg-zinc-900 border-b border-zinc-800 p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <FlaskConical className="w-5 h-5 text-white" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">V2.1 Strategy Backtest</h2>
              <p className="text-xs text-zinc-500">MEXC Historical Data Analysis</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
            data-testid="close-backtest-modal"
          >
            <X className="w-5 h-5 text-zinc-400" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Run Button */}
          {!result && (
            <button
              onClick={runQuickBacktest}
              disabled={loading}
              data-testid="run-quick-backtest-btn"
              className="w-full py-4 bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-600 hover:to-orange-700 disabled:opacity-40 rounded-xl text-white font-semibold transition-all flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Running Analysis (30-60 sec)...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Run Quick Backtest (BTC, ETH, SOL)
                </>
              )}
            </button>
          )}

          {/* Error */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-4 text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Results */}
          {result && (
            <div className="space-y-5">
              {/* Win Rate Highlight */}
              <div className="bg-zinc-800/50 border border-zinc-700 rounded-xl p-6 text-center">
                <p className="text-zinc-400 text-sm mb-2">V2.1 Win Rate</p>
                <p className={`text-5xl font-bold ${result.aggregate?.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
                  {result.aggregate?.win_rate}%
                </p>
                <div className="mt-3 flex items-center justify-center gap-4 text-sm">
                  <span className="text-zinc-500">Old: {result.aggregate?.old_win_rate}%</span>
                  <span className={result.aggregate?.improvement > 0 ? 'text-green-400' : 'text-red-400'}>
                    {result.aggregate?.improvement > 0 ? '+' : ''}{result.aggregate?.improvement}% improvement
                  </span>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-800/30 border border-zinc-700 rounded-xl p-4">
                  <p className="text-zinc-500 text-xs">Total Trades</p>
                  <p className="text-xl font-bold text-white">{result.aggregate?.total_trades}</p>
                  <p className="text-xs text-zinc-400">{result.aggregate?.wins}W / {result.aggregate?.losses}L</p>
                </div>
                <div className="bg-zinc-800/30 border border-zinc-700 rounded-xl p-4">
                  <p className="text-zinc-500 text-xs">Signal Reduction</p>
                  <p className="text-xl font-bold text-cyan-400">{result.aggregate?.signal_reduction_pct}%</p>
                  <p className="text-xs text-zinc-400">Fewer low-quality trades</p>
                </div>
              </div>

              {/* By Symbol */}
              {result.by_symbol && (
                <div className="bg-zinc-800/30 border border-zinc-700 rounded-xl p-4">
                  <p className="text-zinc-400 text-xs mb-3 flex items-center gap-2">
                    <Filter className="w-3 h-3" />
                    Results by Symbol
                  </p>
                  <div className="space-y-3">
                    {result.by_symbol.map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between">
                        <span className="text-white font-medium">{item.symbol}</span>
                        <div className="flex items-center gap-4 text-sm">
                          <span className="text-zinc-400">{item.trades} trades</span>
                          <span className={Number(item.win_rate) >= 50 ? 'text-green-400' : 'text-amber-400'}>
                            {item.win_rate}% WR
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Filter Effectiveness */}
              {result.filter_effectiveness && (
                <div className="bg-zinc-800/30 border border-zinc-700 rounded-xl p-4">
                  <p className="text-zinc-400 text-xs mb-3">Filter Effectiveness</p>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    {Object.entries(result.filter_effectiveness)
                      .filter(([_, v]) => v > 0)
                      .map(([key, value]) => (
                        <div key={key} className="flex items-center justify-between px-2 py-1 bg-zinc-900/50 rounded">
                          <span className="text-zinc-400">{key.replace(/_/g, ' ')}</span>
                          <span className="text-amber-400 font-medium">{value}</span>
                        </div>
                      ))
                    }
                  </div>
                </div>
              )}

              {/* Recommendations */}
              {result.recommendations && result.recommendations.length > 0 && (
                <div className="bg-amber-500/10 border border-amber-500/30 rounded-xl p-4">
                  <p className="text-amber-400 text-xs mb-2 flex items-center gap-2">
                    <Trophy className="w-3 h-3" />
                    Recommendations
                  </p>
                  <div className="space-y-1 text-sm text-zinc-300">
                    {result.recommendations.map((rec, idx) => (
                      <p key={idx}>{rec}</p>
                    ))}
                  </div>
                </div>
              )}

              {/* V2.1 Settings Summary */}
              <div className="bg-zinc-800/30 border border-zinc-700 rounded-xl p-4">
                <p className="text-zinc-400 text-xs mb-3">V2.1 HIGH WIN RATE Settings</p>
                <div className="flex flex-wrap gap-3 text-xs">
                  <span className="flex items-center gap-1 px-2 py-1 bg-amber-500/10 text-amber-400 rounded">
                    <Target className="w-3 h-3" /> 90% Confidence
                  </span>
                  <span className="flex items-center gap-1 px-2 py-1 bg-green-500/10 text-green-400 rounded">
                    <Check className="w-3 h-3" /> 5/5 Confirmations
                  </span>
                  <span className="flex items-center gap-1 px-2 py-1 bg-blue-500/10 text-blue-400 rounded">
                    <Shield className="w-3 h-3" /> 3:1 R:R
                  </span>
                  <span className="flex items-center gap-1 px-2 py-1 bg-purple-500/10 text-purple-400 rounded">
                    <TrendingUp className="w-3 h-3" /> 200 EMA Filter
                  </span>
                  <span className="flex items-center gap-1 px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded">
                    <Zap className="w-3 h-3" /> ADX &gt; 25
                  </span>
                </div>
              </div>

              {/* Re-run button */}
              <button
                onClick={() => { setResult(null); runQuickBacktest(); }}
                disabled={loading}
                className="w-full py-3 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 rounded-xl text-zinc-300 font-medium transition-all flex items-center justify-center gap-2"
              >
                {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                Re-run Backtest
              </button>

              {/* Timestamp */}
              {result.timestamp && (
                <p className="text-center text-xs text-zinc-600">
                  Last run: {new Date(result.timestamp).toLocaleString()}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
