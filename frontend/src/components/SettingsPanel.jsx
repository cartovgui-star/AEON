import React, { useState, useEffect, useRef } from 'react';
import { 
  Settings, Save, RotateCcw, Bot, Bell, Volume2, Shield, Clock, TrendingUp, TrendingDown,
  User, Brain, Zap, Target, Mic, MicOff, Play, Loader2, Send, BarChart3,
  ChevronDown, ChevronUp, Info, AlertTriangle, CheckCircle2, Power,
  Sun, Calendar, RefreshCw
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    autoTraderEnabled: true,
    minConfidence: 85,
    freeWillEnabled: true,
    freeWillMinConf: 80,
    dayTraderEnabled: true,
    dayTraderConf: 75,
    longTermEnabled: true,
    longTermConf: 88,
    selectedVoice: 'guy',
    notifications: {
      tradeAlerts: true,
      priceAlerts: true,
      newsAlerts: true,
      marketUpdates: false,
      soundEnabled: true,
      browserNotifications: false
    }
  });
  const [freeWillStats, setFreeWillStats] = useState(null);
  const [dualStats, setDualStats] = useState(null);
  const [userProfile, setUserProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState('trading');
  const [tradingMode, setTradingMode] = useState('custom');
  const [expandedSections, setExpandedSections] = useState({
    autoTrader: true,
    dayTrader: true,
    longTerm: true,
    eliteAlerts: false,
    vwapScalper: false
  });

  // Trading mode presets
  const TRADING_MODES = {
    yolo: { name: 'YOLO', emoji: '🚀', conf: 50, confirms: 1, rr: 1.0, desc: 'MAX trading, no filters', color: 'purple' },
    easy: { name: 'Easy', emoji: '🟢', conf: 70, confirms: 2, rr: 1.5, desc: 'More trades, relaxed', color: 'green' },
    balanced: { name: 'Balanced', emoji: '🟡', conf: 80, confirms: 3, rr: 2.0, desc: 'Moderate filters', color: 'yellow' },
    strict: { name: 'Strict', emoji: '🟠', conf: 85, confirms: 4, rr: 2.5, desc: 'Fewer, better', color: 'orange' },
    elite: { name: 'Elite', emoji: '🔴', conf: 90, confirms: 5, rr: 3.0, desc: 'Ultra-selective', color: 'red' }
  };

  useEffect(() => {
    fetchSettings();
    fetchFreeWillStats();
    fetchDualStats();
    fetchUserProfile();
    fetchTradingMode();
  }, []);

  const fetchTradingMode = async () => {
    try {
      const res = await fetch(`${API_URL}/api/trading/modes`);
      if (res.ok) {
        const data = await res.json();
        setTradingMode(data.current_mode || 'custom');
      }
    } catch (err) {
      console.error('Failed to fetch trading mode:', err);
    }
  };

  const setMode = async (modeId) => {
    try {
      const res = await fetch(`${API_URL}/api/trading/mode/${modeId}`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setTradingMode(modeId);
        setSettings(s => ({
          ...s,
          minConfidence: data.settings_applied.min_confidence
        }));
        // Refresh settings
        fetchSettings();
      }
    } catch (err) {
      console.error('Failed to set mode:', err);
    }
  };

  const fetchSettings = async () => {
    try {
      const [tradingRes, freeWillRes, dualRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/freewill/stats`),
        fetch(`${API_URL}/api/dual/stats`)
      ]);
      const trading = await tradingRes.json();
      const freeWill = await freeWillRes.json();
      const dual = await dualRes.json();
      setSettings(s => ({
        ...s,
        autoTraderEnabled: trading.active ?? true,
        minConfidence: trading.min_confidence ?? 85,
        freeWillEnabled: freeWill.active ?? true,
        freeWillMinConf: freeWill.min_confidence ?? 80,
        dayTraderEnabled: dual.day_trader?.active ?? true,
        dayTraderConf: dual.day_trader?.min_confidence ?? 75,
        longTermEnabled: dual.long_term?.active ?? true,
        longTermConf: dual.long_term?.min_confidence ?? 88
      }));
    } catch (err) {
      console.error('Failed to fetch settings:', err);
    }
  };

  const fetchDualStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/dual/stats`);
      const data = await res.json();
      setDualStats(data);
    } catch (err) {
      console.error('Failed to fetch dual stats:', err);
    }
  };

  const fetchFreeWillStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/freewill/stats`);
      const data = await res.json();
      setFreeWillStats(data);
    } catch (err) {
      console.error('Failed to fetch free will stats:', err);
    }
  };

  const fetchUserProfile = async () => {
    try {
      const res = await fetch(`${API_URL}/api/user/profile`);
      if (res.ok) {
        const data = await res.json();
        setUserProfile(data);
      }
    } catch (err) {
      console.error('Failed to fetch user profile:', err);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await Promise.all([
        fetch(`${API_URL}/api/trading/toggle?active=${settings.autoTraderEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${settings.minConfidence}`, { method: 'POST' }),
        fetch(`${API_URL}/api/freewill/toggle?active=${settings.freeWillEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/freewill/confidence?min_conf=${settings.freeWillMinConf}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/day-trader/toggle?active=${settings.dayTraderEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/day-trader/confidence?min_conf=${settings.dayTraderConf}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/long-term/toggle?active=${settings.longTermEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/long-term/confidence?min_conf=${settings.longTermConf}`, { method: 'POST' })
      ]);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      fetchDualStats();
      fetchFreeWillStats();
    } catch (err) {
      console.error('Failed to save:', err);
    }
    setSaving(false);
  };

  const toggleSection = (section) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  const tabs = [
    { id: 'trading', label: 'Trading Engines', icon: Bot },
    { id: 'alerts', label: 'Alert System', icon: Bell },
    { id: 'briefing', label: 'Daily Briefing', icon: Sun },
    { id: 'weekly', label: 'Weekly Report', icon: Calendar },
    { id: 'profile', label: 'Profile', icon: User },
    { id: 'voice', label: 'Voice', icon: Volume2 }
  ];

  // Reusable Toggle Switch Component
  const ToggleSwitch = ({ enabled, onChange, color = 'orange' }) => {
    const colors = {
      orange: enabled ? 'bg-orange-500' : 'bg-zinc-700',
      yellow: enabled ? 'bg-yellow-500' : 'bg-zinc-700',
      blue: enabled ? 'bg-blue-500' : 'bg-zinc-700',
      green: enabled ? 'bg-green-500' : 'bg-zinc-700'
    };
    return (
      <button 
        onClick={onChange}
        className={`relative w-12 h-6 rounded-full transition-colors ${colors[color]}`}
      >
        <div className={`absolute top-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
          enabled ? 'left-6' : 'left-0.5'
        }`} />
      </button>
    );
  };

  // Confidence Slider Component
  const ConfidenceSlider = ({ value, onChange, min = 60, max = 95, color = 'orange' }) => {
    const colors = {
      orange: 'accent-orange-500',
      yellow: 'accent-yellow-500',
      blue: 'accent-blue-500'
    };
    const textColors = {
      orange: 'text-orange-400',
      yellow: 'text-yellow-400',
      blue: 'text-blue-400'
    };
    return (
      <div className="space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-zinc-400 text-sm">Min Confidence</span>
          <span className={`font-bold ${textColors[color]}`}>{value}%</span>
        </div>
        <input 
          type="range" 
          min={min} 
          max={max} 
          value={value}
          onChange={(e) => onChange(Number(e.target.value))}
          className={`w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer ${colors[color]}`}
        />
        <div className="flex justify-between text-xs text-zinc-600">
          <span>More trades</span>
          <span>Higher quality</span>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6" data-testid="settings-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-orange-400" />
          Settings
        </h2>
        <div className="flex gap-2">
          <button 
            onClick={fetchSettings} 
            className="px-3 py-2 bg-zinc-800 rounded-lg text-zinc-400 hover:text-white flex items-center gap-2 transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            <span className="hidden sm:inline">Refresh</span>
          </button>
          <button 
            onClick={saveSettings} 
            disabled={saving} 
            data-testid="save-settings-btn"
            className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 transition-all ${
              saved ? 'bg-green-500' : 'bg-orange-500 hover:bg-orange-600'
            } text-white`}
          >
            {saved ? <CheckCircle2 className="w-4 h-4" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 bg-zinc-800/30 p-1 rounded-xl overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            data-testid={`settings-tab-${tab.id}`}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 px-4 py-2.5 rounded-lg flex items-center justify-center gap-2 transition-all whitespace-nowrap ${
              activeTab === tab.id 
                ? 'bg-orange-500 text-white' 
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            <span className="text-sm font-medium">{tab.label}</span>
          </button>
        ))}
      </div>

      {/* Trading Engines Tab */}
      {activeTab === 'trading' && (
        <div className="space-y-4">
          {/* Paper Trading Notice */}
          <div className="flex items-center gap-3 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
            <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0" />
            <p className="text-yellow-200 text-sm">
              <span className="font-semibold">Paper Trading Mode</span> - Using live MEXC data for simulated trades. No real money at risk.
            </p>
          </div>

          {/* Trading Mode Selector */}
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 p-4">
            <h3 className="text-white font-semibold mb-3 flex items-center gap-2">
              <Settings className="w-4 h-4 text-orange-400" />
              Trading Mode
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(TRADING_MODES).map(([modeId, mode]) => (
                <button
                  key={modeId}
                  onClick={() => setMode(modeId)}
                  data-testid={`mode-${modeId}-btn`}
                  className={`p-3 rounded-lg border transition-all text-left ${
                    tradingMode === modeId
                      ? `bg-${mode.color}-500/20 border-${mode.color}-500/50 ring-1 ring-${mode.color}-500/50`
                      : 'bg-zinc-800/50 border-zinc-700/50 hover:border-zinc-600'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-lg">{mode.emoji}</span>
                    <span className={`font-medium ${tradingMode === modeId ? 'text-white' : 'text-zinc-300'}`}>
                      {mode.name}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-500">{mode.desc}</p>
                  <div className="mt-2 text-xs text-zinc-400">
                    {mode.conf}% conf • {mode.confirms} confirms
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Autonomous Trader v2 */}
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <button 
              onClick={() => toggleSection('autoTrader')}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${settings.autoTraderEnabled ? 'bg-orange-500/20' : 'bg-zinc-700/50'}`}>
                  <Bot className={`w-5 h-5 ${settings.autoTraderEnabled ? 'text-orange-400' : 'text-zinc-500'}`} />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-white">Autonomous Trader v2</h3>
                  <p className="text-xs text-zinc-500">Main trading engine with SMC analysis</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-2 py-1 rounded text-xs font-medium ${
                  settings.autoTraderEnabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
                }`}>
                  {settings.autoTraderEnabled ? 'ACTIVE' : 'PAUSED'}
                </span>
                {expandedSections.autoTrader ? <ChevronUp className="w-5 h-5 text-zinc-400" /> : <ChevronDown className="w-5 h-5 text-zinc-400" />}
              </div>
            </button>
            
            {expandedSections.autoTrader && (
              <div className="px-5 pb-5 space-y-4 border-t border-zinc-700/50 pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-medium">Enable Trading</p>
                    <p className="text-zinc-500 text-xs">Auto-execute trades based on signals</p>
                  </div>
                  <ToggleSwitch 
                    enabled={settings.autoTraderEnabled} 
                    onChange={() => setSettings(s => ({ ...s, autoTraderEnabled: !s.autoTraderEnabled }))}
                  />
                </div>
                <ConfidenceSlider 
                  value={settings.minConfidence}
                  onChange={(val) => setSettings(s => ({ ...s, minConfidence: val }))}
                  min={70}
                  max={95}
                />
              </div>
            )}
          </div>

          {/* Dual Strategy Engines */}
          <div className="grid md:grid-cols-2 gap-4">
            {/* Day Trader */}
            <div className="bg-zinc-800/30 rounded-xl border border-yellow-500/30 overflow-hidden">
              <button 
                onClick={() => toggleSection('dayTrader')}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${settings.dayTraderEnabled ? 'bg-yellow-500/20' : 'bg-zinc-700/50'}`}>
                    <Zap className={`w-5 h-5 ${settings.dayTraderEnabled ? 'text-yellow-400' : 'text-zinc-500'}`} />
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold text-white">Day Trader</h3>
                    <p className="text-xs text-zinc-500">Aggressive scalps & swings</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    settings.dayTraderEnabled ? 'bg-yellow-500/20 text-yellow-400' : 'bg-zinc-700 text-zinc-400'
                  }`}>
                    {settings.dayTraderEnabled ? 'ON' : 'OFF'}
                  </span>
                  {expandedSections.dayTrader ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
                </div>
              </button>
              
              {expandedSections.dayTrader && (
                <div className="px-5 pb-5 space-y-4 border-t border-yellow-500/20 pt-4">
                  <div className="flex items-center justify-between">
                    <span className="text-white text-sm">Enable</span>
                    <ToggleSwitch 
                      enabled={settings.dayTraderEnabled} 
                      onChange={() => setSettings(s => ({ ...s, dayTraderEnabled: !s.dayTraderEnabled }))}
                      color="yellow"
                    />
                  </div>
                  <ConfidenceSlider 
                    value={settings.dayTraderConf}
                    onChange={(val) => setSettings(s => ({ ...s, dayTraderConf: val }))}
                    min={65}
                    max={90}
                    color="yellow"
                  />
                  {dualStats?.day_trader && (
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-700/50">
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.day_trader.daily_alerts}</p>
                        <p className="text-xs text-zinc-500">Today</p>
                      </div>
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.day_trader.setups_analyzed}</p>
                        <p className="text-xs text-zinc-500">Analyzed</p>
                      </div>
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.day_trader.direction_lock_hours}h</p>
                        <p className="text-xs text-zinc-500">Lock</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Long Term */}
            <div className="bg-zinc-800/30 rounded-xl border border-blue-500/30 overflow-hidden">
              <button 
                onClick={() => toggleSection('longTerm')}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-lg ${settings.longTermEnabled ? 'bg-blue-500/20' : 'bg-zinc-700/50'}`}>
                    <Target className={`w-5 h-5 ${settings.longTermEnabled ? 'text-blue-400' : 'text-zinc-500'}`} />
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold text-white">Long Term</h3>
                    <p className="text-xs text-zinc-500">Position trades on HTF</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${
                    settings.longTermEnabled ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-700 text-zinc-400'
                  }`}>
                    {settings.longTermEnabled ? 'ON' : 'OFF'}
                  </span>
                  {expandedSections.longTerm ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
                </div>
              </button>
              
              {expandedSections.longTerm && (
                <div className="px-5 pb-5 space-y-4 border-t border-blue-500/20 pt-4">
                  <div className="flex items-center justify-between">
                    <span className="text-white text-sm">Enable</span>
                    <ToggleSwitch 
                      enabled={settings.longTermEnabled} 
                      onChange={() => setSettings(s => ({ ...s, longTermEnabled: !s.longTermEnabled }))}
                      color="blue"
                    />
                  </div>
                  <ConfidenceSlider 
                    value={settings.longTermConf}
                    onChange={(val) => setSettings(s => ({ ...s, longTermConf: val }))}
                    min={80}
                    max={95}
                    color="blue"
                  />
                  {dualStats?.long_term && (
                    <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-700/50">
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.long_term.daily_alerts}</p>
                        <p className="text-xs text-zinc-500">Today</p>
                      </div>
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.long_term.setups_analyzed}</p>
                        <p className="text-xs text-zinc-500">Analyzed</p>
                      </div>
                      <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                        <p className="text-lg font-bold text-white">{dualStats.long_term.direction_lock_hours}h</p>
                        <p className="text-xs text-zinc-500">Lock</p>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* VWAP Scalper */}
            <div className="bg-zinc-800/30 rounded-xl border border-cyan-500/30 overflow-hidden">
              <button 
                onClick={() => toggleSection('vwapScalper')}
                className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-cyan-500/20">
                    <TrendingUp className="w-5 h-5 text-cyan-400" />
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold text-white">VWAP Scalper</h3>
                    <p className="text-xs text-zinc-500">VWAP + EMA Cross + RSI</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded text-xs bg-cyan-500/20 text-cyan-400">NEW</span>
                  {expandedSections.vwapScalper ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
                </div>
              </button>
              
              {expandedSections.vwapScalper && (
                <div className="px-5 pb-5 space-y-4 border-t border-cyan-500/20 pt-4">
                  <div className="text-sm text-zinc-400 bg-zinc-900/50 p-3 rounded-lg">
                    <p className="text-cyan-400 font-medium mb-2">Strategy Logic:</p>
                    <ul className="space-y-1 text-xs">
                      <li>• LONG: EMA9 crosses above EMA21 + Price &gt; VWAP + RSI 50-70</li>
                      <li>• SHORT: EMA9 crosses below EMA21 + Price &lt; VWAP + RSI 30-50</li>
                      <li>• Risk: 0.3% SL / 0.6% TP (2:1 R:R)</li>
                      <li>• Timeframe: 5-minute candles</li>
                      <li>• Data: yfinance (real market data)</li>
                    </ul>
                  </div>
                  <div className="grid grid-cols-3 gap-2 pt-2">
                    <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                      <p className="text-lg font-bold text-cyan-400">EMA 9/21</p>
                      <p className="text-xs text-zinc-500">Cross</p>
                    </div>
                    <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                      <p className="text-lg font-bold text-cyan-400">VWAP</p>
                      <p className="text-xs text-zinc-500">Filter</p>
                    </div>
                    <div className="text-center p-2 bg-zinc-900/50 rounded-lg">
                      <p className="text-lg font-bold text-cyan-400">RSI 14</p>
                      <p className="text-xs text-zinc-500">Confirm</p>
                    </div>
                  </div>
                  <p className="text-xs text-zinc-500 text-center">
                    Scans every 5 minutes • Uses Telegram: /vwap
                  </p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Alert System Tab */}
      {activeTab === 'alerts' && (
        <div className="space-y-4">
          {/* Elite Alerts (Legacy) */}
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <button 
              onClick={() => toggleSection('eliteAlerts')}
              className="w-full flex items-center justify-between px-5 py-4 hover:bg-zinc-800/30 transition-colors"
            >
              <div className="flex items-center gap-3">
                <div className={`p-2 rounded-lg ${settings.freeWillEnabled ? 'bg-orange-500/20' : 'bg-zinc-700/50'}`}>
                  <Bell className={`w-5 h-5 ${settings.freeWillEnabled ? 'text-orange-400' : 'text-zinc-500'}`} />
                </div>
                <div className="text-left">
                  <h3 className="font-semibold text-white">Elite Alerts</h3>
                  <p className="text-xs text-zinc-500">High-confidence trade signals</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-xs ${
                  settings.freeWillEnabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
                }`}>
                  {settings.freeWillEnabled ? 'ACTIVE' : 'PAUSED'}
                </span>
                {expandedSections.eliteAlerts ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
              </div>
            </button>
            
            {expandedSections.eliteAlerts && (
              <div className="px-5 pb-5 space-y-4 border-t border-zinc-700/50 pt-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-white font-medium">Enable Alerts</p>
                    <p className="text-zinc-500 text-xs">Receive LONG/SHORT signals</p>
                  </div>
                  <ToggleSwitch 
                    enabled={settings.freeWillEnabled} 
                    onChange={() => setSettings(s => ({ ...s, freeWillEnabled: !s.freeWillEnabled }))}
                  />
                </div>
                <ConfidenceSlider 
                  value={settings.freeWillMinConf}
                  onChange={(val) => setSettings(s => ({ ...s, freeWillMinConf: val }))}
                  min={65}
                  max={95}
                />
              </div>
            )}
          </div>

          {/* Alert Stats Dashboard */}
          {freeWillStats && (
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
                <Shield className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white">Alert Statistics</h3>
              </div>
              <div className="p-5 space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-white">{freeWillStats.daily_alerts}</p>
                    <p className="text-xs text-zinc-500">Today's Alerts</p>
                    <p className="text-xs text-zinc-600">Max: {freeWillStats.max_daily_alerts}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-orange-400">{freeWillStats.total_alerts_sent}</p>
                    <p className="text-xs text-zinc-500">Total Sent</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-green-400">{freeWillStats.contradictions_blocked}</p>
                    <p className="text-xs text-zinc-500">Blocked</p>
                    <p className="text-xs text-zinc-600">Contradictions</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
                    <p className="text-2xl font-bold text-blue-400">{freeWillStats.pairs_monitored}</p>
                    <p className="text-xs text-zinc-500">Pairs</p>
                  </div>
                </div>
                
                <div className="flex flex-wrap gap-3 pt-2">
                  <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900/50 rounded-lg">
                    <Clock className="w-4 h-4 text-zinc-500" />
                    <span className="text-zinc-300 text-sm">{freeWillStats.alert_cooldown_mins}min cooldown</span>
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 bg-zinc-900/50 rounded-lg">
                    <Shield className="w-4 h-4 text-zinc-500" />
                    <span className="text-zinc-300 text-sm">{freeWillStats.direction_lock_hours}h direction lock</span>
                  </div>
                </div>

                {/* Recent Signal Directions */}
                {freeWillStats.recent_directions && Object.keys(freeWillStats.recent_directions).length > 0 && (
                  <div className="pt-3 border-t border-zinc-700/50">
                    <p className="text-sm text-zinc-400 mb-2">Recent Directions (locked)</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(freeWillStats.recent_directions).map(([symbol, dir]) => (
                        <span key={symbol} className={`px-3 py-1.5 rounded-lg text-xs font-medium ${
                          dir === 'LONG' ? 'bg-green-500/20 text-green-400 border border-green-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'
                        }`}>
                          {symbol.replace('/USDT', '')}: {dir}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Data Sources */}
          {freeWillStats && (
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
                <Brain className="w-5 h-5 text-purple-400" />
                <h3 className="font-semibold text-white">Data Sources</h3>
                <span className="ml-auto px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">{freeWillStats.data_sources?.length || 0} active</span>
              </div>
              <div className="p-5">
                <div className="flex flex-wrap gap-2">
                  {freeWillStats.data_sources?.map((source, i) => (
                    <div key={i} className="flex items-center gap-2 px-3 py-2 bg-zinc-900/50 rounded-lg border border-zinc-700/50">
                      <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                      <span className="text-sm text-zinc-300">{source}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-zinc-500 mt-4">
                  Monitoring on {freeWillStats.timeframes?.join(', ')} timeframes
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Daily Briefing Tab */}
      {activeTab === 'briefing' && (
        <MorningBriefingTab />
      )}

      {/* Weekly Report Tab */}
      {activeTab === 'weekly' && (
        <WeeklyReportTab />
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
              <User className="w-5 h-5 text-orange-400" />
              <h3 className="font-semibold text-white">Your Profile</h3>
            </div>
            <div className="p-5">
              {userProfile ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                    <span className="text-zinc-400">Trading Style</span>
                    <span className="text-white font-medium">{userProfile.trading_style || 'Learning...'}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                    <span className="text-zinc-400">Risk Tolerance</span>
                    <span className={`font-medium px-2 py-0.5 rounded ${
                      userProfile.risk_tolerance === 'high' ? 'bg-red-500/20 text-red-400' :
                      userProfile.risk_tolerance === 'medium' ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'
                    }`}>{userProfile.risk_tolerance || 'Unknown'}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                    <span className="text-zinc-400">Favorite Coins</span>
                    <span className="text-orange-400 text-sm">{userProfile.favorite_coins?.join(', ') || 'None yet'}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                    <span className="text-zinc-400">Messages</span>
                    <span className="text-white">{userProfile.messages_analyzed || 0} analyzed</span>
                  </div>
                </div>
              ) : (
                <div className="text-center py-8">
                  <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
                  <p className="text-zinc-400">Learning your preferences...</p>
                  <p className="text-sm text-zinc-500 mt-2">Chat more to build your profile!</p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
              <Brain className="w-5 h-5 text-purple-400" />
              <h3 className="font-semibold text-white">Aeon's Understanding</h3>
            </div>
            <div className="p-5">
              <p className="text-zinc-400 text-sm mb-4">
                Aeon learns from your conversations to personalize responses.
              </p>
              <div className="space-y-2">
                {[
                  'Tracks coins you ask about most',
                  'Learns your risk preferences',
                  'Adapts communication style',
                  'Remembers trading history'
                ].map((item, i) => (
                  <div key={i} className="flex items-center gap-2 p-2 text-sm text-zinc-300">
                    <CheckCircle2 className="w-4 h-4 text-green-400" />
                    {item}
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Voice Tab */}
      {activeTab === 'voice' && (
        <VoiceTab settings={settings} setSettings={setSettings} />
      )}
    </div>
  );
}

// Voice Tab Component
function VoiceTab({ settings, setSettings }) {
  const [message, setMessage] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [aeonResponse, setAeonResponse] = useState('');
  const [error, setError] = useState('');
  const audioRef = useRef(null);
  const recognitionRef = useRef(null);

  const voices = [
    { id: 'guy', name: 'Guy', desc: 'Confident & calm' },
    { id: 'davis', name: 'Davis', desc: 'Professional' },
    { id: 'british', name: 'British', desc: 'Sophisticated' },
    { id: 'australian', name: 'Australian', desc: 'Friendly' }
  ];

  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const current = event.resultIndex;
        const text = event.results[current][0].transcript;
        setTranscript(text);
        if (event.results[current].isFinal) {
          setMessage(text);
        }
      };

      recognitionRef.current.onend = () => setIsListening(false);
      recognitionRef.current.onerror = () => {
        setIsListening(false);
        setError('Speech recognition error. Please try again.');
      };
    }
  }, []);

  const toggleListening = () => {
    if (isListening) {
      recognitionRef.current?.stop();
      setIsListening(false);
    } else {
      setTranscript('');
      setError('');
      recognitionRef.current?.start();
      setIsListening(true);
    }
  };

  const sendMessage = async () => {
    if (!message.trim()) return;
    setIsLoading(true);
    setError('');
    setAeonResponse('');

    try {
      const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/voice/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: message, voice: settings.selectedVoice })
      });
      const data = await res.json();

      if (data.error) {
        setError(data.error);
      } else {
        setAeonResponse(data.text);
        if (data.audio) {
          const audioBlob = new Blob(
            [Uint8Array.from(atob(data.audio), c => c.charCodeAt(0))],
            { type: 'audio/mp3' }
          );
          const audioUrl = URL.createObjectURL(audioBlob);
          if (audioRef.current) {
            audioRef.current.src = audioUrl;
            audioRef.current.play();
            setIsPlaying(true);
            audioRef.current.onended = () => {
              setIsPlaying(false);
              URL.revokeObjectURL(audioUrl);
            };
          }
        }
      }
    } catch {
      setError('Failed to connect to Aeon. Please try again.');
    }
    setIsLoading(false);
  };

  return (
    <div className="space-y-4">
      {/* Voice Selection */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
          <Volume2 className="w-5 h-5 text-orange-400" />
          <h3 className="font-semibold text-white">Voice Selection</h3>
        </div>
        <div className="p-5">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {voices.map(v => (
              <button 
                key={v.id} 
                onClick={() => setSettings(s => ({ ...s, selectedVoice: v.id }))}
                data-testid={`voice-option-${v.id}`}
                className={`p-3 rounded-xl border text-left transition-all ${
                  settings.selectedVoice === v.id 
                    ? 'border-orange-500 bg-orange-500/10' 
                    : 'border-zinc-700 hover:border-zinc-600'
                }`}
              >
                <p className={`font-medium text-sm ${settings.selectedVoice === v.id ? 'text-orange-400' : 'text-white'}`}>
                  {v.name}
                </p>
                <p className="text-xs text-zinc-500">{v.desc}</p>
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Voice Chat */}
      <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
          <Mic className="w-5 h-5 text-orange-400" />
          <h3 className="font-semibold text-white">Talk to Aeon</h3>
          <span className="ml-auto px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">LIVE</span>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex gap-2">
            <input
              type="text"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
              placeholder={isListening ? 'Listening...' : 'Type or speak...'}
              data-testid="voice-input"
              className="flex-1 px-4 py-3 bg-zinc-900/50 border border-zinc-700 rounded-xl text-white placeholder-zinc-500 focus:border-orange-500 focus:outline-none"
            />
            <button
              onClick={toggleListening}
              data-testid="voice-mic-button"
              disabled={!recognitionRef.current}
              className={`p-3 rounded-xl transition-all ${
                isListening ? 'bg-red-500 text-white animate-pulse' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'
              }`}
            >
              {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
            </button>
            <button
              onClick={sendMessage}
              disabled={!message.trim() || isLoading}
              data-testid="voice-send-button"
              className={`px-4 rounded-xl flex items-center gap-2 transition-all ${
                message.trim() && !isLoading ? 'bg-orange-500 text-white hover:bg-orange-600' : 'bg-zinc-700 text-zinc-500'
              }`}
            >
              {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </button>
          </div>

          {error && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-sm">
              {error}
            </div>
          )}

          {aeonResponse && (
            <div className="p-4 bg-zinc-900/50 border border-zinc-700 rounded-xl">
              <div className="flex items-start gap-3">
                <div className="w-8 h-8 rounded-full bg-orange-500/20 flex items-center justify-center flex-shrink-0">
                  <Bot className="w-4 h-4 text-orange-400" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-zinc-400 mb-1">Aeon says:</p>
                  <p className="text-white">{aeonResponse}</p>
                </div>
                <button
                  onClick={() => audioRef.current?.play()}
                  disabled={isPlaying}
                  data-testid="voice-play-button"
                  className={`p-2 rounded-lg ${isPlaying ? 'bg-orange-500/20 text-orange-400' : 'bg-zinc-700 text-zinc-300 hover:bg-zinc-600'}`}
                >
                  {isPlaying ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                </button>
              </div>
            </div>
          )}

          <audio ref={audioRef} className="hidden" />
          <p className="text-xs text-zinc-500">Click the microphone to speak, or type your message.</p>
        </div>
      </div>
    </div>
  );
}

// Morning Briefing Tab Component
function MorningBriefingTab() {
  const [status, setStatus] = useState(null);
  const [preview, setPreview] = useState(null);
  const [movers, setMovers] = useState(null);
  const [setups, setSetups] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [testSent, setTestSent] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    fetchStatus();
    fetchMovers();
    fetchSetups();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/briefing/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch briefing status:', err);
    }
  };

  const fetchMovers = async () => {
    try {
      const res = await fetch(`${API_URL}/api/briefing/movers`);
      const data = await res.json();
      setMovers(data);
    } catch (err) {
      console.error('Failed to fetch movers:', err);
    }
  };

  const fetchSetups = async () => {
    try {
      const res = await fetch(`${API_URL}/api/briefing/setups`);
      const data = await res.json();
      setSetups(data.setups || []);
    } catch (err) {
      console.error('Failed to fetch setups:', err);
    }
  };

  const fetchPreview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/briefing/preview`);
      const data = await res.json();
      setPreview(data.preview);
    } catch (err) {
      console.error('Failed to fetch preview:', err);
    }
    setLoading(false);
  };

  const sendTestBriefing = async () => {
    setSendingTest(true);
    try {
      await fetch(`${API_URL}/api/briefing/test`, { method: 'POST' });
      setTestSent(true);
      setTimeout(() => setTestSent(false), 5000);
    } catch (err) {
      console.error('Failed to send test:', err);
    }
    setSendingTest(false);
  };

  return (
    <div className="space-y-4">
      {/* Briefing Status */}
      <div className="bg-zinc-800/30 rounded-xl border border-amber-500/30 overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-amber-500/20">
          <Sun className="w-5 h-5 text-amber-400" />
          <h3 className="font-semibold text-white">Morning Briefing</h3>
          <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
            status?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
          }`}>
            {status?.enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between p-4 bg-zinc-900/50 rounded-xl">
            <div>
              <p className="text-white font-medium">Daily Market Overview</p>
              <p className="text-zinc-500 text-sm">Sent every day at 6:00 AM Central Time (Austin, TX)</p>
            </div>
            <div className="text-right">
              <p className="text-amber-400 font-bold">{status?.scheduled_time}</p>
              <p className="text-xs text-zinc-500">{status?.timezone}</p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-zinc-900/50 rounded-lg text-center">
              <p className="text-sm text-zinc-400">Current Time (CT)</p>
              <p className="text-white font-medium">{status?.current_time_ct?.split(' ')[1]}</p>
            </div>
            <div className="p-3 bg-zinc-900/50 rounded-lg text-center">
              <p className="text-sm text-zinc-400">Next Briefing</p>
              <p className="text-amber-400 font-medium">{status?.next_briefing?.split(' ')[1]}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={fetchPreview}
              disabled={loading}
              data-testid="briefing-preview-btn"
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-white transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Preview Today's Briefing
            </button>
            <button
              onClick={sendTestBriefing}
              disabled={sendingTest}
              data-testid="briefing-send-test-btn"
              className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-colors ${
                testSent ? 'bg-green-500 text-white' : 'bg-amber-500 hover:bg-amber-600 text-white'
              }`}
            >
              {sendingTest ? <Loader2 className="w-4 h-4 animate-spin" /> : testSent ? <CheckCircle2 className="w-4 h-4" /> : <Send className="w-4 h-4" />}
              {testSent ? 'Sent!' : 'Send Now'}
            </button>
          </div>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
            <Calendar className="w-5 h-5 text-amber-400" />
            <h3 className="font-semibold text-white">Briefing Preview</h3>
          </div>
          <div className="p-5">
            <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-mono bg-zinc-900/50 p-4 rounded-xl max-h-96 overflow-y-auto">
              {preview}
            </pre>
          </div>
        </div>
      )}

      {/* Live Data Cards */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Overnight Movers */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
            <TrendingUp className="w-5 h-5 text-green-400" />
            <h3 className="font-semibold text-white">Overnight Movers</h3>
          </div>
          <div className="p-5 space-y-3">
            {movers?.losers?.length > 0 && (
              <div>
                <p className="text-xs text-zinc-500 mb-2">Biggest Losers</p>
                {movers.losers.slice(0, 3).map((coin, i) => (
                  <div key={i} className="flex items-center justify-between py-1">
                    <span className="text-white">{coin.symbol}</span>
                    <span className="text-red-400 font-medium">{coin.change_24h}%</span>
                  </div>
                ))}
              </div>
            )}
            {movers?.gainers?.length > 0 && (
              <div>
                <p className="text-xs text-zinc-500 mb-2">Biggest Gainers</p>
                {movers.gainers.slice(0, 3).map((coin, i) => (
                  <div key={i} className="flex items-center justify-between py-1">
                    <span className="text-white">{coin.symbol}</span>
                    <span className="text-green-400 font-medium">+{coin.change_24h}%</span>
                  </div>
                ))}
              </div>
            )}
            {!movers?.losers?.length && !movers?.gainers?.length && (
              <p className="text-zinc-500 text-center py-4">No significant moves</p>
            )}
          </div>
        </div>

        {/* Setups to Watch */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
            <Target className="w-5 h-5 text-purple-400" />
            <h3 className="font-semibold text-white">Setups to Watch</h3>
          </div>
          <div className="p-5 space-y-2">
            {setups?.length > 0 ? setups.slice(0, 4).map((setup, i) => (
              <div key={i} className="flex items-center justify-between p-2 bg-zinc-900/50 rounded-lg">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 rounded-full ${
                    setup.direction === 'LONG' ? 'bg-green-400' : setup.direction === 'SHORT' ? 'bg-red-400' : 'bg-yellow-400'
                  }`} />
                  <span className="text-white font-medium">{setup.symbol}</span>
                </div>
                <div className="text-right">
                  <p className="text-xs text-zinc-400">{setup.setup}</p>
                  <p className="text-xs text-zinc-500">RSI: {setup.rsi}</p>
                </div>
              </div>
            )) : (
              <p className="text-zinc-500 text-center py-4">No setups identified</p>
            )}
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="flex items-start gap-3 p-4 bg-amber-500/10 border border-amber-500/30 rounded-xl">
        <Info className="w-5 h-5 text-amber-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-amber-200">
          <p className="font-medium mb-1">What's included in the briefing?</p>
          <ul className="text-amber-200/80 space-y-1">
            <li>• BTC & ETH market structure and trend analysis</li>
            <li>• Fear & Greed Index with actionable insights</li>
            <li>• Overnight price movers (gainers/losers)</li>
            <li>• Top setups to watch for the day</li>
            <li>• Key support/resistance levels</li>
          </ul>
        </div>
      </div>
    </div>
  );
}


// Weekly Report Tab Component
function WeeklyReportTab() {
  const [status, setStatus] = useState(null);
  const [preview, setPreview] = useState(null);
  const [strategyStats, setStrategyStats] = useState(null);
  const [coinPerformance, setCoinPerformance] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sendingTest, setSendingTest] = useState(false);
  const [testSent, setTestSent] = useState(false);

  const API_URL = process.env.REACT_APP_BACKEND_URL;

  useEffect(() => {
    fetchStatus();
    fetchStrategyStats();
    fetchCoinPerformance();
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${API_URL}/api/report/status`);
      const data = await res.json();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch report status:', err);
    }
  };

  const fetchStrategyStats = async () => {
    try {
      const res = await fetch(`${API_URL}/api/report/strategy-stats`);
      const data = await res.json();
      setStrategyStats(data);
    } catch (err) {
      console.error('Failed to fetch strategy stats:', err);
    }
  };

  const fetchCoinPerformance = async () => {
    try {
      const res = await fetch(`${API_URL}/api/report/coin-performance`);
      const data = await res.json();
      setCoinPerformance(data);
    } catch (err) {
      console.error('Failed to fetch coin performance:', err);
    }
  };

  const fetchPreview = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_URL}/api/report/preview`);
      const data = await res.json();
      setPreview(data.preview);
    } catch (err) {
      console.error('Failed to fetch preview:', err);
    }
    setLoading(false);
  };

  const sendTestReport = async () => {
    setSendingTest(true);
    try {
      await fetch(`${API_URL}/api/report/test`, { method: 'POST' });
      setTestSent(true);
      setTimeout(() => setTestSent(false), 5000);
    } catch (err) {
      console.error('Failed to send test:', err);
    }
    setSendingTest(false);
  };

  return (
    <div className="space-y-4">
      {/* Report Status */}
      <div className="bg-zinc-800/30 rounded-xl border border-blue-500/30 overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-blue-500/20">
          <BarChart3 className="w-5 h-5 text-blue-400" />
          <h3 className="font-semibold text-white">Weekly Performance Report</h3>
          <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
            status?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
          }`}>
            {status?.enabled ? 'ACTIVE' : 'PAUSED'}
          </span>
        </div>
        <div className="p-5 space-y-4">
          <div className="flex items-center justify-between p-4 bg-zinc-900/50 rounded-xl">
            <div>
              <p className="text-white font-medium">Trading Performance Summary</p>
              <p className="text-zinc-500 text-sm">Sent every {status?.scheduled_day} at {status?.scheduled_time}</p>
            </div>
            <div className="text-right">
              <p className="text-blue-400 font-bold">{status?.scheduled_day} {status?.scheduled_time}</p>
              <p className="text-xs text-zinc-500">{status?.timezone}</p>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div className="p-3 bg-zinc-900/50 rounded-lg text-center">
              <p className="text-sm text-zinc-400">Trades This Week</p>
              <p className="text-xl font-bold text-white">{status?.trades_this_week || 0}</p>
            </div>
            <div className="p-3 bg-zinc-900/50 rounded-lg text-center">
              <p className="text-sm text-zinc-400">Next Report</p>
              <p className="text-blue-400 font-medium text-sm">{status?.next_report?.split(' ')[0] || '-'}</p>
            </div>
            <div className="p-3 bg-zinc-900/50 rounded-lg text-center">
              <p className="text-sm text-zinc-400">Recipients</p>
              <p className="text-xl font-bold text-white">{status?.active_users || 0}</p>
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={fetchPreview}
              disabled={loading}
              data-testid="report-preview-btn"
              className="flex-1 flex items-center justify-center gap-2 px-4 py-3 bg-zinc-700 hover:bg-zinc-600 rounded-xl text-white transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <RefreshCw className="w-4 h-4" />}
              Preview This Week's Report
            </button>
            <button
              onClick={sendTestReport}
              disabled={sendingTest}
              data-testid="report-send-test-btn"
              className={`flex items-center justify-center gap-2 px-4 py-3 rounded-xl transition-colors ${
                testSent ? 'bg-green-500 text-white' : 'bg-blue-500 hover:bg-blue-600 text-white'
              }`}
            >
              {sendingTest ? <Loader2 className="w-4 h-4 animate-spin" /> : testSent ? <CheckCircle2 className="w-4 h-4" /> : <Send className="w-4 h-4" />}
              {testSent ? 'Sent!' : 'Send Now'}
            </button>
          </div>
        </div>
      </div>

      {/* Preview */}
      {preview && (
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
            <Calendar className="w-5 h-5 text-blue-400" />
            <h3 className="font-semibold text-white">Report Preview</h3>
          </div>
          <div className="p-5">
            <pre className="whitespace-pre-wrap text-sm text-zinc-300 font-mono bg-zinc-900/50 p-4 rounded-xl max-h-96 overflow-y-auto">
              {preview}
            </pre>
          </div>
        </div>
      )}

      {/* Strategy Performance */}
      {strategyStats?.strategies && Object.keys(strategyStats.strategies).length > 0 && (
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4 border-b border-zinc-700/50">
            <Target className="w-5 h-5 text-purple-400" />
            <h3 className="font-semibold text-white">Strategy Performance (This Week)</h3>
          </div>
          <div className="p-5 space-y-3">
            {Object.entries(strategyStats.strategies).map(([name, stats]) => (
              <div key={name} className="flex items-center justify-between p-3 bg-zinc-900/50 rounded-lg">
                <div>
                  <p className="text-white font-medium">{name}</p>
                  <p className="text-xs text-zinc-500">{stats.total_trades} trades</p>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-center">
                    <p className={`text-sm font-medium ${stats.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
                      {stats.win_rate}%
                    </p>
                    <p className="text-xs text-zinc-500">Win Rate</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-sm font-medium ${stats.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {stats.total_pnl > 0 ? '+' : ''}{stats.total_pnl}%
                    </p>
                    <p className="text-xs text-zinc-500">PnL</p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Info */}
      <div className="flex items-start gap-3 p-4 bg-blue-500/10 border border-blue-500/30 rounded-xl">
        <Info className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" />
        <div className="text-sm text-blue-200">
          <p className="font-medium mb-1">What's included in the weekly report?</p>
          <ul className="text-blue-200/80 space-y-1">
            <li>• Win rate by strategy (V2.1, Scalper, Day Trader, Long Term)</li>
            <li>• Best and worst performing coins</li>
            <li>• Total PnL breakdown</li>
            <li>• Weekly highlights (biggest win, biggest loss)</li>
            <li>• Strategy recommendations based on performance</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
