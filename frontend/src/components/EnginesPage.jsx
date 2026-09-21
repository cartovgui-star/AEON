import React, { useState, useEffect, useCallback } from 'react';
import { Cpu, ToggleLeft, ToggleRight, RefreshCw, AlertTriangle, ChevronDown, ChevronUp, Clock, Ban } from 'lucide-react';
import { fetchEngineStatus, toggleEngine, fetchGovernance } from '../services/api';
import AeonLoader from './AeonLoader';

const ENGINE_META = {
  autonomous_trader_v2: { label: 'Autonomous V2',       emoji: '🤖', color: 'orange' },
  free_will_v2:         { label: 'Free Will V2',         emoji: '🔮', color: 'purple' },
  dual_engine:          { label: 'Dual Engine',          emoji: '⚔️',  color: 'blue'   },
  vwap_scalper:         { label: 'VWAP Scalper',         emoji: '⚡', color: 'yellow' },
  yolo_engine:          { label: 'YOLO Engine',          emoji: '🚀', color: 'red'    },
  elite_strategy:       { label: 'Elite Strategy',       emoji: '👑', color: 'green'  },
  institutional_scalper:{ label: 'Institutional Scalper',emoji: '🏦', color: 'teal'   },
  tcn_neural:           { label: 'TCN Neural',           emoji: '🧠', color: 'cyan'   },
  quant_analyzer:       { label: 'Quant Analyzer',       emoji: '📊', color: 'indigo' },
  day_trader:           { label: 'Day Trader',           emoji: '🎯', color: 'amber'  },
};

const COLOR_MAP = {
  orange: { border: 'border-orange-500/30', bg: 'bg-orange-500/10', text: 'text-orange-400' },
  purple: { border: 'border-purple-500/30', bg: 'bg-purple-500/10', text: 'text-purple-400' },
  blue:   { border: 'border-blue-500/30',   bg: 'bg-blue-500/10',   text: 'text-blue-400'   },
  yellow: { border: 'border-yellow-500/30', bg: 'bg-yellow-500/10', text: 'text-yellow-400' },
  red:    { border: 'border-red-500/30',    bg: 'bg-red-500/10',    text: 'text-red-400'    },
  green:  { border: 'border-green-500/30',  bg: 'bg-green-500/10',  text: 'text-green-400'  },
  teal:   { border: 'border-teal-500/30',   bg: 'bg-teal-500/10',   text: 'text-teal-400'   },
  cyan:   { border: 'border-cyan-500/30',   bg: 'bg-cyan-500/10',   text: 'text-cyan-400'   },
  indigo: { border: 'border-indigo-500/30', bg: 'bg-indigo-500/10', text: 'text-indigo-400' },
  amber:  { border: 'border-amber-500/30',  bg: 'bg-amber-500/10',  text: 'text-amber-400'  },
};

const fmt1 = (v) => v != null ? Number(v).toFixed(1) : '—';
const fmt2 = (v) => v != null ? Number(v).toFixed(2) : '—';

const GOV_KEY_MAP = {
  autonomous_trader_v2: 'AUTONOMOUS_V2',
  free_will_v2: 'FREE_WILL_V2',
  dual_engine: 'DUAL_DAY_TRADER',
  vwap_scalper: 'VWAP_SCALPER',
  yolo_engine: 'YOLO_ENGINE',
  elite_strategy: 'ELITE_STRATEGY',
  institutional_scalper: 'INSTITUTIONAL_SCALPER',
  tcn_neural: 'TCN_NEURAL',
  quant_analyzer: null,
};

const tierColor = (tier) => {
  if (!tier || tier === 'insufficient_data') return 'text-zinc-500';
  if (tier.startsWith('A')) return 'text-emerald-400';
  if (tier === 'B') return 'text-cyan-400';
  if (tier === 'C') return 'text-amber-400';
  return 'text-rose-400';
};

const recColor = (rec) => {
  if (!rec || rec === 'monitor') return 'text-zinc-400';
  if (rec === 'promote') return 'text-emerald-400';
  if (rec === 'restrict' || rec === 'restricted' || rec === 'sandbox_only') return 'text-amber-400';
  if (rec === 'disable_candidate') return 'text-rose-400';
  return 'text-zinc-400';
};

function timeSinceSignal(ts) {
  if (!ts) return null;
  const diff = Math.floor((Date.now() - new Date(ts).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function EngineCard({ engineKey, data, gov, onToggle, toggling }) {
  const [expanded, setExpanded] = useState(false);
  const meta = ENGINE_META[engineKey] || { label: engineKey, emoji: '⚙️', color: 'orange' };
  const c = COLOR_MAP[meta.color] || COLOR_MAP.orange;
  const stats = data.stats || {};
  const config = data.config || {};

  const isActive = config.active !== false;
  const winRate = stats.win_rate != null ? parseFloat(stats.win_rate).toFixed(1)
    : stats.total_trades > 0 ? ((stats.wins / stats.total_trades) * 100).toFixed(1)
    : null;
  const pnl = stats.total_pnl || 0;
  const trades24h = stats.daily_trades || 0;
  const lastSignalTime = stats.last_signal_time || data.last_signal_time;

  const statusLabel = !isActive ? 'DISABLED' : data.open_count > 0 ? 'LIVE' : 'SCANNING';
  const statusColor = !isActive ? 'text-zinc-500 bg-zinc-800/50 border-zinc-700/50'
    : data.open_count > 0 ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/30'
    : 'text-amber-400 bg-amber-500/10 border-amber-500/30';

  return (
    <div className={`bg-zinc-900/70 border ${c.border} rounded-xl p-4 space-y-3 transition-all ${!isActive ? 'opacity-60' : ''}`}>
      {/* Header row */}
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg flex-shrink-0">{meta.emoji}</span>
          <div className="min-w-0">
            <div className="text-sm font-semibold text-white">{meta.label}</div>
            <div className="text-[10px] text-zinc-500 truncate">{data.description || engineKey}</div>
          </div>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${statusColor}`}>
            {statusLabel}
          </span>
        </div>
      </div>

      {/* Last signal */}
      {lastSignalTime && (
        <div className="text-[11px] text-zinc-500">
          Last signal: <span className="text-zinc-300">{timeSinceSignal(lastSignalTime)}</span>
        </div>
      )}

      {/* Governance badge */}
      {gov && (
        <div className="flex items-center gap-3 bg-zinc-950/40 rounded-lg px-3 py-1.5 text-[10px]">
          <span className="text-zinc-500 uppercase tracking-wider">Gov</span>
          <span className={`font-semibold font-mono ${recColor(gov.recommendation)}`}>{gov.recommendation || 'n/a'}</span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-500">Tier</span>
          <span className={`font-bold font-mono ${tierColor(gov.current_tier)}`}>{gov.current_tier === 'insufficient_data' ? '—' : (gov.current_tier || '—')}</span>
          <span className="text-zinc-600">|</span>
          <span className="text-zinc-500">Score</span>
          <span className="font-mono text-zinc-300">{gov.current_score != null ? Number(gov.current_score).toFixed(1) : '—'}</span>
          {gov.consecutive_d_weeks > 0 && (
            <span className="ml-auto text-rose-400 font-semibold">{gov.consecutive_d_weeks}D-wk</span>
          )}
        </div>
      )}

      {/* Stats strip */}
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-[10px] text-zinc-500">24h Trades</div>
          <div className="font-mono text-sm font-bold text-white">{trades24h}</div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500">Win Rate</div>
          <div className={`font-mono text-sm font-bold ${winRate == null ? 'text-zinc-600' : parseFloat(winRate) >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {winRate != null ? `${winRate}%` : '—'}
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-500">PnL</div>
          <div className={`font-mono text-sm font-bold ${pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {pnl >= 0 ? '+' : ''}{fmt2(pnl)}R
          </div>
        </div>
      </div>

      {/* Expanded details */}
      {expanded && (
        <div className="border-t border-zinc-800/50 pt-3 space-y-2">
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-[11px]">
            <div className="text-zinc-500">Min Confidence <span className="text-white font-mono">{config.min_confidence}%</span></div>
            <div className="text-zinc-500">Max Leverage <span className="text-white font-mono">{config.max_leverage}x</span></div>
            <div className="text-zinc-500">Max Position <span className="text-white font-mono">${config.max_position_size}</span></div>
            <div className="text-zinc-500">Max Daily Loss <span className="text-rose-400 font-mono">${Math.abs(config.max_loss_per_day || 0)}</span></div>
            <div className="text-zinc-500">Blocked <span className="text-amber-400 font-mono">{stats.blocked_trades || 0}</span></div>
            <div className="text-zinc-500">Open <span className="text-cyan-400 font-mono">{data.open_count || 0}</span></div>
          </div>
          {(data.blacklisted?.length > 0 || data.in_cooldown?.length > 0) && (
            <div className="space-y-1">
              {data.blacklisted?.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Ban className="w-3 h-3 text-rose-400" />
                  <span className="text-[10px] text-zinc-500">Blacklisted:</span>
                  {data.blacklisted.slice(0, 4).map(s => (
                    <span key={s} className="text-[10px] bg-rose-500/10 text-rose-400 px-1.5 py-0.5 rounded">{s.replace('/USDT', '')}</span>
                  ))}
                </div>
              )}
              {data.in_cooldown?.length > 0 && (
                <div className="flex items-center gap-1.5 flex-wrap">
                  <Clock className="w-3 h-3 text-amber-400" />
                  <span className="text-[10px] text-zinc-500">Cooldown:</span>
                  {data.in_cooldown.slice(0, 4).map(s => (
                    <span key={s} className="text-[10px] bg-amber-500/10 text-amber-400 px-1.5 py-0.5 rounded">{s.replace('/USDT', '')}</span>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Actions row */}
      <div className="flex items-center justify-between pt-1 border-t border-zinc-800/50">
        <button
          onClick={() => setExpanded(v => !v)}
          className="flex items-center gap-1 text-[11px] text-zinc-500 hover:text-zinc-300 transition-colors"
        >
          {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          {expanded ? 'Less' : 'Details'}
        </button>

        <button
          onClick={() => onToggle(engineKey, !isActive)}
          disabled={toggling === engineKey}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-[11px] font-semibold transition-all ${
            toggling === engineKey ? 'opacity-50 cursor-not-allowed bg-zinc-800 text-zinc-500' :
            isActive
              ? 'bg-rose-500/10 border border-rose-500/30 text-rose-400 hover:bg-rose-500/20'
              : 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20'
          }`}
        >
          {toggling === engineKey ? (
            <RefreshCw className="w-3 h-3 animate-spin" />
          ) : isActive ? (
            <ToggleRight className="w-3.5 h-3.5" />
          ) : (
            <ToggleLeft className="w-3.5 h-3.5" />
          )}
          {toggling === engineKey ? 'Toggling...' : isActive ? 'DISABLE ENGINE' : 'ENABLE ENGINE'}
        </button>
      </div>
    </div>
  );
}

export default function EnginesPage() {
  const [engines, setEngines] = useState({});
  const [globalStats, setGlobalStats] = useState(null);
  const [govMap, setGovMap] = useState({});
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState(null);
  const [toggleMsg, setToggleMsg] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    try {
      const [engData, govData] = await Promise.allSettled([
        fetchEngineStatus(),
        fetchGovernance(),
      ]);
      if (engData.status === 'fulfilled') {
        setEngines(engData.value.engines || {});
        setGlobalStats(engData.value.global || null);
      }
      if (govData.status === 'fulfilled') {
        const map = {};
        for (const s of (govData.value.states || [])) {
          map[s.engine] = s;
        }
        setGovMap(map);
      }
      setLastUpdated(new Date());
    } catch (e) {
      console.error('EnginesPage load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    const iv = setInterval(load, 15000);
    return () => clearInterval(iv);
  }, [load]);

  const handleToggle = async (engineKey, newActive) => {
    setToggling(engineKey);
    setToggleMsg(null);
    try {
      await toggleEngine(engineKey, newActive);
      setToggleMsg({ type: 'ok', text: `${engineKey} ${newActive ? 'enabled' : 'disabled'}` });
      await load();
    } catch (e) {
      setToggleMsg({ type: 'err', text: `Toggle failed: ${e.message}` });
    } finally {
      setToggling(null);
      setTimeout(() => setToggleMsg(null), 3000);
    }
  };

  if (loading) return <AeonLoader message="Loading engines..." />;

  const g = globalStats || {};
  const engineKeys = Object.keys(engines);
  const activeCount = engineKeys.filter(k => engines[k]?.config?.active !== false).length;

  return (
    <div className="space-y-4 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-cyan-400" />
            Engine Control Room
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">{activeCount}/{engineKeys.length} engines active</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} className="p-1.5 text-zinc-500 hover:text-zinc-300 transition-colors">
            <RefreshCw className="w-4 h-4" />
          </button>
          {lastUpdated && (
            <span className="text-[10px] text-zinc-600 font-mono">
              {Math.floor((Date.now() - lastUpdated.getTime()) / 1000)}s ago
            </span>
          )}
        </div>
      </div>

      {/* Toggle message */}
      {toggleMsg && (
        <div className={`px-4 py-2 rounded-lg text-xs font-semibold ${
          toggleMsg.type === 'ok'
            ? 'bg-emerald-500/10 border border-emerald-500/30 text-emerald-400'
            : 'bg-rose-500/10 border border-rose-500/30 text-rose-400'
        }`}>
          {toggleMsg.text}
        </div>
      )}

      {/* Global stats */}
      {g.total_trades > 0 && (
        <div className="grid grid-cols-3 gap-2">
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-3 text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Total Trades</div>
            <div className="font-mono text-xl font-bold text-white">{g.total_trades}</div>
          </div>
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-3 text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Win Rate</div>
            <div className={`font-mono text-xl font-bold ${g.total_trades > 0 && (g.total_wins / g.total_trades * 100) >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {g.total_trades > 0 ? ((g.total_wins / g.total_trades) * 100).toFixed(1) : 0}%
            </div>
          </div>
          <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-3 text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Open</div>
            <div className="font-mono text-xl font-bold text-cyan-400">{g.total_open || 0}</div>
          </div>
        </div>
      )}

      {/* Engine cards */}
      <div className="space-y-3">
        {engineKeys.length === 0 && (
          <div className="text-center text-zinc-600 py-8 text-sm">No engines found</div>
        )}
        {engineKeys.map(key => (
          <EngineCard
            key={key}
            engineKey={key}
            data={engines[key]}
            gov={govMap[GOV_KEY_MAP[key]] || null}
            onToggle={handleToggle}
            toggling={toggling}
          />
        ))}
      </div>
    </div>
  );
}
