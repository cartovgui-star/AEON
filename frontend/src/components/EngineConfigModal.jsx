import React, { useState, useEffect } from 'react';
import { X, Save, RotateCcw, Settings2 } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;
const headers = { 'Content-Type': 'application/json' };

const FIELD_META = {
  min_confidence:       { label: 'Min Confidence',      type: 'float', min: 0, max: 100, step: 1,   unit: '%' },
  min_confluences:      { label: 'Min Confluences',     type: 'int',   min: 1, max: 10,  step: 1,   unit: '' },
  max_leverage:         { label: 'Max Leverage',        type: 'int',   min: 1, max: 125, step: 1,   unit: 'x' },
  max_position_size:    { label: 'Max Position Size',   type: 'float', min: 0, max: 100000, step: 100, unit: '$' },
  max_concurrent_trades:{ label: 'Max Concurrent Trades', type: 'int', min: 1, max: 20, step: 1,   unit: '' },
  max_daily_trades:     { label: 'Max Daily Trades',    type: 'int',   min: 1, max: 100, step: 1,   unit: '' },
  max_loss_per_day:     { label: 'Max Daily Loss',      type: 'float', min: 0, max: 100, step: 0.5, unit: '%' },
  cooldown_hours:       { label: 'Cooldown Hours',      type: 'int',   min: 1, max: 72,  step: 1,   unit: 'h' },
  use_blacklist:        { label: 'Use Blacklist',       type: 'bool' },
  use_cooldown:         { label: 'Use Cooldown',        type: 'bool' },
};

export default function EngineConfigModal({ engineName, onClose }) {
  const [config, setConfig] = useState(null);
  const [original, setOriginal] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/engines/config/${engineName}`, { headers })
      .then(r => r.json())
      .then(data => { setConfig(data); setOriginal(data); })
      .catch(() => setError('Failed to load config'));
  }, [engineName]);

  const handleChange = (field, value) => {
    setConfig(c => ({ ...c, [field]: value }));
    setSaved(false);
  };

  const handleReset = () => {
    setConfig({ ...original });
    setSaved(false);
    setError(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const payload = {};
      Object.keys(FIELD_META).forEach(f => {
        if (config[f] !== original[f]) payload[f] = config[f];
      });
      if (Object.keys(payload).length === 0) { setSaving(false); return; }

      const res = await fetch(`${API_URL}/api/engines/config/${engineName}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      const updated = await res.json();
      setOriginal(updated);
      setConfig(updated);
      setSaved(true);
    } catch (e) {
      setError(e.message || 'Save failed');
    }
    setSaving(false);
  };

  const dirty = config && original &&
    Object.keys(FIELD_META).some(f => config[f] !== original[f]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-zinc-950 border border-zinc-800 rounded-2xl w-full max-w-lg shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-zinc-800">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-orange-500/20 border border-orange-500/30 flex items-center justify-center">
              <Settings2 className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h2 className="text-white font-bold">Engine Config</h2>
              <p className="text-zinc-500 text-xs font-mono">{engineName}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-2 text-zinc-500 hover:text-white rounded-lg hover:bg-zinc-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <div className="p-5 max-h-[60vh] overflow-y-auto space-y-3">
          {!config ? (
            <p className="text-zinc-500 text-center py-8">{error || 'Loading...'}</p>
          ) : (
            Object.entries(FIELD_META).map(([field, meta]) => (
              <div key={field} className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm text-zinc-300 font-medium">{meta.label}</p>
                  {meta.unit && <p className="text-xs text-zinc-600">{meta.unit}</p>}
                </div>
                {meta.type === 'bool' ? (
                  <button
                    onClick={() => handleChange(field, !config[field])}
                    className={`relative w-11 h-6 rounded-full transition-colors ${
                      config[field] ? 'bg-orange-500' : 'bg-zinc-700'
                    }`}
                  >
                    <span className={`absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white transition-transform ${
                      config[field] ? 'translate-x-5' : ''
                    }`} />
                  </button>
                ) : (
                  <div className="flex items-center gap-2">
                    <input
                      type="number"
                      min={meta.min}
                      max={meta.max}
                      step={meta.step}
                      value={config[field] ?? ''}
                      onChange={e => handleChange(field, meta.type === 'int' ? parseInt(e.target.value) : parseFloat(e.target.value))}
                      className={`w-24 px-3 py-1.5 bg-zinc-900 border rounded-lg text-right text-white text-sm font-mono focus:outline-none focus:ring-1 focus:ring-orange-500/50 ${
                        config[field] !== original[field] ? 'border-orange-500/50' : 'border-zinc-700'
                      }`}
                    />
                    {meta.unit && <span className="text-xs text-zinc-500 w-4">{meta.unit}</span>}
                  </div>
                )}
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between p-5 border-t border-zinc-800">
          <div className="text-xs">
            {error && <span className="text-red-400">{error}</span>}
            {saved && !dirty && <span className="text-green-400">Saved successfully</span>}
            {dirty && <span className="text-yellow-400">Unsaved changes</span>}
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleReset}
              disabled={!dirty}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-white text-sm disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <RotateCcw className="w-4 h-4" />
              Reset
            </button>
            <button
              onClick={handleSave}
              disabled={!dirty || saving}
              className="flex items-center gap-2 px-4 py-2 rounded-lg bg-orange-500 hover:bg-orange-600 text-white text-sm font-medium disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Save className="w-4 h-4" />
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
