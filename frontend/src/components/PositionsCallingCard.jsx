import React, { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react';
import {
  TrendingUp, TrendingDown, Clock, Zap, AlertTriangle,
  X, CheckCircle, RefreshCw, Activity, DollarSign
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const API_KEY = process.env.REACT_APP_API_KEY || '';
const authHeaders = { 'X-API-Key': API_KEY };

const POLL_MS = 6000;

const ENGINE_COLORS = {
  FREE_WILL_V2:   'text-purple-400 bg-purple-500/10 border-purple-500/20',
  YOLO:           'text-red-400 bg-red-500/10 border-red-500/20',
  VWAP_SCALP_MTF: 'text-blue-400 bg-blue-500/10 border-blue-500/20',
  VWAP_SCALP:     'text-blue-400 bg-blue-500/10 border-blue-500/20',
  DAY_TRADER:     'text-orange-400 bg-orange-500/10 border-orange-500/20',
  LONG_TERM:      'text-green-400 bg-green-500/10 border-green-500/20',
  ELITE:          'text-yellow-400 bg-yellow-500/10 border-yellow-500/20',
  AUTONOMOUS_V2:  'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  HYPER_ACCURACY: 'text-pink-400 bg-pink-500/10 border-pink-500/20',
  AEON:           'text-orange-400 bg-orange-500/10 border-orange-500/20',
};
const engineColor = (e) => ENGINE_COLORS[e] || 'text-zinc-400 bg-zinc-500/10 border-zinc-500/20';

const fmt = (n) => {
  if (n == null || isNaN(n)) return '—';
  if (Math.abs(n) >= 10000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(n) >= 100)   return n.toLocaleString(undefined, { maximumFractionDigits: 1 });
  if (Math.abs(n) >= 1)     return n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return n.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
};

const fmtPnl = (n) => {
  if (n == null || isNaN(n)) return '—';
  const abs = Math.abs(n);
  const str = abs >= 10000
    ? abs.toLocaleString(undefined, { maximumFractionDigits: 0 })
    : abs >= 100
      ? abs.toLocaleString(undefined, { maximumFractionDigits: 1 })
      : abs.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return (n >= 0 ? '+' : '-') + '$' + str;
};

const fmtDuration = (min) => {
  if (!min) return '0m';
  if (min < 60) return `${min}m`;
  const h = Math.floor(min / 60);
  const m = min % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
};

// ── Single calling card (memoized — only re-renders when its own props change) ─

const CallingCard = memo(({ position, onClose, onDismissError, isClosing, closeError }) => {
  const [armed, setArmed] = useState(false);
  const armTimeout = useRef(null);

  const isLong = position.direction === 'LONG';
  const pnl = position.pnl_pct ?? 0;
  const isProfit = pnl >= 0;
  const isPanicZone = pnl < -30;

  const handleCloseClick = () => {
    if (!armed) {
      setArmed(true);
      armTimeout.current = setTimeout(() => setArmed(false), 3000);
    } else {
      clearTimeout(armTimeout.current);
      setArmed(false);
      onClose(position);
    }
  };

  useEffect(() => () => clearTimeout(armTimeout.current), []);

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl border transition-all duration-300
        ${isClosing ? 'opacity-40 scale-95 pointer-events-none' : 'opacity-100 scale-100'}
        ${isProfit
          ? 'border-emerald-500/30 bg-gradient-to-br from-zinc-900 via-emerald-950/20 to-zinc-900'
          : isPanicZone
            ? 'border-rose-500/60 bg-gradient-to-br from-zinc-900 via-rose-950/30 to-zinc-900'
            : 'border-rose-500/30 bg-gradient-to-br from-zinc-900 via-rose-950/20 to-zinc-900'
        }
      `}
      style={{
        boxShadow: isProfit
          ? '0 0 20px rgba(16,185,129,0.06)'
          : isPanicZone
            ? '0 0 28px rgba(239,68,68,0.22)'
            : '0 0 20px rgba(239,68,68,0.06)',
      }}
    >
      {/* Panic zone: pulsing ring overlay */}
      {isPanicZone && (
        <div className="absolute inset-0 rounded-2xl border-2 border-rose-500/50 animate-pulse pointer-events-none z-10" />
      )}

      {/* Live pulse bar across top */}
      <div className={`h-0.5 w-full ${isProfit ? 'bg-emerald-500/40' : 'bg-rose-500/40'}`}>
        <div
          className={`h-full ${isProfit ? 'bg-emerald-400' : 'bg-rose-400'}`}
          style={{ width: '40%', animation: 'pulse-slide 2s ease-in-out infinite' }}
        />
      </div>

      {/* Header row */}
      <div className="flex items-start justify-between px-4 pt-3 pb-2">
        <div className="flex items-center gap-3 min-w-0">
          {/* Direction icon */}
          <div className={`flex-shrink-0 w-10 h-10 rounded-xl flex items-center justify-center border ${
            isLong
              ? 'bg-emerald-500/10 border-emerald-500/20'
              : 'bg-rose-500/10 border-rose-500/20'
          }`}>
            {isLong
              ? <TrendingUp className="w-5 h-5 text-emerald-400" />
              : <TrendingDown className="w-5 h-5 text-rose-400" />
            }
          </div>

          {/* Symbol + badges */}
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-white font-bold text-lg leading-none">
                {position.base || position.symbol?.replace('/USDT', '')}
              </span>
              <span className={`text-xs px-2 py-0.5 rounded-full font-bold border ${
                isLong
                  ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                  : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
              }`}>
                {position.direction}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20">
                {position.leverage}x
              </span>
            </div>
            {/* Engine + time */}
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono font-medium ${engineColor(position.engine)}`}>
                {position.engine}
              </span>
              <span className="text-[10px] text-zinc-500 flex items-center gap-0.5">
                <Clock className="w-2.5 h-2.5" />
                {fmtDuration(position.duration_min)}
              </span>
              {position.account_id && (
                <span className="text-[10px] text-zinc-600">{position.account_id}</span>
              )}
            </div>
          </div>
        </div>

        {/* PnL — hero number */}
        <div className="text-right flex-shrink-0 ml-2">
          <div className={`text-2xl font-mono font-black leading-none ${isProfit ? 'text-emerald-400' : isPanicZone ? 'text-rose-300' : 'text-rose-400'}`}>
            {isProfit ? '+' : ''}{pnl.toFixed(2)}%
          </div>
          <div className={`text-xs font-mono mt-0.5 ${isProfit ? 'text-emerald-400/60' : 'text-rose-400/60'}`}>
            {fmtPnl(position.unrealized_pnl)} USDT
          </div>
          <div className="text-[10px] text-zinc-600 mt-0.5">ROE</div>
        </div>
      </div>

      {/* Price data grid */}
      <div className="grid grid-cols-3 border-t border-zinc-800/60 mx-4 mb-0">
        <div className="py-2 pr-3">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Entry</div>
          <div className="text-xs font-mono text-blue-400 font-semibold">${fmt(position.entry_price)}</div>
        </div>
        <div className="py-2 px-3 border-x border-zinc-800/60">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">
            Current {!position.price_is_live && <span className="text-zinc-700 normal-case">(stale)</span>}
          </div>
          <div className={`text-xs font-mono font-semibold ${position.price_is_live ? 'text-white' : 'text-zinc-500'}`}>
            ${fmt(position.current_price)}
          </div>
        </div>
        <div className="py-2 pl-3">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Liq Price</div>
          <div className={`text-xs font-mono font-semibold ${
            position.liquidation_price ? 'text-rose-400/70' : 'text-zinc-600'
          }`}>
            {position.liquidation_price ? `$${fmt(position.liquidation_price)}` : 'N/A'}
          </div>
        </div>
      </div>

      {/* Size + Margin row */}
      <div className="grid grid-cols-2 border-t border-zinc-800/60 mx-4">
        <div className="py-2 pr-3">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Size (notional)</div>
          <div className="text-xs font-mono text-zinc-300">${fmt(position.position_size)}</div>
        </div>
        <div className="py-2 pl-3 border-l border-zinc-800/60">
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Margin</div>
          <div className="text-xs font-mono text-zinc-300">${fmt(position.margin)}</div>
        </div>
      </div>

      {/* Error state */}
      {closeError && (
        <div className="mx-4 mb-2 flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-rose-500/10 border border-rose-500/30">
          <div className="flex items-center gap-1.5 text-xs text-rose-300">
            <AlertTriangle className="w-3 h-3 flex-shrink-0" />
            {closeError}
          </div>
          <button onClick={onDismissError} className="text-rose-400 hover:text-rose-200 flex-shrink-0">
            <X className="w-3 h-3" />
          </button>
        </div>
      )}

      {/* Close button */}
      <div className="px-4 pb-3 pt-2 border-t border-zinc-800/60">
        <button
          onClick={handleCloseClick}
          disabled={isClosing}
          className={`w-full py-2 rounded-xl text-sm font-semibold transition-all duration-200 flex items-center justify-center gap-2 border ${
            isClosing
              ? 'bg-zinc-800 border-zinc-700 text-zinc-500 cursor-not-allowed'
              : armed
              ? 'bg-rose-500 border-rose-400 text-white shadow-lg shadow-rose-500/30 animate-pulse'
              : 'bg-zinc-800/80 border-zinc-700/50 text-zinc-400 hover:bg-rose-500/10 hover:border-rose-500/30 hover:text-rose-400'
          }`}
        >
          {isClosing ? (
            <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Closing…</>
          ) : armed ? (
            <><CheckCircle className="w-3.5 h-3.5" /> Confirm Close — tap again</>
          ) : (
            <><X className="w-3.5 h-3.5" /> Close Position</>
          )}
        </button>
      </div>
    </div>
  );
});

// ── Main container ────────────────────────────────────────────────────────────

export default function PositionsCallingCard() {
  const [positions, setPositions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [closingId, setClosingId] = useState(null);
  const [errors, setErrors] = useState({});   // id → errorMsg
  const [exiting, setExiting] = useState({}); // id → true (card is animating out)

  const fetchPositions = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/positions`, { headers: authHeaders });
      if (!res.ok) return;
      const data = await res.json();
      const incoming = Array.isArray(data?.positions) ? data.positions : [];

      // Smart merge: only replace objects whose price/PnL actually changed.
      // This prevents React.memo from seeing false-positive prop changes.
      setPositions(prev => {
        const incomingMap = new Map(incoming.map(p => [p.id, p]));
        const prevIds = new Set(prev.map(p => p.id));

        // Update existing, preserve object identity if nothing changed
        const updated = prev
          .filter(p => incomingMap.has(p.id))
          .map(p => {
            const fresh = incomingMap.get(p.id);
            if (
              fresh.pnl_pct === p.pnl_pct &&
              fresh.current_price === p.current_price &&
              fresh.unrealized_pnl === p.unrealized_pnl
            ) return p; // same reference → memo skips re-render
            return fresh;
          });

        // Append newly opened positions (not seen before)
        const newOnes = incoming.filter(p => !prevIds.has(p.id));
        return newOnes.length > 0 ? [...updated, ...newOnes] : updated;
      });

      setLastRefresh(Date.now());
    } catch (_) {
      // silent — keep showing last known state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPositions();
    const id = setInterval(fetchPositions, POLL_MS);
    return () => clearInterval(id);
  }, [fetchPositions]);

  const closePosition = useCallback(async (position) => {
    const { id, symbol, account_id } = position;
    setClosingId(id);
    setErrors(prev => { const n = { ...prev }; delete n[id]; return n; });

    try {
      const res = await fetch(`${API_URL}/api/positions/close`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders },
        body: JSON.stringify({ symbol, account_id }),
      });
      const data = await res.json();

      if (data?.error) {
        // Error: keep card on screen, show error state
        setErrors(prev => ({ ...prev, [id]: data.error }));
        return;
      }

      // Success: animate card out then remove
      setExiting(prev => ({ ...prev, [id]: true }));
      setTimeout(() => {
        setPositions(prev => prev.filter(p => p.id !== id));
        setExiting(prev => { const n = { ...prev }; delete n[id]; return n; });
      }, 400);

      // Background sync to reconcile any other closed positions
      setTimeout(fetchPositions, 800);
    } catch (err) {
      setErrors(prev => ({ ...prev, [id]: `Close failed: ${err.message}` }));
    } finally {
      setClosingId(null);
    }
  }, [fetchPositions]);

  const dismissError = useCallback((id) => {
    setErrors(prev => { const n = { ...prev }; delete n[id]; return n; });
  }, []);

  // Summary stats (memoized — only recomputes when positions array changes)
  const summary = useMemo(() => {
    const totalPnl = positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
    const totalMargin = positions.reduce((sum, p) => sum + (p.margin ?? 0), 0);
    const warnings = positions.filter(p => (p.pnl_pct ?? 0) < -30).length;
    return { totalPnl, totalMargin, warnings };
  }, [positions]);

  // Sort: largest loss first (most urgent at top); exiting cards sink to bottom
  const sortedPositions = useMemo(() => (
    [...positions].sort((a, b) => {
      const aEx = exiting[a.id] ? 1 : 0;
      const bEx = exiting[b.id] ? 1 : 0;
      if (aEx !== bEx) return aEx - bEx;
      return (a.pnl_pct ?? 0) - (b.pnl_pct ?? 0);
    })
  ), [positions, exiting]);

  if (loading) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 p-6 text-center">
        <Activity className="w-6 h-6 text-zinc-600 mx-auto mb-2 animate-pulse" />
        <p className="text-zinc-500 text-sm">Loading positions…</p>
      </div>
    );
  }

  if (positions.length === 0) {
    return (
      <div className="rounded-2xl border border-zinc-800 bg-zinc-900/40 px-4 py-8 text-center">
        <div className="w-10 h-10 rounded-xl bg-zinc-800 flex items-center justify-center mx-auto mb-3">
          <Zap className="w-5 h-5 text-zinc-600" />
        </div>
        <p className="text-zinc-400 text-sm font-medium">No open positions</p>
        <p className="text-zinc-600 text-xs mt-1">Cards will appear here when trades are active</p>
      </div>
    );
  }

  const totalPnlIsProfit = summary.totalPnl >= 0;

  return (
    <div>
      {/* Section header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-emerald-400 animate-pulse" />
          <span className="text-sm font-semibold text-white">Open Positions</span>
          <span className="px-1.5 py-0.5 bg-emerald-500/20 text-emerald-400 text-xs rounded-full font-bold">
            {positions.length}
          </span>
          {summary.warnings > 0 && (
            <span className="px-1.5 py-0.5 bg-rose-500/20 text-rose-400 text-xs rounded-full font-bold flex items-center gap-1 animate-pulse">
              <AlertTriangle className="w-2.5 h-2.5" />
              {summary.warnings} critical
            </span>
          )}
        </div>
        {lastRefresh && (
          <span className="text-[10px] text-zinc-600">
            Updated {Math.floor((Date.now() - lastRefresh) / 1000)}s ago
          </span>
        )}
      </div>

      {/* Summary bar */}
      <div className="grid grid-cols-3 gap-2 mb-3 rounded-xl border border-zinc-800/60 bg-zinc-900/60 px-4 py-2.5">
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Positions</div>
          <div className="text-sm font-mono font-bold text-white">{positions.length}</div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Unrealized PnL</div>
          <div className={`text-sm font-mono font-bold ${totalPnlIsProfit ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fmtPnl(summary.totalPnl)} USDT
          </div>
        </div>
        <div>
          <div className="text-[10px] text-zinc-600 uppercase tracking-wide mb-0.5">Margin at Risk</div>
          <div className="text-sm font-mono font-bold text-amber-400">
            ${fmt(summary.totalMargin)} USDT
          </div>
        </div>
      </div>

      {/* Cards grid — max height with smooth scroll */}
      <div className="max-h-[720px] overflow-y-auto positions-scroll pr-0.5">
        <div className="grid sm:grid-cols-2 xl:grid-cols-3 gap-3">
          {sortedPositions.map(pos => (
            <div
              key={pos.id}
              className={`transition-all duration-400 ${
                exiting[pos.id] ? 'opacity-0 scale-90 -translate-y-2' : 'opacity-100 scale-100'
              }`}
            >
              <CallingCard
                position={pos}
                onClose={closePosition}
                isClosing={closingId === pos.id}
                closeError={errors[pos.id]}
                onDismissError={() => dismissError(pos.id)}
              />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
