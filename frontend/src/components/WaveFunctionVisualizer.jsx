import React, { useEffect, useRef, useState, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Zap, RefreshCw } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

const ENGINE_NAMES = {
  day_trader:           'DAY',
  autonomous_trader_v2: 'AUTO V2',
  free_will_v2:         'FREE WILL',
  dual_engine:          'DUAL',
  yolo_engine:          'YOLO',
  vwap_scalper:         'VWAP',
  elite_strategy:       'ELITE',
  tcn_neural:           'TCN',
  quant_analyzer:       'QUANT',
};

const ENGINE_COLORS = [
  '#f97316', // orange
  '#3b82f6', // blue
  '#a855f7', // purple
  '#22c55e', // green
  '#ef4444', // red
  '#06b6d4', // cyan
  '#eab308', // yellow
  '#ec4899', // pink
  '#14b8a6', // teal
];

function drawWaves(ctx, width, height, engineEntries, phase, signalFired) {
  ctx.clearRect(0, 0, width, height);

  const midY = height / 2;
  const xStep = width / 200;
  const MAX_AMP = height * 0.18;

  // Draw individual engine waves
  engineEntries.forEach(([, alpha], idx) => {
    const color = ENGINE_COLORS[idx % ENGINE_COLORS.length];
    const amp = Math.abs(alpha || 0) * MAX_AMP;
    const freq = 0.04 + idx * 0.006;
    const phaseOffset = idx * 0.7;

    ctx.beginPath();
    ctx.strokeStyle = color + '55'; // semi-transparent
    ctx.lineWidth = 1.2;
    for (let x = 0; x <= 200; x++) {
      const y = midY + amp * Math.sin(freq * x * Math.PI + phase + phaseOffset) * ((alpha || 0) >= 0 ? 1 : -1);
      if (x === 0) ctx.moveTo(x * xStep, y);
      else ctx.lineTo(x * xStep, y);
    }
    ctx.stroke();
  });

  // Combined |Ψ⟩ wave
  const psiColor = signalFired ? '#ffd700' : '#f97316';
  const psiGlow = signalFired ? '#ffd70088' : '#f9731644';

  ctx.beginPath();
  ctx.shadowColor = psiGlow;
  ctx.shadowBlur = signalFired ? 20 : 8;
  ctx.strokeStyle = psiColor;
  ctx.lineWidth = signalFired ? 3 : 2.2;
  for (let x = 0; x <= 200; x++) {
    let y = midY;
    engineEntries.forEach(([, alpha], idx) => {
      const amp = Math.abs(alpha || 0) * MAX_AMP * 0.6;
      const freq = 0.04 + idx * 0.006;
      const phaseOffset = idx * 0.7;
      y += amp * Math.sin(freq * x * Math.PI + phase + phaseOffset) * ((alpha || 0) >= 0 ? 1 : -1);
    });
    if (x === 0) ctx.moveTo(x * xStep, y);
    else ctx.lineTo(x * xStep, y);
  }
  ctx.stroke();
  ctx.shadowBlur = 0;

  // Centre axis
  ctx.beginPath();
  ctx.strokeStyle = '#27272a';
  ctx.lineWidth = 0.5;
  ctx.setLineDash([4, 4]);
  ctx.moveTo(0, midY);
  ctx.lineTo(width, midY);
  ctx.stroke();
  ctx.setLineDash([]);
}

const WaveFunctionVisualizer = forwardRef(function WaveFunctionVisualizer(props, ref) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);
  const phaseRef = useRef(0);
  const signalFiredRef = useRef(false);
  const signalTimerRef = useRef(null);

  const [alphas, setAlphas] = useState({});
  const [psi, setPsi] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [signalFired, setSignalFired] = useState(false);

  // Expose triggerSignal to parent (App.js WebSocket handler)
  useImperativeHandle(ref, () => ({ triggerSignal }));

  const headers = {};

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch(`${API_URL}/api/quantum/state`, { headers });
      if (res.ok) {
        const data = await res.json();

        // Backend returns engine_states as array of {engine, alpha, ...}
        // Build a keyed dict for easy rendering
        const normalized = {};
        const engineStates = data.engine_states;
        if (Array.isArray(engineStates)) {
          engineStates.forEach((rec) => {
            const key = rec.engine || rec.name || 'unknown';
            normalized[key] = typeof rec.alpha === 'number' ? rec.alpha : 0;
          });
        } else if (data.alphas && typeof data.alphas === 'object') {
          // Legacy fallback if backend ever returns alphas dict
          Object.entries(data.alphas).forEach(([k, v]) => {
            normalized[k] = typeof v === 'object' ? (v?.alpha ?? v?.value ?? 0) : (v ?? 0);
          });
        }

        setAlphas(normalized);
        setPsi(data.H ?? null);
        setLastUpdated(new Date());
      }
    } catch (_) {}
    setLoading(false);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 30000);
    return () => clearInterval(interval);
  }, [fetchState]);

  // Canvas animation loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const engineEntries = Object.entries(alphas);

    const animate = () => {
      phaseRef.current += 0.035;
      const w = canvas.width;
      const h = canvas.height;
      drawWaves(ctx, w, h, engineEntries, phaseRef.current, signalFiredRef.current);
      animRef.current = requestAnimationFrame(animate);
    };

    animRef.current = requestAnimationFrame(animate);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [alphas, signalFired]);

  // Resize canvas to container
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Signal fired flash trigger (can be called from WebSocket parent or polling)
  const triggerSignal = () => {
    signalFiredRef.current = true;
    setSignalFired(true);
    if (signalTimerRef.current) clearTimeout(signalTimerRef.current);
    signalTimerRef.current = setTimeout(() => {
      signalFiredRef.current = false;
      setSignalFired(false);
    }, 2000);
  };

  const engineEntries = Object.entries(alphas);

  return (
    <div className="bg-zinc-900/50 border border-zinc-800/50 rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-zinc-800/50">
        <Zap className="w-4 h-4 text-orange-400" />
        <span className="text-xs font-bold uppercase tracking-wider text-orange-400">
          Wave Function |Ψ⟩
        </span>
        {signalFired && (
          <span className="ml-2 px-2 py-0.5 rounded text-[10px] font-bold bg-yellow-500/20 text-yellow-300 border border-yellow-500/40 animate-pulse">
            SIGNAL FIRED
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          {psi !== null && (
            <span className="text-xs text-zinc-400 font-mono">H={psi.toFixed(3)}</span>
          )}
          <button
            onClick={fetchState}
            className="p-1 rounded hover:bg-zinc-700/50 text-zinc-500 hover:text-white transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Canvas */}
      <div className="relative" style={{ height: '160px', background: '#050505' }}>
        <canvas
          ref={canvasRef}
          className="w-full h-full"
          style={{ display: 'block' }}
        />
        {loading && engineEntries.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center text-zinc-600 text-xs gap-2">
            <RefreshCw className="w-3 h-3 animate-spin" />
            Awaiting quantum state...
          </div>
        )}
        {/* Legend overlay */}
        <div className="absolute top-2 left-3 flex items-center gap-3 text-[9px]">
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5" style={{ background: '#f97316' }} />
            <span className="text-zinc-500">|Ψ⟩ combined</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-4 h-0.5" style={{ background: '#ffffff44' }} />
            <span className="text-zinc-600">engine αᵢ</span>
          </div>
        </div>
      </div>

      {/* Amplitude bars */}
      {engineEntries.length > 0 && (
        <div className="px-4 py-3 grid grid-cols-3 sm:grid-cols-5 md:grid-cols-9 gap-2 border-t border-zinc-800/30">
          {engineEntries.map(([name, alpha], idx) => {
            const color = ENGINE_COLORS[idx % ENGINE_COLORS.length];
            const label = ENGINE_NAMES[name] || name.toUpperCase().slice(0, 5);
            const pct = Math.min(100, Math.abs(alpha || 0) * 100);
            const positive = (alpha || 0) >= 0;
            return (
              <div key={name} className="flex flex-col gap-1">
                <span className="text-[9px] text-zinc-500 truncate">{label}</span>
                <div className="h-1 bg-zinc-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full transition-all duration-500"
                    style={{ width: `${pct}%`, background: color }}
                  />
                </div>
                <span
                  className="text-[9px] font-mono"
                  style={{ color: positive ? color : '#ef4444' }}
                >
                  {positive ? '+' : ''}{(alpha || 0).toFixed(3)}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

export default WaveFunctionVisualizer;
