import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, TrendingUp, TrendingDown, DollarSign, Target,
  Play, Pause, RefreshCw, X, Settings2, Zap, Radio, BarChart3,
  AlertTriangle, Shield, Flame, Clock, ChevronRight, Percent,
  ArrowUpRight, ArrowDownRight, Crosshair, LineChart, CandlestickChart,
  Wallet, Crown, Leaf, CheckCircle
} from 'lucide-react';
import TradingChart from './TradingChart';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// ─── Helpers ────────────────────────────────────────────────────────────────

const formatPrice = (price) => {
  if (!price && price !== 0) return '-';
  if (Math.abs(price) > 1000) return price.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(price) > 1)    return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return price.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
};

const STRATEGY_COLORS = {
  FREE_WILL_V2:   'bg-purple-500/20 text-purple-300',
  YOLO:           'bg-red-500/20 text-red-300',
  VWAP_SCALP:     'bg-blue-500/20 text-blue-300',
  DAY_TRADER:     'bg-orange-500/20 text-orange-300',
  LONG_TERM:      'bg-green-500/20 text-green-300',
  ELITE:          'bg-yellow-500/20 text-yellow-300',
  AUTONOMOUS_V2:  'bg-cyan-500/20 text-cyan-300',
};
const strategyColor = (s) => STRATEGY_COLORS[s] || 'bg-zinc-500/20 text-zinc-300';

// ─── PnL Sparkline ──────────────────────────────────────────────────────────

const PnLChart = ({ data }) => {
  if (!data || data.length < 2) return (
    <div className="h-32 flex items-center justify-center text-zinc-500 text-sm">No trade history yet</div>
  );
  const maxPnl = Math.max(...data.map(d => d.cumulative_pnl), 0);
  const minPnl = Math.min(...data.map(d => d.cumulative_pnl), 0);
  const range = Math.max(maxPnl - minPnl, 1);
  const W = 100, H = 120;
  const points = data.map((d, i) => {
    const x = (i / (data.length - 1)) * W;
    const y = H - ((d.cumulative_pnl - minPnl) / range) * H;
    return `${x},${y}`;
  }).join(' ');
  const isPositive = data[data.length - 1]?.cumulative_pnl >= 0;
  return (
    <div className="relative h-32">
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-full" preserveAspectRatio="none">
        <line x1="0" y1={H - ((0 - minPnl) / range) * H} x2={W} y2={H - ((0 - minPnl) / range) * H}
          stroke="#52525b" strokeWidth="0.5" strokeDasharray="2,2" />
        <polyline fill="none" stroke={isPositive ? '#22c55e' : '#ef4444'} strokeWidth="2" points={points} />
        <polygon fill={isPositive ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)'}
          points={`0,${H} ${points} ${W},${H}`} />
      </svg>
      <div className="absolute top-0 right-0 text-xs text-zinc-500">{maxPnl > 0 && `+${maxPnl.toFixed(1)}%`}</div>
      <div className="absolute bottom-0 right-0 text-xs text-zinc-500">{minPnl < 0 && `${minPnl.toFixed(1)}%`}</div>
    </div>
  );
};

// ─── Compact Position Row ────────────────────────────────────────────────────

const PositionRow = ({ position, onClose, onSelect, closing }) => {
  const isLong = position.direction === 'LONG';
  const pnl = position.pnl_pct || 0;
  const leverage = position.leverage || 1;
  const leveragedPnl = pnl * leverage;
  const isProfitable = leveragedPnl >= 0;
  const symbol = (position.symbol || '').replace('/USDT', '');
  const accountBadge = position.account_id === 'STARTER' ? '🌱' : position.account_id === 'PRO' ? '👑' : '🤖';

  return (
    <div
      className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer hover:border-zinc-600/60 transition-colors ${
        isProfitable ? 'border-emerald-500/20 bg-emerald-500/5' : 'border-rose-500/20 bg-rose-500/5'
      }`}
      onClick={() => onSelect && onSelect(position)}
    >
      {/* Direction + Symbol */}
      <div className={`p-2 rounded-lg flex-shrink-0 ${isLong ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
        {isLong ? <TrendingUp className="w-4 h-4 text-emerald-400" /> : <TrendingDown className="w-4 h-4 text-rose-400" />}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 flex-wrap">
          <span className="font-semibold text-white text-sm">{symbol}</span>
          <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
            {isLong ? 'L' : 'S'}
          </span>
          <span className="text-xs text-orange-400">{leverage}x</span>
          <span className="text-xs">{accountBadge}</span>
          {position.strategy && (
            <span className={`text-xs px-1 py-0.5 rounded ${strategyColor(position.strategy)}`}>
              {position.strategy}
            </span>
          )}
        </div>
        <div className="text-xs text-zinc-500 mt-0.5 font-mono">
          Entry ${formatPrice(position.entry_price)} · SL ${formatPrice(position.stop_price || position.stop_loss)}
        </div>
      </div>

      {/* PnL */}
      <div className={`text-right flex-shrink-0 ${isProfitable ? 'text-emerald-400' : 'text-rose-400'}`}>
        <div className="font-mono font-bold text-sm">{isProfitable ? '+' : ''}{leveragedPnl.toFixed(2)}%</div>
        <div className="text-xs font-mono opacity-70">
          ${formatPrice(position.current_price || position.entry_price)}
        </div>
      </div>

      {/* Close button */}
      <button
        onClick={(e) => { e.stopPropagation(); onClose(position); }}
        disabled={closing === position.id}
        className="flex-shrink-0 p-1.5 rounded-lg bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 transition-colors disabled:opacity-40"
        title="Close position"
      >
        {closing === position.id
          ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
          : <X className="w-3.5 h-3.5" />
        }
      </button>
    </div>
  );
};

// ─── Account Health Card ─────────────────────────────────────────────────────

const AccountCard = ({ account, onReset }) => {
  const healthPct = account.starting_balance ? (account.balance / account.starting_balance) * 100 : 100;
  const isLow = healthPct < 20;
  const isCritical = healthPct < 5;
  return (
    <div className={`glass-card p-4 ${isCritical ? 'border-rose-500/50' : isLow ? 'border-amber-500/30' : ''}`}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {account.account_id === 'PRO' ? <Crown className="w-4 h-4 text-amber-500" /> : <Leaf className="w-4 h-4 text-green-500" />}
          <span className="font-semibold text-white">{account.name || account.account_id}</span>
          {isCritical && <span className="text-xs bg-rose-500/20 text-rose-300 px-1.5 py-0.5 rounded">Auto-reloading</span>}
          {isLow && !isCritical && <span className="text-xs bg-amber-500/20 text-amber-300 px-1.5 py-0.5 rounded">Low</span>}
        </div>
        <button onClick={() => onReset(account.account_id)} className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors" title="Reset account">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Health bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-zinc-500">Health</span>
          <span className={healthPct > 50 ? 'text-emerald-400' : healthPct > 20 ? 'text-amber-400' : 'text-rose-400'}>{healthPct.toFixed(1)}%</span>
        </div>
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <div className={`h-full transition-all duration-500 ${healthPct > 50 ? 'bg-emerald-500' : healthPct > 20 ? 'bg-amber-500' : 'bg-rose-500'}`}
            style={{ width: `${Math.min(100, healthPct)}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-zinc-500">Balance</div>
          <div className="font-bold text-white">${formatPrice(account.balance)}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Total PnL</div>
          <div className={`font-bold ${account.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {account.total_pnl >= 0 ? '+' : ''}${formatPrice(account.total_pnl)}
          </div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Positions</div>
          <div className="font-semibold text-white">{account.open_positions}</div>
        </div>
        <div>
          <div className="text-xs text-zinc-500">Win Rate</div>
          <div className={`font-semibold ${account.win_rate >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>{account.win_rate}%</div>
        </div>
      </div>
    </div>
  );
};

// ─── Main Component ──────────────────────────────────────────────────────────

export default function Trading() {
  const [stats, setStats] = useState(null);
  const [livePositions, setLivePositions] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [pnlHistory, setPnlHistory] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('positions');
  const [confidence, setConfidence] = useState(70);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [closingId, setClosingId] = useState(null);
  const [closeError, setCloseError] = useState(null);
  const [positionFilter, setPositionFilter] = useState('all'); // all | PRO | STARTER | v2

  const fetchData = useCallback(async () => {
    try {
      const [statsRes, liveRes, closedRes, historyRes, accountsRes, perfRes] = await Promise.allSettled([
        fetch(`${API_URL}/api/trading/v2/stats`).then(r => r.json()),
        fetch(`${API_URL}/api/trading/v2/live-positions`).then(r => r.json()),
        fetch(`${API_URL}/api/trading/v2/closed`).then(r => r.json()),
        fetch(`${API_URL}/api/trading/v2/pnl-history`).then(r => r.json()),
        fetch(`${API_URL}/api/paper/accounts`).then(r => r.json()),
        fetch(`${API_URL}/api/paper/performance`).then(r => r.json()),
      ]);

      if (statsRes.status === 'fulfilled') {
        setStats(statsRes.value);
        setConfidence(statsRes.value.min_confidence || 70);
      }
      if (liveRes.status === 'fulfilled') setLivePositions(liveRes.value.positions || []);
      if (closedRes.status === 'fulfilled') setClosedTrades(closedRes.value.closed_trades || []);
      if (historyRes.status === 'fulfilled') setPnlHistory(historyRes.value.history || []);
      if (accountsRes.status === 'fulfilled') setAccounts(accountsRes.value.accounts || []);
      if (perfRes.status === 'fulfilled') setStrategies(perfRes.value.strategies || []);
    } catch (err) {
      console.error('Failed to fetch trading data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleTrading = async () => {
    try {
      await fetch(`${API_URL}/api/trading/toggle?active=${!stats?.active}`, { method: 'POST' });
      fetchData();
    } catch (err) { console.error('Toggle failed:', err); }
  };

  const updateConfidence = async (val) => {
    try {
      await fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${val}`, { method: 'POST' });
      setConfidence(val);
    } catch (err) { console.error('Update confidence failed:', err); }
  };

  // ── Close position — accepts full position object, routes by account_id ──
  const closeTrade = async (position) => {
    if (!position) return;
    const { id, symbol, account_id } = position;
    const cleanSymbol = (symbol || '').replace('/USDT', '');
    setClosingId(id);
    setCloseError(null);
    try {
      let res, data;
      if (account_id) {
        // Paper trade (PRO or STARTER) — close by account + symbol
        res = await fetch(`${API_URL}/api/paper/close/${account_id}/${cleanSymbol}`, { method: 'POST' });
        data = await res.json();
      } else {
        // Autonomous v2 in-memory trade
        res = await fetch(`${API_URL}/api/trading/v2/close/${cleanSymbol}`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ percentage: 100 })
        });
        data = await res.json();
      }

      if (data?.error) {
        setCloseError(`${symbol}: ${data.error}`);
        return;
      }

      // Optimistic remove by ID (unique per position)
      setLivePositions(prev => prev.filter(p => p.id !== id));
      setSelectedPosition(null);
    } catch (err) {
      setCloseError(`Failed to close ${symbol}: ${err.message}`);
    } finally {
      setClosingId(null);
      // Refresh in background
      setTimeout(fetchData, 1000);
    }
  };

  const resetAccount = async (accountId) => {
    if (!window.confirm(`Reset ${accountId} to starting balance? All positions will be closed.`)) return;
    try {
      await fetch(`${API_URL}/api/paper/reset/${accountId}`, { method: 'POST' });
      fetchData();
    } catch (err) { console.error('Reset failed:', err); }
  };

  // ── Derived ──────────────────────────────────────────────────────────────
  const totalLivePnl = livePositions.reduce((s, p) => s + (p.pnl_pct || 0), 0);

  const filteredPositions = livePositions.filter(p => {
    if (positionFilter === 'PRO')     return p.account_id === 'PRO';
    if (positionFilter === 'STARTER') return p.account_id === 'STARTER';
    if (positionFilter === 'v2')      return !p.account_id;
    return true;
  });

  return (
    <div className="space-y-3 sm:space-y-4">
      {/* Live banner */}
      <div className="flex items-center gap-2 px-3 sm:px-4 py-2 glass-card border-emerald-500/20">
        <div className="relative">
          <Radio className="w-4 h-4 text-emerald-400" />
          <span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-emerald-400 rounded-full animate-ping" />
        </div>
        <span className="text-emerald-400 text-sm font-medium">Live MEXC · Paper Mode</span>
        <span className="text-zinc-500 text-xs ml-auto">{livePositions.length} open positions</span>
      </div>

      {/* Close error */}
      {closeError && (
        <div className="flex items-center justify-between p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-sm">
          <div className="flex items-center gap-2 text-rose-300">
            <AlertTriangle className="w-4 h-4 flex-shrink-0" />
            {closeError}
          </div>
          <button onClick={() => setCloseError(null)} className="text-rose-400 hover:text-rose-200 ml-3">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Stats row */}
      <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 sm:gap-3">
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Status</p>
              <p className={`text-lg sm:text-xl font-display font-bold ${stats?.active ? 'text-emerald-400' : 'text-rose-400'}`}>
                {stats?.active ? 'ON' : 'OFF'}
              </p>
            </div>
            <button onClick={toggleTrading}
              className={`p-2 rounded-xl transition-all ${stats?.active ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30' : 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30'}`}>
              {stats?.active ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
            </button>
          </div>
        </div>
        <div className="glass-card-hover p-3 sm:p-4">
          <p className="data-label">Positions</p>
          <p className="text-lg sm:text-xl font-display font-bold text-white">{livePositions.length}</p>
        </div>
        <div className="glass-card-hover p-3 sm:p-4">
          <p className="data-label">Live PnL</p>
          <p className={`text-lg sm:text-xl font-mono font-bold ${totalLivePnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {totalLivePnl >= 0 ? '+' : ''}{totalLivePnl.toFixed(1)}%
          </p>
        </div>
        <div className="glass-card-hover p-3 sm:p-4 hidden sm:block">
          <p className="data-label">Win Rate</p>
          <p className={`text-xl font-mono font-bold ${(stats?.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-orange-400'}`}>
            {stats?.win_rate || 0}%
          </p>
        </div>
        <div className="glass-card-hover p-3 sm:p-4 hidden sm:block">
          <p className="data-label">Trades</p>
          <p className="text-xl font-mono font-bold">
            <span className="text-emerald-400">{stats?.wins || 0}W</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-rose-400">{stats?.losses || 0}L</span>
          </p>
        </div>
      </div>

      {/* Confidence slider */}
      <div className="glass-card p-3 sm:p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-orange-400" />
            <span className="text-white text-sm font-medium">Min Confidence</span>
          </div>
          <span className="text-orange-400 font-bold text-sm">{confidence}%</span>
        </div>
        <input type="range" min="60" max="95" value={confidence}
          onChange={(e) => setConfidence(parseInt(e.target.value))}
          onMouseUp={(e) => updateConfidence(parseInt(e.target.value))}
          onTouchEnd={(e) => updateConfidence(parseInt(e.target.value))}
          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500" />
        <div className="flex justify-between text-xs text-zinc-500 mt-1">
          <span>More trades (60%)</span><span>Elite only (95%)</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 overflow-x-auto no-scrollbar">
        <div className="flex bg-zinc-800/50 rounded-lg p-1 min-w-max">
          {[
            { id: 'positions', label: 'Positions', badge: livePositions.length },
            { id: 'accounts', label: 'Accounts' },
            { id: 'history', label: 'History' },
            { id: 'opportunities', label: 'Opps' },
            { id: 'chart', label: 'Chart' },
          ].map(t => (
            <button key={t.id} onClick={() => setActiveTab(t.id)}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1 ${
                activeTab === t.id ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}>
              {t.label}
              {t.badge > 0 && (
                <span className={`text-[10px] px-1 rounded-full ${activeTab === t.id ? 'bg-white/20' : 'bg-zinc-700'}`}>
                  {t.badge}
                </span>
              )}
            </button>
          ))}
        </div>
        <button onClick={fetchData} className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white transition-all">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* ── TAB: POSITIONS ─────────────────────────────────────────────────── */}
      {activeTab === 'positions' && (
        <div className="space-y-3">
          {/* Account filter */}
          <div className="flex gap-2 flex-wrap">
            {['all', 'PRO', 'STARTER', 'v2'].map(f => (
              <button key={f} onClick={() => setPositionFilter(f)}
                className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                  positionFilter === f ? 'bg-orange-500 text-white' : 'bg-zinc-800/50 text-zinc-400 hover:text-white'
                }`}>
                {f === 'all' ? `All (${livePositions.length})` :
                 f === 'PRO' ? `👑 PRO (${livePositions.filter(p => p.account_id === 'PRO').length})` :
                 f === 'STARTER' ? `🌱 STARTER (${livePositions.filter(p => p.account_id === 'STARTER').length})` :
                 `🤖 Engine V2 (${livePositions.filter(p => !p.account_id).length})`}
              </button>
            ))}
          </div>

          {/* Selected position detail panel */}
          {selectedPosition && (
            <div className={`glass-card p-4 border ${
              selectedPosition.direction === 'LONG' ? 'border-emerald-500/30' : 'border-rose-500/30'
            }`}>
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-white">{selectedPosition.symbol}</span>
                  <span className={`text-xs px-2 py-0.5 rounded ${selectedPosition.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                    {selectedPosition.direction} {selectedPosition.leverage}x
                  </span>
                  {selectedPosition.account_id && (
                    <span className="text-xs text-zinc-400">
                      {selectedPosition.account_id === 'PRO' ? '👑 PRO' : '🌱 STARTER'}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => closeTrade(selectedPosition)}
                    disabled={closingId === selectedPosition.id}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-500 hover:bg-rose-600 disabled:opacity-50 text-white rounded-lg text-sm font-medium transition-all"
                  >
                    {closingId === selectedPosition.id
                      ? <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      : <X className="w-3.5 h-3.5" />}
                    Close Position
                  </button>
                  <button onClick={() => setSelectedPosition(null)} className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-400">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div><p className="text-xs text-zinc-500">Entry</p><p className="text-white font-mono">${formatPrice(selectedPosition.entry_price)}</p></div>
                <div><p className="text-xs text-zinc-500">Current</p><p className="text-cyan-400 font-mono">${formatPrice(selectedPosition.current_price)}</p></div>
                <div><p className="text-xs text-zinc-500">Stop Loss</p><p className="text-rose-400 font-mono">${formatPrice(selectedPosition.stop_price || selectedPosition.stop_loss)}</p></div>
                <div><p className="text-xs text-zinc-500">Take Profit</p><p className="text-emerald-400 font-mono">${formatPrice(selectedPosition.target_price || selectedPosition.take_profit)}</p></div>
                {selectedPosition.margin && <div><p className="text-xs text-zinc-500">Margin</p><p className="text-white font-mono">${formatPrice(selectedPosition.margin)}</p></div>}
                {selectedPosition.liquidation_price && <div><p className="text-xs text-zinc-500">Liq Price</p><p className="text-rose-400 font-mono">${formatPrice(selectedPosition.liquidation_price)}</p></div>}
                {selectedPosition.confidence && <div><p className="text-xs text-zinc-500">Confidence</p><p className="text-white">{selectedPosition.confidence}%</p></div>}
                <div>
                  <p className="text-xs text-zinc-500">Unrealized PnL</p>
                  <p className={`font-bold ${(selectedPosition.pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {(selectedPosition.pnl_pct || 0) >= 0 ? '+' : ''}{((selectedPosition.pnl_pct || 0) * (selectedPosition.leverage || 1)).toFixed(2)}%
                  </p>
                </div>
              </div>
              {selectedPosition.confirmations?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {selectedPosition.confirmations.slice(0, 5).map((c, i) => (
                    <span key={i} className="text-xs px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20">✓ {c}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Position list */}
          {filteredPositions.length > 0 ? (
            <div className="space-y-1.5">
              {filteredPositions.map((pos, i) => (
                <PositionRow
                  key={pos.id || i}
                  position={pos}
                  onClose={closeTrade}
                  onSelect={setSelectedPosition}
                  closing={closingId}
                />
              ))}
            </div>
          ) : (
            <div className="glass-card p-8 text-center">
              <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400 font-medium">No open positions</p>
              <p className="text-zinc-600 text-sm mt-1">Aeon is scanning MEXC for high-probability setups…</p>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: ACCOUNTS ──────────────────────────────────────────────────── */}
      {activeTab === 'accounts' && (
        <div className="space-y-4">
          {/* PnL chart */}
          <div className="glass-card p-4 hidden sm:block">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-4 h-4 text-orange-400" />
                <span className="text-white text-sm font-medium">Cumulative PnL</span>
              </div>
              <span className={`text-sm font-mono font-bold ${(stats?.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(stats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(stats?.total_pnl_pct || 0).toFixed(2)}% Total
              </span>
            </div>
            <PnLChart data={pnlHistory} />
          </div>

          {/* Account cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {accounts.map(acc => (
              <AccountCard key={acc.account_id} account={acc} onReset={resetAccount} />
            ))}
          </div>

          {/* Strategy performance */}
          {strategies.length > 0 && (
            <div className="glass-card p-4">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-4 h-4 text-orange-400" />
                <span className="text-white font-medium">Strategy Performance</span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {strategies.map(s => (
                  <div key={s.name} className="p-3 bg-zinc-800/50 rounded-lg border border-zinc-700/50">
                    <div className="flex items-center justify-between mb-2">
                      <span className={`text-xs px-2 py-0.5 rounded font-medium border ${strategyColor(s.name)}`}>{s.name}</span>
                      <span className="text-xs text-zinc-500">{s.total_trades} trades</span>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <p className="text-xs text-zinc-500">Win Rate</p>
                        <p className={`font-semibold ${s.win_rate >= 50 ? 'text-emerald-400' : 'text-amber-400'}`}>{s.win_rate}%</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">Total PnL</p>
                        <p className={`font-semibold ${s.total_pnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>${formatPrice(s.total_pnl)}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: HISTORY ───────────────────────────────────────────────────── */}
      {activeTab === 'history' && (
        <div className="space-y-2">
          {closedTrades.length > 0 ? (
            [...closedTrades].reverse().map((trade, i) => (
              <div key={i} className={`glass-card p-3 border ${(trade.pnl_pct || 0) >= 0 ? 'border-emerald-500/20' : 'border-rose-500/20'}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                      trade.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                    }`}>{trade.direction}</span>
                    <span className="text-white font-medium text-sm">{(trade.symbol || '').replace('/USDT', '')}</span>
                    {trade.exit_reason && (
                      <span className={`text-xs px-1.5 py-0.5 rounded ${(trade.pnl_pct || 0) >= 0 ? 'bg-emerald-500/10 text-emerald-400' : 'bg-rose-500/10 text-rose-400'}`}>
                        {trade.exit_reason}
                      </span>
                    )}
                  </div>
                  <span className={`font-bold ${(trade.pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                    {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-2 text-xs text-zinc-500 font-mono">
                  <span>Entry: ${formatPrice(trade.entry_price)}</span>
                  <span>Exit: ${formatPrice(trade.exit_price)}</span>
                </div>
              </div>
            ))
          ) : (
            <div className="glass-card p-8 text-center">
              <DollarSign className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400">No trade history yet</p>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: OPPORTUNITIES ─────────────────────────────────────────────── */}
      {activeTab === 'opportunities' && (
        <div className="space-y-3">
          <p className="text-xs text-zinc-500 text-center">Scanning MEXC for live setups — updates when engines find signals</p>
          {opportunities.length > 0 ? opportunities.slice(0, 10).map((opp, i) => (
            <div key={i} className={`glass-card p-4 border ${opp.direction === 'LONG' ? 'border-emerald-500/20' : 'border-rose-500/20'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <Zap className={`w-4 h-4 ${opp.direction === 'LONG' ? 'text-emerald-400' : 'text-rose-400'}`} />
                  <span className="text-white font-medium">{(opp.symbol || '').replace('/USDT', '')}</span>
                  <span className={`text-xs px-2 py-0.5 rounded font-bold ${opp.direction === 'LONG' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
                    {opp.direction}
                  </span>
                </div>
                <span className="text-orange-400 font-bold">{opp.confidence}%</span>
              </div>
              <div className="grid grid-cols-3 gap-3 text-xs">
                <div><span className="text-zinc-500">Entry: </span><span className="text-white">${opp.entry?.toLocaleString()}</span></div>
                <div><span className="text-zinc-500">TP: </span><span className="text-emerald-400">${opp.target?.toLocaleString()}</span></div>
                <div><span className="text-zinc-500">SL: </span><span className="text-rose-400">${opp.stop?.toLocaleString()}</span></div>
              </div>
            </div>
          )) : (
            <div className="glass-card p-8 text-center">
              <Target className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No opportunities right now</p>
            </div>
          )}
        </div>
      )}

      {/* ── TAB: CHART ─────────────────────────────────────────────────────── */}
      {activeTab === 'chart' && (
        <TradingChart symbol="BTC" trades={closedTrades} positions={livePositions} height={450} showControls={true} />
      )}
    </div>
  );
}
