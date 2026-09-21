import React, { useState, useEffect, useRef } from 'react';
import { Activity, RefreshCw, TrendingUp, AlertTriangle, Shield } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const REGIME_CONFIG = {
  STRUCTURED:   { color: 'text-green-400',  bg: 'bg-green-500/10',  border: 'border-green-500/30',  emoji: '🟢', label: 'STRUCTURED' },
  TRANSITIONAL: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', emoji: '🟡', label: 'TRANSITIONAL' },
  CHAOTIC:      { color: 'text-red-400',    bg: 'bg-red-500/10',    border: 'border-red-500/30',    emoji: '🔴', label: 'CHAOTIC' },
};

const DEFAULT_CONFIG = REGIME_CONFIG.TRANSITIONAL;

// Thin arc gauge: renders H_market as a 180-degree arc
function EntropyGauge({ value }) {
  const pct = Math.min(1, Math.max(0, value));
  const radius = 54;
  const cx = 70, cy = 70;
  const startAngle = Math.PI;
  const endAngle = 0;

  const angleRange = Math.PI; // 180 degrees
  const fillAngle = startAngle - pct * angleRange;

  const arcX = (angle) => cx + radius * Math.cos(angle);
  const arcY = (angle) => cy + radius * Math.sin(angle);

  // Zone colours on arc
  const zones = [
    { start: 1.00, end: 0.65, color: '#22c55e' }, // 0.00–0.40 → green
    { start: 0.65, end: 0.40, color: '#eab308' }, // 0.40–0.65 → yellow
    { start: 0.40, end: 0.00, color: '#ef4444' }, // 0.65–1.00 → red
  ];

  const needleAngle = startAngle - pct * angleRange;
  const needleLen = 42;
  const needleX = cx + needleLen * Math.cos(needleAngle);
  const needleY = cy + needleLen * Math.sin(needleAngle);

  // Build colour for current fill
  let fillColor = '#22c55e';
  if (value >= 0.65) fillColor = '#ef4444';
  else if (value >= 0.40) fillColor = '#eab308';

  return (
    <svg viewBox="0 0 140 80" className="w-full max-w-[200px]">
      {/* Track */}
      <path
        d={`M ${arcX(startAngle)} ${arcY(startAngle)} A ${radius} ${radius} 0 0 1 ${arcX(endAngle)} ${arcY(endAngle)}`}
        fill="none" stroke="#27272a" strokeWidth="10" strokeLinecap="round"
      />
      {/* Fill */}
      {pct > 0 && (
        <path
          d={`M ${arcX(startAngle)} ${arcY(startAngle)} A ${radius} ${radius} 0 0 1 ${arcX(fillAngle)} ${arcY(fillAngle)}`}
          fill="none" stroke={fillColor} strokeWidth="10" strokeLinecap="round"
        />
      )}
      {/* Zone ticks */}
      {[0.40, 0.65].map((mark) => {
        const ang = startAngle - mark * angleRange;
        const x1 = cx + (radius - 7) * Math.cos(ang);
        const y1 = cy + (radius - 7) * Math.sin(ang);
        const x2 = cx + (radius + 7) * Math.cos(ang);
        const y2 = cy + (radius + 7) * Math.sin(ang);
        return <line key={mark} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#52525b" strokeWidth="1.5" />;
      })}
      {/* Needle */}
      <line x1={cx} y1={cy} x2={needleX} y2={needleY} stroke="white" strokeWidth="2" strokeLinecap="round" />
      <circle cx={cx} cy={cy} r="4" fill="white" />
      {/* Value label */}
      <text x={cx} y={cy + 16} textAnchor="middle" fill="white" fontSize="13" fontWeight="bold">
        {value.toFixed(3)}
      </text>
    </svg>
  );
}

// Per-asset entropy bar
function AssetBar({ asset, data }) {
  const pct = Math.min(100, Math.max(0, (data.H_j ?? 0.5) * 100));
  let barColor = 'bg-green-500';
  if (data.H_j >= 0.65) barColor = 'bg-red-500';
  else if (data.H_j >= 0.40) barColor = 'bg-yellow-500';

  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="w-8 font-mono text-zinc-300">{asset}</span>
      <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-700 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-zinc-400">{(data.H_j ?? 0).toFixed(3)}</span>
      <span className="w-8 text-right text-zinc-600 text-[10px]">{Math.round((data.weight ?? 0) * 100)}%</span>
    </div>
  );
}

// Mini sparkline for 7-day history
function Sparkline({ history }) {
  if (!history || history.length < 2) {
    return <div className="h-10 flex items-center justify-center text-zinc-600 text-xs">No history yet</div>;
  }

  const values = history.map(d => d.H_market);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 0.01;
  const w = 280, h = 40;
  const pts = values.map((v, i) => {
    const x = (i / (values.length - 1)) * w;
    const y = h - ((v - min) / range) * (h - 4) - 2;
    return `${x},${y}`;
  });

  // Colour last point by regime
  const last = values[values.length - 1];
  let strokeColor = '#22c55e';
  if (last >= 0.65) strokeColor = '#ef4444';
  else if (last >= 0.40) strokeColor = '#eab308';

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-10">
      {/* Zone bands */}
      <rect x="0" y="0" width={w} height={((1 - 0.65) / (max - min || 1)) * h} fill="#ef444420" />
      <polyline points={pts.join(' ')} fill="none" stroke={strokeColor} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      {/* Last point dot */}
      {(() => {
        const [lx, ly] = pts[pts.length - 1].split(',');
        return <circle cx={lx} cy={ly} r="2.5" fill={strokeColor} />;
      })()}
    </svg>
  );
}

export default function MarketRegime({ compact = false }) {
  const [status, setStatus] = useState(null);
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchStatus = async () => {
    try {
      // Primary: quantum state has H, C, S_norm, regime, position_multiplier, engine_states
      const res = await fetch(`${API_URL}/api/quantum/state`);
      if (res.ok) {
        const data = await res.json();
        if (!data.error) {
          const H = data.H ?? 0.5;
          // Derive entropy-based regime from H score
          // (quantum state uses "trending/ranging" — we reclassify here)
          let derivedRegime = 'TRANSITIONAL';
          if (H < 0.40) derivedRegime = 'STRUCTURED';
          else if (H >= 0.65) derivedRegime = 'CHAOTIC';

          // Map quantum state fields to oracle-entropy shape expected by this component
          setStatus({
            regime:         derivedRegime,
            H_market:       H,
            H_combined:     data.C ?? 0.5,
            H_internal:     data.S_norm ?? 0.5,
            size_modifier:  data.position_multiplier ?? 1.0,
            per_asset:      data.per_asset ?? null,
            error_state:    false,
          });
          setLastRefresh(Date.now());
        }
      }
    } catch (err) {
      console.warn('Quantum state fetch failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const fetchHistory = async () => {
    try {
      // quantum/history returns snapshots with H, C, regime, timestamp
      const res = await fetch(`${API_URL}/api/quantum/history?limit=168`);
      if (res.ok) {
        const data = await res.json();
        // Map to oracle-entropy history shape: [{H_market, timestamp}]
        const mapped = (data.history || []).map(d => ({
          H_market:  d.H ?? 0.5,
          timestamp: d.timestamp,
        }));
        setHistory(mapped);
      }
    } catch (err) {
      console.warn('Quantum history fetch failed:', err);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchHistory();
    const si = setInterval(fetchStatus, 60000);   // refresh every minute
    const hi = setInterval(fetchHistory, 600000);  // refresh history every 10min
    return () => { clearInterval(si); clearInterval(hi); };
  }, []);

  const regime = status?.regime ?? 'TRANSITIONAL';
  const cfg = REGIME_CONFIG[regime] ?? DEFAULT_CONFIG;
  const H = status?.H_market ?? 0.5;
  const Hc = status?.H_combined ?? 0.5;
  const assets = ["BTC", "ETH", "SOL", "BNB", "XRP"];

  if (compact) {
    // Compact widget for Dashboard page embedding
    return (
      <Card className={`border ${cfg.border} ${cfg.bg}`}>
        <CardContent className="p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Shield className="w-3.5 h-3.5 text-zinc-400" />
              <span className="text-xs font-semibold text-zinc-300">ORACLE Gate</span>
            </div>
            <span className={`text-xs font-bold ${cfg.color}`}>{cfg.emoji} {cfg.label}</span>
          </div>
          {/* Mini gauge row */}
          <div className="flex items-center gap-3">
            <div className="flex-1">
              <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                <span>H_market</span>
                <span className={`font-mono ${cfg.color}`}>{H.toFixed(3)}</span>
              </div>
              <div className="h-1.5 bg-zinc-700 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    H >= 0.65 ? 'bg-red-500' : H >= 0.40 ? 'bg-yellow-500' : 'bg-green-500'
                  }`}
                  style={{ width: `${H * 100}%` }}
                />
              </div>
            </div>
            <div className="text-right">
              <div className="text-[10px] text-zinc-500">Size mod</div>
              <div className="text-xs font-mono text-zinc-300">
                {status ? `×${(status.size_modifier ?? 1).toFixed(2)}` : '—'}
              </div>
            </div>
          </div>
          {loading && <p className="text-[10px] text-zinc-600 mt-1">Loading...</p>}
        </CardContent>
      </Card>
    );
  }

  // Full-page panel
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-600 to-purple-700 flex items-center justify-center shadow-lg">
            <Shield className="w-5 h-5 text-white" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">ORACLE Entropy Gate</h2>
            <p className="text-xs text-zinc-500">Market-Wide Chaos Monitor — outermost trade gate</p>
          </div>
        </div>
        <button
          onClick={() => { fetchStatus(); fetchHistory(); }}
          className="p-2 text-zinc-400 hover:text-white transition-colors"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Main regime card */}
      <Card className={`border-2 ${cfg.border} ${cfg.bg}`}>
        <CardContent className="p-5">
          <div className="flex flex-col sm:flex-row items-center gap-6">
            {/* Gauge */}
            <div className="flex flex-col items-center">
              <EntropyGauge value={H} />
              <div className="text-center mt-1">
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider">H_market</div>
              </div>
            </div>

            {/* Regime info */}
            <div className="flex-1 space-y-3">
              <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg border ${cfg.border} ${cfg.bg}`}>
                <span className="text-xl">{cfg.emoji}</span>
                <span className={`text-lg font-bold ${cfg.color}`}>{cfg.label}</span>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-zinc-500 text-xs">H_market</div>
                  <div className={`font-mono font-bold ${cfg.color}`}>{H.toFixed(4)}</div>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-zinc-500 text-xs">H_combined</div>
                  <div className="font-mono font-bold text-white">{Hc.toFixed(4)}</div>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-zinc-500 text-xs">Size Modifier</div>
                  <div className="font-mono font-bold text-orange-400">
                    ×{(status?.size_modifier ?? 1).toFixed(2)}
                  </div>
                </div>
                <div className="bg-zinc-800/50 rounded-lg p-2">
                  <div className="text-zinc-500 text-xs">H_internal</div>
                  <div className="font-mono font-bold text-blue-400">
                    {(status?.H_internal ?? 0).toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Threshold legend */}
              <div className="flex gap-3 text-xs text-zinc-500">
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-green-500 inline-block" /> &lt;0.40 Structured</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-yellow-500 inline-block" /> 0.40–0.65 Transitional</span>
                <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-full bg-red-500 inline-block" /> &gt;0.65 Chaotic</span>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Per-asset entropy bars */}
      <Card className="bg-zinc-900/50 border-zinc-800/50">
        <CardContent className="p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-zinc-400" />
            <span className="text-sm font-semibold text-zinc-300">Per-Asset Entropy</span>
          </div>
          <div className="space-y-2">
            {status?.per_asset
              ? assets.map(asset =>
                  status.per_asset[asset] ? (
                    <AssetBar key={asset} asset={asset} data={status.per_asset[asset]} />
                  ) : (
                    <div key={asset} className="flex items-center gap-2 text-xs text-zinc-600">
                      <span className="w-8 font-mono">{asset}</span>
                      <span>no data</span>
                    </div>
                  )
                )
              : <p className="text-zinc-600 text-xs">Loading asset data...</p>
            }
          </div>
          <div className="mt-2 flex justify-end gap-3 text-[10px] text-zinc-600">
            <span>bar = H_j (entropy)</span>
            <span>last col = market cap weight</span>
          </div>
        </CardContent>
      </Card>

      {/* 7-day history chart */}
      <Card className="bg-zinc-900/50 border-zinc-800/50">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-zinc-400" />
              <span className="text-sm font-semibold text-zinc-300">H_market — 7 Day History</span>
            </div>
            <span className="text-xs text-zinc-600">{history.length} readings</span>
          </div>
          <Sparkline history={history} />
          <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
            <span>{history[0] ? new Date(history[0].timestamp).toLocaleDateString() : '—'}</span>
            <span>now</span>
          </div>
        </CardContent>
      </Card>

      {/* Status footer */}
      <div className="flex items-center justify-between text-[10px] text-zinc-600">
        <span>
          {status?.error_state
            ? <span className="text-amber-500 flex items-center gap-1"><AlertTriangle className="w-3 h-3" /> Error state — using cached regime</span>
            : 'Updates every 1h on candle close'
          }
        </span>
        <span>
          {lastRefresh
            ? `Last API fetch: ${new Date(lastRefresh).toLocaleTimeString()}`
            : 'Never fetched'
          }
        </span>
      </div>
    </div>
  );
}
