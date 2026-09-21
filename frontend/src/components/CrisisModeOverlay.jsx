import React, { useState, useEffect, useCallback } from 'react';
import { AlertTriangle, X, Play } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function CrisisModeOverlay({ wsConnected }) {
  const [crisis, setCrisis] = useState(false);
  const [dismissed, setDismissed] = useState(false);
  const [regime, setRegime] = useState(null);
  const [hScore, setHScore] = useState(null);
  const [resuming, setResuming] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmCountdown, setConfirmCountdown] = useState(5);

  const headers = {};

  const checkCrisis = useCallback(async () => {
    try {
      const [configRes, stateRes] = await Promise.all([
        fetch(`${API_URL}/api/nexus/config`, { headers }),
        fetch(`${API_URL}/api/quantum/state`, { headers }),
      ]);
      let configRegime = null;
      if (configRes.ok) {
        const config = await configRes.json();
        const isCrisis = Boolean(config.crisis);
        setCrisis(isCrisis);
        configRegime = config.regime || null;
        if (configRegime) setRegime(configRegime);
        // Auto-dismiss when crisis resolves
        if (!isCrisis) setDismissed(false);
      }
      if (stateRes.ok) {
        const st = await stateRes.json();
        setHScore(st.H ?? null);
        // Only set regime from state if config didn't provide one
        if (!configRegime && (st.regime ?? null)) setRegime(st.regime);
      }
    } catch (_) {}
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    checkCrisis();
    const interval = setInterval(checkCrisis, 10000);
    return () => clearInterval(interval);
  }, [checkCrisis]);

  const handleResumeClick = () => {
    setShowConfirm(true);
    setConfirmCountdown(5);
  };

  useEffect(() => {
    if (!showConfirm) return;
    if (confirmCountdown <= 0) return;
    const t = setTimeout(() => setConfirmCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [showConfirm, confirmCountdown]);

  const handleConfirmResume = async () => {
    setResuming(true);
    setShowConfirm(false);
    try {
      await fetch(`${API_URL}/api/control/resume`, {
        method: 'POST',
        headers: { ...headers, 'Content-Type': 'application/json' },
      });
      setCrisis(false);
      setDismissed(false);
    } catch (_) {}
    setResuming(false);
  };

  // Only show if crisis AND not dismissed
  if (!crisis || dismissed) return null;

  return (
    <div
      className="fixed inset-0 z-[9999] flex flex-col items-center justify-center"
      style={{
        background: 'rgba(0,0,0,0.92)',
        animation: 'crisisPulse 2s ease-in-out infinite',
      }}
    >
      <style>{`
        @keyframes crisisPulse {
          0%, 100% { background: rgba(0,0,0,0.92); }
          50% { background: rgba(60,0,0,0.95); }
        }
        @keyframes crisisGlow {
          0%, 100% { box-shadow: 0 0 30px #ef444488, 0 0 60px #ef444444; }
          50% { box-shadow: 0 0 60px #ef4444cc, 0 0 120px #ef444466; }
        }
      `}</style>

      <div
        className="bg-zinc-950 border-2 border-red-500/60 rounded-2xl p-8 max-w-lg w-full mx-4 text-center"
        style={{ animation: 'crisisGlow 2s ease-in-out infinite' }}
      >
        {/* Icon */}
        <div className="flex justify-center mb-4">
          <div className="w-20 h-20 rounded-full bg-red-500/20 border-2 border-red-500/60 flex items-center justify-center">
            <AlertTriangle className="w-10 h-10 text-red-400 animate-pulse" />
          </div>
        </div>

        {/* Title */}
        <h1 className="text-2xl font-bold text-red-400 mb-2 tracking-widest uppercase">
          Crisis Mode Active
        </h1>
        <p className="text-zinc-400 text-sm mb-6">
          AEON is paused — all trading halted
        </p>

        {/* Stats */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3">
            <p className="text-xs text-zinc-600 mb-1">Last Regime</p>
            <p className="text-sm font-bold text-orange-400 font-mono">{regime || '—'}</p>
          </div>
          <div className="bg-zinc-900/80 border border-zinc-800 rounded-xl p-3">
            <p className="text-xs text-zinc-600 mb-1">H Score</p>
            <p className="text-sm font-bold text-blue-400 font-mono">
              {hScore !== null ? hScore.toFixed(3) : '—'}
            </p>
          </div>
        </div>

        <p className="text-xs text-zinc-500 mb-6">
          Correlation spike or extreme volatility detected. NEXUS HEALER is monitoring the situation.
        </p>

        {/* Buttons */}
        {showConfirm ? (
          <div className="text-center">
            <p className="text-yellow-300 font-bold mb-1">Confirm Resume Trading?</p>
            <p className="text-zinc-500 text-xs mb-4">All engines will re-activate immediately</p>
            <div className="flex gap-3 justify-center">
              <button
                onClick={() => setShowConfirm(false)}
                className="px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmResume}
                disabled={confirmCountdown > 0 || resuming}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-green-600 hover:bg-green-500 text-white transition-colors font-medium disabled:opacity-50"
              >
                <Play className="w-4 h-4" />
                {confirmCountdown > 0 ? `Confirm (${confirmCountdown}s)` : resuming ? 'Resuming...' : 'Confirm Resume'}
              </button>
            </div>
          </div>
        ) : (
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => setDismissed(true)}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-zinc-800 hover:bg-zinc-700 text-zinc-300 hover:text-white transition-colors font-medium"
            >
              <X className="w-4 h-4" />
              Acknowledge
            </button>
            <button
              onClick={handleResumeClick}
              disabled={resuming}
              className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-green-600 hover:bg-green-500 text-white transition-colors font-medium disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              {resuming ? 'Resuming...' : 'Resume Trading'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
