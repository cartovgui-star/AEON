import React, { useState, useEffect } from 'react';
import { BarChart3, TrendingUp, TrendingDown, RefreshCw, Target, Zap, Award, AlertTriangle } from 'lucide-react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell
} from 'recharts';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const fmt = (n) => n === null || n === undefined ? '—' : Number(n).toLocaleString('en-US', { maximumFractionDigits: 2 });
const pct = (n) => n === null || n === undefined ? '—' : `${Number(n).toFixed(1)}%`;

function StatCard({ label, value, sub, color = 'text-white', icon: Icon }) {
  return (
    <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
      <div className="flex items-center gap-2 mb-1">
        {Icon && <Icon className="w-4 h-4 text-zinc-400" />}
        <span className="text-xs text-zinc-400">{label}</span>
      </div>
      <div className={`text-2xl font-bold ${color}`}>{value}</div>
      {sub && <div className="text-xs text-zinc-500 mt-1">{sub}</div>}
    </div>
  );
}

function WinRateBar({ label, trades, wins, win_rate, pnl }) {
  const isPos = pnl >= 0;
  const barW = Math.min(100, win_rate || 0);
  return (
    <div className="py-2 border-b border-zinc-800 last:border-0">
      <div className="flex justify-between text-sm mb-1">
        <span className="text-zinc-300 font-mono truncate max-w-[140px]">{label}</span>
        <span className={`font-semibold ${isPos ? 'text-green-400' : 'text-red-400'}`}>
          {isPos ? '+' : ''}${fmt(pnl)}
        </span>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex-1 bg-zinc-700 rounded-full h-1.5">
          <div className="h-1.5 rounded-full bg-blue-500" style={{ width: `${barW}%` }} />
        </div>
        <span className="text-xs text-zinc-400 w-20 text-right">{pct(win_rate)} ({wins}/{trades})</span>
      </div>
    </div>
  );
}

export default function PerformanceAnalytics() {
  const [report, setReport] = useState(null);
  const [equity, setEquity] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState('overview');
  const [equityDays, setEquityDays] = useState(60);

  const load = async () => {
    setLoading(true);
    try {
      const [rRes, eRes] = await Promise.all([
        fetch(`${API_URL}/api/analytics/report`),
        fetch(`${API_URL}/api/analytics/equity-curve?days=${equityDays}`)
      ]);
      const rData = await rRes.json();
      const eData = await eRes.json();
      setReport(rData);
      setEquity(Array.isArray(eData) ? eData : []);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [equityDays]);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'engines', label: 'By Engine' },
    { id: 'pairs', label: 'By Pair' },
    { id: 'equity', label: 'Equity Curve' },
  ];

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-zinc-400">
      <RefreshCw className="w-6 h-6 animate-spin mr-2" /> Loading analytics...
    </div>
  );

  if (error || report?.error) return (
    <div className="flex items-center justify-center h-64 text-zinc-500">
      <AlertTriangle className="w-5 h-5 mr-2" /> {error || report?.error}
    </div>
  );

  if (!report) return null;

  const winColor = (wr) => wr >= 60 ? 'text-green-400' : wr >= 45 ? 'text-yellow-400' : 'text-red-400';

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h2 className="text-lg font-bold text-white">Performance Analytics</h2>
        </div>
        <button onClick={load} className="text-zinc-400 hover:text-white">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-zinc-800 rounded-lg p-1">
        {tabs.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)}
            className={`flex-1 py-1.5 text-sm rounded-md transition-colors ${
              tab === t.id ? 'bg-blue-600 text-white' : 'text-zinc-400 hover:text-white'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Overview Tab */}
      {tab === 'overview' && (
        <div className="space-y-4">
          {/* Big Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Total Trades" value={report.total_trades} icon={BarChart3} />
            <StatCard label="Win Rate" value={pct(report.win_rate)}
              color={winColor(report.win_rate)} icon={Target} />
            <StatCard label="Total PnL"
              value={`${report.total_pnl >= 0 ? '+' : ''}$${fmt(report.total_pnl)}`}
              color={report.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'} icon={TrendingUp} />
            <StatCard label="Profit Factor" value={report.profit_factor}
              color={report.profit_factor >= 1.5 ? 'text-green-400' : report.profit_factor >= 1 ? 'text-yellow-400' : 'text-red-400'}
              icon={Zap} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <StatCard label="Avg Win" value={`+$${fmt(report.avg_win)}`} color="text-green-400" />
            <StatCard label="Avg Loss" value={`$${fmt(report.avg_loss)}`} color="text-red-400" />
            <StatCard label="Wins / Losses"
              value={`${report.wins} / ${report.losses}`} icon={Award} />
            <StatCard label="Max Consec. Losses" value={report.max_consecutive_losses}
              color={report.max_consecutive_losses >= 5 ? 'text-red-400' : 'text-zinc-300'} icon={AlertTriangle} />
          </div>

          {/* Direction + Close Reason */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-semibold text-zinc-300 mb-3">By Direction</h3>
              {Object.entries(report.by_direction || {}).map(([dir, d]) => (
                <div key={dir} className="flex justify-between items-center py-2 border-b border-zinc-700 last:border-0">
                  <span className={`font-semibold ${dir === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>{dir}</span>
                  <span className="text-zinc-400 text-sm">{d.trades} trades</span>
                  <span className={`text-sm font-semibold ${winColor(d.win_rate)}`}>{pct(d.win_rate)} WR</span>
                  <span className={`text-sm font-mono ${d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {d.pnl >= 0 ? '+' : ''}${fmt(d.pnl)}
                  </span>
                </div>
              ))}
            </div>

            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-semibold text-zinc-300 mb-3">By Close Reason</h3>
              {Object.entries(report.by_close_reason || {}).map(([reason, d]) => (
                <div key={reason} className="flex justify-between items-center py-2 border-b border-zinc-700 last:border-0">
                  <span className="text-zinc-300 text-sm capitalize">{reason.replace('_', ' ')}</span>
                  <span className="text-zinc-400 text-sm">{d.count}×</span>
                  <span className={`text-sm font-mono ${d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {d.pnl >= 0 ? '+' : ''}${fmt(d.pnl)}
                  </span>
                </div>
              ))}
            </div>
          </div>

          {/* Recent Trades */}
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Recent 10 Trades</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-zinc-500 text-xs border-b border-zinc-700">
                    <th className="text-left pb-2">Symbol</th>
                    <th className="text-left pb-2">Dir</th>
                    <th className="text-left pb-2">PnL</th>
                    <th className="text-left pb-2">Reason</th>
                    <th className="text-left pb-2">Engine</th>
                  </tr>
                </thead>
                <tbody>
                  {(report.recent_trades || []).map((t, i) => (
                    <tr key={i} className="border-b border-zinc-800 last:border-0">
                      <td className="py-1.5 font-mono text-zinc-300">{t.symbol?.replace('/USDT', '')}</td>
                      <td className={`py-1.5 font-semibold ${t.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`}>{t.direction}</td>
                      <td className={`py-1.5 font-mono font-semibold ${t.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {t.pnl >= 0 ? '+' : ''}${fmt(t.pnl)}
                      </td>
                      <td className="py-1.5 text-zinc-400 capitalize text-xs">{(t.close_reason || '').replace('_', ' ')}</td>
                      <td className="py-1.5 text-zinc-500 text-xs">{t.strategy}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* By Engine Tab */}
      {tab === 'engines' && (
        <div className="space-y-4">
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">Engine Performance</h3>
            {Object.entries(report.by_engine || {})
              .sort((a, b) => b[1].pnl - a[1].pnl)
              .map(([eng, d]) => (
                <WinRateBar key={eng} label={eng} trades={d.trades} wins={d.wins}
                  win_rate={d.win_rate} pnl={d.pnl} />
              ))}
          </div>

          {/* By Leverage */}
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">By Leverage Range</h3>
            {Object.entries(report.by_leverage || {}).map(([bucket, d]) => (
              <WinRateBar key={bucket} label={bucket} trades={d.trades} wins={d.wins}
                win_rate={d.win_rate} pnl={d.pnl} />
            ))}
          </div>

          {/* By Confidence */}
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">By Confidence Level</h3>
            {Object.entries(report.by_confidence || {}).map(([bucket, d]) => (
              <WinRateBar key={bucket} label={bucket} trades={d.trades} wins={d.wins}
                win_rate={d.win_rate} pnl={d.avg_pnl} />
            ))}
          </div>
        </div>
      )}

      {/* By Pair Tab */}
      {tab === 'pairs' && (
        <div className="space-y-4">
          <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
            <h3 className="text-sm font-semibold text-zinc-300 mb-3">All Pairs (sorted by PnL)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-zinc-500 text-xs border-b border-zinc-700">
                    <th className="text-left pb-2">Pair</th>
                    <th className="text-right pb-2">Trades</th>
                    <th className="text-right pb-2">Win Rate</th>
                    <th className="text-right pb-2">Total PnL</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(report.by_symbol || {}).map(([sym, d]) => (
                    <tr key={sym} className="border-b border-zinc-800 last:border-0">
                      <td className="py-1.5 font-mono text-zinc-300">{sym.replace('/USDT', '')}</td>
                      <td className="py-1.5 text-right text-zinc-400">{d.trades}</td>
                      <td className={`py-1.5 text-right font-semibold ${winColor(d.win_rate)}`}>{pct(d.win_rate)}</td>
                      <td className={`py-1.5 text-right font-mono font-semibold ${d.pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {d.pnl >= 0 ? '+' : ''}${fmt(d.pnl)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Equity Curve Tab */}
      {tab === 'equity' && (
        <div className="space-y-4">
          <div className="flex gap-2">
            {[30, 60, 90].map(d => (
              <button key={d} onClick={() => setEquityDays(d)}
                className={`px-3 py-1 rounded text-sm ${equityDays === d ? 'bg-blue-600 text-white' : 'bg-zinc-700 text-zinc-400 hover:text-white'}`}>
                {d}d
              </button>
            ))}
          </div>

          {equity.length === 0 ? (
            <div className="text-center text-zinc-500 py-12">No trade data for this period</div>
          ) : (
            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-semibold text-zinc-300 mb-4">
                Cumulative PnL — last {equityDays} days
              </h3>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={equity} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="pnlGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#3f3f46" />
                  <XAxis dataKey="date" hide />
                  <YAxis tick={{ fill: '#71717a', fontSize: 11 }} tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                    labelStyle={{ color: '#a1a1aa' }}
                    formatter={(v, name) => [`$${fmt(v)}`, name === 'cumulative_pnl' ? 'Cum. PnL' : 'Trade PnL']}
                  />
                  <Area type="monotone" dataKey="cumulative_pnl" stroke="#3b82f6"
                    fill="url(#pnlGrad)" strokeWidth={2} dot={false} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Per-trade PnL bars */}
          {equity.length > 0 && (
            <div className="bg-zinc-800 rounded-xl p-4 border border-zinc-700">
              <h3 className="text-sm font-semibold text-zinc-300 mb-4">Per-Trade PnL</h3>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={equity.slice(-50)} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <XAxis dataKey="symbol" hide />
                  <YAxis tick={{ fill: '#71717a', fontSize: 10 }} tickFormatter={v => `$${v}`} />
                  <Tooltip
                    contentStyle={{ background: '#18181b', border: '1px solid #3f3f46', borderRadius: 8 }}
                    formatter={(v) => [`$${fmt(v)}`, 'PnL']}
                  />
                  <Bar dataKey="pnl" radius={[2, 2, 0, 0]}>
                    {equity.slice(-50).map((e, i) => (
                      <Cell key={i} fill={e.pnl >= 0 ? '#22c55e' : '#ef4444'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
