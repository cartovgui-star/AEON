import React, { useState, useEffect } from 'react';
import { Settings, Save, RotateCcw, Bot, Bell, Volume2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    autoTraderEnabled: true,
    minConfidence: 85,
    freeWillEnabled: true,
    freeWillMinConf: 80,
    selectedVoice: 'guy'
  });
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const [tradingRes, freeWillRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/freewill/stats`)
      ]);
      const trading = await tradingRes.json();
      const freeWill = await freeWillRes.json();
      setSettings(s => ({
        ...s,
        autoTraderEnabled: trading.active ?? true,
        minConfidence: trading.min_confidence ?? 85,
        freeWillEnabled: freeWill.active ?? true,
        freeWillMinConf: freeWill.min_confidence ?? 80
      }));
    } catch (err) {
      console.error('Failed to fetch settings:', err);
    }
  };

  const saveSettings = async () => {
    setSaving(true);
    try {
      await Promise.all([
        fetch(`${API_URL}/api/trading/toggle?active=${settings.autoTraderEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${settings.minConfidence}`, { method: 'POST' }),
        fetch(`${API_URL}/api/freewill/toggle?active=${settings.freeWillEnabled}`, { method: 'POST' }),
        fetch(`${API_URL}/api/freewill/confidence?min_conf=${settings.freeWillMinConf}`, { method: 'POST' })
      ]);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-orange-400" />
          Configuration
        </h2>
        <div className="flex gap-3">
          <button onClick={fetchSettings} className="px-4 py-2 bg-zinc-800 rounded-lg text-zinc-400 hover:text-white flex items-center gap-2">
            <RotateCcw className="w-4 h-4" /> Reset
          </button>
          <button onClick={saveSettings} disabled={saving}
            className={`px-6 py-2 rounded-lg font-medium flex items-center gap-2 ${saved ? 'bg-green-500' : 'bg-orange-500 hover:bg-orange-600'} text-white`}>
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Auto Trader */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
            <Bot className="w-5 h-5 text-orange-400" />
            <h3 className="font-semibold text-white">Autonomous Trader v2</h3>
          </div>
          <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-white">Enable Auto Trading</p>
                <p className="text-sm text-zinc-500">Let Aeon take trades automatically</p>
              </div>
              <button onClick={() => setSettings(s => ({ ...s, autoTraderEnabled: !s.autoTraderEnabled }))}
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
                className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer" />
            </div>
          </div>
        </div>

        {/* Free Will */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
          <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
            <Bell className="w-5 h-5 text-orange-400" />
            <h3 className="font-semibold text-white">Free Will Alerts</h3>
          </div>
          <div className="p-6 space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-white">Enable Alerts</p>
                <p className="text-sm text-zinc-500">Receive proactive trading alerts</p>
              </div>
              <button onClick={() => setSettings(s => ({ ...s, freeWillEnabled: !s.freeWillEnabled }))}
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
                className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer" />
            </div>
          </div>
        </div>

        {/* Voice */}
        <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden md:col-span-2">
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
      </div>
    </div>
  );
}
