import React, { useState, useEffect } from 'react';
import { Activity, RefreshCw, Shield, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

function getStatusColor(status) {
  const map = {
    healthy: 'text-green-400',
    degraded: 'text-yellow-400',
    stale: 'text-orange-400',
    throttled: 'text-red-400',
    restarted: 'text-blue-400',
    critical: 'text-red-500',
  };
  return map[status] || 'text-zinc-500';
}

function StatusIcon({ status }) {
  if (status === 'healthy') return <CheckCircle className="w-3 h-3" />;
  if (status === 'degraded') return <AlertTriangle className="w-3 h-3" />;
  if (status === 'stale') return <Clock className="w-3 h-3" />;
  if (status === 'throttled') return <XCircle className="w-3 h-3" />;
  if (status === 'restarted') return <RefreshCw className="w-3 h-3" />;
  return <Activity className="w-3 h-3" />;
}

function ServiceCard({ name, svc }) {
  const heartbeat = svc.last_heartbeat ? new Date(svc.last_heartbeat).toLocaleTimeString() : 'N/A';
  const errClass = svc.errors_this_hour > 5 ? 'text-red-400' : '';

  return (
    <Card className="bg-zinc-800/30 border-zinc-700/50" data-testid={`service-${name}`}>
      <CardContent className="p-4">
        <div className="flex items-center justify-between mb-3">
          <span className="font-semibold text-white capitalize">{name.replace(/_/g, ' ')}</span>
          <span className={`flex items-center gap-1 text-xs font-medium ${getStatusColor(svc.status)}`}>
            <StatusIcon status={svc.status} />
            {svc.status}
          </span>
        </div>
        <div className="space-y-1 text-xs text-zinc-400">
          <div className="flex justify-between"><span>Heartbeat</span><span>{heartbeat}</span></div>
          <div className="flex justify-between"><span>Errors/hr</span><span className={errClass}>{svc.errors_this_hour}</span></div>
          <div className="flex justify-between"><span>Restarts</span><span>{svc.restart_count}</span></div>
        </div>
        {svc.is_throttled && (
          <div className="mt-2 px-2 py-1 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-xs">
            Throttled - too many errors
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HealingEntry({ entry }) {
  let actionColor = 'text-yellow-400';
  if (entry.action === 'RESTARTED') actionColor = 'text-green-400';
  if (entry.action === 'DETECTED_DEAD' || entry.action === 'THROTTLED') actionColor = 'text-red-400';

  return (
    <div className="flex items-center gap-3 text-xs">
      <span className="text-zinc-600 w-20 flex-shrink-0">{new Date(entry.time).toLocaleTimeString()}</span>
      <span className={`font-medium w-32 flex-shrink-0 ${actionColor}`}>{entry.action}</span>
      <span className="text-zinc-400 capitalize">{entry.service}</span>
      <span className="text-zinc-600 truncate">{entry.detail}</span>
    </div>
  );
}

export default function SystemHealth() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchHealth = async () => {
    try {
      const res = await fetch(`${API_URL}/api/system/health`);
      const data = await res.json();
      setHealth(data);
    } catch (err) {
      console.error('Failed to fetch health:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchHealth();
    const iv = setInterval(fetchHealth, 15000);
    return () => clearInterval(iv);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  const services = health ? health.services : {};
  const serviceEntries = Object.entries(services || {});
  const overall = health ? health.overall : 'unknown';
  const healingLog = health ? (health.recent_healing || []) : [];
  const totalRestarts = serviceEntries.reduce(function(s, e) { return s + (e[1].restart_count || 0); }, 0);
  const totalErrors = serviceEntries.reduce(function(s, e) { return s + (e[1].error_count || 0); }, 0);

  return (
    <div className="space-y-6" data-testid="system-health-page">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold text-white">System Health</h2>
          <span className={`flex items-center gap-1 text-sm font-medium ${getStatusColor(overall)}`}>
            <StatusIcon status={overall} />
            {overall.toUpperCase()}
          </span>
        </div>
        <button onClick={fetchHealth} data-testid="refresh-health-btn"
          className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Services</p>
            <p className="text-2xl font-bold text-white">{health ? health.total_services : 0}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Healthy</p>
            <p className="text-2xl font-bold text-green-400">{health ? health.healthy_services : 0}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Restarts</p>
            <p className="text-2xl font-bold text-blue-400">{totalRestarts}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Total Errors</p>
            <p className="text-2xl font-bold text-red-400">{totalErrors}</p>
          </CardContent>
        </Card>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {serviceEntries.map(function(pair) {
          return <ServiceCard key={pair[0]} name={pair[0]} svc={pair[1]} />;
        })}
      </div>

      {healingLog.length > 0 && (
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-orange-400" /> Auto-Heal Log
            </h3>
            <div className="space-y-2">
              {healingLog.map(function(entry, i) {
                return <HealingEntry key={i} entry={entry} />;
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
