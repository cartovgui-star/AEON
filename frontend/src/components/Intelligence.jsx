import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, RefreshCw, Loader2, Shield, Activity,
  ArrowRightLeft, AlertTriangle, Eye
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function ScoreBadge({ score }) {
  const color = score >= 80 ? 'bg-green-500/20 text-green-400' :
    score >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400';
  return <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${color}`}>{score}</span>;
}

function HealthCard({ id, data, onUnbench }) {
  const borderColor = data.benched ? 'border-red-500/40 bg-red-500/5' :
    data.score >= 70 ? 'border-green-500/20 bg-zinc-800/30' : 'border-yellow-500/30 bg-zinc-800/30';

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
          <span className="text-xs text-red-300 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Benched {data.bench_remaining_min > 0 ? `(${data.bench_remaining_min}m)` : ''}
          </span>
          <button onClick={() => onUnbench(id)} className="text-xs px-2 py-1 bg-red-500/20 text-red-300 rounded"
            data-testid={`unbench-${id}`}>Unbench</button>
        </div>
      )}

      <div className="grid grid-cols-4 gap-2 text-center">
        <MiniStat label="Trades" value={data.total_trades} />
        <MiniStat label="Win %" value={`${data.win_rate}%`} color={data.win_rate >= 50 ? 'text-green-400' : 'text-zinc-400'} />
        <MiniStat label="PnL" value={`${data.total_pnl >= 0 ? '+' : ''}${data.total_pnl}%`}
          color={data.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'} />
        <MiniStat label="Streak"
          value={data.consecutive_wins > 0 ? `W${data.consecutive_wins}` : data.consecutive_losses > 0 ? `L${data.consecutive_losses}` : '-'}
          color={data.consecutive_wins > 0 ? 'text-green-400' : data.consecutive_losses > 0 ? 'text-red-400' : 'text-zinc-400'} />
      </div>
    </div>
  );
}

function MiniStat({ label, value, color }) {
  return (
    <div>
      <p className="text-xs text-zinc-600">{label}</p>
      <p className={`text-sm font-medium ${color || 'text-white'}`}>{value}</p>
    </div>
  );
}

function ArbiOpp({ opp, index }) {
  return (
    <div className="bg-zinc-800/30 border border-emerald-500/20 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
      data-testid={`arbi-opp-${index}`}>
      <div className="flex items-center gap-3">
        <span className="text-sm font-semibold text-white">{opp.symbol?.replace('/USDT', '')}</span>
        <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-400">
          Buy: {opp.buy_exchange} ${opp.buy_price?.toLocaleString()}
        </span>
        <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-400">
          Sell: {opp.sell_exchange} ${opp.sell_price?.toLocaleString()}
        </span>
      </div>
      <span className="text-emerald-400 font-bold text-sm">+{opp.spread_pct}%</span>
    </div>
  );
}

export default function Intelligence() {
  const [sentiment, setSentiment] = useState(null);
  const [arbitrage, setArbitrage] = useState(null);
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [arbiLoading, setArbiLoading] = useState(false);

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
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-orange-400 animate-spin" /></div>;
  }

  const fgValue = sentiment?.fear_greed?.value || 50;
  const fgLabel = sentiment?.fear_greed?.label || 'Neutral';
  const signalColor = sentiment?.signal === 'BULLISH' ? 'text-green-400' : sentiment?.signal === 'BEARISH' ? 'text-red-400' : 'text-yellow-400';

  return (
    <div className="space-y-6" data-testid="intelligence-page">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center">
              <Brain className="w-5 h-5 text-white" />
            </div>
            Market Intelligence
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Sentiment, arbitrage & strategy health</p>
        </div>
        <button onClick={fetchData} className="p-2.5 bg-zinc-800/50 hover:bg-zinc-800 rounded-xl text-zinc-400 hover:text-white">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* SENTIMENT */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-cyan-400" /> Market Sentiment
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="sentiment-composite">
            <div className="text-center mb-4">
              <div className={`text-3xl font-bold ${signalColor}`}>{sentiment?.signal || 'N/A'}</div>
              <p className="text-xs text-zinc-500">Score: {sentiment?.composite_score || 0}</p>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-zinc-400">News</span>
                <span className="text-zinc-200">{sentiment?.news?.sentiment || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Bullish/Bearish</span>
                <span className="text-zinc-200">{sentiment?.news?.bullish_pct || 0}% / {sentiment?.news?.bearish_pct || 0}%</span>
              </div>
            </div>
          </div>

          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="fear-greed">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">Fear & Greed Index</h3>
            <div className="text-center">
              <div className={`text-4xl font-bold ${fgValue >= 60 ? 'text-green-400' : fgValue <= 40 ? 'text-red-400' : 'text-yellow-400'}`}>
                {fgValue}
              </div>
              <p className="text-xs text-zinc-500 mt-1">{fgLabel}</p>
            </div>
            <div className="mt-4 flex items-end gap-1 h-16">
              {(sentiment?.fear_greed?.history || []).map((h, i) => {
                const v = h.value;
                const bg = v >= 60 ? 'bg-green-500' : v <= 40 ? 'bg-red-500' : 'bg-yellow-500';
                return <div key={i} className={`flex-1 rounded-t ${bg}`} style={{ height: `${v}%` }} title={`${v}`} />;
              })}
            </div>
          </div>

          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="sentiment-recommendation">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">Recommendation</h3>
            <p className="text-sm text-zinc-200 leading-relaxed">{sentiment?.recommendation || 'Loading...'}</p>
            <div className="mt-4 space-y-1">
              {(sentiment?.news?.headlines || []).slice(0, 4).map((h, i) => (
                <div key={i} className="flex items-start gap-2 text-xs">
                  <span className={`mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ${h.score > 0 ? 'bg-green-500' : h.score < 0 ? 'bg-red-500' : 'bg-zinc-600'}`} />
                  <span className="text-zinc-400 line-clamp-1">{h.title}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ARBITRAGE */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <ArrowRightLeft className="w-5 h-5 text-emerald-400" /> Arbitrage Scanner
          </h2>
          <button onClick={scanArbitrage} disabled={arbiLoading} data-testid="scan-arbitrage-btn"
            className="flex items-center gap-2 px-4 py-2 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 rounded-xl text-sm font-medium disabled:opacity-40">
            {arbiLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
            {arbiLoading ? 'Scanning...' : 'Scan Exchanges'}
          </button>
        </div>

        {arbitrage ? (
          <div className="space-y-3">
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
                <p className="text-xs text-zinc-500">Scanned</p>
                <p className="text-lg font-bold text-white">{arbitrage.symbols_scanned || 0}</p>
              </div>
              <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                <p className="text-xs text-zinc-500">Min Spread</p>
                <p className="text-lg font-bold text-zinc-300">{arbitrage.min_spread || 0.3}%</p>
              </div>
            </div>

            {(arbitrage.best_opportunities || []).length > 0 ? (
              <div className="space-y-2">
                {arbitrage.best_opportunities.map((opp, i) => (
                  <ArbiOpp key={i} opp={opp} index={i} />
                ))}
              </div>
            ) : (
              <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-6 text-center">
                <p className="text-zinc-500 text-sm">No opportunities above {arbitrage.min_spread}% spread</p>
              </div>
            )}
          </div>
        ) : (
          <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-8 text-center">
            <ArrowRightLeft className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
            <p className="text-zinc-500 text-sm">Click "Scan Exchanges" to find arbitrage</p>
            <p className="text-zinc-600 text-xs mt-1">Checks MEXC, Binance, Bybit, OKX, KuCoin</p>
          </div>
        )}
      </div>

      {/* STRATEGY HEALTH */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <Shield className="w-5 h-5 text-violet-400" /> Strategy Health
          <span className="text-xs text-zinc-500 font-normal">(auto-bench after 3 losses)</span>
        </h2>
        {health && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {Object.entries(health).map(([id, data]) => (
              <HealthCard key={id} id={id} data={data} onUnbench={unbenchStrategy} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
