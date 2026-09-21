import React, { useState, useEffect, useCallback } from 'react';
import {
  Settings, Shield, AlertTriangle, RefreshCw, CheckCircle,
  RotateCcw, Power, Activity, Database, Cpu
} from 'lucide-react';
import { fetchSystemHealth, killSwitch, fetchAccounts, fetchSettings } from '../services/api';
import AeonLoader from './AeonLoader';

const API_URL = process.env.REACT_APP_BACKEND_URL || '';

const fmtBalance = (v) =>
  v != null ? `$${Number(v).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—';

function Section({ title, icon: Icon, children }) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800/50 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-zinc-800/50">
        {Icon && <Icon className="w-4 h-4 text-cyan-400" />}
        <h3 className="text-sm font-semibold text-white">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

export default function SettingsPage() {
  const [health, setHealth] = useState(null);
  const [accounts, setAccounts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);

  // Kill switch state
  const [killConfirm, setKillConfirm] = useState(false);
  const [killing, setKilling] = useState(false);
  const [killResult, setKillResult] = useState(null);

  // Reset account state
  const [resetConfirm, setResetConfirm] = useState(null);
  const [resetting, setResetting] = useState(null);
  const [resetResult, setResetResult] = useState(null);

  const load = useCallback(async () => {
    try {
      const [healthRes, accsRes, setRes] = await Promise.allSettled([
        fetchSystemHealth(),
        fetchAccounts(),
        fetchSettings().catch(() => null),
      ]);
      if (healthRes.status === 'fulfilled') setHealth(healthRes.value);
      if (accsRes.status === 'fulfilled') setAccounts(accsRes.value?.accounts || []);
      if (setRes.status === 'fulfilled' && setRes.value) setSettings(setRes.value);
    } catch (e) {
      console.error('SettingsPage load error:', e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleKillSwitch = async () => {
    if (!killConfirm) { setKillConfirm(true); return; }
    setKilling(true);
    try {
      const result = await killSwitch();
      setKillResult({ ok: true, msg: `Kill switch activated. ${result?.engines_stopped || 0} engines stopped, ${result?.positions_closed || 0} positions closed.` });
    } catch (e) {
      setKillResult({ ok: false, msg: `Kill switch failed: ${e.message}` });
    } finally {
      setKilling(false);
      setKillConfirm(false);
      setTimeout(() => setKillResult(null), 6000);
    }
  };

  const handleResetAccount = async (accountId) => {
    if (resetConfirm !== accountId) { setResetConfirm(accountId); return; }
    setResetting(accountId);
    try {
      // Correct backend path: POST /api/paper/reset/{account_id}
      const res = await fetch(`${API_URL}/api/paper/reset/${accountId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResetResult({ ok: true, msg: `${accountId} reset successfully` });
      await load();
    } catch (e) {
      setResetResult({ ok: false, msg: `Reset failed: ${e.message}` });
    } finally {
      setResetting(null);
      setResetConfirm(null);
      setTimeout(() => setResetResult(null), 4000);
    }
  };

  const getStatusColor = (status) => {
    if (!status || status === 'unknown') return 'text-zinc-500';
    if (status === 'healthy') return 'text-emerald-400';
    if (status === 'degraded') return 'text-amber-400';
    return 'text-rose-400';
  };
  const getStatusDot = (status) => {
    if (status === 'healthy') return 'bg-emerald-500';
    if (status === 'degraded') return 'bg-amber-500';
    if (status === 'unknown') return 'bg-zinc-600';
    return 'bg-rose-500';
  };

  if (loading) return <AeonLoader message="Loading settings..." />;

  const overallStatus = health?.overall || 'unknown';
  const services = health?.services || {};

  return (
    <div className="space-y-4 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-cyan-400" />
          Settings
        </h2>
        <button onClick={load} className="p-1.5 text-zinc-500 hover:text-zinc-300">
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* System Status */}
      <Section title="System Status" icon={Activity}>
        <div className="space-y-2">
          <div className="flex items-center justify-between py-1.5">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${getStatusDot(overallStatus)}`} />
              <span className="text-sm text-white">Overall Status</span>
            </div>
            <span className={`text-xs font-bold uppercase ${getStatusColor(overallStatus)}`}>{overallStatus}</span>
          </div>
          {Object.entries(services).map(([svcName, svc]) => (
            <div key={svcName} className="flex items-center justify-between py-1.5 border-t border-zinc-800/30">
              <div className="flex items-center gap-2">
                <div className={`w-1.5 h-1.5 rounded-full ${getStatusDot(svc.status)}`} />
                <span className="text-xs text-zinc-400">{svcName.replace(/_/g, ' ')}</span>
              </div>
              <div className="flex items-center gap-2">
                {svc.error_count > 0 && (
                  <span className="text-[10px] text-rose-400 font-mono">{svc.error_count} err</span>
                )}
                <span className={`text-[10px] font-bold uppercase ${getStatusColor(svc.status)}`}>{svc.status}</span>
              </div>
            </div>
          ))}
        </div>
      </Section>

      {/* Paper Accounts */}
      <Section title="Paper Accounts" icon={Database}>
        {resetResult && (
          <div className={`mb-3 px-3 py-2 rounded-lg text-xs font-semibold ${
            resetResult.ok ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
          }`}>
            {resetResult.msg}
          </div>
        )}
        <div className="space-y-3">
          {accounts.map(acc => {
            const pct = acc.starting_balance
              ? ((acc.balance - acc.starting_balance) / acc.starting_balance) * 100
              : 0;
            const isConfirming = resetConfirm === acc.account_id;
            const isResetting = resetting === acc.account_id;
            return (
              <div key={acc.account_id} className="border border-zinc-800/50 rounded-xl p-3">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <span className="text-sm font-semibold text-white">{acc.account_id}</span>
                    <span className="text-xs text-zinc-500 ml-2">{acc.name}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {isConfirming && !isResetting && (
                      <button
                        onClick={() => setResetConfirm(null)}
                        className="text-[10px] text-zinc-500 hover:text-zinc-300 px-2 py-1 bg-zinc-800 rounded"
                      >
                        Cancel
                      </button>
                    )}
                    <button
                      onClick={() => handleResetAccount(acc.account_id)}
                      disabled={isResetting}
                      className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-[10px] font-semibold transition-all ${
                        isResetting ? 'opacity-50 cursor-not-allowed bg-zinc-800 text-zinc-500' :
                        isConfirming
                          ? 'bg-rose-500/20 border border-rose-500/40 text-rose-400 hover:bg-rose-500/30 animate-pulse'
                          : 'bg-zinc-800/60 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                      }`}
                    >
                      {isResetting ? <RefreshCw className="w-3 h-3 animate-spin" /> : <RotateCcw className="w-3 h-3" />}
                      {isResetting ? 'Resetting...' : isConfirming ? 'Confirm Reset?' : 'Reset'}
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div>
                    <div className="text-[10px] text-zinc-500">Balance</div>
                    <div className="font-mono text-xs font-bold text-white">{fmtBalance(acc.balance)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-zinc-500">Start</div>
                    <div className="font-mono text-xs text-zinc-400">{fmtBalance(acc.starting_balance)}</div>
                  </div>
                  <div>
                    <div className="text-[10px] text-zinc-500">Return</div>
                    <div className={`font-mono text-xs font-bold ${pct >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {pct >= 0 ? '+' : ''}{pct.toFixed(2)}%
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3 mt-2 text-[10px] text-zinc-600">
                  <span>{acc.total_trades} trades</span>
                  <span>{acc.win_rate?.toFixed(1)}% WR</span>
                  <span>{acc.open_positions} open</span>
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      {/* Active Gates */}
      {settings && (
        <Section title="Active Gates" icon={Shield}>
          <div className="space-y-1.5">
            {Object.entries(settings).map(([k, v]) => (
              typeof v === 'number' || typeof v === 'boolean' ? (
                <div key={k} className="flex items-center justify-between py-1 border-b border-zinc-800/20 last:border-0">
                  <span className="text-xs text-zinc-400">{k.replace(/_/g, ' ')}</span>
                  <span className={`font-mono text-xs font-semibold ${
                    typeof v === 'boolean' ? (v ? 'text-emerald-400' : 'text-rose-400') : 'text-white'
                  }`}>
                    {typeof v === 'boolean' ? (v ? 'ON' : 'OFF') : v}
                  </span>
                </div>
              ) : null
            ))}
          </div>
        </Section>
      )}

      {/* Emergency Kill Switch */}
      <Section title="Emergency Kill Switch" icon={Power}>
        {killResult && (
          <div className={`mb-4 px-3 py-2 rounded-lg text-xs font-semibold ${
            killResult.ok ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30' : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
          }`}>
            {killResult.msg}
          </div>
        )}
        <div className="space-y-3">
          <p className="text-xs text-zinc-500">
            Immediately stops ALL engines and closes ALL open positions. This action cannot be undone.
          </p>
          {killConfirm && !killing && (
            <div className="bg-rose-500/10 border border-rose-500/30 rounded-xl p-3 text-xs text-rose-400">
              <AlertTriangle className="w-4 h-4 mb-1" />
              Are you sure? This will stop ALL engines and close ALL positions immediately.
            </div>
          )}
          <div className="flex gap-2">
            {killConfirm && !killing && (
              <button
                onClick={() => setKillConfirm(false)}
                className="flex-1 py-3 bg-zinc-800 text-zinc-400 rounded-xl text-sm font-semibold hover:bg-zinc-700 transition-all"
              >
                Cancel
              </button>
            )}
            <button
              onClick={handleKillSwitch}
              disabled={killing}
              className={`flex-1 py-3 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 ${
                killing ? 'opacity-50 cursor-not-allowed bg-zinc-800 text-zinc-500' :
                killConfirm
                  ? 'bg-rose-500 text-white hover:bg-rose-600 animate-pulse shadow-lg shadow-rose-500/20'
                  : 'bg-rose-500/20 border border-rose-500/30 text-rose-400 hover:bg-rose-500/30'
              }`}
            >
              {killing ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Power className="w-4 h-4" />}
              {killing ? 'Stopping...' : killConfirm ? 'CONFIRM EMERGENCY STOP' : 'EMERGENCY STOP'}
            </button>
          </div>
        </div>
      </Section>

      {/* Version info */}
      <div className="text-center text-[10px] text-zinc-700 pb-2">
        AEON Trading System — Paper Trading Only
      </div>
    </div>
  );
}
