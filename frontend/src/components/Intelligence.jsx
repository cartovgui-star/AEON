import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, RefreshCw, Loader2, Shield, Activity,
  ArrowRightLeft, AlertTriangle, Eye, Globe, TrendingUp, TrendingDown
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function HealthCard({ id, data, onUnbench }) {
  const borderColor = data.benched ? 'border-red-500/40 bg-red-500/5' :
    data.score >= 70 ? 'border-green-500/20 bg-zinc-800/30' : 'border-yellow-500/30 bg-zinc-800/30';
  const scoreColor = data.score >= 80 ? 'bg-green-500/20 text-green-400' :
    data.score >= 50 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-red-500/20 text-red-400';
  const wrColor = data.win_rate >= 50 ? 'text-green-400' : 'text-zinc-400';
  const pnlColor = data.total_pnl >= 0 ? 'text-green-400' : 'text-red-400';
  const pnlStr = (data.total_pnl >= 0 ? '+' : '') + data.total_pnl + '%';
  let streakStr = '-';
  let streakColor = 'text-zinc-400';
  if (data.consecutive_wins > 0) { streakStr = 'W' + data.consecutive_wins; streakColor = 'text-green-400'; }
  if (data.consecutive_losses > 0) { streakStr = 'L' + data.consecutive_losses; streakColor = 'text-red-400'; }

  return (
    <div className={`border rounded-xl p-4 ${borderColor}`} data-testid={`strategy-health-${id}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white text-sm">{data.name}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-zinc-700 text-zinc-400">{data.style}</span>
        </div>
        <span className={`px-2 py-0.5 rounded-full text-xs font-bold ${scoreColor}`}>{data.score}</span>
      </div>
      {data.benched && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-2 mb-3 flex items-center justify-between">
          <span className="text-xs text-red-300 flex items-center gap-1">
            <AlertTriangle className="w-3 h-3" /> Benched
          </span>
          <button onClick={() => onUnbench(id)} className="text-xs px-2 py-1 bg-red-500/20 text-red-300 rounded"
            data-testid={`unbench-${id}`}>Unbench</button>
        </div>
      )}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center">
        <div><p className="text-xs text-zinc-600">Trades</p><p className="text-sm font-medium text-white">{data.total_trades}</p></div>
        <div><p className="text-xs text-zinc-600">Win %</p><p className={`text-sm font-medium ${wrColor}`}>{data.win_rate}%</p></div>
        <div><p className="text-xs text-zinc-600">PnL</p><p className={`text-sm font-medium ${pnlColor}`}>{pnlStr}</p></div>
        <div><p className="text-xs text-zinc-600">Streak</p><p className={`text-sm font-medium ${streakColor}`}>{streakStr}</p></div>
      </div>
    </div>
  );
}

export default function Intelligence() {
  const [sentiment, setSentiment] = useState(null);
  const [arbitrage, setArbitrage] = useState(null);
  const [health, setHealth] = useState(null);
  const [regime, setRegime] = useState(null);
  const [loading, setLoading] = useState(true);
  const [arbiLoading, setArbiLoading] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [sentRes, healthRes, regimeRes] = await Promise.all([
        fetch(API_URL + '/api/sentiment/composite?symbol=BTC'),
        fetch(API_URL + '/api/strategy-health/status'),
        fetch(API_URL + '/api/regime/global'),
      ]);
      setSentiment(await sentRes.json());
      setHealth(await healthRes.json());
      try { const r = await regimeRes.json(); if (!r.error) setRegime(r); } catch {}
    } catch (err) {
      console.error('Intel fetch error:', err);
    }
    setLoading(false);
  }, []);

  const scanArbitrage = async () => {
    setArbiLoading(true);
    try {
      const res = await fetch(API_URL + '/api/arbitrage/scan');
      setArbitrage(await res.json());
    } catch (err) {
      console.error('Arbitrage error:', err);
    }
    setArbiLoading(false);
  };

  const unbench = async (sid) => {
    try {
      await fetch(API_URL + '/api/strategy-health/unbench/' + sid, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Unbench failed:', err);
    }
  };

  useEffect(() => { fetchData(); const i = setInterval(fetchData, 30000); return () => clearInterval(i); }, [fetchData]);

  if (loading) return <div className="flex items-center justify-center h-64"><Loader2 className="w-8 h-8 text-orange-400 animate-spin" /></div>;

  // Pre-extract data to avoid deep chaining in JSX
  const signal = sentiment ? sentiment.signal : 'N/A';
  const compScore = sentiment ? sentiment.composite_score : 0;
  const newsSent = sentiment && sentiment.news ? sentiment.news.sentiment : 'N/A';
  const bullPct = sentiment && sentiment.news ? sentiment.news.bullish_pct : 0;
  const bearPct = sentiment && sentiment.news ? sentiment.news.bearish_pct : 0;
  const fgValue = sentiment && sentiment.fear_greed ? sentiment.fear_greed.value : 50;
  const fgLabel = sentiment && sentiment.fear_greed ? sentiment.fear_greed.label : 'Neutral';
  const fgHistory = sentiment && sentiment.fear_greed && sentiment.fear_greed.history ? sentiment.fear_greed.history : [];
  const recommendation = sentiment ? sentiment.recommendation : 'Loading...';
  const headlines = sentiment && sentiment.news && sentiment.news.headlines ? sentiment.news.headlines.slice(0, 4) : [];
  const signalColor = signal === 'BULLISH' ? 'text-green-400' : signal === 'BEARISH' ? 'text-red-400' : 'text-yellow-400';
  const fgColor = fgValue >= 60 ? 'text-green-400' : fgValue <= 40 ? 'text-red-400' : 'text-yellow-400';

  const arbiOpps = arbitrage && arbitrage.best_opportunities ? arbitrage.best_opportunities : [];
  const arbiExCount = arbitrage && arbitrage.exchanges ? arbitrage.exchanges.length : 0;
  const arbiTotal = arbitrage ? arbitrage.total_opportunities || 0 : 0;
  const arbiScanned = arbitrage ? arbitrage.symbols_scanned || 0 : 0;
  const arbiSpread = arbitrage ? arbitrage.min_spread || 0.3 : 0.3;

  const healthEntries = health ? Object.entries(health) : [];

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
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <Activity className="w-5 h-5 text-cyan-400" /> Market Sentiment
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="sentiment-composite">
          <div className="text-center mb-4">
            <div className={`text-3xl font-bold ${signalColor}`}>{signal}</div>
            <p className="text-xs text-zinc-500">Score: {compScore}</p>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-400">News</span><span className="text-zinc-200">{newsSent}</span></div>
            <div className="flex justify-between"><span className="text-zinc-400">Bull/Bear</span><span className="text-zinc-200">{bullPct}% / {bearPct}%</span></div>
          </div>
        </div>

        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="fear-greed">
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Fear & Greed</h3>
          <div className="text-center">
            <div className={`text-4xl font-bold ${fgColor}`}>{fgValue}</div>
            <p className="text-xs text-zinc-500 mt-1">{fgLabel}</p>
          </div>
          <FGBars history={fgHistory} />
        </div>

        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-5" data-testid="sentiment-recommendation">
          <h3 className="text-sm font-medium text-zinc-400 mb-2">Recommendation</h3>
          <p className="text-sm text-zinc-200 leading-relaxed">{recommendation}</p>
          <HeadlineList headlines={headlines} />
        </div>
      </div>

      {/* MACRO REGIME */}
      {regime && (
        <>
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Globe className="w-5 h-5 text-sky-400" /> Global Market Regime
          </h2>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {Object.entries(regime).map(([key, val]) => {
              if (typeof val !== 'string' && typeof val !== 'number') return null;
              const isUp = String(val).toLowerCase().includes('bull') || String(val).toLowerCase().includes('risk_on');
              const isDn = String(val).toLowerCase().includes('bear') || String(val).toLowerCase().includes('risk_off');
              const col  = isUp ? 'text-green-400' : isDn ? 'text-red-400' : 'text-zinc-300';
              const label = key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
              return (
                <div key={key} className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
                  <p className="text-xs text-zinc-500 mb-1">{label}</p>
                  <p className={`text-sm font-semibold ${col} flex items-center gap-1`}>
                    {isUp && <TrendingUp className="w-3 h-3" />}
                    {isDn && <TrendingDown className="w-3 h-3" />}
                    {String(val)}
                  </p>
                </div>
              );
            })}
          </div>
        </>
      )}

      {/* ARBITRAGE */}
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
            <StatCard label="Opportunities" value={arbiTotal} color="text-emerald-400" />
            <StatCard label="Exchanges" value={arbiExCount} color="text-white" />
            <StatCard label="Scanned" value={arbiScanned} color="text-white" />
            <StatCard label="Min Spread" value={arbiSpread + '%'} color="text-zinc-300" />
          </div>
          {arbiOpps.length > 0 ? (
            <div className="space-y-2">{arbiOpps.map((opp, i) => <ArbiCard key={i} opp={opp} i={i} />)}</div>
          ) : (
            <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-6 text-center">
              <p className="text-zinc-500 text-sm">No opportunities above min spread</p>
            </div>
          )}
        </div>
      ) : (
        <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-8 text-center">
          <ArrowRightLeft className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
          <p className="text-zinc-500 text-sm">Click Scan to find cross-exchange opportunities</p>
          <p className="text-zinc-600 text-xs mt-1">MEXC, Binance, Bybit, OKX, KuCoin</p>
        </div>
      )}

      {/* STRATEGY HEALTH */}
      <h2 className="text-lg font-semibold text-white flex items-center gap-2">
        <Shield className="w-5 h-5 text-violet-400" /> Strategy Health
        <span className="text-xs text-zinc-500 font-normal">(auto-bench after 3 losses)</span>
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {healthEntries.map(([id, data]) => <HealthCard key={id} id={id} data={data} onUnbench={unbench} />)}
      </div>
    </div>
  );
}

function StatCard({ label, value, color }) {
  return (
    <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-3">
      <p className="text-xs text-zinc-500">{label}</p>
      <p className={`text-lg font-bold ${color}`}>{value}</p>
    </div>
  );
}

function ArbiCard({ opp, i }) {
  const sym = opp.symbol ? opp.symbol.replace('/USDT', '') : '';
  const buyStr = opp.buy_exchange + ' $' + (opp.buy_price || 0).toLocaleString();
  const sellStr = opp.sell_exchange + ' $' + (opp.sell_price || 0).toLocaleString();
  return (
    <div className="bg-zinc-800/30 border border-emerald-500/20 rounded-xl p-3 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
      data-testid={'arbi-opp-' + i}>
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-semibold text-white">{sym}</span>
        <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-400">Buy: {buyStr}</span>
        <span className="text-xs px-2 py-1 rounded bg-orange-500/10 text-orange-400">Sell: {sellStr}</span>
      </div>
      <span className="text-emerald-400 font-bold text-sm">+{opp.spread_pct}%</span>
    </div>
  );
}

function FGBars({ history }) {
  if (!history || history.length === 0) return null;
  return (
    <div className="mt-4 flex items-end gap-1 h-16">
      {history.map((h, i) => {
        const v = h.value;
        const bg = v >= 60 ? 'bg-green-500' : v <= 40 ? 'bg-red-500' : 'bg-yellow-500';
        return <div key={i} className={'flex-1 rounded-t ' + bg} style={{ height: v + '%' }} />;
      })}
    </div>
  );
}

function HeadlineList({ headlines }) {
  if (!headlines || headlines.length === 0) return null;
  return (
    <div className="mt-3 space-y-1">
      {headlines.map((h, i) => {
        const dotColor = h.score > 0 ? 'bg-green-500' : h.score < 0 ? 'bg-red-500' : 'bg-zinc-600';
        return (
          <div key={i} className="flex items-start gap-2 text-xs">
            <span className={'mt-1 w-1.5 h-1.5 rounded-full flex-shrink-0 ' + dotColor} />
            <span className="text-zinc-400 line-clamp-1">{h.title}</span>
          </div>
        );
      })}
    </div>
  );
}
