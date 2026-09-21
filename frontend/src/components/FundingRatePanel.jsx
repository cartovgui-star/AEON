import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown, Minus, RefreshCw, DollarSign } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const HEADERS = {};

const SYMBOLS = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP'];

function rateColor(rate) {
  if (rate > 0.0005) return 'text-red-400';
  if (rate > 0.0001) return 'text-orange-400';
  if (rate < -0.0003) return 'text-green-400';
  if (rate < 0) return 'text-cyan-400';
  return 'text-zinc-400';
}

function RateIcon({ rate }) {
  if (rate > 0.0001) return <TrendingUp className="w-3.5 h-3.5" />;
  if (rate < -0.0001) return <TrendingDown className="w-3.5 h-3.5" />;
  return <Minus className="w-3.5 h-3.5" />;
}

function interpretLabel(text) {
  // Strip emoji prefix for a clean label
  return text.replace(/^[^\w]+/, '').trim();
}

export default function FundingRatePanel() {
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);

  const fetchAll = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    try {
      const results = await Promise.allSettled(
        SYMBOLS.map(sym =>
          fetch(`${API_URL}/api/derivatives/funding/${sym}`, { headers: HEADERS })
            .then(r => r.json())
            .then(d => ({ sym, d }))
        )
      );
      const next = {};
      results.forEach(r => {
        if (r.status === 'fulfilled' && r.value?.d && !r.value.d.detail) {
          next[r.value.sym] = r.value.d;
        }
      });
      setData(next);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('Funding rate fetch failed:', e);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const iv = setInterval(() => fetchAll(), 60000);
    return () => clearInterval(iv);
  }, []);

  return (
    <div className="space-y-6" data-testid="funding-rate-panel">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <DollarSign className="w-6 h-6 text-orange-400" />
          <div>
            <h2 className="text-xl font-bold text-white">Funding Rates</h2>
            <p className="text-xs text-zinc-500">Aggregated from OKX · Bitget · KuCoin · Gate.io</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-zinc-500">
              Updated {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={() => fetchAll(true)}
            disabled={refreshing}
            className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700 disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-40">
          <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
        </div>
      ) : (
        <>
          {/* Summary Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {SYMBOLS.map(sym => {
              const d = data[sym];
              const rate = d?.average_funding_rate ?? null;
              const color = rate !== null ? rateColor(rate) : 'text-zinc-500';
              return (
                <Card key={sym} className="bg-zinc-800/30 border-zinc-700/50">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-white">{sym}</span>
                      {rate !== null && (
                        <span className={`${color} flex items-center gap-1`}>
                          <RateIcon rate={rate} />
                        </span>
                      )}
                    </div>
                    {rate !== null ? (
                      <>
                        <p className={`text-lg font-mono font-bold ${color}`}>
                          {(rate * 100).toFixed(4)}%
                        </p>
                        <p className="text-[10px] text-zinc-500 mt-1">
                          {d.data_sources} exchange{d.data_sources !== 1 ? 's' : ''}
                        </p>
                      </>
                    ) : (
                      <p className="text-sm text-zinc-500">No data</p>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Detailed Breakdown */}
          <div className="space-y-4">
            {SYMBOLS.map(sym => {
              const d = data[sym];
              if (!d) return null;
              const rate = d.average_funding_rate;
              const color = rateColor(rate);
              return (
                <Card key={sym} className="bg-zinc-800/30 border-zinc-700/50">
                  <CardContent className="p-4">
                    <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
                      <div className="flex items-center gap-3">
                        <span className="text-lg font-bold text-white">{sym}/USDT</span>
                        <span className={`flex items-center gap-1.5 text-sm font-medium ${color}`}>
                          <RateIcon rate={rate} />
                          {(rate * 100).toFixed(4)}% avg
                        </span>
                      </div>
                      <span className="text-xs text-zinc-400 italic">{interpretLabel(d.interpretation)}</span>
                    </div>
                    {/* Per-exchange breakdown */}
                    {d.exchanges && d.exchanges.length > 0 && (
                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                        {d.exchanges.map((ex, i) => {
                          const exRate = ex.funding_rate ?? 0;
                          const exColor = rateColor(exRate);
                          return (
                            <div key={i} className="bg-zinc-900/50 rounded-lg p-2.5">
                              <p className="text-xs text-zinc-500 capitalize mb-1">{ex.exchange || `Source ${i + 1}`}</p>
                              <p className={`text-sm font-mono font-bold ${exColor}`}>
                                {(exRate * 100).toFixed(4)}%
                              </p>
                              {ex.next_funding_time && (
                                <p className="text-[10px] text-zinc-600 mt-1">
                                  Next: {new Date(ex.next_funding_time).toLocaleTimeString()}
                                </p>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>

          {/* Interpretation Guide */}
          <Card className="bg-zinc-800/20 border-zinc-700/30">
            <CardContent className="p-4">
              <h3 className="text-xs font-semibold text-zinc-400 mb-3 uppercase tracking-wider">Interpretation Guide</h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-xs">
                <div className="flex gap-2"><span className="text-red-400 font-medium w-32">&gt; +0.05%</span><span className="text-zinc-400">Longs heavily crowded — squeeze risk high</span></div>
                <div className="flex gap-2"><span className="text-orange-400 font-medium w-32">+0.01% to +0.05%</span><span className="text-zinc-400">Positive bias, longs paying shorts</span></div>
                <div className="flex gap-2"><span className="text-zinc-400 font-medium w-32">~0%</span><span className="text-zinc-400">Neutral market, no crowding</span></div>
                <div className="flex gap-2"><span className="text-cyan-400 font-medium w-32">-0.01% to 0%</span><span className="text-zinc-400">Slight short bias, shorts paying longs</span></div>
                <div className="flex gap-2"><span className="text-green-400 font-medium w-32">&lt; -0.03%</span><span className="text-zinc-400">Shorts crowded — squeeze potential</span></div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
