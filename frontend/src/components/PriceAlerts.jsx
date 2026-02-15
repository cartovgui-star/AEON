import React, { useState, useEffect, useCallback } from 'react';
import {
  Bell, Plus, Trash2, RefreshCw, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle, Clock, Target, ArrowUp, ArrowDown,
  Activity, Eye, EyeOff, X, Loader2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const COINS = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LINK', 'DOT',
  'MATIC', 'NEAR', 'UNI', 'ATOM', 'LTC', 'FIL', 'APT', 'ARB', 'OP', 'SUI'
];

export default function PriceAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [dashAlerts, setDashAlerts] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [adding, setAdding] = useState(false);
  const [livePrice, setLivePrice] = useState(null);
  const [fetchingPrice, setFetchingPrice] = useState(false);

  // Form state
  const [symbol, setSymbol] = useState('BTC');
  const [targetPrice, setTargetPrice] = useState('');
  const [direction, setDirection] = useState('above');
  const [showForm, setShowForm] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [alertsRes, dashRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/alerts/custom`),
        fetch(`${API_URL}/api/alerts/dashboard?limit=30`),
        fetch(`${API_URL}/api/alerts/stats`)
      ]);
      const alertsData = await alertsRes.json();
      const dashData = await dashRes.json();
      const statsData = await statsRes.json();
      setAlerts(alertsData.alerts || []);
      setDashAlerts(dashData.alerts || []);
      setStats(statsData);
    } catch (err) {
      console.error('Failed to fetch alerts:', err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 15000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // Fetch live price when symbol changes
  useEffect(() => {
    const fetchPrice = async () => {
      setFetchingPrice(true);
      try {
        const res = await fetch(`${API_URL}/api/mexc/live`);
        const data = await res.json();
        const found = data.symbols?.find(s =>
          s.symbol?.replace('/USDT', '').replace('USDT', '') === symbol
        );
        setLivePrice(found?.price || null);
      } catch (e) {
        setLivePrice(null);
      }
      setFetchingPrice(false);
    };
    if (showForm) fetchPrice();
  }, [symbol, showForm]);

  const addAlert = async () => {
    if (!targetPrice || isNaN(targetPrice)) return;
    setAdding(true);
    try {
      const res = await fetch(`${API_URL}/api/alerts/add`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol, target_price: parseFloat(targetPrice), direction })
      });
      const data = await res.json();
      if (data.success) {
        setTargetPrice('');
        setShowForm(false);
        fetchAll();
      }
    } catch (err) {
      console.error('Failed to add alert:', err);
    }
    setAdding(false);
  };

  const removeAlert = async (alertId) => {
    try {
      await fetch(`${API_URL}/api/alerts/${alertId}`, { method: 'DELETE' });
      fetchAll();
    } catch (err) {
      console.error('Failed to remove alert:', err);
    }
  };

  const clearDashboard = async () => {
    try {
      await fetch(`${API_URL}/api/alerts/clear`, { method: 'POST' });
      fetchAll();
    } catch (err) {
      console.error('Failed to clear alerts:', err);
    }
  };

  const markRead = async (dashboardId) => {
    try {
      await fetch(`${API_URL}/api/alerts/mark-read/${dashboardId}`, { method: 'POST' });
      fetchAll();
    } catch (err) {
      console.error('Failed to mark read:', err);
    }
  };

  const getSeverityColor = (severity) => {
    if (severity === 'high') return 'border-red-500/40 bg-red-500/5';
    if (severity === 'medium') return 'border-orange-500/40 bg-orange-500/5';
    return 'border-zinc-700/50 bg-zinc-800/20';
  };

  const getSeverityBadge = (severity) => {
    if (severity === 'high') return 'bg-red-500/20 text-red-400';
    if (severity === 'medium') return 'bg-orange-500/20 text-orange-400';
    return 'bg-zinc-700 text-zinc-400';
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="price-alerts-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <Bell className="w-5 h-5 text-white" />
            </div>
            Price Alerts
          </h1>
          <p className="text-zinc-500 text-sm mt-1">Set custom alerts and monitor real-time price movements</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowForm(!showForm)}
            data-testid="add-alert-btn"
            className="flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 rounded-xl text-white text-sm font-medium transition-all shadow-lg shadow-orange-500/20"
          >
            <Plus className="w-4 h-4" />
            New Alert
          </button>
          <button
            onClick={fetchAll}
            className="p-2.5 bg-zinc-800/50 hover:bg-zinc-800 rounded-xl text-zinc-400 hover:text-white transition-all"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Active Custom</p>
          <p className="text-xl font-bold text-white" data-testid="custom-alerts-count">{alerts.filter(a => a.active).length}</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Tracking</p>
          <p className="text-xl font-bold text-cyan-400">{stats?.tracked_symbols || 0} coins</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Alerts Today</p>
          <p className="text-xl font-bold text-orange-400">{stats?.alerts_today || 0}</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Unread</p>
          <p className="text-xl font-bold text-amber-400">
            {dashAlerts.filter(a => !a.read).length}
          </p>
        </div>
      </div>

      {/* New Alert Form */}
      {showForm && (
        <div className="bg-zinc-800/40 border border-zinc-700/50 rounded-2xl p-6 space-y-5" data-testid="add-alert-form">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-orange-400" />
              Create Price Alert
            </h3>
            <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white">
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Symbol */}
            <div>
              <label className="block text-xs text-zinc-400 mb-2">Coin</label>
              <select
                value={symbol}
                onChange={(e) => setSymbol(e.target.value)}
                data-testid="alert-symbol-select"
                className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
              >
                {COINS.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            {/* Direction */}
            <div>
              <label className="block text-xs text-zinc-400 mb-2">Condition</label>
              <div className="flex rounded-xl overflow-hidden border border-zinc-700">
                <button
                  onClick={() => setDirection('above')}
                  data-testid="alert-direction-above"
                  className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-all ${
                    direction === 'above'
                      ? 'bg-green-500/20 text-green-400 border-r border-green-500/30'
                      : 'bg-zinc-900 text-zinc-400 border-r border-zinc-700 hover:text-white'
                  }`}
                >
                  <ArrowUp className="w-4 h-4" />
                  Above
                </button>
                <button
                  onClick={() => setDirection('below')}
                  data-testid="alert-direction-below"
                  className={`flex-1 flex items-center justify-center gap-2 py-3 text-sm font-medium transition-all ${
                    direction === 'below'
                      ? 'bg-red-500/20 text-red-400'
                      : 'bg-zinc-900 text-zinc-400 hover:text-white'
                  }`}
                >
                  <ArrowDown className="w-4 h-4" />
                  Below
                </button>
              </div>
            </div>

            {/* Target Price */}
            <div>
              <label className="block text-xs text-zinc-400 mb-2">
                Target Price
                {livePrice && !fetchingPrice && (
                  <span className="ml-2 text-zinc-600">
                    Current: ${livePrice.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                )}
              </label>
              <div className="relative">
                <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500 text-sm">$</span>
                <input
                  type="number"
                  value={targetPrice}
                  onChange={(e) => setTargetPrice(e.target.value)}
                  placeholder={livePrice ? livePrice.toLocaleString() : '0.00'}
                  data-testid="alert-price-input"
                  className="w-full bg-zinc-900 border border-zinc-700 rounded-xl pl-8 pr-4 py-3 text-white text-sm focus:border-orange-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          {/* Preview */}
          {targetPrice && livePrice && (
            <div className="bg-zinc-900/50 rounded-xl p-4 border border-zinc-800">
              <p className="text-sm text-zinc-300">
                Alert when <span className="font-semibold text-white">{symbol}</span> goes{' '}
                <span className={direction === 'above' ? 'text-green-400' : 'text-red-400'}>{direction}</span>{' '}
                <span className="font-semibold text-white">${parseFloat(targetPrice).toLocaleString()}</span>
                {livePrice && (
                  <span className="text-zinc-500 ml-2">
                    ({((parseFloat(targetPrice) - livePrice) / livePrice * 100).toFixed(2)}% from current)
                  </span>
                )}
              </p>
            </div>
          )}

          <button
            onClick={addAlert}
            disabled={adding || !targetPrice}
            data-testid="submit-alert-btn"
            className="w-full py-3 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-xl text-white font-medium transition-all flex items-center justify-center gap-2"
          >
            {adding ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />}
            {adding ? 'Setting Alert...' : 'Set Alert'}
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Active Custom Alerts */}
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-white flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-400" />
            Custom Alerts
            <span className="text-xs text-zinc-500 font-normal">({alerts.length})</span>
          </h2>

          {alerts.length === 0 ? (
            <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-8 text-center">
              <Bell className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-500 text-sm">No custom alerts set</p>
              <p className="text-zinc-600 text-xs mt-1">Click "New Alert" to get started</p>
            </div>
          ) : (
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div
                  key={alert.alert_id}
                  data-testid={`custom-alert-${alert.alert_id}`}
                  className={`bg-zinc-800/30 border rounded-xl p-4 flex items-center justify-between transition-all ${
                    alert.active ? 'border-zinc-700/50' : 'border-zinc-800/30 opacity-60'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      alert.condition?.direction === 'above'
                        ? 'bg-green-500/10 text-green-400'
                        : 'bg-red-500/10 text-red-400'
                    }`}>
                      {alert.condition?.direction === 'above'
                        ? <TrendingUp className="w-5 h-5" />
                        : <TrendingDown className="w-5 h-5" />
                      }
                    </div>
                    <div>
                      <p className="text-sm font-medium text-white">
                        {alert.symbol?.replace('/USDT', '')}
                        <span className={`ml-2 text-xs ${
                          alert.condition?.direction === 'above' ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {alert.condition?.direction?.toUpperCase()}
                        </span>
                      </p>
                      <p className="text-xs text-zinc-500">
                        ${alert.condition?.target_price?.toLocaleString()}
                        {alert.triggered_at && (
                          <span className="ml-2 text-amber-400">Triggered</span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {alert.active ? (
                      <span className="text-xs px-2 py-1 rounded bg-green-500/10 text-green-400">Active</span>
                    ) : (
                      <span className="text-xs px-2 py-1 rounded bg-zinc-700 text-zinc-400">Triggered</span>
                    )}
                    <button
                      onClick={() => removeAlert(alert.alert_id)}
                      data-testid={`remove-alert-${alert.alert_id}`}
                      className="p-1.5 text-zinc-600 hover:text-red-400 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Recent Dashboard Alerts (Auto + Triggered) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-orange-400" />
              Alert Feed
              <span className="text-xs text-zinc-500 font-normal">({dashAlerts.length})</span>
            </h2>
            {dashAlerts.length > 0 && (
              <button
                onClick={clearDashboard}
                data-testid="clear-alerts-btn"
                className="text-xs text-zinc-500 hover:text-red-400 transition-colors flex items-center gap-1"
              >
                <Trash2 className="w-3 h-3" />
                Clear All
              </button>
            )}
          </div>

          {dashAlerts.length === 0 ? (
            <div className="bg-zinc-800/20 border border-zinc-700/30 rounded-xl p-8 text-center">
              <Activity className="w-10 h-10 text-zinc-700 mx-auto mb-3" />
              <p className="text-zinc-500 text-sm">No alerts yet</p>
              <p className="text-zinc-600 text-xs mt-1">Auto-alerts monitor 10 coins for big moves, RSI extremes & volume spikes</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-[500px] overflow-y-auto pr-1">
              {dashAlerts.map((alert, i) => (
                <div
                  key={alert.dashboard_id || i}
                  data-testid={`dash-alert-${i}`}
                  className={`border rounded-xl p-4 transition-all cursor-pointer ${getSeverityColor(alert.severity)} ${
                    alert.read ? 'opacity-60' : ''
                  }`}
                  onClick={() => !alert.read && markRead(alert.dashboard_id)}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${getSeverityBadge(alert.severity)}`}>
                          {alert.type?.replace('_', ' ').toUpperCase()}
                        </span>
                        <span className="text-xs text-zinc-600">
                          {alert.symbol?.replace('/USDT', '')}
                        </span>
                        {!alert.read && (
                          <span className="w-2 h-2 rounded-full bg-orange-400 animate-pulse" />
                        )}
                      </div>
                      <p className="text-sm text-zinc-300 whitespace-pre-line line-clamp-3">
                        {alert.message?.split('\n').filter(l => l.trim()).slice(0, 3).join('\n')}
                      </p>
                      <p className="text-xs text-zinc-600 mt-2">
                        {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : ''}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Auto Alert Thresholds */}
      <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6">
        <h3 className="text-sm font-semibold text-zinc-400 mb-4 flex items-center gap-2">
          <AlertTriangle className="w-4 h-4" />
          AUTO-ALERT THRESHOLDS
        </h3>
        <div className="grid grid-cols-3 sm:grid-cols-5 gap-4">
          <div>
            <p className="text-xs text-zinc-600 mb-1">5min Move</p>
            <p className="text-sm font-medium text-white">{stats?.thresholds?.price_change_5min || 2}%</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-1">1h Move</p>
            <p className="text-sm font-medium text-white">{stats?.thresholds?.price_change_1h || 5}%</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-1">RSI Oversold</p>
            <p className="text-sm font-medium text-cyan-400">{stats?.thresholds?.rsi_oversold || 25}</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-1">RSI Overbought</p>
            <p className="text-sm font-medium text-amber-400">{stats?.thresholds?.rsi_overbought || 75}</p>
          </div>
          <div>
            <p className="text-xs text-zinc-600 mb-1">Vol Spike</p>
            <p className="text-sm font-medium text-white">{stats?.thresholds?.volume_spike_mult || 3}x</p>
          </div>
        </div>
      </div>
    </div>
  );
}
