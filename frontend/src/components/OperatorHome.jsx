import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Shield, Layers, AlertTriangle, Radar, Wallet } from 'lucide-react';
import { api } from './api';

const card = 'bg-zinc-900/70 border border-zinc-800/60 rounded-xl p-4';
const muted = 'text-zinc-500';

function StatCard({ icon: Icon, label, value, subvalue }) {
  return (
    <div className={card}>
      <div className="flex items-center gap-2 text-zinc-400 mb-2">
        <Icon className="w-4 h-4" />
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-white">{value}</div>
      {subvalue ? <div className="text-xs text-zinc-500 mt-1">{subvalue}</div> : null}
    </div>
  );
}

export default function OperatorHome() {
  const [systemHealth, setSystemHealth] = useState(null);
  const [portfolio, setPortfolio] = useState(null);
  const [governance, setGovernance] = useState(null);
  const [engineHealth, setEngineHealth] = useState(null);
  const [fw, setFw] = useState(null);
  const [quantum, setQuantum] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const results = await Promise.allSettled([
          api.get('/api/system/health'),
          api.get('/api/portfolio/summary'),
          api.get('/api/engine/governance'),
          api.get('/api/engine/health?days=7'),
          api.get('/api/engine/fw_v2/report'),
          api.get('/api/quantum/state'),
        ]);
        if (!alive) return;
        const [sys, port, gov, eh, fwv2, q] = results;
        if (sys.status === 'fulfilled') setSystemHealth(sys.value);
        if (port.status === 'fulfilled') setPortfolio(port.value);
        if (gov.status === 'fulfilled') setGovernance(gov.value);
        if (eh.status === 'fulfilled') setEngineHealth(eh.value);
        if (fwv2.status === 'fulfilled') setFw(fwv2.value);
        if (q.status === 'fulfilled') setQuantum(q.value);
        const failures = results.filter(r => r.status === 'rejected');
        setError(failures.length ? `${failures.length} operator data source(s) unavailable` : null);
      } catch (e) {
        if (alive) setError(e.message || 'Failed to load operator home');
      }
    };
    load();
    const interval = setInterval(load, 30000);
    return () => {
      alive = false;
      clearInterval(interval);
    };
  }, []);

  const govStates = governance?.states || [];
  const engineRows = useMemo(() => {
    const healthMap = engineHealth?.engines || {};
    return govStates.map((state) => ({
      engine: state.engine,
      recommendation: state.current_recommendation,
      tier: state.current_tier,
      score: state.current_score,
      nClean: state.n_clean_last_week,
      health: healthMap[state.engine] || null,
    }));
  }, [govStates, engineHealth]);

  const degradedServices = Object.values(systemHealth?.services || {}).filter(s => s.status && s.status !== 'healthy');
  const regime = quantum?.market_regime || quantum?.regime || quantum?.summary?.regime || 'unknown';

  return (
    <div className="space-y-4 p-4 lg:p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold text-white">Operator Home</h1>
          <p className="text-sm text-zinc-500">Trust-first AEON cockpit built on governance, portfolio, and system truth.</p>
        </div>
        {error ? <div className="text-xs text-amber-400">{error}</div> : null}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard icon={Activity} label="System" value={systemHealth?.overall || 'loading'} subvalue={`${degradedServices.length} non-healthy services`} />
        <StatCard icon={Wallet} label="Portfolio Heat" value={portfolio ? `${((portfolio.aggregate_portfolio_heat || 0) * 100).toFixed(1)}%` : 'loading'} subvalue={`${portfolio?.total_open_positions ?? '…'} open positions`} />
        <StatCard icon={Radar} label="Regime" value={String(regime).replace(/_/g, ' ')} subvalue={quantum?.timestamp ? `updated ${new Date(quantum.timestamp).toLocaleTimeString()}` : undefined} />
        <StatCard icon={Shield} label="FW V2" value={fw?.status || 'loading'} subvalue={fw ? `Tier ${fw.health_7d?.tier || 'n/a'} · cohorts ${fw.health_7d?.n_cohorts ?? 0}` : undefined} />
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        <div className={`${card} xl:col-span-1`}>
          <div className="flex items-center gap-2 mb-3 text-zinc-300"><Wallet className="w-4 h-4" /><span className="font-medium">Portfolio Summary</span></div>
          <div className="space-y-3">
            {(portfolio?.accounts_list || []).map((acc) => (
              <div key={acc.account_id} className="border border-zinc-800/60 rounded-lg p-3 bg-zinc-950/50">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-sm font-medium text-white">{acc.account_id}</div>
                  <div className="text-sm text-cyan-400">${Number(acc.balance || 0).toLocaleString()}</div>
                </div>
                <div className={`text-xs ${muted}`}>{acc.open_count} open, heat {(Number(acc.portfolio_heat || 0) * 100).toFixed(1)}%</div>
                <div className="text-xs text-zinc-400 mt-1">{(acc.symbols || []).join(', ') || 'No open symbols'}</div>
              </div>
            ))}
          </div>
        </div>

        <div className={`${card} xl:col-span-2`}>
          <div className="flex items-center gap-2 mb-3 text-zinc-300"><Layers className="w-4 h-4" /><span className="font-medium">Engine Governance</span></div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-zinc-500 border-b border-zinc-800">
                <tr>
                  <th className="text-left py-2">Engine</th>
                  <th className="text-left py-2">Tier</th>
                  <th className="text-left py-2">Recommendation</th>
                  <th className="text-left py-2">Score</th>
                  <th className="text-left py-2">Cohorts</th>
                </tr>
              </thead>
              <tbody>
                {engineRows.map((row) => (
                  <tr key={row.engine} className="border-b border-zinc-900">
                    <td className="py-2 text-white">{row.engine}</td>
                    <td className="py-2 text-zinc-300">{row.tier || row.health?.tier || 'n/a'}</td>
                    <td className="py-2 text-zinc-300">{row.recommendation || 'monitor'}</td>
                    <td className="py-2 text-zinc-300">{row.score ?? row.health?.score ?? 'n/a'}</td>
                    <td className="py-2 text-zinc-300">{row.health?.n_cohorts ?? 'n/a'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        <div className={card}>
          <div className="flex items-center gap-2 mb-3 text-zinc-300"><Shield className="w-4 h-4" /><span className="font-medium">FREE_WILL_V2</span></div>
          {fw ? (
            <div className="grid grid-cols-2 gap-3 text-sm">
              <div><div className={muted}>Status</div><div className="text-white">{fw.status}</div></div>
              <div><div className={muted}>Tier</div><div className="text-white">{fw.health_7d?.tier}</div></div>
              <div><div className={muted}>Score</div><div className="text-white">{fw.health_7d?.score}</div></div>
              <div><div className={muted}>Cohorts</div><div className="text-white">{fw.health_7d?.n_cohorts}</div></div>
              <div><div className={muted}>Malformed trades</div><div className="text-white">{fw.health_7d?.malformed_trades}</div></div>
              <div><div className={muted}>Malformed rejects 30d</div><div className="text-white">{fw.malformed_rejects_30d}</div></div>
            </div>
          ) : <div className={muted}>Loading FW_V2 report…</div>}
        </div>

        <div className={card}>
          <div className="flex items-center gap-2 mb-3 text-zinc-300"><AlertTriangle className="w-4 h-4" /><span className="font-medium">Material Warnings</span></div>
          <div className="space-y-2 text-sm">
            {degradedServices.slice(0, 8).map((svc) => (
              <div key={svc.name} className="border border-zinc-800/60 rounded-lg p-3 bg-zinc-950/50">
                <div className="text-white">{svc.name}</div>
                <div className="text-zinc-400 text-xs">status: {svc.status}</div>
              </div>
            ))}
            {!degradedServices.length && <div className={muted}>No material warnings from system health right now.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
