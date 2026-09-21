import React, { useEffect, useRef, useState, useCallback } from 'react';
import { Volume2, VolumeX } from 'lucide-react';

/**
 * SoundAlertSystem
 * - Listens to the WebSocket ref for trade/regime events
 * - Uses Web Audio API to generate tones (no external lib)
 * - Persists mute state in localStorage
 * - Renders a mute toggle button fixed in the bottom-right
 */

const MUTE_KEY = 'aeon_sound_muted';

function createAudioCtx() {
  try {
    return new (window.AudioContext || window.webkitAudioContext)();
  } catch (_) {
    return null;
  }
}

// Generate a tone sequence
function playTone(ctx, notes, type = 'sine') {
  if (!ctx) return;
  // Resume suspended context (browser policy)
  if (ctx.state === 'suspended') ctx.resume();
  notes.forEach(({ freq, start, dur, vol = 0.18 }) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime + start);
    gain.gain.setValueAtTime(0, ctx.currentTime + start);
    gain.gain.linearRampToValueAtTime(vol, ctx.currentTime + start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + start + dur);
    osc.start(ctx.currentTime + start);
    osc.stop(ctx.currentTime + start + dur + 0.01);
  });
}

// Trade opened — short ascending tone
function soundTradeOpen(ctx) {
  playTone(ctx, [
    { freq: 440, start: 0, dur: 0.12 },
    { freq: 554, start: 0.13, dur: 0.12 },
    { freq: 659, start: 0.26, dur: 0.18 },
  ]);
}

// Trade closed profit — ascending chime
function soundTradeProfit(ctx) {
  playTone(ctx, [
    { freq: 523, start: 0, dur: 0.1 },
    { freq: 659, start: 0.11, dur: 0.1 },
    { freq: 784, start: 0.22, dur: 0.1 },
    { freq: 1047, start: 0.33, dur: 0.25, vol: 0.22 },
  ]);
}

// Trade closed loss — descending tone
function soundTradeLoss(ctx) {
  playTone(ctx, [
    { freq: 440, start: 0, dur: 0.15 },
    { freq: 370, start: 0.16, dur: 0.15 },
    { freq: 311, start: 0.32, dur: 0.25, vol: 0.15 },
  ]);
}

// Crisis — 3-pulse alarm
function soundCrisis(ctx) {
  [0, 0.35, 0.70].forEach((offset) => {
    playTone(ctx, [
      { freq: 880, start: offset, dur: 0.18, vol: 0.25 },
      { freq: 660, start: offset + 0.19, dur: 0.12, vol: 0.2 },
    ], 'square');
  });
}

// Regime change — subtle notification
function soundRegimeChange(ctx) {
  playTone(ctx, [
    { freq: 600, start: 0, dur: 0.12, vol: 0.12 },
    { freq: 750, start: 0.13, dur: 0.18, vol: 0.12 },
  ]);
}

export default function SoundAlertSystem({ wsRef }) {
  const audioCtxRef = useRef(null);
  const [muted, setMuted] = useState(() => {
    try { return localStorage.getItem(MUTE_KEY) === 'true'; } catch (_) { return false; }
  });
  const mutedRef = useRef(muted);
  const prevRegimeRef = useRef(null);
  const prevCrisisRef = useRef(false);

  // Keep ref in sync
  useEffect(() => {
    mutedRef.current = muted;
    try { localStorage.setItem(MUTE_KEY, String(muted)); } catch (_) {}
  }, [muted]);

  // Init audio context on first user interaction
  const ensureCtx = useCallback(() => {
    if (!audioCtxRef.current) {
      audioCtxRef.current = createAudioCtx();
    }
    return audioCtxRef.current;
  }, []);

  const play = useCallback((fn) => {
    if (mutedRef.current) return;
    const ctx = ensureCtx();
    fn(ctx);
  }, [ensureCtx]);

  // WebSocket message handler
  useEffect(() => {
    const ws = wsRef?.current;
    if (!ws) return;

    const origOnMessage = ws.onmessage;

    const handleMessage = (event) => {
      // Call original handler first
      if (origOnMessage) origOnMessage(event);

      try {
        const data = JSON.parse(event.data);

        if (data.type === 'trade_opened') {
          play(soundTradeOpen);
        } else if (data.type === 'trade_closed') {
          if ((data.pnl || 0) >= 0) {
            play(soundTradeProfit);
          } else {
            play(soundTradeLoss);
          }
        } else if (data.type === 'crisis') {
          if (!prevCrisisRef.current) {
            play(soundCrisis);
            prevCrisisRef.current = true;
          }
        } else if (data.type === 'crisis_resolved') {
          prevCrisisRef.current = false;
        } else if (data.type === 'regime_change' || data.type === 'regime') {
          const newRegime = data.regime || data.new_regime;
          if (newRegime && newRegime !== prevRegimeRef.current) {
            play(soundRegimeChange);
            prevRegimeRef.current = newRegime;
          }
        }
      } catch (_) {}
    };

    ws.onmessage = handleMessage;

    // Cleanup: restore original using captured ws reference
    return () => {
      ws.onmessage = origOnMessage;
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wsRef, play]);

  // Test tones on unmute (for UX feedback that audio works)
  const toggleMute = () => {
    const newMuted = !muted;
    setMuted(newMuted);
    if (!newMuted) {
      // Play a small confirmation tone
      const ctx = ensureCtx();
      setTimeout(() => play(soundRegimeChange), 50);
    }
  };

  return (
    <button
      onClick={toggleMute}
      title={muted ? 'Sound Off — click to enable' : 'Sound On — click to mute'}
      className={`fixed bottom-20 right-4 lg:bottom-6 z-40 p-2.5 rounded-full border shadow-lg transition-all ${
        muted
          ? 'bg-zinc-800/90 border-zinc-700 text-zinc-500 hover:text-zinc-300'
          : 'bg-orange-500/20 border-orange-500/40 text-orange-400 hover:bg-orange-500/30'
      }`}
    >
      {muted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4" />}
    </button>
  );
}
