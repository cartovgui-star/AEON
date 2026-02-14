import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, TrendingUp, TrendingDown, RefreshCw, Loader2,
  Shield, Zap, Activity, ArrowRightLeft, AlertTriangle,
  Trophy, Heart, Skull, Eye, Clock, Target, ChevronDown
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function SentimentGauge({ value, label }) {
  const angle = ((value - 50) / 50) * 90;
  const color = value >= 60 ? 'text-green-400' : value <= 40 ? 'text-red-400' : 'text-yellow-400';
  return (
    <div className="text-center">
      <div className={`text-3xl font-bold ${color}`}>{value}</div>
      <div className="text-xs text-zinc-500 mt-1">{label}</div>
    </div>
  );
}

function ScoreBadge({ score }) {
  const color = score >= 80 ? 'bg-green-500/20 text-green-400' :
    score >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400';
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>{score}</span>;
}

function StrategyHealthCard({ id, data, onUnbench }) {
  const isHealthy = data.score >= 70;
  const borderColor = data.benched ? 'border-red-500/40 bg-red-500/5' :
    isHealthy ? 'border-green-500/20 bg-zinc-800/30' : 'border-yellow-500/30 bg-zinc-800/30';

  return (
    <div className={`border rounded-xl p-4 ${borderColor}`} data-testid={`strategy-health-${id}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white text-sm">{data.name}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">{data.style}</span>
        </div>
        <ScoreBadge score={data.score} />
      </div>

      {data.benched && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2 mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span className="text-xs text-red-300">
              Auto-benched {data.bench_remaining_min > 0 ? `(${data.bench_remaining_min}m remaining)` : ''}
            </span>
          </div>
          <button onClick={() => onUnbench(id)} className="text-xs px-2 py-1 bg-red-500/20 text-red-300 rounded hover:bg-red-500/30"
            data-testid={`unbench-${id}`}>
            Force Unbench
          </button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 text-center">
        <div>
          <p className="text-xs text-zinc-600">Trades</p>
          <p className="text-sm font-medium text-white">{data.total_trades}</p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">Win Rate</p>
          <p className={`text-sm font-medium ${data.win_rate >= 50 ? 'text-green-400' : data.total_trades > 0 ? 'text-red-400' : 'text-zinc-400'}`}>
            {data.win_rate}%
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">PnL</p>
          <p className={`text-sm font-medium ${data.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
            {data.total_pnl >= 0 ? '+' : ''}{data.total_pnl}%
          </p>
        </div>
        <div>
          <p className="text-xs text-zinc-600">Streak</p>
          <p className={`text-sm font-medium ${
            data.consecutive_wins > 0 ? 'text-green-400' :
            data.consecutive_losses > 0 ? 'text-red-400' : 'text-zinc-400'
          }`}>
            {data.consecutive_wins > 0 ? `W${data.consecutive_wins}` :
             data.consecutive_losses > 0 ? `L${data.consecutive_losses}` : '-'}
          </p>
        </div>
      </div>

      {data.recent_pnl?.length > 0 && (
        <div className="flex gap-1 mt-3">
          {data.recent_pnl.map((pnl, i) => (
            <div key={i} className={`flex-1 h-2 rounded-full ${pnl >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
              title={`${pnl >= 0 ? '+' : ''}${pnl}%`} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function Intelligence() {
  const [sentiment, setSentiment] = useState(null);
  const [arbitrage, setArbitrage] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [arbiLoading, setArbiLoading] = useState(false);
  const [activeSection, setActiveSection] = useState('all');

  const fetchData = useCallback(async () => {
    try {
      const [sentRes, healthRes] = await Promise.all([
        fetch(`${API_URL}/api/sentiment/composite?symbol=BTC`),
        fetch(`${API_URL}/api/strategy-health/status`)
      ]);
      setSentiment(await sentRes.json());
      setHealth(await healthRes.json());
    } catch (err) {
      console.error('Intel fetch error:', err);
    }
    setLoading(false);
  }, []);

  const scanArbitrage = async () => {
    setArbiLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/arbitrage/scan`);
      setArbitrage(await res.json());
    } catch (err) {
      console.error('Arbitrage scan error:', err);
    }
    setArbiLoading(false);
  };

  const unbenchStrategy = async (strategyId) => {
    try {
      await fetch(`${API_URL}/api/strategy-health/unbench/${strategyId}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Unbench error:', err);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="intelligence-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            Market Intelligence
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Sentiment analysis, arbitrage detection & strategy health</p>
        </div>
        <button onClick={fetchData} className="p-2.5 bg-zinc-800/50 hover:bg-zinc-800 rounded-xl text-zinc-400 hover:text-white transition-all">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* ═══ SENTIMENT SECTION ═══ */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" />
          Market Sentiment
        </h2>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Composite */}
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5 col-span-1" data-testid="sentiment-composite">
            <div className="text-center">
              <div className={`text-4xl font-bold mb-1 ${
                sentiment?.signal === 'BULLISH' ? 'text-green-400' :
                sentiment?.signal === 'BEARISH' ? 'text-red-400' : 'text-yellow-400'
              }`}>
                {sentiment?.signal || 'N/A'}
              </div>
              <p className="text-xs text-zinc-500">Composite Score: {sentiment?.composite_score || 0}</p>
            </div>
            <div className="mt-4 space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-400">News</span>
                <span className={sentiment?.news?.sentiment === 'BULLISH' ? 'text-green-400' :
                  sentiment?.news?.sentiment === 'BEARISH' ? 'text-red-400' : 'text-zinc-300'}>
                  {sentiment?.news?.sentiment || 'N/A'}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-zinc-400">Fear & Greed</span>
                <SentimentGauge value={sentiment?.fear_greed?.value || 50} label={sentiment?.fear_greed?.label || ''} />
              </div>
            </div>
          </div>

          {/* Fear & Greed History */}
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="fear-greed-chart">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">Fear & Greed (7d)</h3>
            <div className="flex items-end gap-2 h-24">
              {sentiment?.fear_greed?.history?.map((h, i) => {
                const val = h.value;
                const color = val >= 60 ? 'bg-green-500' : val <= 40 ? 'bg-red-500' : 'bg-yellow-500';
                return (
                  <div key={i} className="flex-1 flex flex-col items-center gap-1">
                    <span className="text-xs text-zinc-500">{val}</span>
                    <div className={`w-full rounded-t ${color}`} style={{ height: `${val}%` }} />
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recommendation */}
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="sentiment-recommendation">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">AI Recommendation</h3>
            <p className="text-sm text-zinc-200 leading-relaxed">{sentiment?.recommendation || 'Loading...'}</p>
            {sentiment?.news?.headlines?.length > 0 && (
              <div className="mt-4 space-y-1.5">
                <p className="text-xs text-zinc-500">Recent Headlines</p>
                {sentiment.news.headlines.slice(0, 3).map((h, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                      h.score > 0 ? 'bg-green-500' : h.score < 0 ? 'bg-red-500' : 'bg-zinc-600'
                    }`} />
                    <span className="text-zinc-400 line-clamp-1">{h.title}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══ ARBITRAGE SECTION ═══ */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-emerald-400" />
            Arbitrage Scanner
          </h2>
          <button onClick={scanArbitrage} disabled={arbiLoading} data-testid="scan-arbitrage-btn"
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-xl text-sm font-medium transition-all disabled:opacity-40">
            {arbiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            {arbiLoading ? 'Scanning...' : 'Scan Exchanges'}
          </button>
        </div>

        {arbitrage ? (
          <div className="space-y-3">
            {/* Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                <p className="text-xs text-zinc-500">Opportunities</p>
                <p className="text-lg font-bold text-emerald-400">{arbitrage.total_opportunities || 0}</p>
              </div>
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                <p className="text-xs text-zinc-500">Exchanges</p>
                <p className="text-lg font-bold text-white">{arbitrage.exchanges?.length || 0}</p>
              </div>
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                <p className="text-xs text-zinc-500">Symbols Scanned</p>
                <p className="text-lg font-bold text-white">{arbitrage.symbols_scanned || 0}</p>
              </div>
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                <p className="text-xs text-zinc-500">Min Spread</p>
                <p className="text-lg font-bold text-zinc-300">{arbitrage.min_spread || 0.3}%</p>
              </div>
            </div>

            {/* Opportunities */}
            {arbitrage.best_opportunities?.length > 0 ? (
              <div className="space-y-2">
                {arbitrage.best_opportunities.map((opp, i) => (
                  <div key={i} className="bg-zinc-800/30 border border-emerald-500/20 rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                    data-testid={`arbi-opp-${i}`}>
                    <div className="flex items-center gap-4">
                      <span className="text-sm font-semibold text-white w-16">{opp.symbol?.replace('/USDT', '')}</span>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="px-2 py-1 rounded bg-green-500/10 text-green-400">
                          Buy: {opp.buy_exchange} @ ${opp.buy_price?.toLocaleString()}
                        </span>
                        <ArrowRightLeft className="w-3 h-3 text-zinc-500" />
                        <span className="px-2 py-1 rounded bg-orange-500/10 text-orange-400">
                          Sell: {opp.sell_exchange} @ ${opp.sell_price?.toLocaleString()}
                        </span>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-emerald-400 font-bold text-sm">+{opp.spread_pct}%</span>
                      <span className="text-xs text-zinc-500 ml-2">(${opp.est_profit_per_1k}/1k)</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-6 text-center">
                <p className="text-zinc-500 text-sm">No arbitrage opportunities found above {arbitrage.min_spread}% spread</p>
              </div>
            )}

            {/* Cross-exchange prices */}
            {Object.keys(arbitrage.prices || {}).length > 0 && (
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
                <h3 className="text-xs font-medium text-zinc-500 mb-3">CROSS-EXCHANGE PRICES</h3>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="text-zinc-500 border-b border-zinc-800">
                        <th className="text-left py-2 px-2">Coin</th>
                        {arbitrage.exchanges?.map(ex => (
                          <th key={ex} className="text-right py-2 px-2">{ex}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(arbitrage.prices).map(([sym, prices]) => (
                        <tr key={sym} className="border-b border-zinc-800/50">
                          <td className="py-2 px-2 font-medium text-white">{sym.replace('/USDT', '')}</td>
                          {arbitrage.exchanges?.map(ex => {
                            const p = prices.find(pp => pp.exchange === ex);
                            return (
                              <td key={ex} className="text-right py-2 px-2 text-zinc-300">
                                {p ? `$${p.price?.toLocaleString(undefined, { maximumFractionDigits: 4 })}` : '-'}
                              </td>
                            );
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-8 text-center">
            <ArrowRightLeft className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-500 text-sm">Click "Scan Exchanges" to detect arbitrage opportunities</p>
            <p className="text-zinc-600 text-xs mt-1">Scans MEXC, Binance, Bybit, OKX, KuCoin for price differences</p>
          </div>
        )}
      </div>

      {/* ═══ STRATEGY HEALTH SECTION ═══ */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Shield className="w-5 h-5 text-violet-400" />
          Strategy Health
          <span className="text-xs text-zinc-500 font-normal ml-1">(Auto-benches after 3 consecutive losses)</span>
        </h2>

        {health && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(health).map(([id, data]) => (
              <StrategyHealthCard key={id} id={id} data={data} onUnbench={unbenchStrategy} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
