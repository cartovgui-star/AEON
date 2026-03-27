import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  BarChart3, RefreshCw, TrendingUp, TrendingDown, Flame,
  Target, AlertTriangle, Activity, Layers, Zap
} from 'lucide-react';
import {
  ComposedChart, Bar, XAxis, YAxis, ReferenceLine,
  Tooltip, ResponsiveContainer, Cell
} from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Badge } from './ui/badge';
import { Button } from './ui/button';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const SYMBOLS = [
  'BTC/USDT', 'ETH/USDT', 'SOL/USDT', 'BNB/USDT', 'XRP/USDT',
  'DOGE/USDT', 'ADA/USDT', 'AVAX/USDT', 'LINK/USDT', 'DOT/USDT',
];

const formatPrice = (p) => {
  if (!p && p !== 0) return '-';
  if (Math.abs(p) > 1000) return `$${p.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  if (Math.abs(p) > 1) return `$${p.toFixed(4)}`;
  return `$${p.toFixed(6)}`;
};

const formatPct = (v) => v == null ? '-' : `${v > 0 ? '+' : ''}${v.toFixed(2)}%`;

function VolumeHeatmapBar({ bucket, maxVol, pocPrice }) {
  const intensity = bucket.intensity || 0;
  const isPoc = Math.abs(bucket.price - pocPrice) / pocPrice < 0.003;
  const barWidth = Math.max(2, intensity * 100);
  const color = isPoc
    ? 'bg-yellow-400'
    : intensity > 0.7
    ? 'bg-orange-500'
    : intensity > 0.4
    ? 'bg-orange-400/70'
    : intensity > 0.2
    ? 'bg-blue-400/50'
    : 'bg-zinc-700/40';

  return (
    <div className="flex items-center gap-1 h-1.5 group relative">
      <div className={`${color} rounded-sm`} style={{ width: `${barWidth}%`, height: '100%' }} />
      {isPoc && (
        <span className="absolute right-0 text-yellow-400 text-[8px] font-bold opacity-0 group-hover:opacity-100">
          POC
        </span>
      )}
    </div>
  );
}

const LIQ_CHART_REFRESH_MS = 30_000;

function LiqHeatmapChart({ heatmap_buckets = [], current_price }) {
  // Build chart data: price on Y, long goes left (negative), short goes right (positive)
  const chartData = [...heatmap_buckets]
    .sort((a, b) => a.price - b.price)  // ascending — recharts vertical goes bottom-up
    .map(b => ({
      price: b.price,
      long:  -Math.round((b.long_intensity  || 0) * 1000) / 1000,   // negative = left
      short:  Math.round((b.short_intensity || 0) * 1000) / 1000,   // positive = right
    }));

  if (chartData.length === 0) {
    return <div className="text-zinc-600 text-xs text-center py-8">No heatmap data</div>;
  }

  const priceMin = chartData[0].price;
  const priceMax = chartData[chartData.length - 1].price;

  const fmtPrice = (v) => {
    if (v == null) return '';
    if (Math.abs(v) > 10000) return `$${(v / 1000).toFixed(0)}k`;
    if (Math.abs(v) > 1)     return `$${v.toFixed(0)}`;
    return `$${v.toFixed(4)}`;
  };

  const CustomTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null;
    const d = payload[0]?.payload;
    return (
      <div className="bg-zinc-900 border border-zinc-700 rounded px-2 py-1.5 text-xs">
        <div className="text-zinc-300 font-mono mb-1">{fmtPrice(d.price)}</div>
        <div className="text-red-400">Long Liq: {Math.abs(d.long).toFixed(3)}</div>
        <div className="text-green-400">Short Liq: {d.short.toFixed(3)}</div>
      </div>
    );
  };

  return (
    <div className="w-full" style={{ height: 380 }}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          layout="vertical"
          data={chartData}
          margin={{ top: 4, right: 8, bottom: 4, left: 56 }}
        >
          <XAxis
            type="number"
            domain={[-1, 1]}
            tickFormatter={v => v === 0 ? '' : `${Math.abs(v * 100).toFixed(0)}%`}
            tick={{ fill: '#71717a', fontSize: 9 }}
            axisLine={{ stroke: '#3f3f46' }}
            tickLine={false}
          />
          <YAxis
            type="number"
            dataKey="price"
            domain={[priceMin, priceMax]}
            tickFormatter={fmtPrice}
            tick={{ fill: '#71717a', fontSize: 9 }}
            axisLine={false}
            tickLine={false}
            width={54}
            tickCount={8}
          />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />

          {/* Long liq — negative X = goes left, red */}
          <Bar dataKey="long" barSize={4} isAnimationActive={false}>
            {chartData.map((entry, i) => {
              const intensity = Math.abs(entry.long);
              const alpha = 0.3 + intensity * 0.7;
              return <Cell key={i} fill={`rgba(239,68,68,${alpha.toFixed(2)})`} />;
            })}
          </Bar>

          {/* Short liq — positive X = goes right, green */}
          <Bar dataKey="short" barSize={4} isAnimationActive={false}>
            {chartData.map((entry, i) => {
              const alpha = 0.3 + entry.short * 0.7;
              return <Cell key={i} fill={`rgba(34,197,94,${alpha.toFixed(2)})`} />;
            })}
          </Bar>

          {/* Center axis line */}
          <ReferenceLine x={0} stroke="#52525b" strokeWidth={1} />

          {/* Current price */}
          {current_price > 0 && (
            <ReferenceLine
              y={current_price}
              stroke="#f97316"
              strokeWidth={1.5}
              strokeDasharray="4 3"
              label={{
                value: fmtPrice(current_price),
                position: 'insideBottomRight',
                fill: '#f97316',
                fontSize: 9,
                fontWeight: 600,
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      <div className="flex justify-between text-xs text-zinc-600 px-2 mt-1">
        <span className="text-red-400/70">◀ Long liq (below price)</span>
        <span className="text-orange-400/70">— current price</span>
        <span className="text-green-400/70">Short liq (above price) ▶</span>
      </div>
    </div>
  );
}

function ProfilePanel({ data }) {
  if (!data || data.error) return null;

  const { poc_price, vah, val, hvn_levels = [], lvn_levels = [], profile_buckets = [], total_volume } = data;
  const currentPrice = data.current_price || poc_price;
  // Show only the bucket range near current price for the mini heatmap
  const visible = profile_buckets.slice(Math.max(0, profile_buckets.length - 60));

  return (
    <div className="space-y-3">
      {/* Key levels */}
      <div className="grid grid-cols-3 gap-2">
        <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-2 text-center">
          <div className="text-yellow-400 text-xs font-bold">POC</div>
          <div className="text-white text-xs font-mono">{formatPrice(poc_price)}</div>
        </div>
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-2 text-center">
          <div className="text-green-400 text-xs font-bold">VAH</div>
          <div className="text-white text-xs font-mono">{formatPrice(vah)}</div>
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-center">
          <div className="text-red-400 text-xs font-bold">VAL</div>
          <div className="text-white text-xs font-mono">{formatPrice(val)}</div>
        </div>
      </div>

      {/* Mini profile heatmap */}
      <div className="bg-zinc-900/50 rounded-lg p-2">
        <div className="text-zinc-500 text-xs mb-1 flex justify-between">
          <span>Volume Profile (last 96 candles)</span>
          <span className="text-zinc-600">Vol: {(total_volume / 1e6).toFixed(1)}M</span>
        </div>
        <div className="space-y-px" style={{ maxHeight: '120px', overflowY: 'hidden' }}>
          {visible.slice(-50).reverse().map((b, i) => (
            <VolumeHeatmapBar key={i} bucket={b} pocPrice={poc_price} />
          ))}
        </div>
      </div>

      {/* HVN / LVN */}
      <div className="grid grid-cols-2 gap-2">
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <Layers className="w-3 h-3" /> HVN (Support/Resistance)
          </div>
          <div className="space-y-1">
            {hvn_levels.slice(0, 4).map((h, i) => (
              <div key={i} className="flex justify-between text-xs bg-orange-500/10 px-2 py-0.5 rounded">
                <span className="text-orange-300 font-mono">{formatPrice(h.price)}</span>
                <span className="text-zinc-500">{(h.volume / 1000).toFixed(0)}K</span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500 mb-1 flex items-center gap-1">
            <Zap className="w-3 h-3" /> LVN (Thin Air)
          </div>
          <div className="space-y-1">
            {lvn_levels.slice(0, 4).map((l, i) => (
              <div key={i} className="flex justify-between text-xs bg-blue-500/10 px-2 py-0.5 rounded">
                <span className="text-blue-300 font-mono">{formatPrice(l.price)}</span>
                <span className="text-zinc-500">{(l.volume / 1000).toFixed(0)}K</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function LiqPanel({ data, lastRefresh }) {
  if (!data || data.error) return null;

  const {
    long_liq_clusters = [], short_liq_clusters = [],
    nearest_long_cluster, nearest_short_cluster,
    approaching_long_liq, approaching_short_liq,
    heatmap_buckets = [], current_price,
    open_interest,
  } = data;

  return (
    <div className="space-y-3">
      {/* Approaching warnings */}
      {(approaching_long_liq || approaching_short_liq) && (
        <div className={`flex items-center gap-2 p-2 rounded-lg border text-xs font-medium ${
          approaching_long_liq
            ? 'bg-red-500/10 border-red-500/30 text-red-300'
            : 'bg-green-500/10 border-green-500/30 text-green-300'
        }`}>
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {approaching_long_liq
            ? '⚠️ Approaching LONG LIQ cluster — stop hunt incoming'
            : '⚠️ Approaching SHORT LIQ cluster — squeeze incoming'}
        </div>
      )}

      {/* Nearest clusters */}
      <div className="grid grid-cols-2 gap-2">
        <div className="bg-green-500/10 border border-green-500/20 rounded-lg p-2">
          <div className="text-xs text-green-400 font-bold mb-1">🟢 Short Liq Above</div>
          {nearest_short_cluster ? (
            <>
              <div className="text-white text-xs font-mono">{formatPrice(nearest_short_cluster.price)}</div>
              <div className="text-zinc-400 text-xs">{formatPct(nearest_short_cluster.dist_pct)} away</div>
              <div className="mt-1 bg-green-500/30 rounded-full h-1.5">
                <div className="bg-green-400 rounded-full h-1.5" style={{ width: `${nearest_short_cluster.intensity * 100}%` }} />
              </div>
            </>
          ) : <span className="text-zinc-600 text-xs">None nearby</span>}
        </div>
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-2">
          <div className="text-xs text-red-400 font-bold mb-1">🔴 Long Liq Below</div>
          {nearest_long_cluster ? (
            <>
              <div className="text-white text-xs font-mono">{formatPrice(nearest_long_cluster.price)}</div>
              <div className="text-zinc-400 text-xs">{formatPct(nearest_long_cluster.dist_pct)} away</div>
              <div className="mt-1 bg-red-500/30 rounded-full h-1.5">
                <div className="bg-red-400 rounded-full h-1.5" style={{ width: `${nearest_long_cluster.intensity * 100}%` }} />
              </div>
            </>
          ) : <span className="text-zinc-600 text-xs">None nearby</span>}
        </div>
      </div>

      {/* Live heatmap chart */}
      <div className="bg-zinc-900/50 rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-zinc-400 text-xs font-medium">Liquidation Density Map</span>
          <div className="flex items-center gap-3 text-xs text-zinc-600">
            {open_interest > 0 && (
              <span>OI: {open_interest.toLocaleString(undefined, { maximumFractionDigits: 0 })} contracts</span>
            )}
            {lastRefresh && (
              <span className="text-zinc-700">
                {lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            )}
          </div>
        </div>
        <LiqHeatmapChart heatmap_buckets={heatmap_buckets} current_price={current_price} />
      </div>

      {/* All clusters */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-zinc-500 mb-1">Short Liq Clusters (↑)</div>
          {short_liq_clusters.slice(0, 5).map((c, i) => (
            <div key={i} className="flex justify-between bg-green-500/10 px-2 py-0.5 rounded mb-0.5">
              <span className="text-green-300 font-mono">{formatPrice(c.price)}</span>
              <span className="text-zinc-500">{formatPct(c.dist_pct)}</span>
            </div>
          ))}
        </div>
        <div>
          <div className="text-zinc-500 mb-1">Long Liq Clusters (↓)</div>
          {long_liq_clusters.slice(0, 5).map((c, i) => (
            <div key={i} className="flex justify-between bg-red-500/10 px-2 py-0.5 rounded mb-0.5">
              <span className="text-red-300 font-mono">{formatPrice(c.price)}</span>
              <span className="text-zinc-500">{formatPct(c.dist_pct)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function OrderbookPanel({ data }) {
  if (!data || data.error) return null;

  const { walls = {}, imbalance = {}, sweeps = [], mid_price, spread_pct } = data;
  const bidWalls = walls.bid_walls || [];
  const askWalls = walls.ask_walls || [];
  const ratio = imbalance.imbalance_ratio || 1;
  const bias = imbalance.bias || 'NEUTRAL';
  const biasColor = bias.includes('BULLISH') ? 'text-green-400' : bias.includes('BEARISH') ? 'text-red-400' : 'text-zinc-400';
  const bidBarWidth = Math.min(100, (ratio / (1 + ratio)) * 100);

  return (
    <div className="space-y-3">
      {/* Mid price + spread */}
      <div className="flex items-center justify-between">
        <div className="text-xs text-zinc-500">Mid Price</div>
        <div className="text-white font-mono text-sm font-bold">{formatPrice(mid_price)}</div>
        <div className="text-zinc-500 text-xs">Spread: {spread_pct?.toFixed(4)}%</div>
      </div>

      {/* Imbalance bar */}
      <div className="bg-zinc-900/50 rounded-lg p-2">
        <div className={`text-xs font-medium mb-1 ${biasColor}`}>
          Book Imbalance: {bias.replace('_', ' ')} ({ratio.toFixed(2)}x)
        </div>
        <div className="flex rounded-full overflow-hidden h-2">
          <div className="bg-green-500" style={{ width: `${bidBarWidth}%` }} />
          <div className="bg-red-500" style={{ width: `${100 - bidBarWidth}%` }} />
        </div>
        <div className="flex justify-between text-xs text-zinc-500 mt-1">
          <span className="text-green-400">Bids {imbalance.bid_pct?.toFixed(0)}%</span>
          <span className="text-red-400">Asks {imbalance.ask_pct?.toFixed(0)}%</span>
        </div>
      </div>

      {/* Walls */}
      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-zinc-500 mb-1">Bid Walls 🟢</div>
          {bidWalls.length === 0 && <span className="text-zinc-600">None detected</span>}
          {bidWalls.map((w, i) => (
            <div key={i} className="bg-green-500/10 px-2 py-1 rounded mb-0.5">
              <div className="text-green-300 font-mono">{formatPrice(w.price)}</div>
              <div className="text-zinc-400">${(w.size_usd / 1000).toFixed(0)}K · {w.strength}x avg</div>
            </div>
          ))}
        </div>
        <div>
          <div className="text-zinc-500 mb-1">Ask Walls 🔴</div>
          {askWalls.length === 0 && <span className="text-zinc-600">None detected</span>}
          {askWalls.map((w, i) => (
            <div key={i} className="bg-red-500/10 px-2 py-1 rounded mb-0.5">
              <div className="text-red-300 font-mono">{formatPrice(w.price)}</div>
              <div className="text-zinc-400">${(w.size_usd / 1000).toFixed(0)}K · {w.strength}x avg</div>
            </div>
          ))}
        </div>
      </div>

      {/* Sweeps */}
      {sweeps.length > 0 && (
        <div className="space-y-1">
          <div className="text-zinc-500 text-xs">⚡ Wall Sweeps Detected</div>
          {sweeps.map((s, i) => (
            <div key={i} className={`text-xs px-2 py-1 rounded ${
              s.direction === 'BULLISH' ? 'bg-green-500/10 text-green-300' : 'bg-red-500/10 text-red-300'
            }`}>
              {s.desc}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SignalCard({ signal, symbol, currentPrice }) {
  if (!signal || signal.direction === 'NONE') return null;

  const isLong = signal.direction === 'LONG';
  return (
    <div className={`rounded-lg border p-3 ${
      isLong
        ? 'bg-green-500/10 border-green-500/30'
        : 'bg-red-500/10 border-red-500/30'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          {isLong ? <TrendingUp className="w-5 h-5 text-green-400" /> : <TrendingDown className="w-5 h-5 text-red-400" />}
          <span className={`font-bold text-sm ${isLong ? 'text-green-400' : 'text-red-400'}`}>
            {signal.direction} — {signal.confidence?.toFixed(0)}% Confidence
          </span>
        </div>
        <Badge className={isLong ? 'bg-green-500/20 text-green-300' : 'bg-red-500/20 text-red-300'}>
          R:R {signal.rr ?? '-'}x
        </Badge>
      </div>

      <div className="grid grid-cols-3 gap-2 mb-2 text-xs">
        <div className="text-center">
          <div className="text-zinc-500">Entry</div>
          <div className="text-white font-mono font-bold">{formatPrice(signal.entry)}</div>
        </div>
        <div className="text-center">
          <div className="text-zinc-500">TP</div>
          <div className="text-green-400 font-mono font-bold">{formatPrice(signal.tp)}</div>
        </div>
        <div className="text-center">
          <div className="text-zinc-500">SL</div>
          <div className="text-red-400 font-mono font-bold">{formatPrice(signal.sl)}</div>
        </div>
      </div>

      {signal.confirmations?.length > 0 && (
        <div className="space-y-0.5">
          {signal.confirmations.slice(0, 5).map((c, i) => (
            <div key={i} className="text-xs text-zinc-400 flex items-start gap-1">
              <span className="text-green-400 shrink-0">✓</span> {c}
            </div>
          ))}
        </div>
      )}

      {signal.warnings?.length > 0 && (
        <div className="mt-1 space-y-0.5">
          {signal.warnings.map((w, i) => (
            <div key={i} className="text-xs text-yellow-400 flex items-start gap-1">
              <span className="shrink-0">⚠</span> {w}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function VolumeProfile() {
  const [symbol, setSymbol] = useState('BTC/USDT');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('profile');
  const [scanResults, setScanResults] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [liqLastRefresh, setLiqLastRefresh] = useState(null);
  const liqIntervalRef = useRef(null);

  const fetchData = useCallback(async (sym = symbol) => {
    setLoading(true);
    try {
      const apiSym = sym.replace('/', '');  // BTC/USDT → BTCUSDT (avoids URL slash issues)
      const res = await fetch(`${API_URL}/api/vp/full/${apiSym}`);
      const json = await res.json();
      setData(json);
      setLastUpdated(new Date());
    } catch (e) {
      console.error('VP fetch error:', e);
    } finally {
      setLoading(false);
    }
  }, [symbol]);

  const runScan = async () => {
    setScanning(true);
    try {
      const apiSyms = SYMBOLS.map(s => s.replace('/', '')).join(',');
      const res = await fetch(`${API_URL}/api/vp/scan?symbols=${apiSyms}`);
      const json = await res.json();
      setScanResults(json.signals || []);
    } catch (e) {
      console.error('VP scan error:', e);
    } finally {
      setScanning(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [symbol]);

  // Auto-refresh liq heatmap every 30s when on liq tab
  useEffect(() => {
    clearInterval(liqIntervalRef.current);
    if (activeTab === 'liq') {
      setLiqLastRefresh(new Date());
      liqIntervalRef.current = setInterval(() => {
        fetchData(symbol);
        setLiqLastRefresh(new Date());
      }, LIQ_CHART_REFRESH_MS);
    }
    return () => clearInterval(liqIntervalRef.current);
  }, [activeTab, symbol]);

  const tabs = [
    { id: 'profile', label: 'Volume Profile', icon: BarChart3 },
    { id: 'liq', label: 'Liq Heatmap', icon: Flame },
    { id: 'book', label: 'Orderbook', icon: Activity },
    { id: 'scan', label: 'Multi-Scan', icon: Target },
  ];

  return (
    <div className="max-w-5xl mx-auto px-4 py-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-orange-400" />
            Hyper Accuracy Engine
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Volume Profile · Liquidation Heatmap · Orderbook · BTC Macro Gate
          </p>
        </div>
        <div className="flex items-center gap-2">
          {lastUpdated && (
            <span className="text-xs text-zinc-600">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={() => fetchData()}
            disabled={loading}
            className="border-zinc-700 text-zinc-300 hover:bg-zinc-800"
          >
            <RefreshCw className={`w-3 h-3 mr-1 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Symbol selector */}
      <div className="flex flex-wrap gap-1.5">
        {SYMBOLS.map(s => (
          <button
            key={s}
            onClick={() => setSymbol(s)}
            className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
              symbol === s
                ? 'bg-orange-500 text-white'
                : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-white'
            }`}
          >
            {s.replace('/USDT', '')}
          </button>
        ))}
      </div>

      {/* Signal card (if any) */}
      {data?.signal && data.signal.direction !== 'NONE' && (
        <SignalCard signal={data.signal} symbol={symbol} currentPrice={data.current_price} />
      )}

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-900/50 p-1 rounded-lg">
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all flex-1 justify-center ${
              activeTab === t.id
                ? 'bg-orange-500/20 text-orange-400'
                : 'text-zinc-500 hover:text-white'
            }`}
          >
            <t.icon className="w-3 h-3" />
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'profile' && (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-zinc-300 flex items-center justify-between">
              <span>Volume Session Profile — {symbol}</span>
              {data?.current_price && (
                <span className="text-orange-400 font-mono">{formatPrice(data.current_price)}</span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center text-zinc-500 py-8">Loading...</div>
            ) : data ? (
              <ProfilePanel data={data.volume_profile_1h} />
            ) : null}
          </CardContent>
        </Card>
      )}

      {activeTab === 'liq' && (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-zinc-300">Liquidation Heatmap — {symbol}</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center text-zinc-500 py-8">Loading...</div>
            ) : data ? (
              <LiqPanel data={data.liquidation_heatmap} lastRefresh={liqLastRefresh} />
            ) : null}
          </CardContent>
        </Card>
      )}

      {activeTab === 'book' && (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-zinc-300">Orderbook Depth — {symbol}</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center text-zinc-500 py-8">Loading...</div>
            ) : data ? (
              <OrderbookPanel data={data.orderbook} />
            ) : null}
          </CardContent>
        </Card>
      )}

      {activeTab === 'scan' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <p className="text-xs text-zinc-500">Scan top 10 pairs for VP setups (confidence ≥ 65%)</p>
            <Button
              size="sm"
              onClick={runScan}
              disabled={scanning}
              className="bg-orange-500 hover:bg-orange-600 text-white"
            >
              {scanning ? (
                <><RefreshCw className="w-3 h-3 mr-1 animate-spin" /> Scanning...</>
              ) : (
                <><Target className="w-3 h-3 mr-1" /> Run Scan</>
              )}
            </Button>
          </div>

          {scanResults.length === 0 && !scanning && (
            <div className="text-center text-zinc-600 py-8 text-sm">
              Hit "Run Scan" to find VP setups across top pairs
            </div>
          )}

          {scanResults.map((result, i) => (
            <Card key={i} className="bg-zinc-900/50 border-zinc-800">
              <CardContent className="pt-4">
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-bold">{result.symbol}</span>
                    <Badge className={
                      result.signal?.direction === 'LONG'
                        ? 'bg-green-500/20 text-green-300'
                        : 'bg-red-500/20 text-red-300'
                    }>
                      {result.signal?.direction}
                    </Badge>
                  </div>
                  <span className="text-orange-400 text-sm font-bold">
                    {result.signal?.confidence?.toFixed(0)}%
                  </span>
                </div>
                <SignalCard
                  signal={result.signal}
                  symbol={result.symbol}
                  currentPrice={result.current_price}
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
