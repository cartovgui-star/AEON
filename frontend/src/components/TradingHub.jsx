import React, { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Flame,
  Layers,
  Shield,
  Siren,
  Wallet,
  Waves,
} from 'lucide-react';
import PaperTrading from './PaperTrading';

const API_URL = process.env.REACT_APP_BACKEND_URL;

async function apiGet(path) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
    },
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function formatMoney(value, digits = 0) {
  return `$${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: digits, maximumFractionDigits: digits })}`;
}

function formatPct(value, digits = 1) {
  return `${(Number(value || 0) * 100).toFixed(digits)}%`;
}

function toneClasses(tone) {
  const map = {
    rose: 'border-rose-500/20 bg-rose-500/10 text-rose-100 ring-1 ring-rose-500/10',
    orange: 'border-orange-500/15 bg-orange-500/8 text-orange-100',
    violet: 'border-violet-500/15 bg-violet-500/8 text-violet-100',
    emerald: 'border-emerald-500/15 bg-emerald-500/8 text-emerald-100',
    cyan: 'border-cyan-500/15 bg-cyan-500/8 text-cyan-100',
    neutral: 'border-zinc-800/60 bg-zinc-950/70 text-white',
  };
  return map[tone] || map.neutral;
}

function StatCard({ label, value, subvalue, tone = 'neutral', icon: Icon }) {
  return (
    <div className={`rounded-xl border px-3 py-3 ${toneClasses(tone)}`}>
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.24em] text-zinc-400">
        {Icon ? <Icon className="w-3.5 h-3.5" /> : null}
        <span>{label}</span>
      </div>
      <div className="mt-2 text-lg font-semibold text-white">{value}</div>
      {subvalue ? <div className="mt-1 text-xs text-zinc-500">{subvalue}</div> : null}
    </div>
  );
}

export default function TradingHub() {
  const [portfolioSummary, setPortfolioSummary] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [governance, setGovernance] = useState(null);
  const [fwReport, setFwReport] = useState(null);
  const [liveStats, setLiveStats] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;

    const load = async () => {
      try {
        const results = await Promise.allSettled([
          apiGet('/api/portfolio/summary'),
          apiGet('/api/system/health'),
          apiGet('/api/engine/governance'),
          apiGet('/api/engine/fw_v2/report'),
          apiGet('/api/trading/v2/stats'),
        ]);

        if (!alive) return;

        const [portfolioRes, systemRes, govRes, fwRes, liveStatsRes] = results;
        if (portfolioRes.status === 'fulfilled') setPortfolioSummary(portfolioRes.value);
        if (systemRes.status === 'fulfilled') setSystemHealth(systemRes.value);
        if (govRes.status === 'fulfilled') setGovernance(govRes.value);
        if (fwRes.status === 'fulfilled') setFwReport(fwRes.value);
        if (liveStatsRes.status === 'fulfilled') setLiveStats(liveStatsRes.value);

        const failures = results.filter((r) => r.status === 'rejected').length;
        setError(failures ? `${failures} trusted source(s) unavailable` : null);
      } catch (err) {
        if (alive) setError(err.message || 'Failed to load trading hub');
      }
    };

    load();
    const iv = setInterval(load, 15000);
    return () => {
      alive = false;
      clearInterval(iv);
    };
  }, []);

  const accounts = portfolioSummary?.accounts_list || [];
  const hottestAccount = useMemo(() => {
    return [...accounts].sort((a, b) => Number(b.portfolio_heat || 0) - Number(a.portfolio_heat || 0))[0];
  }, [accounts]);
  const restrictedEngines = (governance?.states || []).filter((state) =>
    ['restricted', 'sandbox', 'disabled'].includes(String(state.current_recommendation || '').toLowerCase())
  );
  const degradedServices = Object.values(systemHealth?.services || {}).filter((svc) => svc.status && svc.status !== 'healthy');
  const totalBalance = portfolioSummary?.total_balance || 0;
  const totalOpenPositions = portfolioSummary?.total_open_positions || 0;
  const totalHeat = portfolioSummary?.aggregate_portfolio_heat || 0;

  const warnings = [
    degradedServices.length ? `${degradedServices.length} degraded service(s)` : null,
    hottestAccount ? `${hottestAccount.account_id} at ${formatPct(hottestAccount.portfolio_heat || 0)}` : null,
    restrictedEngines.length ? `${restrictedEngines.length} engine(s) restricted/sandboxed/disabled` : null,
    fwReport?.malformed_rejects_30d ? `${fwReport.malformed_rejects_30d} malformed rejects over 30d` : null,
  ].filter(Boolean);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Wallet className="w-5 h-5 text-orange-400" />
            Trading Control Room
          </h2>
          <p className="text-zinc-500 text-sm mt-0.5">Read positions and accounts through pressure, governance, and system trust, not raw motion alone.</p>
        </div>
        {error ? <div className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-full px-3 py-1.5">{error}</div> : null}
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="System trust" value={systemHealth?.overall || 'unknown'} subvalue={`${degradedServices.length} degraded services`} tone="cyan" icon={Shield} />
        <StatCard label="Portfolio heat" value={formatPct(totalHeat)} subvalue={`${totalOpenPositions} open positions`} tone="orange" icon={Flame} />
        <StatCard label="Book balance" value={formatMoney(totalBalance, 0)} subvalue={hottestAccount ? `Hottest: ${hottestAccount.account_id}` : 'No pressure leader'} tone="emerald" icon={Wallet} />
        <StatCard label="Governance pressure" value={restrictedEngines.length} subvalue="restricted, sandboxed, or disabled engines" tone="rose" icon={Siren} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-2xl border border-zinc-800/60 bg-zinc-950/70 p-4">
          <div className="flex items-center gap-2 text-white font-semibold">
            <Activity className="w-4 h-4 text-orange-300" />
            Trading doctrine
          </div>
          <div className="mt-4 space-y-3 text-sm text-zinc-300">
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">Open positions are not enough. The real question is whether the book is crowded, stressed, or misaligned.</div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">Portfolio heat, account concentration, malformed reject pressure, and system trust should frame every trade view.</div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">If a raw trading panel feels bullish while the operator stack feels stressed, trust the operator stack first.</div>
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800/60 bg-zinc-950/70 p-4">
          <div className="flex items-center gap-2 text-white font-semibold">
            <Layers className="w-4 h-4 text-cyan-300" />
            Operator pressure
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">
              <div className="text-zinc-500 text-xs uppercase tracking-[0.2em]">Live status</div>
              <div className="mt-1 text-white font-medium">{liveStats?.active ? 'ACTIVE' : 'PAUSED'}</div>
            </div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">
              <div className="text-zinc-500 text-xs uppercase tracking-[0.2em]">FW_V2</div>
              <div className="mt-1 text-white font-medium">{fwReport?.status || 'unknown'}</div>
            </div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">
              <div className="text-zinc-500 text-xs uppercase tracking-[0.2em]">Malformed rejects</div>
              <div className="mt-1 text-white font-medium">{fwReport?.malformed_rejects_30d || 0}</div>
            </div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">
              <div className="text-zinc-500 text-xs uppercase tracking-[0.2em]">Open accounts</div>
              <div className="mt-1 text-white font-medium">{accounts.length}</div>
            </div>
          </div>

          <div className="mt-4 space-y-2">
            {warnings.length ? warnings.map((warning) => (
              <div key={warning} className="rounded-xl border border-zinc-800/60 bg-black/30 px-3 py-2 text-sm text-zinc-100">{warning}</div>
            )) : (
              <div className="rounded-xl border border-emerald-500/10 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">No material pressure showing right now.</div>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <div className="rounded-2xl border border-zinc-800/60 bg-zinc-950/70 p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2 text-white font-semibold">
              <Waves className="w-4 h-4 text-orange-300" />
              Trusted account pressure
            </div>
            <button className="text-orange-400 text-xs hover:text-orange-300 flex items-center gap-1">
              Review trading <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          <div className="space-y-3">
            {accounts.map((acc) => (
              <div key={acc.account_id} className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-white">{acc.account_id}</div>
                    <div className="mt-1 text-xs text-zinc-500">{acc.open_count || 0} open position(s) · {(acc.symbols || []).join(', ') || 'No open symbols'}</div>
                  </div>
                  <div className="text-right">
                    <div className="text-sm font-semibold text-cyan-300">{formatMoney(acc.balance || 0, 0)}</div>
                    <div className="mt-1 text-xs text-zinc-500">Heat {formatPct(acc.portfolio_heat || 0)}</div>
                  </div>
                </div>
              </div>
            ))}
            {!accounts.length && <div className="text-sm text-zinc-500">No account pressure data available.</div>}
          </div>
        </div>

        <div className="rounded-2xl border border-zinc-800/60 bg-zinc-950/70 p-4">
          <div className="flex items-center gap-2 text-white font-semibold mb-3">
            <AlertTriangle className="w-4 h-4 text-rose-300" />
            Execution guardrails
          </div>
          <div className="space-y-3 text-sm text-zinc-300">
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">System trust gates execution confidence.</div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">Governance pressure should influence how aggressively you interpret position opportunity.</div>
            <div className="rounded-xl border border-zinc-800/60 bg-black/30 p-3">Malformed reject counts are not trivia, they are proof the gate is actively filtering bad signal flow.</div>
          </div>
        </div>
      </div>

      <PaperTrading />
    </div>
  );
}
