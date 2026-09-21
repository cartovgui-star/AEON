import React, { useState, useEffect, useCallback } from 'react';
import {
  TrendingUp, TrendingDown, Filter, RefreshCw, ChevronDown, ChevronUp,
  Calendar, X
} from 'lucide-react';
import { fetchClosedTrades, fetchOpenTrades } from '../services/api';
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

const fmt4 = (v) => v != null ? Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 }) : '—';
const fmtPct = (v) => {
  if (v == null) return '—';
  const n = Number(v);
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
};
const fmtDate = (d) => {
  if (!d) return '—';
  const dt = new Date(d);
  return dt.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
};

function TradeCard({ trade, open = false }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = trade.direction === 'LONG';
  const pnl = open ? (trade.live_pnl || 0) : (trade.pnl_pct || 0);
  const isWin = pnl >= 0;
  const strategy = trade.strategy || trade.engine || '';
  const engineLabel = ENGINE_SHORT[strategy.toLowerCase()] || strategy.replace(/_/g, ' ');
  const borderColor = open ? 'border-l-amber-500' : isWin ? 'border-l-emerald-500' : 'border-l-rose-500';

  return (
    <div
      className={`bg-zinc-900/70 border border-zinc-800/50 border-l-2 ${borderColor} rounded-xl p-3 cursor-pointer transition-all hover:bg-zinc-900`}
      onClick={() => setExpanded(v => !v)}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 min-w-0">
          <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded flex-shrink-0 font-mono ${isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'}`}>
            {isLong ? '▲' : '▼'} {trade.direction}
          </span>
          <span className="text-sm font-semibold text-white truncate">{trade.symbol?.replace('/USDT', '')}/USDT</span>
          {open && <span className="text-[10px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded flex-shrink-0">OPEN</span>}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <span className={`font-mono text-sm font-bold ${isWin ? 'text-emerald-400' : 'text-rose-400'}`}>
            {fmtPct(pnl)}
          </span>
        </div>
      </div>

      <div className="flex items-center gap-3 mt-1.5 flex-wrap">
        <span className="text-[10px] text-zinc-500 font-mono">Entry {fmt4(trade.entry_price)}</span>
        {!open && trade.exit_price && (
          <span className="text-[10px] text-zinc-500 font-mono">Exit {fmt4(trade.exit_price)}</span>
        )}
        {open && trade.current_price && (
          <span className="text-[10px] text-zinc-500 font-mono">Now {fmt4(trade.current_price)}</span>
        )}
        <span className="text-[10px] text-zinc-600 bg-zinc-800/60 px-1.5 py-0.5 rounded">{engineLabel || '—'}</span>
        <span className="text-[10px] text-zinc-600">{trade.leverage || 1}x</span>
        <span className="text-[10px] text-zinc-600 ml-auto">{fmtDate(trade.closed_at || trade.entry_time || trade.timestamp)}</span>
      </div>

      {trade.account_id && (
        <div className="mt-1">
          <span className="text-[10px] text-cyan-500/80">{trade.account_id}</span>
        </div>
      )}

      {expanded && (
        <div className="mt-2 pt-2 border-t border-zinc-800/50 grid grid-cols-2 gap-x-4 gap-y-1">
          {trade.stop_loss && <div className="text-[10px] text-zinc-500">SL <span className="text-white font-mono">{fmt4(trade.stop_loss)}</span></div>}
          {trade.take_profit && <div className="text-[10px] text-zinc-500">TP <span className="text-white font-mono">{fmt4(trade.take_profit)}</span></div>}
          {trade.margin && <div className="text-[10px] text-zinc-500">Margin <span className="text-white font-mono">${Number(trade.margin).toFixed(0)}</span></div>}
          {trade.confidence && <div className="text-[10px] text-zinc-500">Conf <span className="text-cyan-400 font-mono">{trade.confidence}%</span></div>}
          {trade.close_reason && <div className="text-[10px] text-zinc-500 col-span-2">Reason <span className="text-amber-400">{trade.close_reason}</span></div>}
        </div>
      )}
    </div>
  );
}

const PAGE_SIZE = 50;

export default function TradesPage() {
  const [allTrades, setAllTrades] = useState({ open: [], closed: [] });
  const [loading, setLoading] = useState(true);
  const [filterEngine, setFilterEngine] = useState('ALL');
  const [filterDirection, setFilterDirection] = useState('ALL');
  const [filterResult, setFilterResult] = useState('ALL');
  const [filterAccount, setFilterAccount] = useState('ALL');
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [page, setPage] = useState(1);
  const [tab, setTab] = useState('closed'); // 'open' | 'closed'

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [openRes, closedRes] = await Promise.allSettled([
        fetchOpenTrades(),
        fetchClosedTrades(),
      ]);
      const open = openRes.status === 'fulfilled' ? (openRes.value?.open_trades || []) : [];
      const closed = closedRes.status === 'fulfilled' ? (closedRes.value?.closed_trades || []) : [];
      setAllTrades({ open, closed });
    } catch (e) {
      console.error('TradesPage load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const source = tab === 'open' ? allTrades.open : allTrades.closed;

  // Collect unique engines and accounts for filters
  const allEngines = [...new Set(source.map(t => (t.strategy || t.engine || '')).filter(Boolean))];
  const allAccounts = [...new Set(source.map(t => t.account_id).filter(Boolean))];

  const filtered = source.filter(t => {
    const eng = (t.strategy || t.engine || '').toLowerCase();
    const pnl = tab === 'open' ? (t.live_pnl || 0) : (t.pnl_pct || 0);
    if (filterEngine !== 'ALL' && eng !== filterEngine.toLowerCase()) return false;
    if (filterDirection !== 'ALL' && t.direction !== filterDirection) return false;
    if (filterResult !== 'ALL') {
      if (filterResult === 'WIN' && pnl <= 0) return false;
      if (filterResult === 'LOSS' && pnl >= 0) return false;
    }
    if (filterAccount !== 'ALL' && t.account_id !== filterAccount) return false;
    return true;
  });

  const wins = filtered.filter(t => (tab === 'open' ? (t.live_pnl || 0) : (t.pnl_pct || 0)) > 0);
  const totalPnlPct = filtered.reduce((s, t) => s + (tab === 'open' ? (t.live_pnl || 0) : (t.pnl_pct || 0)), 0);
  const winRate = filtered.length ? ((wins.length / filtered.length) * 100).toFixed(1) : 0;
  const bestTrade = filtered.reduce((best, t) => {
    const p = tab === 'open' ? (t.live_pnl || 0) : (t.pnl_pct || 0);
    return p > best ? p : best;
  }, -Infinity);
  const worstTrade = filtered.reduce((worst, t) => {
    const p = tab === 'open' ? (t.live_pnl || 0) : (t.pnl_pct || 0);
    return p < worst ? p : worst;
  }, Infinity);

  const paged = filtered.slice(0, page * PAGE_SIZE);
  const hasMore = paged.length < filtered.length;

  const clearFilters = () => {
    setFilterEngine('ALL');
    setFilterDirection('ALL');
    setFilterResult('ALL');
    setFilterAccount('ALL');
  };
  const hasFilters = filterEngine !== 'ALL' || filterDirection !== 'ALL' || filterResult !== 'ALL' || filterAccount !== 'ALL';

  if (loading) return <AeonLoader message="Loading trades..." />;

  return (
    <div className="space-y-3 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white">Trade History</h2>
        <button onClick={load} className="p-1.5 text-zinc-500 hover:text-zinc-300">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Tab toggle */}
      <div className="flex bg-zinc-900/60 border border-zinc-800/50 rounded-xl p-1 gap-1">
        {[['closed', `Closed (${allTrades.closed.length})`], ['open', `Open (${allTrades.open.length})`]].map(([id, label]) => (
          <button
            key={id}
            onClick={() => { setTab(id); setPage(1); }}
            className={`flex-1 py-2 rounded-lg text-xs font-semibold transition-all ${
              tab === id ? 'bg-zinc-800 text-white' : 'text-zinc-500 hover:text-zinc-300'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Filter bar */}
      <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl overflow-hidden">
        <button
          className="w-full flex items-center justify-between px-4 py-2.5"
          onClick={() => setFiltersOpen(v => !v)}
        >
          <div className="flex items-center gap-2">
            <Filter className="w-3.5 h-3.5 text-zinc-500" />
            <span className="text-xs text-zinc-400 font-semibold">Filters</span>
            {hasFilters && <span className="w-1.5 h-1.5 rounded-full bg-cyan-400" />}
          </div>
          <div className="flex items-center gap-2">
            {hasFilters && (
              <button onClick={(e) => { e.stopPropagation(); clearFilters(); }} className="text-[10px] text-rose-400 hover:text-rose-300 flex items-center gap-0.5">
                <X className="w-3 h-3" /> Clear
              </button>
            )}
            {filtersOpen ? <ChevronUp className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronDown className="w-3.5 h-3.5 text-zinc-500" />}
          </div>
        </button>

        {filtersOpen && (
          <div className="px-4 pb-3 space-y-3 border-t border-zinc-800/50">
            {/* Engine filter */}
            <div>
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Engine</div>
              <div className="flex flex-wrap gap-1.5">
                {['ALL', ...allEngines].map(eng => (
                  <button
                    key={eng}
                    onClick={() => { setFilterEngine(eng); setPage(1); }}
                    className={`text-[10px] px-2 py-1 rounded-lg font-semibold transition-all ${
                      filterEngine === eng ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' : 'bg-zinc-800/60 text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    {eng === 'ALL' ? 'ALL' : (ENGINE_SHORT[eng.toLowerCase()] || eng.replace(/_/g, ' '))}
                  </button>
                ))}
              </div>
            </div>
            {/* Direction */}
            <div>
              <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Direction</div>
              <div className="flex gap-1.5">
                {['ALL', 'LONG', 'SHORT'].map(d => (
                  <button
                    key={d}
                    onClick={() => { setFilterDirection(d); setPage(1); }}
                    className={`text-[10px] px-3 py-1 rounded-lg font-semibold transition-all ${
                      filterDirection === d
                        ? d === 'LONG' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                          : d === 'SHORT' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                          : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                        : 'bg-zinc-800/60 text-zinc-500 hover:text-zinc-300'
                    }`}
                  >
                    {d}
                  </button>
                ))}
              </div>
            </div>
            {/* Result */}
            {tab === 'closed' && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Result</div>
                <div className="flex gap-1.5">
                  {['ALL', 'WIN', 'LOSS'].map(r => (
                    <button
                      key={r}
                      onClick={() => { setFilterResult(r); setPage(1); }}
                      className={`text-[10px] px-3 py-1 rounded-lg font-semibold transition-all ${
                        filterResult === r
                          ? r === 'WIN' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                            : r === 'LOSS' ? 'bg-rose-500/20 text-rose-400 border border-rose-500/40'
                            : 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40'
                          : 'bg-zinc-800/60 text-zinc-500 hover:text-zinc-300'
                      }`}
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {/* Account */}
            {allAccounts.length > 1 && (
              <div>
                <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Account</div>
                <div className="flex flex-wrap gap-1.5">
                  {['ALL', ...allAccounts].map(a => (
                    <button
                      key={a}
                      onClick={() => { setFilterAccount(a); setPage(1); }}
                      className={`text-[10px] px-2 py-1 rounded-lg font-semibold transition-all ${
                        filterAccount === a ? 'bg-cyan-500/20 text-cyan-400 border border-cyan-500/40' : 'bg-zinc-800/60 text-zinc-500 hover:text-zinc-300'
                      }`}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary strip */}
      {filtered.length > 0 && (
        <div className="bg-zinc-900/40 border border-zinc-800/40 rounded-xl px-4 py-2.5 flex items-center gap-3 flex-wrap text-[11px] overflow-x-auto no-scrollbar">
          <span className="text-zinc-500 whitespace-nowrap"><span className="text-white font-mono font-bold">{filtered.length}</span> trades</span>
          <span className="text-zinc-700">|</span>
          <span className="text-zinc-500 whitespace-nowrap"><span className={`font-mono font-bold ${parseFloat(winRate) >= 50 ? 'text-emerald-400' : 'text-rose-400'}`}>{winRate}%</span> WR</span>
          <span className="text-zinc-700">|</span>
          <span className="text-zinc-500 whitespace-nowrap">
            Total <span className={`font-mono font-bold ${totalPnlPct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>{totalPnlPct >= 0 ? '+' : ''}{totalPnlPct.toFixed(2)}%</span>
          </span>
          {bestTrade > -Infinity && (
            <>
              <span className="text-zinc-700">|</span>
              <span className="text-zinc-500 whitespace-nowrap">Best <span className="font-mono font-bold text-emerald-400">+{bestTrade.toFixed(2)}%</span></span>
            </>
          )}
          {worstTrade < Infinity && (
            <>
              <span className="text-zinc-700">|</span>
              <span className="text-zinc-500 whitespace-nowrap">Worst <span className="font-mono font-bold text-rose-400">{worstTrade.toFixed(2)}%</span></span>
            </>
          )}
        </div>
      )}

      {/* Trade list */}
      {filtered.length === 0 ? (
        <div className="text-center py-12 text-zinc-600 text-sm">No trades match the current filters</div>
      ) : (
        <div className="space-y-2">
          {paged.map((trade, i) => (
            <TradeCard key={trade.id || trade._id || `${trade.symbol}-${i}`} trade={trade} open={tab === 'open'} />
          ))}
          {hasMore && (
            <button
              onClick={() => setPage(p => p + 1)}
              className="w-full py-3 text-xs text-zinc-500 hover:text-zinc-300 bg-zinc-900/40 border border-zinc-800/40 rounded-xl transition-all"
            >
              Load more ({filtered.length - paged.length} remaining)
            </button>
          )}
        </div>
      )}
    </div>
  );
}
