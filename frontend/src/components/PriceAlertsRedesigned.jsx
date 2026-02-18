import React, { useState, useEffect, useCallback } from 'react';
import {
  Bell, Plus, Trash2, RefreshCw, TrendingUp, TrendingDown,
  AlertTriangle, CheckCircle, Clock, Target, ArrowUp, ArrowDown,
  Activity, Eye, Settings as SettingsIcon, X, Loader2, Zap, BarChart3, Volume2
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const COINS = [
  'BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX', 'LINK', 'DOT',
  'MATIC', 'NEAR', 'UNI', 'ATOM', 'LTC', 'FIL', 'APT', 'ARB', 'OP', 'SUI'
];

export default function PriceAlertsRedesigned() {
  const [activeTab, setActiveTab] = useState('price');
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

  // Smart alert thresholds
  const [thresholds, setThresholds] = useState({
    priceMove: 5,
    rsiOversold: 25,
    rsiOverbought: 75,
    volumeSpike: 3
  });
  const [savingThresholds, setSavingThresholds] = useState(false);

  const fetchAll = useCallback(async () => {
    try {
      const [alertsRes, dashRes, statsRes] = await Promise.all([
        fetch(`${API_URL}/api/alerts/custom`),
        fetch(`${API_URL}/api/alerts/dashboard?limit=50`),
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

  const saveThresholds = async () => {
    setSavingThresholds(true);
    try {
      await fetch(`${API_URL}/api/alerts/threshold`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ threshold: 25 }) // Placeholder - backend needs update
      });
    } catch (err) {
      console.error('Failed to save thresholds:', err);
    }
    setSavingThresholds(false);
  };

  const markAsRead = async (dashboardId) => {
    try {
      await fetch(`${API_URL}/api/alerts/mark-read/${dashboardId}`, { method: 'POST' });
      fetchAll();
    } catch (err) {
      console.error('Failed to mark as read:', err);
    }
  };

  const clearAll = async () => {
    try {
      await fetch(`${API_URL}/api/alerts/clear`, { method: 'POST' });
      fetchAll();
    } catch (err) {
      console.error('Failed to clear alerts:', err);
    }
  };

  const calculateDistance = (targetPrice, currentPrice) => {
    if (!currentPrice) return null;
    const diff = ((targetPrice - currentPrice) / currentPrice) * 100;
    return diff;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold text-white flex items-center gap-3">
            <div className="p-2 bg-gradient-to-br from-orange-500 to-amber-600 rounded-xl">
              <Bell className="w-6 h-6 text-white" />
            </div>
            Alerts
          </h1>
          <p className="text-zinc-400 text-sm mt-1">Monitor prices and get notified on big moves</p>
        </div>
        <button
          onClick={fetchAll}
          className="p-2.5 bg-zinc-800/50 hover:bg-zinc-800 rounded-xl text-zinc-400 hover:text-white transition-all self-end md:self-auto"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Active Custom</p>
          <p className="text-xl font-bold text-orange-400">{alerts.filter(a => a.active).length}</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Triggered Today</p>
          <p className="text-xl font-bold text-green-400">{stats?.alerts_today || 0}</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Watching</p>
          <p className="text-xl font-bold text-cyan-400">{stats?.tracked_symbols || 10} coins</p>
        </div>
        <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4">
          <p className="text-zinc-500 text-xs mb-1">Unread</p>
          <p className="text-xl font-bold text-amber-400">{dashAlerts.filter(a => !a.read).length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-zinc-700/50 pb-2 overflow-x-auto">
        <button
          onClick={() => setActiveTab('price')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all whitespace-nowrap ${
            activeTab === 'price'
              ? 'bg-orange-500/20 text-orange-400 border border-orange-500/50'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
          }`}
        >
          <Target className="w-4 h-4" />
          My Price Alerts
        </button>
        <button
          onClick={() => setActiveTab('smart')}
          className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all whitespace-nowrap ${
            activeTab === 'smart'
              ? 'bg-orange-500/20 text-orange-400 border border-orange-500/50'
              : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
          }`}
        >
          <Zap className="w-4 h-4" />
          Smart Alerts
        </button>
      </div>

      {/* MY PRICE ALERTS TAB */}
      {activeTab === 'price' && (
        <div className="space-y-6">
          {/* Description */}
          <div className="bg-blue-500/10 border border-blue-500/30 rounded-xl p-4">
            <p className="text-blue-300 text-sm">
              <strong>Get notified</strong> when a coin hits YOUR target price. Set custom alerts for any price level.
            </p>
          </div>

          {/* Add Alert Button */}
          <button
            onClick={() => setShowForm(!showForm)}
            className="w-full md:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 rounded-xl text-white font-medium transition-all shadow-lg shadow-orange-500/20"
          >
            <Plus className="w-5 h-5" />
            New Price Alert
          </button>

          {/* New Alert Form */}
          {showForm && (
            <div className="bg-zinc-800/40 border border-zinc-700/50 rounded-2xl p-6 space-y-5">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  <Target className="w-5 h-5 text-orange-400" />
                  Create Price Alert
                </h3>
                <button onClick={() => setShowForm(false)} className="text-zinc-500 hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {/* Symbol */}
                <div>
                  <label className="block text-sm text-zinc-300 mb-2 font-medium">Coin</label>
                  <select
                    value={symbol}
                    onChange={(e) => setSymbol(e.target.value)}
                    className="w-full bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-white focus:border-orange-500 focus:outline-none"
                  >
                    {COINS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                </div>

                {/* Target Price */}
                <div>
                  <label className="block text-sm text-zinc-300 mb-2 font-medium">Target Price</label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 text-zinc-500">$</span>
                    <input
                      type="number"
                      value={targetPrice}
                      onChange={(e) => setTargetPrice(e.target.value)}
                      placeholder="100000"
                      className="w-full bg-zinc-900 border border-zinc-700 rounded-xl pl-8 pr-4 py-3 text-white focus:border-orange-500 focus:outline-none"
                    />
                  </div>
                  {livePrice && (
                    <p className="text-xs text-zinc-500 mt-1">
                      Current: ${livePrice.toLocaleString()}
                    </p>
                  )}
                </div>

                {/* Direction */}
                <div>
                  <label className="block text-sm text-zinc-300 mb-2 font-medium">Condition</label>
                  <div className="flex rounded-xl overflow-hidden border border-zinc-700">
                    <button
                      onClick={() => setDirection('above')}
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
              </div>

              <button
                onClick={addAlert}
                disabled={adding || !targetPrice}
                className="w-full py-3 bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-xl font-medium transition-all"
              >
                {adding ? 'Creating...' : 'Create Alert'}
              </button>
            </div>
          )}

          {/* Active Alerts List */}
          {alerts.length > 0 ? (
            <div className="space-y-3">
              <h3 className="text-white font-semibold flex items-center gap-2">
                Your Active Alerts ({alerts.filter(a => a.active).length})
              </h3>
              {alerts.filter(a => a.active).map(alert => {
                const distance = livePrice ? calculateDistance(alert.target_price, livePrice) : null;
                return (
                  <div key={alert.id} className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-4 hover:border-zinc-600 transition-all">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-3 mb-2">
                          <span className="text-lg font-bold text-white">{alert.symbol}</span>
                          <span className={`px-2 py-1 rounded-lg text-xs font-medium ${
                            alert.direction === 'above'
                              ? 'bg-green-500/20 text-green-400'
                              : 'bg-red-500/20 text-red-400'
                          }`}>
                            {alert.direction === 'above' ? '↑' : '↓'} {alert.direction}
                          </span>
                          <span className="text-zinc-400 text-sm">
                            ${alert.target_price?.toLocaleString()}
                          </span>
                        </div>
                        {distance !== null && (
                          <p className="text-sm text-zinc-500">
                            {Math.abs(distance).toFixed(1)}% {distance > 0 ? 'below target' : 'above target'}
                          </p>
                        )}
                      </div>
                      <button
                        onClick={() => removeAlert(alert.id)}
                        className="p-2 hover:bg-red-500/20 rounded-lg text-zinc-500 hover:text-red-400 transition-all"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="bg-zinc-800/20 border border-zinc-700/50 rounded-xl p-12 text-center">
              <Target className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
              <h3 className="text-white font-semibold mb-2">No Price Alerts Set</h3>
              <p className="text-zinc-500 text-sm mb-4">
                Create your first price alert to get notified when a coin hits your target
              </p>
              <button
                onClick={() => setShowForm(true)}
                className="inline-flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium transition-all"
              >
                <Plus className="w-4 h-4" />
                Create Alert
              </button>
            </div>
          )}

          {/* Recent Triggers */}
          {dashAlerts.filter(a => a.type === 'custom_price').length > 0 && (
            <div className="space-y-3">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <CheckCircle className="w-5 h-5 text-green-400" />
                Recent Triggers
              </h3>
              <div className="space-y-2">
                {dashAlerts.filter(a => a.type === 'custom_price').slice(0, 5).map(alert => (
                  <div key={alert.id} className="bg-green-500/10 border border-green-500/30 rounded-lg p-3 text-sm">
                    <p className="text-green-300">
                      <strong>{alert.symbol}</strong> {alert.message}
                    </p>
                    <p className="text-zinc-500 text-xs mt-1">
                      {new Date(alert.timestamp).toLocaleString()}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* SMART ALERTS TAB */}
      {activeTab === 'smart' && (
        <div className="space-y-6">
          {/* Description */}
          <div className="bg-purple-500/10 border border-purple-500/30 rounded-xl p-4">
            <p className="text-purple-300 text-sm">
              <strong>Aeon monitors top coins</strong> and alerts you on significant moves, RSI extremes, and volume spikes
            </p>
          </div>

          {/* Threshold Controls */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <SettingsIcon className="w-5 h-5 text-orange-400" />
                What Triggers an Alert
              </h3>
              <button
                onClick={saveThresholds}
                disabled={savingThresholds}
                className="px-4 py-2 bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 text-white rounded-lg text-sm font-medium transition-all"
              >
                {savingThresholds ? 'Saving...' : 'Save Settings'}
              </button>
            </div>

            {/* Price Move Threshold */}
            <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-orange-500/20 rounded-lg">
                  <TrendingUp className="w-5 h-5 text-orange-400" />
                </div>
                <div className="flex-1">
                  <h4 className="text-white font-semibold mb-1">Large Price Move</h4>
                  <p className="text-zinc-400 text-sm mb-4">
                    Alert when price moves ± <strong className="text-orange-400">{thresholds.priceMove}%</strong> in 1 hour
                  </p>
                  <input
                    type="range"
                    min={2}
                    max={10}
                    step={0.5}
                    value={thresholds.priceMove}
                    onChange={(e) => setThresholds(t => ({ ...t, priceMove: Number(e.target.value) }))}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
                  />
                  <div className="flex justify-between text-xs text-zinc-500 mt-2">
                    <span>2% (More alerts)</span>
                    <span>10% (Only big moves)</span>
                  </div>
                </div>
              </div>
            </div>

            {/* RSI Thresholds */}
            <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-blue-500/20 rounded-lg">
                  <BarChart3 className="w-5 h-5 text-blue-400" />
                </div>
                <div className="flex-1">
                  <h4 className="text-white font-semibold mb-1">RSI Extremes</h4>
                  <p className="text-zinc-400 text-sm mb-4">
                    Oversold: RSI below <strong className="text-blue-400">{thresholds.rsiOversold}</strong> | 
                    Overbought: RSI above <strong className="text-red-400">{thresholds.rsiOverbought}</strong>
                  </p>
                  <div className="space-y-4">
                    <div>
                      <label className="text-sm text-zinc-300 mb-2 block">Oversold Threshold</label>
                      <input
                        type="range"
                        min={15}
                        max={35}
                        value={thresholds.rsiOversold}
                        onChange={(e) => setThresholds(t => ({ ...t, rsiOversold: Number(e.target.value) }))}
                        className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-blue-500"
                      />
                      <div className="flex justify-between text-xs text-zinc-500 mt-1">
                        <span>15 (Extreme)</span>
                        <span>35 (Moderate)</span>
                      </div>
                    </div>
                    <div>
                      <label className="text-sm text-zinc-300 mb-2 block">Overbought Threshold</label>
                      <input
                        type="range"
                        min={65}
                        max={85}
                        value={thresholds.rsiOverbought}
                        onChange={(e) => setThresholds(t => ({ ...t, rsiOverbought: Number(e.target.value) }))}
                        className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-red-500"
                      />
                      <div className="flex justify-between text-xs text-zinc-500 mt-1">
                        <span>65 (Moderate)</span>
                        <span>85 (Extreme)</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Volume Spike Threshold */}
            <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-green-500/20 rounded-lg">
                  <Volume2 className="w-5 h-5 text-green-400" />
                </div>
                <div className="flex-1">
                  <h4 className="text-white font-semibold mb-1">Volume Spike</h4>
                  <p className="text-zinc-400 text-sm mb-4">
                    Alert when volume is <strong className="text-green-400">{thresholds.volumeSpike}x</strong> above average
                  </p>
                  <input
                    type="range"
                    min={2}
                    max={5}
                    step={0.5}
                    value={thresholds.volumeSpike}
                    onChange={(e) => setThresholds(t => ({ ...t, volumeSpike: Number(e.target.value) }))}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-green-500"
                  />
                  <div className="flex justify-between text-xs text-zinc-500 mt-2">
                    <span>2x (Sensitive)</span>
                    <span>5x (Only major spikes)</span>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Watching Coins */}
          <div className="bg-zinc-800/30 border border-zinc-700/50 rounded-xl p-6">
            <h4 className="text-white font-semibold mb-3">Monitoring {stats?.tracked_symbols || 10} Coins</h4>
            <div className="flex flex-wrap gap-2">
              {COINS.slice(0, 10).map(coin => (
                <span key={coin} className="px-3 py-1.5 bg-zinc-700/50 text-zinc-300 rounded-lg text-sm font-medium">
                  {coin}
                </span>
              ))}
            </div>
          </div>

          {/* Recent Smart Alerts */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-white font-semibold flex items-center gap-2">
                <Activity className="w-5 h-5 text-cyan-400" />
                Recent Smart Alerts
              </h3>
              {dashAlerts.filter(a => !a.read && a.type !== 'custom_price').length > 0 && (
                <button
                  onClick={clearAll}
                  className="text-sm text-zinc-500 hover:text-white transition-all"
                >
                  Clear All
                </button>
              )}
            </div>

            {dashAlerts.filter(a => a.type !== 'custom_price').length > 0 ? (
              <div className="space-y-2">
                {dashAlerts.filter(a => a.type !== 'custom_price').slice(0, 10).map(alert => (
                  <div
                    key={alert.id}
                    className={`border rounded-xl p-4 transition-all ${
                      alert.read
                        ? 'bg-zinc-800/20 border-zinc-700/30'
                        : 'bg-zinc-800/40 border-cyan-500/30'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="font-bold text-white">{alert.symbol}</span>
                          {alert.direction && (
                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                              alert.direction === 'LONG'
                                ? 'bg-green-500/20 text-green-400'
                                : 'bg-red-500/20 text-red-400'
                            }`}>
                              {alert.direction}
                            </span>
                          )}
                        </div>
                        <p className="text-zinc-300 text-sm mb-2">{alert.message}</p>
                        
                        {/* DETAILED REASONING */}
                        {alert.reasoning && (
                          <div className="mt-3 p-3 bg-zinc-900/50 rounded-lg border border-zinc-700/50">
                            <p className="text-xs text-zinc-400 mb-2 font-semibold">Why {alert.direction}:</p>
                            <p className="text-xs text-zinc-300">{alert.reasoning}</p>
                          </div>
                        )}
                        
                        {/* CONFIRMATIONS */}
                        {alert.confirmations && alert.confirmations.length > 0 && (
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {alert.confirmations.map((conf, idx) => (
                              <span key={idx} className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded text-xs">
                                ✓ {conf}
                              </span>
                            ))}
                          </div>
                        )}
                        
                        <p className="text-xs text-zinc-500 mt-2">
                          {new Date(alert.timestamp).toLocaleString()}
                        </p>
                      </div>
                      {!alert.read && (
                        <button
                          onClick={() => markAsRead(alert.id)}
                          className="p-2 hover:bg-zinc-700 rounded-lg text-cyan-400 hover:text-cyan-300 transition-all"
                        >
                          <CheckCircle className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="bg-zinc-800/20 border border-zinc-700/50 rounded-xl p-12 text-center">
                <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
                <h3 className="text-white font-semibold mb-2">No Smart Alerts Yet</h3>
                <p className="text-zinc-500 text-sm">
                  Aeon is monitoring {stats?.tracked_symbols || 10} coins for big moves, RSI extremes, and volume spikes
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
