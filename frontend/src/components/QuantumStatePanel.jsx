import React, { useState, useEffect, useCallback } from 'react';
import {
  Activity, Zap, Brain, RefreshCw, Shield, TrendingUp,
  Circle, CheckCircle, XCircle, AlertTriangle
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ENGINE_LABELS = {
  day_trader:           'DAY',
  autonomous_trader_v2: 'AUTO V2',
  free_will_v2:         'FREE WILL',
  dual_engine:          'DUAL',
  yolo_engine:          'YOLO',
  vwap_scalper:         'VWAP',
  elite_strategy:       'ELITE',
  tcn_neural:           'TCN',
  quant_analyzer:       'QUANT',
};

function GaugeBar({ value, max = 1, color = 'orange', label, sublabel }) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  const colorMap = {
    orange: 'bg-orange-500',
    blue:   'bg-blue-500',
    purple: 'bg-purple-500',
    green:  'bg-green-500',
    red:    'bg-red-500',
    amber:  'bg-amber-500',
    cyan:   'bg-cyan-500',
  };
  const barColor = colorMap[color] || 'bg-orange-500';
  return (
    <div className="space-y-1">
      <div className="flex justify-between items-center">
        <span className="text-xs text-zinc-400">{label}</span>
        <span className="text-xs font-mono text-white">{typeof value === 'number' ? value.toFixed(3) : '—'}{sublabel || ''}</span>
      </div>
      <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${barColor}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function EngineAmplitude({ name, alpha, score }) {
  const label = ENGINE_LABELS[name] || name;
  const pct = Math.min(100, Math.max(0, Math.abs(alpha || 0) * 100));
  const positive = (alpha || 0) >= 0;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-zinc-500 w-16 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${positive ? 'bg-orange-500' : 'bg-red-500'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className={`text-xs font-mono w-12 text-right ${positive ? 'text-orange-400' : 'text-red-400'}`}>
        {typeof alpha === 'number' ? alpha.toFixed(3) : '—'}
      </span>
    </div>
  );
}

export default function QuantumStatePanel() {
  const [state, setState] = useState(null);
  const [identity, setIdentity] = useState(null);
  const [gate, setGate] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);

  const headers = {};

  const fetchAll = useCallback(async () => {
    try {
      const [stateRes, identityRes, gateRes] = await Promise.all([
        fetch(`${API_URL}/api/quantum/state`, { headers }),
        fetch(`${API_URL}/api/quantum/identity`, { headers }),
        fetch(`${API_URL}/api/quantum/identity/gate`, { headers }),
      ]);
      if (stateRes.ok) setState(await stateRes.json());
      if (identityRes.ok) setIdentity(await identityRes.json());
      if (gateRes.ok) setGate(await gateRes.json());
      setLastUpdated(new Date());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const H = state?.H ?? identity?.H ?? null;
  const C = state?.C ?? null;
  const S = state?.S_norm ?? null;
  const posMul = state?.position_multiplier ?? null;
  const regime = state?.regime ?? identity?.regime ?? null;
  const alphas = state?.alphas ?? identity?.alphas ?? {};
  const gateOpen = gate?.gate_open ?? gate?.decision === 'ALLOW';
  const hGateVal = gate?.H_value ?? gate?.h_value ?? H;

  const regimeColor = {
    STRUCTURED: 'text-green-400 bg-green-500/10 border-green-500/30',
    TRANSITIONAL: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    CHAOTIC: 'text-red-400 bg-red-500/10 border-red-500/30',
  }[regime] || 'text-zinc-400 bg-zinc-500/10 border-zinc-500/30';

  return (
    <div className="min-h-screen bg-zinc-950 p-4 md:p-6 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-600 to-blue-600 flex items-center justify-center shadow-lg shadow-purple-500/20">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">Quantum State</h1>
            <p className="text-xs text-zinc-500">|Ψ⟩ — AEON Identity Engine</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-zinc-500">
              {lastUpdated.toLocaleTimeString()}
            </span>
          )}
          <button
            onClick={fetchAll}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-red-400 text-sm">
          {error}
        </div>
      )}

      {loading && !state && (
        <div className="flex items-center justify-center py-20 text-zinc-500">
          <RefreshCw className="w-5 h-5 animate-spin mr-2" />
          Loading quantum state...
        </div>
      )}

      {/* Master Identity */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* H Score */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-1">H Score</p>
          <p className="text-2xl font-bold text-orange-400 font-mono">
            {H !== null ? H.toFixed(3) : '—'}
          </p>
          <p className="text-xs text-zinc-600 mt-1">Health Gate</p>
        </div>

        {/* Coherence */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-1">C Coherence</p>
          <p className="text-2xl font-bold text-blue-400 font-mono">
            {C !== null ? C.toFixed(3) : '—'}
          </p>
          <p className="text-xs text-zinc-600 mt-1">Engine alignment</p>
        </div>

        {/* Entropy */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-1">S Entropy</p>
          <p className="text-2xl font-bold text-purple-400 font-mono">
            {S !== null ? S.toFixed(3) : '—'}
          </p>
          <p className="text-xs text-zinc-600 mt-1">Signal dispersion</p>
        </div>

        {/* Position Multiplier */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <p className="text-xs text-zinc-500 mb-1">Pos Multiplier</p>
          <p className={`text-2xl font-bold font-mono ${(posMul || 0) >= 1 ? 'text-green-400' : 'text-amber-400'}`}>
            {posMul !== null ? `${posMul.toFixed(2)}×` : '—'}
          </p>
          <p className="text-xs text-zinc-600 mt-1">Size scaling</p>
        </div>
      </div>

      {/* Regime + H-Gate Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* Regime */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Activity className="w-4 h-4 text-zinc-400" />
            <h2 className="text-sm font-semibold text-zinc-300">Market Regime</h2>
          </div>
          {regime ? (
            <span className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm font-semibold ${regimeColor}`}>
              {regime}
            </span>
          ) : (
            <span className="text-zinc-500 text-sm">—</span>
          )}
          {state?.adx !== undefined && (
            <p className="text-xs text-zinc-500 mt-2">ADX: {state.adx?.toFixed(1) ?? '—'}</p>
          )}
        </div>

        {/* H-Gate */}
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <Shield className="w-4 h-4 text-zinc-400" />
            <h2 className="text-sm font-semibold text-zinc-300">H-Gate</h2>
          </div>
          <div className="flex items-center gap-3">
            {gateOpen
              ? <CheckCircle className="w-6 h-6 text-green-400" />
              : <XCircle className="w-6 h-6 text-red-400" />
            }
            <div>
              <p className={`text-sm font-bold ${gateOpen ? 'text-green-400' : 'text-red-400'}`}>
                {gateOpen ? 'OPEN — Trading allowed' : 'CLOSED — Trading blocked'}
              </p>
              {gate?.threshold !== undefined && (
                <p className="text-xs text-zinc-500">
                  H = {hGateVal?.toFixed(3)} | Threshold: {gate.threshold?.toFixed(3)}
                </p>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Gauge row */}
      <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 space-y-3">
        <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
          <Zap className="w-4 h-4 text-amber-400" /> Quantum Scores
        </h2>
        <GaugeBar value={H}     label="H — System Health"    color="orange" />
        <GaugeBar value={C}     label="C — Coherence"        color="blue"   />
        <GaugeBar value={S}     label="S — Entropy (norm)"   color="purple" />
        <GaugeBar value={posMul} max={2} label="Position Multiplier" color="green" sublabel="×" />
      </div>

      {/* Engine Amplitudes */}
      {Object.keys(alphas).length > 0 && (
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 space-y-3">
          <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
            <Brain className="w-4 h-4 text-purple-400" /> Engine Amplitudes αᵢ
          </h2>
          <div className="space-y-2">
            {Object.entries(alphas).map(([engine, alpha]) => (
              <EngineAmplitude
                key={engine}
                name={engine}
                alpha={typeof alpha === 'object' ? alpha?.alpha ?? alpha?.value ?? 0 : alpha}
              />
            ))}
          </div>
          <p className="text-xs text-zinc-600">
            Positive = bullish contribution · Negative = bearish drag
          </p>
        </div>
      )}

      {/* Identity A(t) breakdown */}
      {identity && (
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 space-y-3">
          <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-cyan-400" /> A(t) = Ω(|Ψ⟩, ε, M, L)
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 text-xs">
            {identity.epsilon !== undefined && (
              <div className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-zinc-500">ε Environment</p>
                <p className="font-mono text-cyan-400 font-bold">{identity.epsilon?.toFixed?.(3) ?? identity.epsilon}</p>
              </div>
            )}
            {identity.M !== undefined && (
              <div className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-zinc-500">M(t) Memory</p>
                <p className="font-mono text-blue-400 font-bold">{identity.M?.toFixed?.(3) ?? identity.M}</p>
              </div>
            )}
            {identity.L !== undefined && (
              <div className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-zinc-500">L Learning</p>
                <p className="font-mono text-purple-400 font-bold">{identity.L?.toFixed?.(3) ?? identity.L}</p>
              </div>
            )}
            {identity.omega !== undefined && (
              <div className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-zinc-500">Ω Identity</p>
                <p className="font-mono text-orange-400 font-bold">{identity.omega?.toFixed?.(3) ?? identity.omega}</p>
              </div>
            )}
            {identity.n_active !== undefined && (
              <div className="bg-zinc-800/50 rounded-lg p-2">
                <p className="text-zinc-500">Active Engines</p>
                <p className="font-mono text-green-400 font-bold">{identity.n_active}</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
