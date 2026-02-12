import React, { useState, useEffect } from 'react';
import { Settings, Save, RotateCcw, Bot, Bell, Volume2, Shield, Clock, TrendingUp, User, Brain, Zap, Target } from 'lucide-react';

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
    selectedVoice: 'guy'
  });
  const [freeWillStats, setFreeWillStats] = useState(null);
  const [dualStats, setDualStats] = useState(null);
  const [userProfile, setUserProfile] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [activeTab, setActiveTab] = useState('trading');

  useEffect(() => {
    fetchSettings();
    fetchFreeWillStats();
    fetchDualStats();
    fetchUserProfile();
  }, []);

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
        // Auto Trader settings
        fetch(`${API_URL}/api/trading/toggle?active=${settings.autoTraderEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${settings.minConfidence}`, { method: 'POST' }),
        // Free Will settings
        fetch(`${API_URL}/api/freewill/toggle?active=${settings.freeWillEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/freewill/confidence?min_conf=${settings.freeWillMinConf}`, { method: 'POST' }),
        // Day Trader settings
        fetch(`${API_URL}/api/dual/day-trader/toggle?active=${settings.dayTraderEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/day-trader/confidence?min_conf=${settings.dayTraderConf}`, { method: 'POST' }),
        // Long Term settings
        fetch(`${API_URL}/api/dual/long-term/toggle?active=${settings.longTermEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/dual/long-term/confidence?min_conf=${settings.longTermConf}`, { method: 'POST' })
      ]);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      // Refresh stats after saving
      fetchDualStats();
      fetchFreeWillStats();
    } catch (err) {
      console.error('Failed to save:', err);
    }
    setSaving(false);
  };

  const voices = [
    { id: 'guy', name: 'Guy', desc: 'Confident American' },
    { id: 'davis', name: 'Davis', desc: 'Deep American' },
    { id: 'british', name: 'Ryan', desc: 'British' },
    { id: 'australian', name: 'William', desc: 'Australian' }
  ];

  const tabs = [
    { id: 'trading', label: 'Trading', icon: Bot },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'profile', label: 'Your Profile', icon: User },
    { id: 'voice', label: 'Voice', icon: Volume2 }
  ];

  return (
    <div className="space-y-6" data-testid="settings-panel">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-orange-400" />
          Configuration
        </h2>
        <div className="flex gap-3">
          <button onClick={fetchSettings} className="px-4 py-2 bg-zinc-800 rounded-lg text-zinc-400 hover:text-white flex items-center gap-2">
            <RotateCcw className="w-4 h-4" /> Refresh
          </button>
          <button onClick={saveSettings} disabled={saving} data-testid="save-settings-btn"
            className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${saved ? 'bg-green-500' : 'bg-orange-500 hover:bg-orange-600'} text-white`}>
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-zinc-700/50 pb-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2 rounded-lg flex items-center gap-2 transition-all ${
              activeTab === tab.id 
                ? 'bg-orange-500/20 text-orange-400 border border-orange-500/50' 
                : 'text-zinc-400 hover:text-white hover:bg-zinc-800'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Trading Tab */}
      {activeTab === 'trading' && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
              <Bot className="w-5 h-5 text-orange-400" />
              <h3 className="font-semibold text-white">Autonomous Trader v2</h3>
            </div>
            <div className="p-6 space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="font-medium text-white">Enable Auto Trading</p>
                  <p className="text-sm text-zinc-500">Paper trading with live MEXC data</p>
                </div>
                <button onClick={() => setSettings(s => ({ ...s, autoTraderEnabled: !s.autoTraderEnabled }))}
                  data-testid="auto-trader-toggle"
                  className={`w-14 h-7 rounded-full transition-colors ${settings.autoTraderEnabled ? 'bg-orange-500' : 'bg-zinc-700'}`}>
                  <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.autoTraderEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
                </button>
              </div>
              <div>
                <div className="flex justify-between mb-2">
                  <span className="text-white">Min Confidence</span>
                  <span className="text-orange-400 font-semibold">{settings.minConfidence}%</span>
                </div>
                <input type="range" min={70} max={95} value={settings.minConfidence}
                  onChange={e => setSettings(s => ({ ...s, minConfidence: Number(e.target.value) }))}
                  className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500" />
                <div className="flex justify-between text-xs text-zinc-500 mt-1">
                  <span>More Trades (70%)</span>
                  <span>Higher Quality (95%)</span>
                </div>
              </div>
            </div>
          </div>

          {/* Trading Stats */}
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
              <TrendingUp className="w-5 h-5 text-green-400" />
              <h3 className="font-semibold text-white">Trading Stats</h3>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-sm">Open Trades</p>
                  <p className="text-2xl font-bold text-white">10</p>
                </div>
                <div className="bg-zinc-900/50 rounded-lg p-3">
                  <p className="text-zinc-500 text-sm">Mode</p>
                  <p className="text-lg font-bold text-yellow-400">Paper</p>
                </div>
              </div>
              <div className="text-sm text-zinc-400">
                Using live MEXC exchange data for paper trading. No real money at risk.
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Alerts Tab */}
      {activeTab === 'alerts' && (
        <div className="space-y-6">
          {/* Dual Trading Engine - Day Trader + Long Term */}
          <div className="grid md:grid-cols-2 gap-6">
            {/* Day Trader */}
            <div className="bg-zinc-800/30 rounded-xl border border-yellow-500/30 overflow-hidden">
              <div className="flex items-center gap-3 px-6 py-4 bg-yellow-500/10 border-b border-yellow-500/30">
                <Zap className="w-5 h-5 text-yellow-400" />
                <h3 className="font-semibold text-white">Day Trader</h3>
                <span className="ml-auto px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">AGGRESSIVE</span>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Enable Day Trading</p>
                    <p className="text-sm text-zinc-500">Scalps & swings on 15m, 1h, 4h</p>
                  </div>
                  <button onClick={() => setSettings(s => ({ ...s, dayTraderEnabled: !s.dayTraderEnabled }))}
                    className={`w-14 h-7 rounded-full transition-colors ${settings.dayTraderEnabled ? 'bg-yellow-500' : 'bg-zinc-700'}`}>
                    <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.dayTraderEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
                  </button>
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-white text-sm">Min Confidence</span>
                    <span className="text-yellow-400 font-semibold">{settings.dayTraderConf}%</span>
                  </div>
                  <input type="range" min={65} max={90} value={settings.dayTraderConf}
                    onChange={e => setSettings(s => ({ ...s, dayTraderConf: Number(e.target.value) }))}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-yellow-500" />
                </div>
                {dualStats?.day_trader && (
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-700/50">
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Today</p>
                      <p className="font-bold text-white">{dualStats.day_trader.daily_alerts}/{dualStats.day_trader.max_daily_alerts}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Analyzed</p>
                      <p className="font-bold text-white">{dualStats.day_trader.setups_analyzed}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Lock</p>
                      <p className="font-bold text-white">{dualStats.day_trader.direction_lock_hours}h</p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Long Term */}
            <div className="bg-zinc-800/30 rounded-xl border border-blue-500/30 overflow-hidden">
              <div className="flex items-center gap-3 px-6 py-4 bg-blue-500/10 border-b border-blue-500/30">
                <Target className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white">Long Term</h3>
                <span className="ml-auto px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">SMART</span>
              </div>
              <div className="p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Enable Long Term</p>
                    <p className="text-sm text-zinc-500">Position trades on 4h, 1d</p>
                  </div>
                  <button onClick={() => setSettings(s => ({ ...s, longTermEnabled: !s.longTermEnabled }))}
                    className={`w-14 h-7 rounded-full transition-colors ${settings.longTermEnabled ? 'bg-blue-500' : 'bg-zinc-700'}`}>
                    <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.longTermEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
                  </button>
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-white text-sm">Min Confidence</span>
                    <span className="text-blue-400 font-semibold">{settings.longTermConf}%</span>
                  </div>
                  <input type="range" min={80} max={95} value={settings.longTermConf}
                    onChange={e => setSettings(s => ({ ...s, longTermConf: Number(e.target.value) }))}
                    className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-blue-500" />
                </div>
                {dualStats?.long_term && (
                  <div className="grid grid-cols-3 gap-2 pt-2 border-t border-zinc-700/50">
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Today</p>
                      <p className="font-bold text-white">{dualStats.long_term.daily_alerts}/{dualStats.long_term.max_daily_alerts}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Analyzed</p>
                      <p className="font-bold text-white">{dualStats.long_term.setups_analyzed}</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-zinc-500">Lock</p>
                      <p className="font-bold text-white">{dualStats.long_term.direction_lock_hours}h</p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Original Free Will section */}
          <div className="grid md:grid-cols-2 gap-6">
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
                <Bell className="w-5 h-5 text-orange-400" />
                <h3 className="font-semibold text-white">Elite Alerts (Legacy)</h3>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-white">Enable Elite Alerts</p>
                    <p className="text-sm text-zinc-500">80%+ confidence setups</p>
                  </div>
                  <button onClick={() => setSettings(s => ({ ...s, freeWillEnabled: !s.freeWillEnabled }))}
                    data-testid="freewill-toggle"
                    className={`w-14 h-7 rounded-full transition-colors ${settings.freeWillEnabled ? 'bg-orange-500' : 'bg-zinc-700'}`}>
                    <div className={`w-5 h-5 rounded-full bg-white transition-transform ${settings.freeWillEnabled ? 'translate-x-8' : 'translate-x-1'}`} />
                  </button>
                </div>
                <div>
                  <div className="flex justify-between mb-2">
                    <span className="text-white">Alert Confidence</span>
                    <span className="text-orange-400 font-semibold">{settings.freeWillMinConf}%</span>
                  </div>
                <input type="range" min={65} max={95} value={settings.freeWillMinConf}
                  onChange={e => setSettings(s => ({ ...s, freeWillMinConf: Number(e.target.value) }))}
                  className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500" />
              </div>
            </div>
          </div>

          {/* Alert Stats */}
          {freeWillStats && (
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
                <Shield className="w-5 h-5 text-blue-400" />
                <h3 className="font-semibold text-white">Alert System Status</h3>
              </div>
              <div className="p-6 space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="bg-zinc-900/50 rounded-lg p-3 text-center">
                    <p className="text-zinc-500 text-xs">Today</p>
                    <p className="text-xl font-bold text-white">{freeWillStats.daily_alerts}/{freeWillStats.max_daily_alerts}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3 text-center">
                    <p className="text-zinc-500 text-xs">Total</p>
                    <p className="text-xl font-bold text-white">{freeWillStats.total_alerts_sent}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3 text-center">
                    <p className="text-zinc-500 text-xs">Blocked</p>
                    <p className="text-xl font-bold text-green-400">{freeWillStats.contradictions_blocked}</p>
                  </div>
                </div>
                
                <div className="flex items-center gap-2 text-sm">
                  <Clock className="w-4 h-4 text-zinc-500" />
                  <span className="text-zinc-400">Cooldown: {freeWillStats.alert_cooldown_mins} min per coin</span>
                </div>
                <div className="flex items-center gap-2 text-sm">
                  <Shield className="w-4 h-4 text-zinc-500" />
                  <span className="text-zinc-400">Direction lock: {freeWillStats.direction_lock_hours}h (no flip-flop)</span>
                </div>

                {/* Recent Directions */}
                {freeWillStats.recent_directions && Object.keys(freeWillStats.recent_directions).length > 0 && (
                  <div className="mt-4">
                    <p className="text-sm text-zinc-400 mb-2">Recent Signal Directions:</p>
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(freeWillStats.recent_directions).map(([symbol, dir]) => (
                        <span key={symbol} className={`px-2 py-1 rounded text-xs font-medium ${
                          dir === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
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
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden md:col-span-2">
              <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
                <Brain className="w-5 h-5 text-purple-400" />
                <h3 className="font-semibold text-white">Data Sources ({freeWillStats.data_sources?.length || 0})</h3>
              </div>
              <div className="p-6">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  {freeWillStats.data_sources?.map((source, i) => (
                    <div key={i} className="bg-zinc-900/50 rounded-lg p-3 flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-green-400"></div>
                      <span className="text-sm text-zinc-300">{source}</span>
                    </div>
                  ))}
                </div>
                <p className="text-xs text-zinc-500 mt-4">
                  Monitoring {freeWillStats.pairs_monitored} pairs on {freeWillStats.timeframes?.join(', ')} timeframes
                </p>
              </div>
            </div>
          )}
          </div>
        </div>
      )}

      {/* Profile Tab */}
      {activeTab === 'profile' && (
        <div className="grid md:grid-cols-2 gap-6">
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
              <User className="w-5 h-5 text-orange-400" />
              <h3 className="font-semibold text-white">Your Trading Profile</h3>
            </div>
            <div className="p-6 space-y-4">
              {userProfile ? (
                <>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Trading Style</span>
                      <span className="text-white font-medium">{userProfile.trading_style || 'Learning...'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Risk Tolerance</span>
                      <span className={`font-medium ${
                        userProfile.risk_tolerance === 'high' ? 'text-red-400' :
                        userProfile.risk_tolerance === 'medium' ? 'text-yellow-400' : 'text-green-400'
                      }`}>{userProfile.risk_tolerance || 'Unknown'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Favorite Coins</span>
                      <span className="text-orange-400">{userProfile.favorite_coins?.join(', ') || 'None yet'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-zinc-400">Messages Analyzed</span>
                      <span className="text-white">{userProfile.messages_analyzed || 0}</span>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8">
                  <Brain className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
                  <p className="text-zinc-400">Aeon is learning your preferences...</p>
                  <p className="text-sm text-zinc-500 mt-2">Chat more to build your profile!</p>
                </div>
              )}
            </div>
          </div>

          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
              <Brain className="w-5 h-5 text-purple-400" />
              <h3 className="font-semibold text-white">Aeon's Understanding</h3>
            </div>
            <div className="p-6">
              <p className="text-zinc-400 text-sm mb-4">
                Aeon learns from your conversations to personalize responses and trading insights.
              </p>
              <ul className="space-y-2 text-sm">
                <li className="flex items-center gap-2 text-zinc-300">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  Tracks coins you ask about most
                </li>
                <li className="flex items-center gap-2 text-zinc-300">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  Learns your risk preferences
                </li>
                <li className="flex items-center gap-2 text-zinc-300">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  Adapts communication style
                </li>
                <li className="flex items-center gap-2 text-zinc-300">
                  <div className="w-1.5 h-1.5 rounded-full bg-green-400"></div>
                  Remembers your trading history
                </li>
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Voice Tab */}
      {activeTab === 'voice' && (
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
            <Volume2 className="w-5 h-5 text-orange-400" />
            <h3 className="font-semibold text-white">Voice Settings</h3>
          </div>
          <div className="p-6">
            <p className="text-white mb-4">Choose Aeon's Voice</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {voices.map(v => (
                <button key={v.id} onClick={() => setSettings(s => ({ ...s, selectedVoice: v.id }))}
                  className={`p-4 rounded-lg border text-left transition-all ${
                    settings.selectedVoice === v.id ? 'border-orange-500 bg-orange-500/10' : 'border-zinc-700 hover:border-zinc-600'
                  }`}>
                  <p className={`font-medium ${settings.selectedVoice === v.id ? 'text-orange-400' : 'text-white'}`}>{v.name}</p>
                  <p className="text-xs text-zinc-500">{v.desc}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
