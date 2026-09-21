import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, AlertTriangle, Zap, Activity,
  ChevronRight, RefreshCw, Radio
} from 'lucide-react';
import { fetchAccounts, fetchPositions, fetchEngineStatus, fetchRegime, fetchTradingStats } from '../services/api';

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
  day_trader: 'DAYTRADER',
};

const ENGINE_GRID_ORDER = [
  'autonomous_trader_v2', 'free_will_v2', 'dual_engine',
  'vwap_scalper', 'yolo_engine', 'elite_strategy',
  'institutional_scalper', 'tcn_neural', 'quant_analyzer',
];

const fmt = (v, digits = 2) =>
  v == null ? '—' : Number(v).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits });

const fmtPnl = (v) => {
  if (v == null) return '—';
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
};

const fmtPct = (v) => {
  if (v == null) return '—';
  const n = Number(v);
  const sign = n >= 0 ? '+' : '';
  return `${sign}${n.toFixed(2)}%`;
};

const pnlColor = (v) => {
  const n = Number(v);
  if (n > 0) return 'text-emerald-400';
  if (n < 0) return 'text-rose-400';
  return 'text-zinc-400';
};

function AccountCard({ account }) {
  const pnlPct = account.starting_balance
    ? ((account.balance - account.starting_balance) / account.starting_balance) * 100
    : 0;
  const isPos = pnlPct >= 0;

  return (
    <div className="flex-shrink-0 w-36 bg-zinc-900/80 border border-zinc-800/70 rounded-xl p-3 cursor-default select-none">
      <div className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold mb-1">{account.account_id}</div>
      <div className="font-mono text-sm font-bold text-white mb-1">
        ${account.balance != null ? Number(account.balance).toLocaleString(undefined, { maximumFractionDigits: 0 }) : '—'}
      </div>
      <div className={`font-mono text-xs font-semibold flex items-center gap-0.5 ${isPos ? 'text-emerald-400' : 'text-rose-400'}`}>
        {isPos ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
        {fmtPct(pnlPct)}
      </div>
      <div className="text-[10px] text-zinc-600 mt-1 font-mono">{account.open_positions || 0} pos</div>
    </div>
  );
}

function PositionCard({ pos, onExpand, expanded }) {
  const isLong = pos.direction === 'LONG';
  const pnl = pos.pnl_pct || 0;
  const isWin = pnl >= 0;
  const borderColor = isWin ? 'border-l-emerald-500' : 'border-l-rose-500';

  const timeSince = (dateStr) => {
    if (!dateStr) return '—';
    const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}d`;
  };

  return (
    <div
      className={`bg-zinc-900/70 border border-zinc-800/60 border-l-2 ${borderColor} rounded-xl p-3 cursor-pointer transition-all hover:bg-zinc-900`}
      onClick={() => onExpand(pos.id)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className={`text-xs font-bold px-1.5 py-0.5 rounded font-mono ${isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
            {isLong ? '▲ LONG' : '▼ SHORT'}
          </span>
          <span className="text-sm font-semibold text-white">{pos.symbol?.replace('/USDT', '')}/USDT</span>
          <span className="text-[10px] text-zinc-500 bg-zinc-800 px-1.5 py-0.5 rounded">
            {ENGINE_SHORT[pos.strategy?.toLowerCase?.()] || pos.strategy?.replace('_', ' ') || '—'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500">{pos.leverage}x</span>
          <span className={`font-mono text-sm font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fmtPct(pnl)}
          </span>
        </div>
      </div>
      <div className="flex items-center gap-3 mt-1.5">
        <span className="text-[11px] text-zinc-500 font-mono">Entry ${fmt(pos.entry_price, 4)}</span>
        <span className="text-[11px] text-zinc-500 font-mono">Now ${fmt(pos.current_price, 4)}</span>
        <span className={`text-[11px] font-mono font-semibold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
          {fmtPnl(pos.unrealized_pnl)}
        </span>
        <span className="text-[10px] text-zinc-600 ml-auto">{timeSince(pos.entry_time || pos.opened_at)} ago</span>
      </div>

      {expanded === pos.id && (
        <div className="mt-2 pt-2 border-t border-zinc-800/50 grid grid-cols-2 gap-x-4 gap-y-1">
          <div className="text-[10px] text-zinc-500">Stop Loss <span className="text-white font-mono">${fmt(pos.stop_price || pos.stop_loss, 4)}</span></div>
          <div className="text-[10px] text-zinc-500">Take Profit <span className="text-white font-mono">${fmt(pos.target_price || pos.take_profit, 4)}</span></div>
          <div className="text-[10px] text-zinc-500">Account <span className="text-cyan-400">{pos.account_id || '—'}</span></div>
          <div className="text-[10px] text-zinc-500">Margin <span className="text-white font-mono">${fmt(pos.margin, 0)}</span></div>
        </div>
      )}
    </div>
  );
}

function EngineStatusDot({ engineKey, data, onNavigate }) {
  const active = data?.config?.active !== false;
  const hasError = data?.stats?.last_error;
  const label = ENGINE_SHORT[engineKey] || engineKey.replace(/_/g, ' ').toUpperCase();

  let dotColor = 'bg-zinc-600';
  let labelColor = 'text-zinc-500';
  if (!active) { dotColor = 'bg-zinc-700'; labelColor = 'text-zinc-600'; }
  else if (hasError) { dotColor = 'bg-rose-500 animate-pulse'; labelColor = 'text-rose-400'; }
  else { dotColor = 'bg-emerald-500 animate-pulse'; labelColor = 'text-emerald-400'; }

  return (
    <button
      className="flex items-center gap-1.5 bg-zinc-900/60 border border-zinc-800/50 rounded-lg px-2 py-2 hover:bg-zinc-900 transition-all"
      onClick={() => onNavigate('engines')}
    >
      <div className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${dotColor}`} />
      <span className={`text-[10px] font-semibold font-mono truncate ${labelColor}`}>{label}</span>
    </button>
  );
}

export default function CommandCenter({ onNavigate }) {
  const [accounts, setAccounts] = useState([]);
  const [positions, setPositions] = useState([]);
  const [engines, setEngines] = useState({});
  const [regime, setRegime] = useState(null);
  const [stats, setStats] = useState(null);
  const [expandedPos, setExpandedPos] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(Date.now());
  const [refreshing, setRefreshing] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [accs, posData, engData, regData, statsData] = await Promise.allSettled([
        fetchAccounts(),
        fetchPositions(),
        fetchEngineStatus(),
        fetchRegime(),
        fetchTradingStats(),
      ]);
      if (accs.status === 'fulfilled') setAccounts(accs.value?.accounts || []);
      if (posData.status === 'fulfilled') setPositions(posData.value?.positions || []);
      if (engData.status === 'fulfilled') setEngines(engData.value?.engines || {});
      if (regData.status === 'fulfilled') setRegime(regData.value);
      if (statsData.status === 'fulfilled') setStats(statsData.value);
    } catch (e) {
      console.error('CommandCenter load error:', e);
    }
  }, []);

  useEffect(() => {
    loadAll();
    const intervals = [
      setInterval(loadAll, 30000),             // general 30s
    ];
    // positions poll every 10s
    const posInterval = setInterval(async () => {
      try {
        const d = await fetchPositions();
        setPositions(d?.positions || []);
      } catch {}
    }, 10000);
    return () => { intervals.forEach(clearInterval); clearInterval(posInterval); };
  }, [loadAll]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadAll();
    setLastRefresh(Date.now());
    setRefreshing(false);
  };

  const toggleExpand = (id) => setExpandedPos(prev => prev === id ? null : id);

  // Totals
  const totalBalance = accounts.reduce((s, a) => s + (a.balance || 0), 0);
  const totalPnl = accounts.reduce((s, a) => s + (a.total_pnl || 0), 0);
  const dailyPnl = stats?.total_pnl || 0;

  const regimeColor = {
    VOLATILE: 'text-rose-400',
    STRUCTURED: 'text-emerald-400',
    TRENDING: 'text-cyan-400',
    RANGING: 'text-amber-400',
    WEAK_TREND: 'text-amber-300',
    CHAOTIC: 'text-rose-500',
  }[regime?.regime] || 'text-zinc-400';

  const btcBiasColor = regime?.btc_trend === 'BULLISH' ? 'text-emerald-400'
    : regime?.btc_trend === 'BEARISH' ? 'text-rose-400'
    : 'text-zinc-400';

  return (
    <div className="space-y-4 pb-24">

      {/* Section 1: Summary strip */}
      <div className="flex items-center justify-between bg-zinc-900/60 border border-zinc-800/50 rounded-xl px-4 py-3">
        <div>
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest">Portfolio</div>
          <div className="font-mono text-xl font-bold text-white">
            ${totalBalance.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
        </div>
        <div className="text-center">
          <div className="text-[10px] text-zinc-500 uppercase tracking-widest">Today PnL</div>
          <div className={`font-mono text-xl font-bold ${pnlColor(dailyPnl)}`}>
            {fmtPnl(dailyPnl)}
          </div>
        </div>
        <div className="text-right flex flex-col items-end gap-1">
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${stats?.active ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500 animate-pulse'}`} />
            <span className={`text-xs font-semibold ${stats?.active ? 'text-emerald-400' : 'text-amber-400'}`}>
              {stats?.active ? 'ACTIVE' : 'PAUSED'}
            </span>
          </div>
          <button
            onClick={handleRefresh}
            className="text-zinc-600 hover:text-zinc-300 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Section 2: Account cards */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">Accounts</span>
          <span className="text-[10px] text-zinc-600 font-mono">{accounts.length} accounts</span>
        </div>
        <div className="flex gap-2 overflow-x-auto no-scrollbar pb-1">
          {accounts.length === 0 && (
            <div className="text-xs text-zinc-600 py-2">Loading accounts...</div>
          )}
          {accounts.map(acc => <AccountCard key={acc.account_id} account={acc} />)}
        </div>
      </div>

      {/* Section 3: Market regime strip */}
      <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl px-4 py-2.5 flex items-center gap-4 flex-wrap">
        <div className="flex items-center gap-1.5">
          <Radio className="w-3 h-3 text-zinc-500" />
          <span className="text-[10px] text-zinc-500 uppercase tracking-wider">Regime</span>
          <span className={`text-xs font-bold font-mono ${regimeColor}`}>{regime?.regime || '—'}</span>
        </div>
        <span className="text-zinc-700">|</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-zinc-500">BTC</span>
          <span className={`text-xs font-bold font-mono ${btcBiasColor}`}>{regime?.btc_trend || regime?.macro_direction || '—'}</span>
        </div>
        <span className="text-zinc-700">|</span>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-zinc-500">Session</span>
          <span className="text-xs font-semibold text-zinc-300">{stats?.current_session?.replace('_', ' ') || regime?.session || '—'}</span>
        </div>
        {stats?.fear_greed != null && (
          <>
            <span className="text-zinc-700">|</span>
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-zinc-500">F&G</span>
              <span className={`text-xs font-bold font-mono ${stats.fear_greed < 25 ? 'text-rose-400' : stats.fear_greed > 65 ? 'text-emerald-400' : 'text-amber-400'}`}>
                {stats.fear_greed}
              </span>
            </div>
          </>
        )}
      </div>

      {/* Section 4: Live positions */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">
            Live Positions
          </span>
          <span className="text-[10px] text-zinc-600 font-mono">{positions.length} open</span>
        </div>

        {positions.length === 0 ? (
          <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl px-4 py-6 text-center">
            <Activity className="w-6 h-6 text-zinc-700 mx-auto mb-2" />
            <p className="text-xs text-zinc-600">No open positions — AEON is scanning</p>
          </div>
        ) : (
          <div className="space-y-2">
            {positions.map(pos => (
              <PositionCard
                key={pos.id}
                pos={pos}
                onExpand={toggleExpand}
                expanded={expandedPos}
              />
            ))}
          </div>
        )}
      </div>

      {/* Section 5: Engine grid */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] text-zinc-500 uppercase tracking-widest font-semibold">Engines</span>
          <button
            onClick={() => onNavigate('engines')}
            className="flex items-center gap-0.5 text-[10px] text-cyan-400 hover:text-cyan-300"
          >
            Manage <ChevronRight className="w-3 h-3" />
          </button>
        </div>
        <div className="grid grid-cols-3 gap-1.5">
          {ENGINE_GRID_ORDER.map(key => (
            <EngineStatusDot
              key={key}
              engineKey={key}
              data={engines[key]}
              onNavigate={onNavigate}
            />
          ))}
        </div>
      </div>

      {/* Quick stats strip */}
      {stats && (
        <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl px-4 py-3 grid grid-cols-3 gap-2">
          <div className="text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Trades</div>
            <div className="font-mono text-lg font-bold text-white">{stats.total_trades || 0}</div>
          </div>
          <div className="text-center border-x border-zinc-800/50">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Win Rate</div>
            <div className={`font-mono text-lg font-bold ${stats.win_rate >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>
              {fmt(stats.win_rate, 1)}%
            </div>
          </div>
          <div className="text-center">
            <div className="text-[10px] text-zinc-500 uppercase tracking-wider">Total PnL%</div>
            <div className={`font-mono text-lg font-bold ${pnlColor(stats.total_pnl_pct)}`}>
              {fmtPct(stats.total_pnl_pct)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
