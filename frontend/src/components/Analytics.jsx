import React, { useState, useEffect } from 'react';
import { Bell, TrendingUp, TrendingDown, Activity, Zap, Target, AlertCircle, Check, X, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Analytics() {
  const [alerts, setAlerts] = useState([]);
  const [alertStats, setAlertStats] = useState(null);
  const [strategies, setStrategies] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState('BTC');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('alerts');

  const symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX'];

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [selectedSymbol]);

  const fetchData = async () => {
    try {
      const [alertsRes, statsRes, strategiesRes] = await Promise.all([
        fetch(`${API_URL}/api/alerts/dashboard?limit=15`),
        fetch(`${API_URL}/api/alerts/stats`),
        fetch(`${API_URL}/api/strategies/all/${selectedSymbol}?timeframe=4h`)
      ]);
      
      const alertsData = await alertsRes.json();
      const statsData = await statsRes.json();
      const strategiesData = await strategiesRes.json();
      
      setAlerts(alertsData.alerts || []);
      setAlertStats(statsData);
      setStrategies(strategiesData);
    } catch (err) {
      console.error('Failed to fetch data:', err);
    }
    setLoading(false);
  };

  const markAsRead = async (dashboardId) => {
    try {
      await fetch(`${API_URL}/api/alerts/mark-read/${dashboardId}`, { method: 'POST' });
      setAlerts(alerts.map(a => a.dashboard_id === dashboardId ? { ...a, read: true } : a));
    } catch (err) {
      console.error('Failed to mark as read:', err);
    }
  };

  const clearAlerts = async () => {
    try {
      await fetch(`${API_URL}/api/alerts/clear`, { method: 'POST' });
      setAlerts([]);
    } catch (err) {
      console.error('Failed to clear alerts:', err);
    }
  };

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'high': return 'bg-red-500/20 text-red-400 border-red-500/30';
      case 'medium': return 'bg-orange-500/20 text-orange-400 border-orange-500/30';
      default: return 'bg-blue-500/20 text-blue-400 border-blue-500/30';
    }
  };

  const getSignalColor = (signal) => {
    if (signal === 'BUY' || signal === 'STRONG_BUY') return 'text-green-400';
    if (signal === 'SELL' || signal === 'STRONG_SELL') return 'text-red-400';
    return 'text-zinc-400';
  };

  const getSignalBg = (signal) => {
    if (signal === 'BUY' || signal === 'STRONG_BUY') return 'bg-green-500/20';
    if (signal === 'SELL' || signal === 'STRONG_SELL') return 'bg-red-500/20';
    return 'bg-zinc-700/50';
  };

  return (
    <div className="space-y-6" data-testid="analytics-page">
      {/* Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-500 text-xs">Alerts Today</p>
              <p className="text-2xl font-bold text-white">{alertStats?.alerts_today || 0}</p>
            </div>
            <Bell className="w-8 h-8 text-orange-400" />
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-500 text-xs">Unread</p>
              <p className="text-2xl font-bold text-orange-400">
                {alerts.filter(a => !a.read).length}
              </p>
            </div>
            <AlertCircle className="w-8 h-8 text-orange-400" />
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-500 text-xs">Symbols Tracked</p>
              <p className="text-2xl font-bold text-green-400">{alertStats?.tracked_symbols || 0}</p>
            </div>
            <Activity className="w-8 h-8 text-green-400" />
          </div>
        </div>
        
        <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-zinc-500 text-xs">Total Alerts</p>
              <p className="text-2xl font-bold text-blue-400">{alertStats?.total_alerts_sent || 0}</p>
            </div>
            <Zap className="w-8 h-8 text-blue-400" />
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['alerts', 'strategies'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
              data-testid={`tab-${t}`}
            >
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        
        {activeTab === 'strategies' && (
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
            data-testid="symbol-select"
          >
            {symbols.map(s => (
              <option key={s} value={s}>{s}/USDT</option>
            ))}
          </select>
        )}
        
        <button onClick={fetchData} className="flex items-center gap-2 px-3 py-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
        
        {activeTab === 'alerts' && alerts.length > 0 && (
          <button onClick={clearAlerts} className="flex items-center gap-2 px-3 py-2 bg-red-500/20 rounded-lg text-red-400 hover:bg-red-500/30 text-sm">
            Clear All
          </button>
        )}
      </div>

      {/* Alerts Tab */}
      {activeTab === 'alerts' && (
        <div className="space-y-3">
          {alerts.length === 0 ? (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Bell className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No alerts yet</p>
              <p className="text-zinc-600 text-sm">Price alerts will appear here when triggered</p>
            </div>
          ) : (
            alerts.map((alert, i) => (
              <div 
                key={alert.dashboard_id || i}
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  alert.read ? 'border-zinc-700/50 opacity-60' : getSeverityColor(alert.severity)
                }`}
                data-testid={`alert-${i}`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${getSeverityColor(alert.severity)}`}>
                        {alert.severity?.toUpperCase()}
                      </span>
                      <span className="text-orange-400 font-medium">{alert.symbol?.replace('/USDT', '')}</span>
                      <span className="text-zinc-500 text-xs">{alert.type?.replace('_', ' ')}</span>
                    </div>
                    <p className="text-zinc-300 text-sm whitespace-pre-line">{alert.message}</p>
                    <p className="text-zinc-600 text-xs mt-2">
                      {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : ''}
                    </p>
                  </div>
                  
                  {!alert.read && (
                    <button 
                      onClick={() => markAsRead(alert.dashboard_id)}
                      className="p-2 hover:bg-zinc-700/50 rounded-lg transition-colors"
                      title="Mark as read"
                    >
                      <Check className="w-4 h-4 text-green-400" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Strategies Tab */}
      {activeTab === 'strategies' && strategies && (
        <div className="space-y-6">
          {/* Overall Signal */}
          <div className={`rounded-xl p-6 border ${getSignalBg(strategies.overall_signal)} border-zinc-700/50`}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-400 text-sm mb-1">Overall Signal for {selectedSymbol}/USDT</p>
                <p className={`text-3xl font-bold ${getSignalColor(strategies.overall_signal)}`}>
                  {strategies.overall_signal || 'NEUTRAL'}
                </p>
              </div>
              <div className="text-right">
                <p className="text-zinc-500 text-xs">Avg Confidence</p>
                <p className="text-2xl font-bold text-white">{strategies.average_confidence || 50}%</p>
              </div>
            </div>
            
            <div className="flex items-center gap-6 mt-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-400" />
                <span className="text-green-400 font-medium">{strategies.buy_signals || 0} Buy</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-red-400" />
                <span className="text-red-400 font-medium">{strategies.sell_signals || 0} Sell</span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-5 h-5 text-zinc-400" />
                <span className="text-zinc-400 font-medium">{strategies.neutral_signals || 0} Neutral</span>
              </div>
            </div>
          </div>

          {/* Best Strategy */}
          {strategies.best_strategy && (
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-orange-500/30">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-5 h-5 text-orange-400" />
                <span className="text-orange-400 font-medium">Best Strategy</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-zinc-500 text-xs">Strategy</p>
                  <p className="text-white font-medium">{strategies.best_strategy.strategy?.replace('_', ' ')}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Signal</p>
                  <p className={`font-medium ${getSignalColor(strategies.best_strategy.signal)}`}>
                    {strategies.best_strategy.signal}
                  </p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Confidence</p>
                  <p className="text-white font-medium">{strategies.best_strategy.confidence}%</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Price</p>
                  <p className="text-white font-medium">${strategies.best_strategy.price?.toLocaleString()}</p>
                </div>
              </div>
              {strategies.best_strategy.explanation && (
                <p className="text-zinc-400 text-sm mt-3 border-t border-zinc-700 pt-3">
                  {strategies.best_strategy.explanation}
                </p>
              )}
            </div>
          )}

          {/* All Strategies */}
          <div className="grid md:grid-cols-2 gap-4">
            {strategies.strategies?.map((strat, i) => (
              <div 
                key={i}
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  strat.signal === 'BUY' ? 'border-green-500/30' :
                  strat.signal === 'SELL' ? 'border-red-500/30' :
                  'border-zinc-700/50'
                }`}
                data-testid={`strategy-${strat.strategy}`}
              >
                <div className="flex items-center justify-between mb-3">
                  <span className="text-white font-medium">{strat.strategy?.replace('_', ' ')}</span>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${getSignalBg(strat.signal)} ${getSignalColor(strat.signal)}`}>
                    {strat.signal}
                  </span>
                </div>
                
                <div className="grid grid-cols-3 gap-2 text-sm mb-3">
                  <div>
                    <p className="text-zinc-500 text-xs">Entry</p>
                    <p className="text-white">${strat.entry?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 text-xs">Stop</p>
                    <p className="text-red-400">${strat.stop?.toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-zinc-500 text-xs">Target</p>
                    <p className="text-green-400">${strat.target?.toLocaleString()}</p>
                  </div>
                </div>
                
                <div className="flex items-center justify-between">
                  <span className="text-zinc-500 text-xs">{strat.explanation}</span>
                  <span className="text-zinc-400 text-xs">{strat.confidence}% conf</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
