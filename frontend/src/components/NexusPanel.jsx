import React, { useState, useEffect, useCallback } from 'react';
import {
  Brain, Activity, Shield, Cpu, RefreshCw, CheckCircle,
  XCircle, AlertTriangle, Heart, Eye, Zap, Clock, TrendingUp, Server
} from 'lucide-react';
import NexusAwarenessFeed from './NexusAwarenessFeed';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const NEXUS_URL = `${API_URL}/api/quantum/identity`; // proxy via AEON backend

// Nexus runs on localhost:8001, AEON proxies nothing — we call NEXUS /nexus/status
// via the Telegram command route. Instead, we read from MongoDB via AEON's APIs
// and display NEXUS awareness data.

function StatusBadge({ value, trueLabel = 'ACTIVE', falseLabel = 'INACTIVE', trueColor = 'green', falseColor = 'red' }) {
  const isTrue = Boolean(value);
  const colorMap = {
    green:  'text-green-400 bg-green-500/10 border-green-500/30',
    red:    'text-red-400 bg-red-500/10 border-red-500/30',
    yellow: 'text-yellow-400 bg-yellow-500/10 border-yellow-500/30',
    orange: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    blue:   'text-blue-400 bg-blue-500/10 border-blue-500/30',
  };
  const cls = isTrue ? (colorMap[trueColor] || colorMap.green) : (colorMap[falseColor] || colorMap.red);
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-semibold ${cls}`}>
      {isTrue ? trueLabel : falseLabel}
    </span>
  );
}

function LayerCard({ icon: Icon, title, subtitle, children, color = 'orange' }) {
  const colorMap = {
    orange: 'text-orange-400 bg-orange-500/10 border-orange-500/30',
    blue:   'text-blue-400 bg-blue-500/10 border-blue-500/30',
    purple: 'text-purple-400 bg-purple-500/10 border-purple-500/30',
    green:  'text-green-400 bg-green-500/10 border-green-500/30',
    red:    'text-red-400 bg-red-500/10 border-red-500/30',
    cyan:   'text-cyan-400 bg-cyan-500/10 border-cyan-500/30',
  };
  const headerColor = colorMap[color] || colorMap.orange;
  return (
    <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
      <div className={`flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800/50 ${headerColor} bg-opacity-5`}>
        <Icon className="w-4 h-4" />
        <span className="text-xs font-bold uppercase tracking-wider">{title}</span>
        {subtitle && <span className="text-xs ml-auto opacity-60">{subtitle}</span>}
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

function StatRow({ label, value, unit, highlight }) {
  return (
    <div className="flex justify-between items-center py-1 border-b border-zinc-800/30 last:border-0">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className={`text-xs font-mono font-semibold ${highlight || 'text-white'}`}>
        {value !== null && value !== undefined ? `${value}${unit || ''}` : '—'}
      </span>
    </div>
  );
}

const NEXUS_COMMANDS = [
  { cmd: '/nexus_status',    label: 'Status',    color: 'blue'   },
  { cmd: '/nexus_regime',    label: 'Regime',    color: 'purple' },
  { cmd: '/nexus_engines',   label: 'Engines',   color: 'orange' },
  { cmd: '/nexus_health',    label: 'Health',    color: 'green'  },
  { cmd: '/nexus_positions', label: 'Positions', color: 'cyan'   },
  { cmd: '/nexus_heal',      label: 'Heal Now',  color: 'amber'  },
  { cmd: '/nexus_adapt',     label: 'Adapt',     color: 'orange' },
  { cmd: '/nexus_pause',     label: 'Pause',     color: 'yellow' },
  { cmd: '/nexus_resume',    label: 'Resume',    color: 'green'  },
  { cmd: '/nexus_crisis',    label: 'Crisis',    color: 'red'    },
];

const CMD_COLOR = {
  blue:   'text-blue-400 hover:bg-blue-500/10 border-blue-500/20',
  purple: 'text-purple-400 hover:bg-purple-500/10 border-purple-500/20',
  orange: 'text-orange-400 hover:bg-orange-500/10 border-orange-500/20',
  green:  'text-green-400 hover:bg-green-500/10 border-green-500/20',
  cyan:   'text-cyan-400 hover:bg-cyan-500/10 border-cyan-500/20',
  amber:  'text-amber-400 hover:bg-amber-500/10 border-amber-500/20',
  yellow: 'text-yellow-400 hover:bg-yellow-500/10 border-yellow-500/20',
  red:    'text-red-400 hover:bg-red-500/10 border-red-500/20',
};

export default function NexusPanel() {
  const [awareness, setAwareness] = useState(null);
  const [nexusConfig, setNexusConfig] = useState(null);
  const [heals, setHeals] = useState([]);
  const [adaptations, setAdaptations] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [heartbeat, setHeartbeat] = useState(null);
  const [suspendedEngines, setSuspendedEngines] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [copiedCmd, setCopiedCmd] = useState(null);

  const headers = {};

  const fetchAll = useCallback(async () => {
    try {
      const [awarenessRes, configRes, healsRes, adaptRes, alertsRes, heartbeatRes, suspendedRes] = await Promise.all([
        fetch(`${API_URL}/api/nexus/awareness`, { headers }),
        fetch(`${API_URL}/api/nexus/config`, { headers }),
        fetch(`${API_URL}/api/nexus/heals`, { headers }),
        fetch(`${API_URL}/api/nexus/adaptations`, { headers }),
        fetch(`${API_URL}/api/nexus/alerts`, { headers }),
        fetch(`${API_URL}/api/nexus/heartbeat`, { headers }),
        fetch(`${API_URL}/api/nexus/suspended-engines`, { headers }),
      ]);
      if (awarenessRes.ok) setAwareness(await awarenessRes.json());
      if (configRes.ok) setNexusConfig(await configRes.json());
      if (healsRes.ok) setHeals((await healsRes.json()).slice(0, 5));
      if (adaptRes.ok) setAdaptations((await adaptRes.json()).slice(0, 5));
      if (alertsRes.ok) setAlerts((await alertsRes.json()).slice(0, 5));
      if (heartbeatRes.ok) setHeartbeat(await heartbeatRes.json());
      if (suspendedRes.ok) setSuspendedEngines(await suspendedRes.json());
      setLastUpdated(new Date());
    } catch (_) {}
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const copyCmd = (cmd) => {
    navigator.clipboard.writeText(cmd).catch(() => {});
    setCopiedCmd(cmd);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  const isPaused = nexusConfig?.pause === true;
  const isCrisis = nexusConfig?.crisis === true;
  const posMod   = nexusConfig?.position_modifier ?? 1.0;

  return (
    <div className="min-h-screen bg-zinc-950 p-4 md:p-6 space-y-4">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Brain className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">NEXUS</h1>
            <p className="text-xs text-zinc-500">Autonomous Nervous System</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-zinc-500">{lastUpdated.toLocaleTimeString()}</span>
          )}
          <button
            onClick={fetchAll}
            className="p-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Crisis / Pause Banner */}
      {(isCrisis || isPaused) && (
        <div className={`rounded-xl border p-3 flex items-center gap-2 ${isCrisis ? 'bg-red-500/10 border-red-500/40 text-red-400' : 'bg-yellow-500/10 border-yellow-500/40 text-yellow-400'}`}>
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span className="text-sm font-semibold">
            {isCrisis
              ? 'CRISIS MODE — All trading halted. Correlation spike detected.'
              : 'PAUSED — Trading paused by NEXUS. Regime normalization in progress.'}
          </span>
        </div>
      )}

      {/* Status Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 text-center">
          <p className="text-xs text-zinc-500 mb-2">Trading Gate</p>
          {isCrisis
            ? <StatusBadge value={false} falseLabel="CRISIS" falseColor="red" />
            : isPaused
            ? <StatusBadge value={false} falseLabel="PAUSED" falseColor="yellow" />
            : <StatusBadge value={true} trueLabel="LIVE" />
          }
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 text-center">
          <p className="text-xs text-zinc-500 mb-1">Pos Modifier</p>
          <p className={`text-xl font-bold font-mono ${posMod >= 1 ? 'text-green-400' : posMod >= 0.5 ? 'text-amber-400' : 'text-red-400'}`}>
            {posMod.toFixed(2)}×
          </p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 text-center">
          <p className="text-xs text-zinc-500 mb-1">Regime</p>
          <p className="text-sm font-bold text-orange-400">
            {nexusConfig?.regime ?? awareness?.market_regime ?? '—'}
          </p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4 text-center">
          <p className="text-xs text-zinc-500 mb-1">Hurst H</p>
          <p className="text-xl font-bold font-mono text-blue-400">
            {awareness?.hurst_exponent?.toFixed?.(3) ?? '—'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* ORACLE_SENSE awareness */}
        <LayerCard icon={Eye} title="Layer 1 — ORACLE_SENSE" color="blue">
          {awareness ? (
            <div className="space-y-0">
              <StatRow label="Market Regime"    value={awareness.market_regime}     />
              <StatRow label="Trend Regime"     value={awareness.trend_regime}      />
              <StatRow label="Hurst Exponent"   value={awareness.hurst_exponent?.toFixed?.(3)} highlight={awareness.hurst_exponent > 0.5 ? 'text-green-400' : 'text-blue-400'} />
              <StatRow label="Cross-Asset Corr" value={awareness.corr_max?.toFixed?.(3)}       />
              <StatRow label="Crisis Mode"      value={awareness.crisis_mode ? 'YES' : 'NO'}  highlight={awareness.crisis_mode ? 'text-red-400' : 'text-green-400'} />
              <StatRow label="Open Positions"   value={awareness.open_positions_count}        />
              <StatRow label="CPU %"            value={awareness.cpu_pct?.toFixed?.(1)} unit="%" />
              <StatRow label="RAM %"            value={awareness.ram_pct?.toFixed?.(1)} unit="%" />
            </div>
          ) : (
            <p className="text-xs text-zinc-500">No awareness data yet</p>
          )}
        </LayerCard>

        {/* MORPHEUS Adaptations */}
        <LayerCard icon={Activity} title="Layer 2 — MORPHEUS" subtitle="Last 5 adaptations" color="purple">
          {adaptations.length > 0 ? (
            <div className="space-y-2">
              {adaptations.map((a, i) => (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-zinc-800/30 pb-1 last:border-0">
                  <TrendingUp className="w-3 h-3 text-purple-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-zinc-300">{a.from_regime} → {a.to_regime}</p>
                    <p className="text-zinc-500">{a.action ?? a.reason ?? ''}</p>
                    <p className="text-zinc-600">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">No adaptations recorded yet</p>
          )}
        </LayerCard>

        {/* HEALER */}
        <LayerCard icon={Heart} title="Layer 3 — HEALER" subtitle="Last 5 heals" color="green">
          {heals.length > 0 ? (
            <div className="space-y-2">
              {heals.map((h, i) => (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-zinc-800/30 pb-1 last:border-0">
                  <CheckCircle className="w-3 h-3 text-green-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-zinc-300">{h.heal_type ?? h.type ?? 'heal'}</p>
                    <p className="text-zinc-500">{h.action ?? h.message ?? h.reason ?? ''}</p>
                    <p className="text-zinc-600">{h.timestamp ? new Date(h.timestamp).toLocaleString() : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">No heals recorded yet — system is healthy</p>
          )}
        </LayerCard>

        {/* WARDEN */}
        <LayerCard icon={Shield} title="Layer 4 — WARDEN" subtitle="Last 5 alerts" color="orange">
          {alerts.length > 0 ? (
            <div className="space-y-2">
              {alerts.map((a, i) => (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-zinc-800/30 pb-1 last:border-0">
                  <AlertTriangle className="w-3 h-3 text-orange-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-zinc-300">{a.alert_type ?? a.type ?? 'alert'}</p>
                    <p className="text-zinc-500">{a.message ?? a.details ?? ''}</p>
                    <p className="text-zinc-600">{a.timestamp ? new Date(a.timestamp).toLocaleString() : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-zinc-500">No warden alerts — interface is healthy</p>
          )}
        </LayerCard>

      </div>

      {/* Heartbeat + Suspended Engines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        <LayerCard icon={Activity} title="NEXUS Heartbeat" color="cyan">
          {heartbeat && Object.keys(heartbeat).length > 0 ? (
            <div className="space-y-0">
              <StatRow label="Status"    value={heartbeat.status ?? heartbeat.state ?? '—'} highlight={heartbeat.status === 'ok' ? 'text-green-400' : 'text-amber-400'} />
              <StatRow label="Loop #"    value={heartbeat.loop_count ?? heartbeat.cycle ?? '—'} />
              <StatRow label="Last Beat" value={heartbeat.timestamp ? new Date(heartbeat.timestamp).toLocaleTimeString() : '—'} />
              <StatRow label="Uptime"    value={heartbeat.uptime_seconds ? `${Math.floor(heartbeat.uptime_seconds / 60)}m` : '—'} />
            </div>
          ) : (
            <p className="text-xs text-zinc-500">No heartbeat data yet</p>
          )}
        </LayerCard>

        <LayerCard icon={Cpu} title="Suspended Engines" subtitle={`${suspendedEngines.length} suspended`} color={suspendedEngines.length > 0 ? 'red' : 'green'}>
          {suspendedEngines.length > 0 ? (
            <div className="space-y-2">
              {suspendedEngines.map((e, i) => (
                <div key={i} className="flex items-start gap-2 text-xs border-b border-zinc-800/30 pb-1 last:border-0">
                  <XCircle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="text-zinc-300 font-mono">{e.engine ?? e.engine_type ?? e.name ?? JSON.stringify(e)}</p>
                    <p className="text-zinc-500">{e.reason ?? ''}</p>
                    <p className="text-zinc-600">{e.suspended_at ? new Date(e.suspended_at).toLocaleString() : e.timestamp ? new Date(e.timestamp).toLocaleString() : ''}</p>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-xs text-green-500">All engines running — none suspended</p>
          )}
        </LayerCard>

      </div>

      {/* Telegram Command Center */}
      <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl p-4">
        <h2 className="text-sm font-semibold text-zinc-300 flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-amber-400" /> Telegram Command Center
          <span className="text-xs text-zinc-600 ml-2">Click to copy → paste in Telegram</span>
        </h2>
        <div className="flex flex-wrap gap-2">
          {NEXUS_COMMANDS.map(({ cmd, label, color }) => (
            <button
              key={cmd}
              onClick={() => copyCmd(cmd)}
              className={`px-3 py-1.5 rounded-lg border text-xs font-mono transition-colors ${CMD_COLOR[color] || CMD_COLOR.orange} ${copiedCmd === cmd ? 'opacity-50' : ''}`}
            >
              {copiedCmd === cmd ? '✓ copied' : cmd}
            </button>
          ))}
        </div>
      </div>

      {/* Live Awareness Feed */}
      <NexusAwarenessFeed />

      {/* Service info */}
      <div className="bg-zinc-900/30 border border-zinc-800/30 rounded-xl p-3 flex items-center gap-3">
        <Server className="w-4 h-4 text-zinc-600 flex-shrink-0" />
        <div className="text-xs text-zinc-600 space-y-0.5">
          <p>NEXUS runs as independent systemd service on port 8001 · 60s master loop</p>
          <p>Layers: ORACLE_SENSE → MORPHEUS → HEALER → WARDEN · Data via MongoDB nexus_* collections</p>
        </div>
      </div>

    </div>
  );
}
