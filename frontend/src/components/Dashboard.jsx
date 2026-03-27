import React, { useState, useEffect, useCallback } from 'react';
import {
  Bot, Activity, TrendingUp, TrendingDown, Target, BarChart3,
  Brain, Zap, AlertTriangle, Radio, Power,
  Flame, ChevronRight, Ban, Timer, Scale, FlaskConical,
  Sparkles, Calendar, BookOpen, Lightbulb, Shield, Cpu,
  ArrowUpRight, ArrowDownRight, DollarSign, Bell, RefreshCw,
  CircleDot, Gauge, Lock, Unlock, Eye
} from 'lucide-react';
import BacktestV21Modal from './BacktestV21Modal';
import PositionsCallingCard from './PositionsCallingCard';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const fmt = (p) => {
  if (!p && p !== 0) return '—';
  if (p > 1000) return p.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (p > 1) return p.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return p.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
};

const pct = (v, dec = 1) => {
  if (v == null) return '0.0%';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(dec)}%`;
};

export default function Dashboard({
  stats,
  tradingStats,
  mexcData,
  messages,
  formatRelativeTime,
  onQuickScan,
  onNavigate
}) {
  const [livePositions, setLivePositions] = useState([]);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [v2Settings, setV2Settings] = useState(null);
  const [scalperStatus, setScalperStatus] = useState(null);
  const [learningStatus, setLearningStatus] = useState(null);
  const [macroRegime, setMacroRegime] = useState(null);
  const [exposure, setExposure] = useState(null);
  const [showKillSwitch, setShowKillSwitch] = useState(false);
  const [showBacktestModal, setShowBacktestModal] = useState(false);
  const [killLoading, setKillLoading] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(Date.now());

  const fetchAll = useCallback(async () => {
    const [posRes, dsRes, v2Res, scalRes, learnRes, macroRes, expRes] = await Promise.allSettled([
      fetch(`${API_URL}/api/trading/v2/live-positions`),
      fetch(`${API_URL}/api/stats/dashboard`),
      fetch(`${API_URL}/api/trading/v2/settings`),
      fetch(`${API_URL}/api/scalper/status`),
      fetch(`${API_URL}/api/learning/status`),
      fetch(`${API_URL}/api/regime/macro`),
      fetch(`${API_URL}/api/trading/exposure`),
    ]);

    if (posRes.status === 'fulfilled') {
      try { const d = await posRes.value.json(); setLivePositions(Array.isArray(d?.positions) ? d.positions : []); } catch {}
    }
    if (dsRes.status === 'fulfilled') {
      try {
        const d = await dsRes.value.json();
        setDashboardStats({ best_pairs: [], worst_pairs: [], blacklisted_pairs: [], ...d });
      } catch {}
    }
    if (v2Res.status === 'fulfilled') {
      try { const d = await v2Res.value.json(); if (!d.error) setV2Settings(d); } catch {}
    }
    if (scalRes.status === 'fulfilled') {
      try { const d = await scalRes.value.json(); setScalperStatus(d); } catch {}
    }
    if (learnRes.status === 'fulfilled') {
      try { const d = await learnRes.value.json(); setLearningStatus(d); } catch {}
    }
    if (macroRes.status === 'fulfilled') {
      try { const d = await macroRes.value.json(); if (!d.error) setMacroRegime(d); } catch {}
    }
    if (expRes.status === 'fulfilled') {
      try { const d = await expRes.value.json(); if (!d.error) setExposure(d); } catch {}
    }
    setLastRefresh(Date.now());
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 10000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const handleKillSwitch = async () => {
    setKillLoading(true);
    try {
      await fetch(`${API_URL}/api/trading/v2/close-all`, { method: 'POST' });
      setShowKillSwitch(false);
      setLivePositions([]);
    } catch (err) {
      alert('Kill switch failed — close manually.');
    } finally {
      setKillLoading(false);
    }
  };

  const totalPnl = tradingStats?.total_pnl_pct || 0;
  const winRate = tradingStats?.win_rate || 0;
  const openCount = livePositions.length;
  const totalExposure = livePositions.reduce((s, p) => s + ((p.position_size || 1000) * (p.leverage || 10) / 1000), 0);
  const isActive = tradingStats?.active;
  const regime = tradingStats?.market_regime || 'Unknown';
  const learningActive = learningStatus?.active;

  // PnL goal
  const dailyGoal = 5;
  const goalPct = Math.min(100, Math.max(0, (totalPnl / dailyGoal) * 100));

  // Top gainers from positions
  const sortedPos = [...livePositions].sort((a, b) => {
    const pa = (a.pnl_pct || 0) * (a.leverage || 10);
    const pb = (b.pnl_pct || 0) * (b.leverage || 10);
    return pb - pa;
  });

  return (
    <div className="space-y-4">

      {/* ── HERO COMMAND BAR ── */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-zinc-900 via-zinc-800/60 to-zinc-900 border border-zinc-700/50">
        <div className="absolute inset-0 bg-gradient-to-r from-orange-500/5 via-transparent to-amber-500/5 pointer-events-none" />
        <div className="relative p-4 sm:p-5">
          <div className="flex flex-col sm:flex-row sm:items-center gap-4">
            {/* Left: Brand + Status */}
            <div className="flex items-center gap-3 flex-1 min-w-0">
              <div className="relative flex-shrink-0">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/30">
                  <Bot className="w-7 h-7 text-white" />
                </div>
                <div className={`absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-full border-2 border-zinc-900 ${isActive ? 'bg-emerald-500' : 'bg-zinc-500'}`} />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h1 className="text-xl font-bold text-white">AEON</h1>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-bold tracking-wide ${isActive ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-zinc-700 text-zinc-400'}`}>
                    {isActive ? '● TRADING' : '○ PAUSED'}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-xs ${
                    regime === 'TRENDING_UP' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                    regime === 'TRENDING_DOWN' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                    regime === 'VOLATILE' ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20' :
                    'bg-zinc-700/50 text-zinc-500'
                  }`}>
                    {regime}
                  </span>
                </div>
                <p className="text-zinc-500 text-xs mt-0.5">
                  {learningActive ? (
                    <span className="flex items-center gap-1 text-purple-400">
                      <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse inline-block" />
                      Learning active · {learningStatus?.knowledge_stats?.coins_analyzed || 0} coins · {learningStatus?.daily_insights_count || 0} insights today
                    </span>
                  ) : (
                    <span className="text-zinc-500">Learning engine paused</span>
                  )}
                </p>
              </div>
            </div>

            {/* Right: Hero Stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4">
              <div className="text-center">
                <p className="text-xs text-zinc-500 mb-0.5">Total PnL</p>
                <p className={`text-base sm:text-lg font-bold font-mono ${totalPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                  {pct(totalPnl)}
                </p>
              </div>
              <div className="text-center">
                <p className="text-xs text-zinc-500 mb-0.5">Win Rate</p>
                <p className="text-base sm:text-lg font-bold font-mono text-orange-400">{winRate}%</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-zinc-500 mb-0.5">Open</p>
                <p className="text-base sm:text-lg font-bold font-mono text-white">{openCount}</p>
              </div>
              <div className="text-center">
                <p className="text-xs text-zinc-500 mb-0.5">Exposure</p>
                <p className={`text-base sm:text-lg font-bold font-mono ${totalExposure > 50 ? 'text-rose-400' : totalExposure > 20 ? 'text-amber-400' : 'text-emerald-400'}`}>
                  {totalExposure.toFixed(0)}x
                </p>
              </div>
            </div>
          </div>

          {/* Daily Goal Bar */}
          <div className="mt-4">
            <div className="flex items-center justify-between text-xs mb-1.5">
              <span className="text-zinc-500 flex items-center gap-1">
                <Target className="w-3 h-3" /> Daily Goal Progress
              </span>
              <span className={`font-mono font-bold ${goalPct >= 100 ? 'text-emerald-400' : 'text-orange-400'}`}>
                {goalPct >= 100 ? '✓ GOAL HIT' : `${totalPnl.toFixed(2)}% / +${dailyGoal}%`}
              </span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${goalPct >= 100 ? 'bg-emerald-500' : 'bg-gradient-to-r from-orange-500 to-amber-500'}`}
                style={{ width: `${goalPct}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      {/* ── QUICK ACTIONS ── */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={() => onNavigate('trading')}
          className="flex items-center gap-1.5 px-3 py-2 bg-gradient-to-r from-orange-500 to-amber-600 rounded-xl text-white text-sm font-medium hover:from-orange-600 hover:to-amber-700 transition-all shadow-lg shadow-orange-500/20"
        >
          <Zap className="w-4 h-4" /> Trade
        </button>
        <button
          onClick={() => onNavigate('engines')}
          className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800/80 hover:bg-zinc-700/80 rounded-xl text-zinc-300 text-sm transition-all border border-zinc-700/50"
        >
          <Cpu className="w-4 h-4" /> Engines
        </button>
        <button
          onClick={() => onNavigate('alerts')}
          className="flex items-center gap-1.5 px-3 py-2 bg-zinc-800/80 hover:bg-zinc-700/80 rounded-xl text-zinc-300 text-sm transition-all border border-zinc-700/50"
        >
          <Bell className="w-4 h-4" /> Alerts
        </button>
        <button
          onClick={() => setShowBacktestModal(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 rounded-xl text-amber-400 text-sm transition-all"
        >
          <FlaskConical className="w-4 h-4" /> Backtest
        </button>
        <button
          onClick={() => onNavigate('learning')}
          className="flex items-center gap-1.5 px-3 py-2 bg-purple-500/10 hover:bg-purple-500/20 border border-purple-500/30 rounded-xl text-purple-400 text-sm transition-all"
        >
          <Brain className="w-4 h-4" /> Learning
        </button>
        <button
          onClick={() => onNavigate('intel')}
          className="flex items-center gap-1.5 px-3 py-2 bg-cyan-500/10 hover:bg-cyan-500/20 border border-cyan-500/30 rounded-xl text-cyan-400 text-sm transition-all"
        >
          <Eye className="w-4 h-4" /> Intel
        </button>
        <button
          onClick={() => setShowKillSwitch(true)}
          className="flex items-center gap-1.5 px-3 py-2 bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 rounded-xl text-rose-400 text-sm transition-all ml-auto"
        >
          <Power className="w-4 h-4" />
          <span className="hidden sm:inline">Kill Switch</span>
        </button>
      </div>

      {/* ── MACRO DIRECTION GATE BANNER ── */}
      {macroRegime && (
        <div className={`flex items-center justify-between rounded-xl border px-4 py-3 ${
          macroRegime.direction === 'BULLISH'
            ? 'bg-emerald-500/10 border-emerald-500/30'
            : macroRegime.direction === 'BEARISH'
            ? 'bg-rose-500/10 border-rose-500/30'
            : 'bg-zinc-800/60 border-zinc-700/50'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${
              macroRegime.direction === 'BULLISH' ? 'bg-emerald-400' :
              macroRegime.direction === 'BEARISH' ? 'bg-rose-400' : 'bg-zinc-500'
            }`} />
            <div>
              <span className="text-xs text-zinc-400 font-medium">BTC Macro Gate · </span>
              <span className={`text-sm font-bold ${
                macroRegime.direction === 'BULLISH' ? 'text-emerald-400' :
                macroRegime.direction === 'BEARISH' ? 'text-rose-400' : 'text-zinc-400'
              }`}>{macroRegime.direction}</span>
            </div>
            {macroRegime.penalty_label && macroRegime.direction !== 'NEUTRAL' && (
              <span className={`text-xs px-2 py-0.5 rounded font-medium border ${
                macroRegime.direction === 'BEARISH'
                  ? 'bg-rose-500/10 border-rose-500/30 text-rose-300'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-300'
              }`}>
                ⚠ {macroRegime.penalty_label}
              </span>
            )}
          </div>
          {macroRegime.cache_age_seconds != null && (
            <span className="text-xs text-zinc-600">
              {macroRegime.cache_age_seconds < 60
                ? `${macroRegime.cache_age_seconds}s ago`
                : `${Math.floor(macroRegime.cache_age_seconds / 60)}m ago`}
            </span>
          )}
        </div>
      )}

      {/* ── MAIN GRID ── */}
      <div className="grid lg:grid-cols-3 gap-4">

        {/* ── LEFT: LIVE POSITIONS (Calling Cards) ── */}
        <div className="lg:col-span-2 space-y-3">

          {/* Open Exposure Widget */}
          {exposure && (exposure.total_open > 0 || exposure.bias_alert) && (
            <div className={`rounded-xl border p-3 ${exposure.bias_alert || (exposure.concentrated_pairs?.length > 0) ? 'border-amber-500/30 bg-amber-500/5' : 'border-zinc-800 bg-zinc-900/30'}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-zinc-300 flex items-center gap-1.5">
                  <Gauge className="w-3.5 h-3.5 text-cyan-400" />
                  Open Exposure
                </span>
                <button onClick={() => onNavigate('trading')} className="text-xs text-orange-400 hover:text-orange-300 flex items-center gap-1">
                  View All <ChevronRight className="w-3 h-3" />
                </button>
              </div>
              <div className="flex items-center gap-2 mb-1.5">
                <div className="flex-1 h-2 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${exposure.long_pct ?? 50}%` }}
                  />
                </div>
                <span className="text-xs font-mono text-emerald-400 w-14 text-right">{exposure.long_count}L / {exposure.short_count}S</span>
              </div>
              <div className="flex justify-between text-[10px] text-zinc-500 mb-1">
                <span className="text-emerald-400">LONG {(exposure.long_pct ?? 0).toFixed(0)}%</span>
                <span className="text-rose-400">SHORT {(100 - (exposure.long_pct ?? 0)).toFixed(0)}%</span>
              </div>
              {exposure.concentrated_pairs?.length > 0 && (
                <div className="flex items-center gap-1.5 mt-1.5 text-xs text-amber-400">
                  <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                  Concentration: {exposure.concentrated_pairs.map(p => p.replace('/USDT', '')).join(', ')} (3+ trades)
                </div>
              )}
              {exposure.bias_alert && (
                <div className="flex items-center gap-1.5 mt-1 text-xs text-amber-400">
                  <AlertTriangle className="w-3 h-3 flex-shrink-0" />
                  Directional bias alert — {(exposure.long_pct ?? 0) > 75 ? 'heavily LONG' : 'heavily SHORT'}
                </div>
              )}
            </div>
          )}

          {/* ── POSITIONS CALLING CARDS ── */}
          <PositionsCallingCard />

          {/* ── MARKET DATA ── */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-white flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-orange-400" />
                Market Snapshot
                <span className="text-xs text-zinc-500 font-normal">
                  {mexcData?.symbols?.length || 0} pairs · click to scan
                </span>
              </h2>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-3 xl:grid-cols-4 gap-2">
              {mexcData?.symbols?.slice(0, 12).map((sym, i) => {
                const chg = sym.change_24h || 0;
                const isUp = chg >= 0;
                return (
                  <button
                    key={i}
                    onClick={() => onQuickScan(sym.symbol?.replace('/USDT', '').replace('USDT', ''))}
                    className="group relative rounded-xl border border-zinc-800 bg-zinc-900/40 hover:border-orange-500/40 hover:bg-zinc-800/60 p-3 text-left transition-all"
                  >
                    <div className="flex items-center justify-between mb-1.5">
                      <span className="text-white text-sm font-semibold group-hover:text-orange-400 transition-colors">
                        {sym.symbol?.replace('/USDT', '')}
                      </span>
                      <span className={`text-xs font-bold flex items-center gap-0.5 ${isUp ? 'text-emerald-400' : 'text-rose-400'}`}>
                        {isUp ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                        {Math.abs(chg).toFixed(1)}%
                      </span>
                    </div>
                    <p className="text-white font-mono text-sm font-medium">${fmt(sym.price)}</p>
                    {/* Mini imbalance bar */}
                    <div className="mt-2 h-1 bg-zinc-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full ${isUp ? 'bg-emerald-500/60' : 'bg-rose-500/60'}`}
                        style={{ width: `${50 + Math.min(50, Math.max(-50, sym.imbalance || 0) / 2)}%` }}
                      />
                    </div>
                  </button>
                );
              })}
            </div>
            {(mexcData?.symbols?.length || 0) > 12 && (
              <button
                onClick={() => onNavigate('dashboard')}
                className="mt-2 text-xs text-zinc-500 hover:text-orange-400 transition-colors"
              >
                +{mexcData.symbols.length - 12} more pairs
              </button>
            )}
          </div>
        </div>

        {/* ── RIGHT COLUMN: AI + RISK ── */}
        <div className="space-y-3">

          {/* AI Intelligence Card */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Brain className="w-4 h-4 text-orange-400" />
              AI Intelligence
            </h3>
            <div className="space-y-2.5">
              {/* Macro Direction Gate — from regime_engine.py EMA20 4H+Daily */}
              <div className="flex items-center justify-between">
                <span className="text-zinc-500 text-xs">Macro Gate</span>
                <div className="flex items-center gap-1.5">
                  <span className={`text-xs font-bold ${
                    macroRegime?.direction === 'BULLISH' ? 'text-emerald-400' :
                    macroRegime?.direction === 'BEARISH' ? 'text-rose-400' : 'text-zinc-400'
                  }`}>{macroRegime?.direction || '…'}</span>
                  {macroRegime?.penalty_direction && macroRegime.direction !== 'NEUTRAL' && (
                    <span className="text-[10px] text-zinc-500">+10% on {macroRegime.penalty_direction}s</span>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500 text-xs">Market Structure</span>
                <span className={`text-xs font-bold px-2 py-0.5 rounded ${
                  regime === 'TRENDING_UP' ? 'bg-emerald-500/15 text-emerald-400' :
                  regime === 'TRENDING_DOWN' ? 'bg-rose-500/15 text-rose-400' :
                  regime === 'VOLATILE' ? 'bg-amber-500/15 text-amber-400' :
                  'bg-zinc-700 text-zinc-400'
                }`}>{regime}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500 text-xs">BTC Bias</span>
                <span className={`text-xs font-medium ${
                  tradingStats?.btc_bias === 'BULLISH' ? 'text-emerald-400' :
                  tradingStats?.btc_bias === 'BEARISH' ? 'text-rose-400' : 'text-zinc-400'
                }`}>{tradingStats?.btc_bias || 'Neutral'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-zinc-500 text-xs">Fear & Greed</span>
                <span className={`text-xs font-mono font-bold ${
                  (tradingStats?.fear_greed || 50) > 60 ? 'text-emerald-400' :
                  (tradingStats?.fear_greed || 50) < 40 ? 'text-rose-400' : 'text-amber-400'
                }`}>{tradingStats?.fear_greed || '—'}</span>
              </div>
              <div className="pt-1 border-t border-zinc-800">
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 text-xs">V2.1 Strategy</span>
                  <div className="flex items-center gap-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${v2Settings?.active ? 'bg-emerald-500' : 'bg-zinc-600'}`} />
                    <span className="text-xs text-zinc-300">{v2Settings?.active ? 'Active' : 'Paused'}</span>
                  </div>
                </div>
                {v2Settings && (
                  <div className="flex gap-1 mt-1.5 flex-wrap">
                    {v2Settings.ema_200_filter_enabled && <span className="px-1.5 py-0.5 bg-purple-500/10 text-purple-400 text-xs rounded">EMA</span>}
                    {v2Settings.adx_filter_enabled && <span className="px-1.5 py-0.5 bg-blue-500/10 text-blue-400 text-xs rounded">ADX</span>}
                    {v2Settings.volume_filter_enabled && <span className="px-1.5 py-0.5 bg-emerald-500/10 text-emerald-400 text-xs rounded">VOL</span>}
                    {v2Settings.session_filter_enabled && <span className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 text-xs rounded">SESSION</span>}
                    <span className="text-xs text-zinc-500">{v2Settings.min_confidence || 90}% conf</span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* 24/7 Learning Engine */}
          <div className={`rounded-xl border p-4 ${learningActive ? 'border-purple-500/30 bg-purple-900/10' : 'border-zinc-800 bg-zinc-900/40'}`}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Brain className={`w-4 h-4 ${learningActive ? 'text-purple-400 animate-pulse' : 'text-zinc-500'}`} />
                24/7 Learning
              </h3>
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${learningActive ? 'bg-purple-400 animate-pulse' : 'bg-zinc-600'}`} />
                <span className={`text-xs font-bold ${learningActive ? 'text-purple-400' : 'text-zinc-500'}`}>
                  {learningActive ? 'ACTIVE' : 'PAUSED'}
                </span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2 mb-3">
              <div className="bg-zinc-900/60 rounded-lg p-2.5 text-center">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <BookOpen className="w-3 h-3 text-purple-400" />
                </div>
                <p className="text-lg font-bold text-white">{learningStatus?.knowledge_stats?.patterns_learned || 0}</p>
                <p className="text-xs text-zinc-500">Patterns</p>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2.5 text-center">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <Lightbulb className="w-3 h-3 text-amber-400" />
                </div>
                <p className="text-lg font-bold text-white">{learningStatus?.daily_insights_count || 0}</p>
                <p className="text-xs text-zinc-500">Insights</p>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2.5 text-center">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <Target className="w-3 h-3 text-cyan-400" />
                </div>
                <p className="text-lg font-bold text-white">{learningStatus?.knowledge_stats?.coins_analyzed || 0}</p>
                <p className="text-xs text-zinc-500">Coins</p>
              </div>
              <div className="bg-zinc-900/60 rounded-lg p-2.5 text-center">
                <div className="flex items-center justify-center gap-1 mb-1">
                  <Sparkles className="w-3 h-3 text-emerald-400" />
                </div>
                <p className="text-lg font-bold text-white">{learningStatus?.knowledge_stats?.optimizations_run || 0}</p>
                <p className="text-xs text-zinc-500">Opts</p>
              </div>
            </div>
            {learningStatus?.last_cycles && (
              <div className="text-xs text-zinc-600 space-y-1 border-t border-zinc-800 pt-2">
                <div className="flex justify-between">
                  <span>Pattern cycle</span>
                  <span className="text-zinc-500">
                    {learningStatus.last_cycles.pattern_learning
                      ? new Date(learningStatus.last_cycles.pattern_learning).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'Pending'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Market analysis</span>
                  <span className="text-zinc-500">
                    {learningStatus.last_cycles.market_analysis
                      ? new Date(learningStatus.last_cycles.market_analysis).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                      : 'Pending'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Next summary</span>
                  <span className="text-purple-400">{learningStatus?.next_daily_summary || '9 PM CT'}</span>
                </div>
              </div>
            )}
            {learningStatus?.knowledge_stats?.patterns_learned === 0 && (
              <p className="text-xs text-zinc-600 mt-2 italic">
                Needs closed trade history to learn patterns
              </p>
            )}
            <button
              onClick={() => onNavigate('learning')}
              className="w-full mt-3 py-1.5 text-xs text-purple-400 hover:text-purple-300 border border-purple-500/30 hover:border-purple-500/50 rounded-lg transition-colors"
            >
              Open Learning Dashboard →
            </button>
          </div>

          {/* Scalper Widget */}
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-white flex items-center gap-2">
                <Zap className="w-4 h-4 text-purple-400" />
                Aggressive Scalper
              </h3>
              <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${scalperStatus?.enabled ? 'bg-emerald-500/15 text-emerald-400' : 'bg-zinc-700 text-zinc-400'}`}>
                {scalperStatus?.enabled ? 'ON' : 'OFF'}
              </span>
            </div>
            <div className="space-y-2">
              <div className="flex justify-between text-xs">
                <span className="text-zinc-500">Active signals</span>
                <span className="text-white font-mono">{scalperStatus?.active_signals || 0}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-zinc-500">Profit target</span>
                <span className="text-emerald-400">{scalperStatus?.settings_summary?.profit_target || '1.5%'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-zinc-500">Stop loss</span>
                <span className="text-rose-400">{scalperStatus?.settings_summary?.stop_loss || '0.5%'}</span>
              </div>
              <div className="flex justify-between text-xs">
                <span className="text-zinc-500">Auto-learn</span>
                <span className={scalperStatus?.learning?.auto_learn_enabled ? 'text-emerald-400' : 'text-zinc-500'}>
                  {scalperStatus?.learning?.auto_learn_enabled ? '● ON' : '○ OFF'}
                </span>
              </div>
            </div>
            <button
              onClick={() => onNavigate('scalper')}
              className="w-full mt-3 py-1.5 text-xs text-purple-400 hover:text-purple-300 border border-purple-500/30 hover:border-purple-500/50 rounded-lg transition-colors"
            >
              Scalper Dashboard →
            </button>
          </div>

        </div>
      </div>

      {/* ── RISK MANAGEMENT + RECENT ACTIVITY ── */}
      <div className="grid md:grid-cols-2 gap-4">

        {/* Risk Management */}
        {dashboardStats && (
          <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Shield className="w-4 h-4 text-amber-400" />
              Risk Management
            </h3>
            <div className="space-y-3">
              {/* Best/Worst compact */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <p className="text-xs text-zinc-500 mb-1.5 flex items-center gap-1">
                    <TrendingUp className="w-3 h-3 text-emerald-400" /> Best Pairs
                  </p>
                  <div className="space-y-1">
                    {dashboardStats.best_pairs?.length > 0 ? dashboardStats.best_pairs.slice(0, 3).map((p, i) => (
                      <div key={i} className="flex justify-between text-xs">
                        <span className="text-zinc-300">{p.symbol?.replace('/USDT', '')}</span>
                        <span className="text-emerald-400 font-mono">{p.win_rate?.toFixed(0)}%</span>
                      </div>
                    )) : <p className="text-zinc-600 text-xs">No data</p>}
                  </div>
                </div>
                <div>
                  <p className="text-xs text-zinc-500 mb-1.5 flex items-center gap-1">
                    <TrendingDown className="w-3 h-3 text-rose-400" /> Worst Pairs
                  </p>
                  <div className="space-y-1">
                    {dashboardStats.worst_pairs?.length > 0 ? dashboardStats.worst_pairs.slice(0, 3).map((p, i) => (
                      <div key={i} className="flex justify-between text-xs">
                        <span className="text-zinc-300">{p.symbol?.replace('/USDT', '')}</span>
                        <span className="text-rose-400 font-mono">{p.win_rate?.toFixed(0)}%</span>
                      </div>
                    )) : <p className="text-zinc-600 text-xs">No data</p>}
                  </div>
                </div>
              </div>

              {/* Blacklist + Cooldowns */}
              <div className="border-t border-zinc-800 pt-3 space-y-2">
                <div>
                  <p className="text-xs text-zinc-500 mb-1">
                    Blacklisted ({dashboardStats.blacklisted_pairs?.length || 0})
                  </p>
                  {dashboardStats.blacklisted_pairs?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {dashboardStats.blacklisted_pairs.map((pair, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-rose-500/10 text-rose-400 text-xs rounded border border-rose-500/20">
                          {pair.replace('/USDT', '')}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-emerald-400 text-xs">None ✓</span>
                  )}
                </div>
                {dashboardStats.pairs_on_cooldown?.length > 0 && (
                  <div>
                    <p className="text-xs text-zinc-500 mb-1">Cooldown ({dashboardStats.pairs_on_cooldown.length})</p>
                    <div className="flex flex-wrap gap-1">
                      {dashboardStats.pairs_on_cooldown.map((pair, i) => (
                        <span key={i} className="px-1.5 py-0.5 bg-amber-500/10 text-amber-400 text-xs rounded border border-amber-500/20 flex items-center gap-1">
                          <Timer className="w-2.5 h-2.5" />
                          {pair.symbol?.replace('/USDT', '')} {pair.minutes_left}m
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                {dashboardStats.position_scaling && (
                  <div className="flex justify-between items-center text-xs">
                    <span className="text-zinc-500 flex items-center gap-1">
                      <Scale className="w-3 h-3 text-cyan-400" /> Position Scaling
                    </span>
                    <span className={dashboardStats.position_scaling.enabled ? 'text-emerald-400' : 'text-zinc-600'}>
                      {dashboardStats.position_scaling.enabled ? '● ON' : '○ OFF'}
                      {dashboardStats.position_scaling.pending_scale_ins > 0 && (
                        <span className="text-cyan-400 ml-1">{dashboardStats.position_scaling.pending_scale_ins} pending</span>
                      )}
                    </span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Recent Activity */}
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4">
          <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-orange-400" />
            Recent Activity
          </h3>
          <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
            {messages?.length > 0 ? messages.slice(0, 10).map((msg, i) => (
              <div key={i} className="flex gap-2.5 py-1.5 border-b border-zinc-800/60 last:border-0">
                <div className="w-6 h-6 rounded-full bg-zinc-700/60 flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-xs text-zinc-300">{msg.username?.[0]?.toUpperCase() || '?'}</span>
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-medium text-zinc-300">{msg.username || 'User'}</span>
                    <span className="text-xs text-zinc-600">{formatRelativeTime(msg.timestamp)}</span>
                  </div>
                  <p className="text-xs text-zinc-500 truncate mt-0.5">{msg.text}</p>
                </div>
              </div>
            )) : (
              <p className="text-zinc-600 text-sm text-center py-6">No recent activity</p>
            )}
          </div>
        </div>
      </div>

      {/* ── KILL SWITCH MODAL ── */}
      {showKillSwitch && (
        <div className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-rose-500/40 rounded-2xl p-6 max-w-sm w-full shadow-2xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-rose-500/15 rounded-xl">
                <AlertTriangle className="w-7 h-7 text-rose-400" />
              </div>
              <div>
                <h3 className="text-lg font-bold text-white">Emergency Kill Switch</h3>
                <p className="text-zinc-400 text-sm">Close ALL {openCount} open positions</p>
              </div>
            </div>
            <p className="text-zinc-300 text-sm mb-5">
              Immediately close all open positions at market price. This cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleKillSwitch}
                disabled={killLoading}
                className="flex-1 py-2.5 bg-rose-500 hover:bg-rose-600 disabled:opacity-50 text-white rounded-lg font-bold text-sm transition-all flex items-center justify-center gap-2"
              >
                {killLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Power className="w-4 h-4" />}
                {killLoading ? 'Closing...' : 'CLOSE ALL'}
              </button>
              <button
                onClick={() => setShowKillSwitch(false)}
                className="px-5 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-lg text-sm transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <BacktestV21Modal isOpen={showBacktestModal} onClose={() => setShowBacktestModal(false)} />
    </div>
  );
}
