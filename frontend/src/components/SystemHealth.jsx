import React, { useState, useEffect } from 'react';
import { Activity, RefreshCw, Shield, AlertTriangle, CheckCircle, XCircle, Clock } from 'lucide-react';
import { Card, CardContent } from './ui/card';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const statusColors = {
  healthy: 'text-green-400',
  degraded: 'text-yellow-400',
  stale: 'text-orange-400',
  throttled: 'text-red-400',
  restarted: 'text-blue-400',
  critical: 'text-red-500',
  unknown: 'text-zinc-500',
};

const statusIcons = {
  healthy: CheckCircle,
  degraded: AlertTriangle,
  stale: Clock,
  throttled: XCircle,
  restarted: RefreshCw,
  critical: XCircle,
  unknown: Activity,
};

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

  const services = health?.services || {};
  const overall = health?.overall || 'unknown';
  const OverallIcon = statusIcons[overall] || Activity;

  return (
    <div className="space-y-6" data-testid="system-health-page">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-orange-400" />
          <h2 className="text-xl font-bold text-white">System Health</h2>
          <span className={`flex items-center gap-1 text-sm font-medium ${statusColors[overall]}`}>
            <OverallIcon className="w-4 h-4" />
            {overall.toUpperCase()}
          </span>
        </div>
        <button onClick={fetchHealth} data-testid="refresh-health-btn"
          className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700 transition-colors">
          <RefreshCw className="w-4 h-4" /> Refresh
        </button>
      </div>

      {/* Overview */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Services</p>
            <p className="text-2xl font-bold text-white">{health?.total_services || 0}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Healthy</p>
            <p className="text-2xl font-bold text-green-400">{health?.healthy_services || 0}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Restarts</p>
            <p className="text-2xl font-bold text-blue-400">
              {Object.values(services).reduce((s, svc) => s + (svc.restart_count || 0), 0)}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4 text-center">
            <p className="text-zinc-500 text-xs">Total Errors</p>
            <p className="text-2xl font-bold text-red-400">
              {Object.values(services).reduce((s, svc) => s + (svc.error_count || 0), 0)}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Service Cards */}
      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(services).map(([name, svc]) => {
          const SvcIcon = statusIcons[svc.status] || Activity;
          return (
            <Card key={name} className="bg-zinc-800/30 border-zinc-700/50" data-testid={`service-${name}`}>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-white capitalize">{name.replace(/_/g, ' ')}</span>
                  <span className={`flex items-center gap-1 text-xs font-medium ${statusColors[svc.status]}`}>
                    <SvcIcon className="w-3 h-3" />
                    {svc.status}
                  </span>
                </div>
                <div className="space-y-1 text-xs text-zinc-400">
                  <div className="flex justify-between">
                    <span>Heartbeat</span>
                    <span>{svc.last_heartbeat ? new Date(svc.last_heartbeat).toLocaleTimeString() : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Errors/hr</span>
                    <span className={svc.errors_this_hour > 5 ? 'text-red-400' : ''}>{svc.errors_this_hour}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Restarts</span>
                    <span>{svc.restart_count}</span>
                  </div>
                  {svc.is_throttled && (
                    <div className="mt-2 px-2 py-1 bg-red-500/10 border border-red-500/20 rounded text-red-400 text-xs">
                      Throttled - too many errors
                    </div>
                  )}
                </div>
                {svc.recent_errors?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-zinc-700">
                    <p className="text-xs text-zinc-500 mb-1">Recent errors:</p>
                    {svc.recent_errors.map((err, i) => (
                      <p key={i} className="text-xs text-red-400/70 truncate">{err.error}</p>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      {/* Healing Log */}
      {health?.recent_healing?.length > 0 && (
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <h3 className="text-sm font-semibold text-white mb-3 flex items-center gap-2">
              <Activity className="w-4 h-4 text-orange-400" /> Auto-Heal Log
            </h3>
            <div className="space-y-2">
              {health.recent_healing.map((entry, i) => (
                <div key={i} className="flex items-center gap-3 text-xs">
                  <span className="text-zinc-600 w-20 flex-shrink-0">
                    {new Date(entry.time).toLocaleTimeString()}
                  </span>
                  <span className={`font-medium w-32 flex-shrink-0 ${
                    entry.action === 'RESTARTED' ? 'text-green-400' :
                    entry.action === 'DETECTED_DEAD' ? 'text-red-400' :
                    entry.action === 'THROTTLED' ? 'text-red-400' : 'text-yellow-400'
                  }`}>{entry.action}</span>
                  <span className="text-zinc-400 capitalize">{entry.service}</span>
                  <span className="text-zinc-600 truncate">{entry.detail}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
