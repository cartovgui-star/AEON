import React, { useState, useEffect } from 'react';
import { Settings, Volume2, Bell, Bot, Shield, Sliders, Save, RotateCcw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SettingsPanel() {
  const [settings, setSettings] = useState({
    // Auto Trader
    autoTraderEnabled: true,
    minConfidence: 85,
    minConfirmations: 4,
    maxOpenTrades: 5,
    
    // Free Will Alerts
    freeWillEnabled: true,
    freeWillMinConf: 80,
    alertCooldown: 30,
    maxAlertsPerDay: 10,
    
    // Voice
    voiceEnabled: true,
    selectedVoice: 'guy',
    
    // Risk Management
    maxRiskPerTrade: 2,
    trailStopDefault: 3,
    takeProfitMultiple: 2,
  });
  
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const voices = [
    { id: 'guy', name: 'Guy', desc: 'Confident American' },
    { id: 'davis', name: 'Davis', desc: 'Deep American' },
    { id: 'british', name: 'Ryan', desc: 'British' },
    { id: 'australian', name: 'William', desc: 'Australian' }
  ];

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const [tradingRes, freeWillRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/freewill/stats`)
      ]);
      
      const tradingData = await tradingRes.json();
      const freeWillData = await freeWillRes.json();
      
      setSettings(prev => ({
        ...prev,
        autoTraderEnabled: tradingData.active ?? true,
        minConfidence: tradingData.min_confidence ?? 85,
        minConfirmations: tradingData.min_confirmations ?? 4,
        freeWillEnabled: freeWillData.active ?? true,
        freeWillMinConf: freeWillData.min_confidence ?? 80,
      }));
    } catch (err) {
      console.error('Failed to fetch settings:', err);
    }
    setLoading(false);
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
      console.error('Failed to save settings:', err);
    }
    setSaving(false);
  };

  const resetDefaults = () => {
    setSettings({
      autoTraderEnabled: true,
      minConfidence: 85,
      minConfirmations: 4,
      maxOpenTrades: 5,
      freeWillEnabled: true,
      freeWillMinConf: 80,
      alertCooldown: 30,
      maxAlertsPerDay: 10,
      voiceEnabled: true,
      selectedVoice: 'guy',
      maxRiskPerTrade: 2,
      trailStopDefault: 3,
      takeProfitMultiple: 2,
    });
  };

  const SettingSection = ({ icon: Icon, title, children }) => (
    <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
      <div className="flex items-center gap-3 px-6 py-4 bg-zinc-800/50 border-b border-zinc-700/50">
        <Icon className="w-5 h-5 text-orange-400" />
        <h3 className="font-semibold text-white">{title}</h3>
      </div>
      <div className="p-6 space-y-6">{children}</div>
    </div>
  );

  const Toggle = ({ label, desc, value, onChange }) => (
    <div className="flex items-center justify-between">
      <div>
        <p className="font-medium text-white">{label}</p>
        <p className="text-sm text-zinc-500">{desc}</p>
      </div>
      <button
        onClick={() => onChange(!value)}
        className={`relative w-14 h-7 rounded-full transition-colors ${
          value ? 'bg-orange-500' : 'bg-zinc-700'
        }`}
      >
        <div className={`absolute top-1 w-5 h-5 rounded-full bg-white transition-transform ${
          value ? 'left-8' : 'left-1'
        }`} />
      </button>
    </div>
  );

  const Slider = ({ label, desc, value, onChange, min, max, step = 1, suffix = '' }) => (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <div>
          <p className="font-medium text-white">{label}</p>
          <p className="text-sm text-zinc-500">{desc}</p>
        </div>
        <span className="text-lg font-semibold text-orange-400">{value}{suffix}</span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer
          [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 
          [&::-webkit-slider-thumb]:h-4 [&::-webkit-slider-thumb]:rounded-full 
          [&::-webkit-slider-thumb]:bg-orange-500 [&::-webkit-slider-thumb]:cursor-pointer"
      />
      <div className="flex justify-between text-xs text-zinc-600">
        <span>{min}{suffix}</span>
        <span>{max}{suffix}</span>
      </div>
    </div>
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin w-8 h-8 border-2 border-orange-500 border-t-transparent rounded-full" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Action Buttons */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-6 h-6 text-orange-400" />
          Configuration
        </h2>
        <div className="flex items-center gap-3">
          <button
            onClick={resetDefaults}
            className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-zinc-400 hover:text-white transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
            Reset Defaults
          </button>
          <button
            onClick={saveSettings}
            disabled={saving}
            className={`flex items-center gap-2 px-6 py-2 rounded-lg font-medium transition-all ${
              saved 
                ? 'bg-green-500 text-white' 
                : 'bg-orange-500 hover:bg-orange-600 text-white'
            }`}
          >
            <Save className="w-4 h-4" />
            {saving ? 'Saving...' : saved ? 'Saved!' : 'Save Changes'}
          </button>
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Auto Trader Settings */}
        <SettingSection icon={Bot} title="Autonomous Trader v2">
          <Toggle
            label="Enable Auto Trading"
            desc="Let Aeon take trades automatically"
            value={settings.autoTraderEnabled}
            onChange={(v) => setSettings(s => ({ ...s, autoTraderEnabled: v }))}
          />
          
          <Slider
            label="Minimum Confidence"
            desc="Only take trades above this confidence level"
            value={settings.minConfidence}
            onChange={(v) => setSettings(s => ({ ...s, minConfidence: v }))}
            min={70}
            max={95}
            suffix="%"
          />
          
          <Slider
            label="Minimum Confirmations"
            desc="Required data sources agreeing on signal"
            value={settings.minConfirmations}
            onChange={(v) => setSettings(s => ({ ...s, minConfirmations: v }))}
            min={2}
            max={6}
          />
          
          <Slider
            label="Max Open Trades"
            desc="Maximum concurrent positions"
            value={settings.maxOpenTrades}
            onChange={(v) => setSettings(s => ({ ...s, maxOpenTrades: v }))}
            min={1}
            max={10}
          />
        </SettingSection>

        {/* Alert Settings */}
        <SettingSection icon={Bell} title="Free Will Alerts">
          <Toggle
            label="Enable Alerts"
            desc="Receive proactive trading alerts"
            value={settings.freeWillEnabled}
            onChange={(v) => setSettings(s => ({ ...s, freeWillEnabled: v }))}
          />
          
          <Slider
            label="Alert Confidence"
            desc="Minimum confidence for alerts"
            value={settings.freeWillMinConf}
            onChange={(v) => setSettings(s => ({ ...s, freeWillMinConf: v }))}
            min={65}
            max={95}
            suffix="%"
          />
          
          <Slider
            label="Alert Cooldown"
            desc="Minutes between alerts for same symbol"
            value={settings.alertCooldown}
            onChange={(v) => setSettings(s => ({ ...s, alertCooldown: v }))}
            min={15}
            max={120}
            suffix=" min"
          />
          
          <Slider
            label="Max Alerts Per Day"
            desc="Maximum daily alert limit"
            value={settings.maxAlertsPerDay}
            onChange={(v) => setSettings(s => ({ ...s, maxAlertsPerDay: v }))}
            min={5}
            max={50}
          />
        </SettingSection>

        {/* Voice Settings */}
        <SettingSection icon={Volume2} title="Voice Settings">
          <Toggle
            label="Enable Voice"
            desc="Allow voice conversations with Aeon"
            value={settings.voiceEnabled}
            onChange={(v) => setSettings(s => ({ ...s, voiceEnabled: v }))}
          />
          
          <div className="space-y-2">
            <p className="font-medium text-white">Aeon's Voice</p>
            <p className="text-sm text-zinc-500">Choose how Aeon sounds</p>
            <div className="grid grid-cols-2 gap-2 mt-3">
              {voices.map(voice => (
                <button
                  key={voice.id}
                  onClick={() => setSettings(s => ({ ...s, selectedVoice: voice.id }))}
                  className={`p-3 rounded-lg border transition-all text-left ${
                    settings.selectedVoice === voice.id
                      ? 'border-orange-500 bg-orange-500/10'
                      : 'border-zinc-700 hover:border-zinc-600'
                  }`}
                >
                  <p className={`font-medium ${settings.selectedVoice === voice.id ? 'text-orange-400' : 'text-white'}`}>
                    {voice.name}
                  </p>
                  <p className="text-xs text-zinc-500">{voice.desc}</p>
                </button>
              ))}
            </div>
          </div>
        </SettingSection>

        {/* Risk Management */}
        <SettingSection icon={Shield} title="Risk Management">
          <Slider
            label="Max Risk Per Trade"
            desc="Maximum portfolio % at risk"
            value={settings.maxRiskPerTrade}
            onChange={(v) => setSettings(s => ({ ...s, maxRiskPerTrade: v }))}
            min={0.5}
            max={5}
            step={0.5}
            suffix="%"
          />
          
          <Slider
            label="Default Trail Stop"
            desc="Default trailing stop percentage"
            value={settings.trailStopDefault}
            onChange={(v) => setSettings(s => ({ ...s, trailStopDefault: v }))}
            min={1}
            max={10}
            suffix="%"
          />
          
          <Slider
            label="Take Profit Multiple"
            desc="TP distance vs SL (Risk:Reward)"
            value={settings.takeProfitMultiple}
            onChange={(v) => setSettings(s => ({ ...s, takeProfitMultiple: v }))}
            min={1}
            max={5}
            step={0.5}
            suffix="x"
          />
        </SettingSection>
      </div>
    </div>
  );
}
