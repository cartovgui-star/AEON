import React, { useState, useEffect, useCallback } from 'react';
import { BarChart3, TrendingDown, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';
import {
  AreaChart, Area, BarChart, Bar, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';
import { fetchClosedTrades, fetchAccounts } from '../services/api';
import AeonLoader from './AeonLoader';

const ENGINE_SHORT = {
  autonomous_trader_v2: 'AUTO V2',
  free_will_v2: 'FREEWILL',
  dual_engine: 'DUAL',
  vwap_scalper: 'VWAP',
  yolo_engine: 'YOLO',
  elite_strategy: 'ELITE',
  institutional_scalper: 'SCALPER',
  tcn_neural: 'TCN',
  quant_analyzer: 'QUANT',
  day_trader: 'DAY',
};

const COLORS = ['#00E5FF', '#00E676', '#FFB800', '#FF3D57', '#B388FF', '#FF6D00'];

function CollapsibleSection({ title, icon: Icon, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-4 py-3"
        onClick={() => setOpen(v => !v)}
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon className="w-4 h-4 text-cyan-400" />}
          <span className="text-sm font-semibold text-white">{title}</span>
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-zinc-500" /> : <ChevronDown className="w-4 h-4 text-zinc-500" />}
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700/50 rounded-lg p-2 text-xs">
      <div className="text-zinc-400 mb-1">{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color }} className="font-mono">
          {p.name}: {typeof p.value === 'number' ? p.value.toFixed(2) : p.value}
        </div>
      ))}
    </div>
  );
};

export default function AnalyticsPage() {
  const [trades, setTrades] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [timeRange, setTimeRange] = useState('30d');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [closedRes, accsRes] = await Promise.allSettled([
        fetchClosedTrades(),
        fetchAccounts(),
      ]);
      if (closedRes.status === 'fulfilled') {
        setTrades(closedRes.value?.closed_trades || []);
      }
      if (accsRes.status === 'fulfilled') {
        setAccounts(accsRes.value?.accounts || []);
      }
    } catch (e) {
      console.error('AnalyticsPage load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Filter by time range
  const getFiltered = () => {
    const now = Date.now();
    const ranges = { '24h': 86400000, '7d': 604800000, '30d': 2592000000, 'all': Infinity };
    return trades
      .filter(t => (now - new Date(t.closed_at || t.timestamp || Date.now()).getTime()) <= (ranges[timeRange] || Infinity))
      .sort((a, b) => new Date(a.closed_at || a.timestamp || 0) - new Date(b.closed_at || b.timestamp || 0));
  };

  const filtered = getFiltered();

  // 1. Cumulative PnL curve
  let cum = 0;
  const pnlCurveData = filtered.map((t, i) => {
    cum += (t.pnl_pct || 0);
    return {
      trade: i + 1,
      pnl: parseFloat(cum.toFixed(2)),
      label: `Trade ${i + 1}`,
    };
  });

  // 2. Win rate by engine
  const engineMap = {};
  filtered.forEach(t => {
    const eng = (t.strategy || t.engine || 'unknown').toLowerCase();
    const label = ENGINE_SHORT[eng] || eng.replace(/_/g, ' ').toUpperCase();
    if (!engineMap[label]) engineMap[label] = { wins: 0, total: 0 };
    engineMap[label].total++;
    if ((t.pnl_pct || 0) > 0) engineMap[label].wins++;
  });
  const engineData = Object.entries(engineMap)
    .map(([name, d]) => ({
      name,
      winRate: d.total > 0 ? parseFloat(((d.wins / d.total) * 100).toFixed(1)) : 0,
      trades: d.total,
    }))
    .sort((a, b) => b.winRate - a.winRate);

  // 3. PnL by hour
  const hourMap = {};
  for (let h = 0; h < 24; h++) hourMap[h] = { pnl: 0, count: 0 };
  filtered.forEach(t => {
    const h = new Date(t.closed_at || t.timestamp || Date.now()).getUTCHours();
    hourMap[h].pnl += (t.pnl_pct || 0);
    hourMap[h].count++;
  });
  const hourData = Object.entries(hourMap).map(([h, d]) => ({
    hour: `${h}:00`,
    pnl: parseFloat(d.pnl.toFixed(2)),
    trades: d.count,
  }));

  // 4. Drawdown — max peak to trough
  let peak = 0, cumForDD = 0;
  const ddData = filtered.map((t, i) => {
    cumForDD += (t.pnl_pct || 0);
    if (cumForDD > peak) peak = cumForDD;
    const dd = peak > 0 ? parseFloat(((cumForDD - peak)).toFixed(2)) : 0;
    return { trade: i + 1, drawdown: dd };
  });

  // Summary stats
  const wins = filtered.filter(t => (t.pnl_pct || 0) > 0);
  const totalPnl = filtered.reduce((s, t) => s + (t.pnl_pct || 0), 0);
  const winRate = filtered.length ? ((wins.length / filtered.length) * 100).toFixed(1) : 0;
  const avgWin = wins.length ? (wins.reduce((s, t) => s + (t.pnl_pct || 0), 0) / wins.length) : 0;
  const losses = filtered.filter(t => (t.pnl_pct || 0) < 0);
  const avgLoss = losses.length ? (losses.reduce((s, t) => s + (t.pnl_pct || 0), 0) / losses.length) : 0;
  const profitFactor = losses.length && avgLoss !== 0 ? Math.abs(avgWin * wins.length / (avgLoss * losses.length)) : null;

  if (loading) return <AeonLoader message="Loading analytics..." />;

  return (
    <div className="space-y-4 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          Analytics
        </h2>
        <button onClick={load} className="p-1.5 text-zinc-500 hover:text-zinc-300">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Time range selector */}
      <div className="flex bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-1 gap-1">
        {['24h', '7d', '30d', 'all'].map(r => (
          <button
            key={r}
            onClick={() => setTimeRange(r)}
            className={`flex-1 py-1.5 rounded-lg text-xs font-semibold transition-all ${
              timeRange === r ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {r.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Quick stats */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[
          { label: 'Trades', value: filtered.length, color: 'text-white' },
          { label: 'Win Rate', value: `${winRate}%`, color: parseFloat(winRate) >= 50 ? 'text-emerald-400' : 'text-rose-400' },
          { label: 'Total PnL', value: `${totalPnl >= 0 ? '+' : ''}${totalPnl.toFixed(2)}%`, color: totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400' },
          { label: 'Profit Factor', value: profitFactor != null ? profitFactor.toFixed(2) : '—', color: profitFactor >= 1.5 ? 'text-emerald-400' : profitFactor >= 1 ? 'text-amber-400' : 'text-rose-400' },
        ].map(s => (
          <div key={s.label} className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-3 text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">{s.label}</div>
            <div className={`font-mono text-lg font-bold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Account balances */}
      {accounts.length > 0 && (
        <CollapsibleSection title="Account Balances" icon={BarChart3}>
          <div className="space-y-2">
            {accounts.map(acc => {
              const pct = acc.starting_balance
                ? ((acc.balance - acc.starting_balance) / acc.starting_balance) * 100
                : 0;
              const isPos = pct >= 0;
              return (
                <div key={acc.account_id} className="flex items-center justify-between py-1.5 border-b border-zinc-800/30 last:border-0">
                  <span className="text-sm text-white">{acc.account_id}</span>
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-sm text-white">${Number(acc.balance).toLocaleString(undefined, { maximumFractionDigits: 0 })}</span>
                    <span className={`font-mono text-xs font-semibold ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {isPos ? '+' : ''}{pct.toFixed(2)}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </CollapsibleSection>
      )}

      {/* Chart 1: Equity curve */}
      <CollapsibleSection title="Cumulative PnL Curve" icon={BarChart3}>
        {pnlCurveData.length < 2 ? (
          <div className="text-center text-zinc-600 text-xs py-4">Not enough trades to display</div>
        ) : (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={pnlCurveData}>
                <defs>
                  <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00E5FF" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#00E5FF" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="trade" tick={{ fill: '#71717a', fontSize: 10 }} />
                <YAxis tick={{ fill: '#71717a', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="pnl" name="PnL%" stroke="#00E5FF" fill="url(#pnlGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CollapsibleSection>

      {/* Chart 2: Win rate by engine */}
      <CollapsibleSection title="Win Rate by Engine" icon={BarChart3}>
        {engineData.length === 0 ? (
          <div className="text-center text-zinc-600 text-xs py-4">No engine data</div>
        ) : (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={engineData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" horizontal={false} />
                <XAxis type="number" domain={[0, 100]} tick={{ fill: '#71717a', fontSize: 10 }} unit="%" />
                <YAxis type="category" dataKey="name" tick={{ fill: '#a1a1aa', fontSize: 9 }} width={60} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="winRate" name="Win Rate" radius={[0, 4, 4, 0]}>
                  {engineData.map((entry, i) => (
                    <Cell key={i} fill={entry.winRate >= 60 ? '#00E5FF' : entry.winRate >= 50 ? '#FFB800' : '#FF3D57'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
        {/* Fallback stat list if chart is empty */}
        {engineData.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {engineData.map(e => (
              <div key={e.name} className="flex items-center justify-between text-xs">
                <span className="text-zinc-400 font-mono">{e.name}</span>
                <div className="flex items-center gap-3">
                  <span className="text-zinc-500">{e.trades} trades</span>
                  <span className={`font-mono font-bold ${e.winRate >= 60 ? 'text-cyan-400' : e.winRate >= 50 ? 'text-amber-400' : 'text-rose-400'}`}>
                    {e.winRate}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CollapsibleSection>

      {/* Chart 3: PnL by hour */}
      <CollapsibleSection title="PnL by Hour (UTC)" icon={BarChart3} defaultOpen={false}>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={hourData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
              <XAxis dataKey="hour" tick={{ fill: '#71717a', fontSize: 9 }} interval={3} />
              <YAxis tick={{ fill: '#71717a', fontSize: 10 }} />
              <Tooltip content={<CustomTooltip />} />
              <Bar dataKey="pnl" name="PnL%">
                {hourData.map((entry, i) => (
                  <Cell key={i} fill={entry.pnl >= 0 ? '#00E676' : '#FF3D57'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </CollapsibleSection>

      {/* Chart 4: Drawdown */}
      <CollapsibleSection title="Drawdown" icon={TrendingDown} defaultOpen={false}>
        {ddData.length < 2 ? (
          <div className="text-center text-zinc-600 text-xs py-4">Not enough data</div>
        ) : (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={ddData}>
                <defs>
                  <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#FF3D57" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#FF3D57" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#27272a" />
                <XAxis dataKey="trade" tick={{ fill: '#71717a', fontSize: 10 }} />
                <YAxis tick={{ fill: '#71717a', fontSize: 10 }} />
                <Tooltip content={<CustomTooltip />} />
                <Area type="monotone" dataKey="drawdown" name="Drawdown%" stroke="#FF3D57" fill="url(#ddGrad)" strokeWidth={1.5} dot={false} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CollapsibleSection>
    </div>
  );
}
