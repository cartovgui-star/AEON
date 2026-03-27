import React, { useState, useEffect, useCallback } from 'react';
import { Activity, RefreshCw, TrendingUp, TrendingDown, Zap, Target, Shield, Ban, Clock, BarChart3, AlertTriangle, Play, Pause } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ENGINE_META = {
  autonomous_trader_v2: { label: 'Autonomous Trader', emoji: '🤖', color: 'blue' },
  free_will_v2:         { label: 'Free Will',          emoji: '🧠', color: 'purple' },
  dual_engine:          { label: 'Dual Engine',         emoji: '⚡', color: 'yellow' },
  day_trader:           { label: 'Day Trader',          emoji: '📈', color: 'orange' },
  yolo_engine:          { label: 'YOLO Engine',         emoji: '🚀', color: 'red' },
  vwap_scalper:         { label: 'VWAP Scalper',        emoji: '🎯', color: 'teal' },
  elite_strategy:       { label: 'Elite Strategy',      emoji: '👑', color: 'gold' },
};

const COLOR_MAP = {
  blue:   { bg: 'bg-blue-500/10',   border: 'border-blue-500/30',   text: 'text-blue-400'   },
  purple: { bg: 'bg-purple-500/10', border: 'border-purple-500/30', text: 'text-purple-400' },
  yellow: { bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', text: 'text-yellow-400' },
  orange: { bg: 'bg-orange-500/10', border: 'border-orange-500/30', text: 'text-orange-400' },
  red:    { bg: 'bg-red-500/10',    border: 'border-red-500/30',    text: 'text-red-400'    },
  teal:   { bg: 'bg-teal-500/10',   border: 'border-teal-500/30',   text: 'text-teal-400'   },
  gold:   { bg: 'bg-amber-500/10',  border: 'border-amber-500/30',  text: 'text-amber-400'  },
};

function WinRateBar({ rate }) {
  const pct = Math.min(100, Math.max(0, rate));
  const color = pct >= 60 ? 'bg-green-500' : pct >= 45 ? 'bg-yellow-500' : 'bg-red-500';
  return (
    <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-1">
      <div className={`${color} h-1.5 rounded-full transition-all duration-500`} style={{ width: `${pct}%` }} />
    </div>
  );
}

function PnlBadge({ pnl }) {
  if (pnl === 0) return <span className="text-zinc-500">$0</span>;
  const cls = pnl > 0 ? 'text-green-400' : 'text-red-400';
  return <span className={cls}>{pnl > 0 ? '+' : ''}${pnl.toFixed(2)}</span>;
}

// Engines that have dedicated toggle endpoints
const ENGINE_TOGGLE_ENDPOINTS = {
  autonomous_trader_v2: '/api/trading/toggle',
  free_will_v2:         '/api/freewill/toggle',
  dual_engine:          '/api/dual/toggle',
  day_trader:           '/api/dual/day-trader/toggle',
  yolo_engine:          '/api/yolo/toggle',
  vwap_scalper:         '/api/vwap-scalper/toggle',
};

function EngineCard({ name, data, isActive, onToggle, toggling }) {
  const meta = ENGINE_META[name] || { label: name, emoji: '⚙️', color: 'blue' };
  const colors = COLOR_MAP[meta.color] || COLOR_MAP.blue;
  const stats = data.stats || {};
  const config = data.config || {};
  const openTrades = data.open_trades || [];
  const blacklisted = data.blacklisted || [];
  const inCooldown = data.in_cooldown || [];

  const winRate = stats.win_rate ?? 0;
  const totalPnl = stats.total_pnl ?? 0;
  const totalTrades = stats.total_trades ?? 0;
  const openCount = stats.open_trades ?? 0;
  const blockedCount = stats.blocked_trades ?? 0;
  const hasToggle = name in ENGINE_TOGGLE_ENDPOINTS;

  return (
    <Card className={`${colors.bg} ${colors.border} border rounded-xl`}>
      <CardContent className="p-4">
        {/* Header */}
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="text-lg">{meta.emoji}</span>
            <div>
              <div className={`text-sm font-semibold ${colors.text}`}>{meta.label}</div>
              <div className="text-xs text-zinc-500">{data.risk_profile || 'balanced'}</div>
            </div>
          </div>
          <div className="flex items-center gap-1.5">
            {/* Active/Paused badge */}
            {isActive !== undefined && (
              <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
                isActive ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
              }`}>
                {isActive ? 'ON' : 'OFF'}
              </span>
            )}
            {openCount > 0 && (
              <span className="text-xs bg-green-500/20 text-green-400 px-1.5 py-0.5 rounded">
                {openCount} open
              </span>
            )}
            {blockedCount > 0 && (
              <span className="text-xs bg-zinc-700 text-zinc-400 px-1.5 py-0.5 rounded">
                {blockedCount} blocked
              </span>
            )}
            {/* Toggle button */}
            {hasToggle && onToggle && (
              <button
                onClick={() => onToggle(name, isActive)}
                disabled={toggling === name}
                className={`p-1.5 rounded-lg transition-all ${
                  isActive
                    ? 'bg-green-500/20 text-green-400 hover:bg-red-500/20 hover:text-red-400'
                    : 'bg-zinc-700 text-zinc-400 hover:bg-green-500/20 hover:text-green-400'
                } disabled:opacity-50`}
                title={isActive ? 'Pause engine' : 'Start engine'}
              >
                {toggling === name
                  ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  : isActive
                    ? <Pause className="w-3.5 h-3.5" />
                    : <Play className="w-3.5 h-3.5" />
                }
              </button>
            )}
          </div>
        </div>

        {/* Stats grid */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="bg-zinc-900/60 rounded-lg p-2 text-center">
            <div className="text-xs text-zinc-500">Win Rate</div>
            <div className={`text-sm font-bold ${winRate >= 50 ? 'text-green-400' : 'text-red-400'}`}>
              {winRate.toFixed(1)}%
            </div>
            <WinRateBar rate={winRate} />
          </div>
          <div className="bg-zinc-900/60 rounded-lg p-2 text-center">
            <div className="text-xs text-zinc-500">Total PnL</div>
            <div className="text-sm font-bold"><PnlBadge pnl={totalPnl} /></div>
            <div className="text-xs text-zinc-600 mt-1">{totalTrades} trades</div>
          </div>
          <div className="bg-zinc-900/60 rounded-lg p-2 text-center">
            <div className="text-xs text-zinc-500">Daily PnL</div>
            <div className="text-sm font-bold"><PnlBadge pnl={stats.daily_pnl ?? 0} /></div>
            <div className="text-xs text-zinc-600 mt-1">{stats.daily_trades ?? 0} today</div>
          </div>
        </div>

        {/* Config row */}
        <div className="flex flex-wrap gap-1 mb-2">
          <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
            {config.min_confidence}% conf
          </span>
          <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
            {config.min_confluences} confluence
          </span>
          <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
            {config.max_leverage}x max
          </span>
          <span className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
            ${config.max_position_size?.toLocaleString()}
          </span>
        </div>

        {/* Open trades */}
        {openTrades.length > 0 && (
          <div className="mt-2 space-y-1">
            <div className="text-xs text-zinc-500 mb-1">Open positions</div>
            {openTrades.slice(0, 3).map((t, i) => (
              <div key={i} className="flex justify-between items-center bg-zinc-900/50 rounded px-2 py-1">
                <div className="flex items-center gap-1.5">
                  {t.direction === 'long' ? (
                    <TrendingUp className="w-3 h-3 text-green-400" />
                  ) : (
                    <TrendingDown className="w-3 h-3 text-red-400" />
                  )}
                  <span className="text-xs text-zinc-300">{t.symbol?.replace('/USDT', '')}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-zinc-500">{t.confidence}%</span>
                  <span className="text-xs text-zinc-500">{t.leverage}x</span>
                </div>
              </div>
            ))}
            {openTrades.length > 3 && (
              <div className="text-xs text-zinc-600 text-center">+{openTrades.length - 3} more</div>
            )}
          </div>
        )}

        {/* Cooldown / blacklist warnings */}
        {(inCooldown.length > 0 || blacklisted.length > 0) && (
          <div className="mt-2 flex flex-wrap gap-1">
            {inCooldown.slice(0, 3).map((s, i) => (
              <span key={i} className="text-xs bg-yellow-500/10 text-yellow-500 px-1.5 py-0.5 rounded flex items-center gap-1">
                <Clock className="w-2.5 h-2.5" />{s.replace('/USDT', '')}
              </span>
            ))}
            {blacklisted.slice(0, 3).map((s, i) => (
              <span key={i} className="text-xs bg-red-500/10 text-red-500 px-1.5 py-0.5 rounded flex items-center gap-1">
                <Ban className="w-2.5 h-2.5" />{s.replace('/USDT', '')}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function GlobalStats({ data }) {
  const g = data?.global || {};
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {[
        { label: 'Total Trades', value: g.total_trades ?? 0, icon: BarChart3, color: 'text-blue-400' },
        { label: 'Win Rate',     value: `${(g.win_rate ?? 0).toFixed(1)}%`, icon: Target, color: (g.win_rate ?? 0) >= 50 ? 'text-green-400' : 'text-red-400' },
        { label: 'Total PnL',    value: `${(g.total_pnl ?? 0) >= 0 ? '+' : ''}$${(g.total_pnl ?? 0).toFixed(2)}`, icon: TrendingUp, color: (g.total_pnl ?? 0) >= 0 ? 'text-green-400' : 'text-red-400' },
        { label: 'Open Now',     value: g.total_open ?? 0, icon: Activity, color: 'text-orange-400' },
      ].map(({ label, value, icon: Icon, color }) => (
        <Card key={label} className="bg-zinc-900/60 border-zinc-800/50">
          <CardContent className="p-3">
            <div className="flex items-center gap-2 mb-1">
              <Icon className={`w-3.5 h-3.5 ${color}`} />
              <span className="text-xs text-zinc-500">{label}</span>
            </div>
            <div className={`text-xl font-bold ${color}`}>{value}</div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

export default function EnginesDashboard() {
  const [status, setStatus] = useState(null);
  const [activeStates, setActiveStates] = useState({});
  const [toggling, setToggling] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      // Fetch engine system status + per-engine active states in parallel
      const [statusRes, v2, fw, dual, yolo, vwap] = await Promise.allSettled([
        fetch(`${API_URL}/api/engines/status`).then(r => r.json()),
        fetch(`${API_URL}/api/trading/v2/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/freewill/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/dual/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/yolo/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/vwap-scalper/stats`).then(r => r.json()),
      ]);

      if (statusRes.status === 'fulfilled') {
        setStatus(statusRes.value);
        setError(null);
      } else {
        throw new Error(statusRes.reason?.message || 'Failed to load engine status');
      }

      setActiveStates({
        autonomous_trader_v2: v2.status === 'fulfilled' ? v2.value.active : undefined,
        free_will_v2:         fw.status === 'fulfilled' ? fw.value.active : undefined,
        dual_engine:          dual.status === 'fulfilled' ? dual.value.active : undefined,
        day_trader:           dual.status === 'fulfilled' ? dual.value.day_trader?.active : undefined,
        yolo_engine:          yolo.status === 'fulfilled' ? yolo.value.active : undefined,
        vwap_scalper:         vwap.status === 'fulfilled' ? vwap.value.active : undefined,
      });

      setLastUpdate(new Date().toLocaleTimeString());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const toggleEngine = useCallback(async (engineName, currentActive) => {
    const endpoint = ENGINE_TOGGLE_ENDPOINTS[engineName];
    if (!endpoint) return;
    setToggling(engineName);
    // Optimistic update
    setActiveStates(prev => ({ ...prev, [engineName]: !currentActive }));
    try {
      await fetch(`${API_URL}${endpoint}?active=${!currentActive}`, { method: 'POST' });
      // Refresh to confirm real state
      fetchStatus();
    } catch (e) {
      // Revert on error
      setActiveStates(prev => ({ ...prev, [engineName]: currentActive }));
    } finally {
      setToggling(null);
    }
  }, [fetchStatus]);

  useEffect(() => {
    fetchStatus();
    const t = setInterval(fetchStatus, 6000);
    return () => clearInterval(t);
  }, [fetchStatus]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Shield className="w-6 h-6 text-orange-400" />
            Engine Control
          </h1>
          <p className="text-sm text-zinc-500 mt-1">
            {status ? Object.keys(status.engines || {}).length : '—'} active trading engines · unified risk validation
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="text-xs text-zinc-600">Updated {lastUpdate}</span>
          )}
          <button
            onClick={fetchStatus}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-4 flex items-center gap-2 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading && !status ? (
        <div className="flex items-center justify-center py-20">
          <div className="flex items-center gap-3 text-zinc-500">
            <Activity className="w-5 h-5 animate-pulse" />
            <span>Loading engine status...</span>
          </div>
        </div>
      ) : status ? (
        <>
          <GlobalStats data={status} />

          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {Object.entries(status.engines || {}).map(([name, data]) => (
              <EngineCard
                key={name}
                name={name}
                data={data}
                isActive={activeStates[name]}
                onToggle={toggleEngine}
                toggling={toggling}
              />
            ))}
          </div>

          {/* Contradiction guard notice */}
          <div className="mt-6 bg-zinc-900/40 border border-zinc-800/50 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-2">
              <Shield className="w-4 h-4 text-orange-400" />
              <span className="text-sm font-semibold text-zinc-300">Cross-Engine Safeguards</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-zinc-500">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-orange-400 flex-shrink-0" />
                Contradiction guard — no conflicting LONG/SHORT on same coin across engines
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-blue-400 flex-shrink-0" />
                R:R enforcement — minimum 1.5:1 reward-to-risk on every trade
              </div>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" />
                Cooldown per engine — auto-cooling symbols after a loss
              </div>
            </div>
          </div>

          {/* Permanent blacklist */}
          <div className="mt-4 bg-zinc-900/40 border border-red-500/20 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Ban className="w-4 h-4 text-red-400" />
              <span className="text-sm font-semibold text-zinc-300">Permanently Banned Coins</span>
              <span className="text-xs text-zinc-600 ml-1">— removed from all engine symbol lists</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {[
                { symbol: 'ARB', reason: '76 trades · 8% WR · -$10,255', date: '2026-03-22' },
                { symbol: 'NEAR', reason: '39 trades · 0% WR · -$8,515', date: '2026-03-22' },
              ].map(({ symbol, reason, date }) => (
                <div key={symbol} className="flex items-center gap-2 bg-red-500/5 border border-red-500/20 rounded-lg px-3 py-2">
                  <Ban className="w-3 h-3 text-red-400 flex-shrink-0" />
                  <div>
                    <span className="text-red-400 font-bold text-sm">{symbol}</span>
                    <span className="text-zinc-500 text-xs ml-2">{reason}</span>
                    <span className="text-zinc-600 text-xs ml-2">({date})</span>
                  </div>
                </div>
              ))}
            </div>
            <p className="text-xs text-zinc-600 mt-2">
              These coins are hardcoded out of all engine watchlists. They cannot be traded regardless of engine settings.
            </p>
          </div>
        </>
      ) : null}
    </div>
  );
}
