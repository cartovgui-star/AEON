import { useState, useEffect, useCallback, useRef } from "react";
import { Activity, Zap, Brain, RefreshCw, TrendingUp, TrendingDown,
         Minus, Search, Clock, Database, Globe, AlertTriangle } from "lucide-react";
import { Card, CardContent } from "./ui/card";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const POLL_MS = 10_000;   // refresh quantum state every 10s

// ─── Engine metadata ──────────────────────────────────────────────────────────
const ENGINE_META = {
  elite_strategy:        { label: "Elite",      emoji: "👑", color: "#f59e0b" },
  yolo_engine:           { label: "YOLO",       emoji: "🚀", color: "#ef4444" },
  vwap_scalper:          { label: "VWAP",       emoji: "🎯", color: "#14b8a6" },
  autonomous_trader:     { label: "Autonomous", emoji: "🤖", color: "#3b82f6" },
  autonomous_trader_v2:  { label: "Autonomous", emoji: "🤖", color: "#3b82f6" },
  free_will:             { label: "Free Will",  emoji: "🧠", color: "#a855f7" },
  free_will_v2:          { label: "Free Will",  emoji: "🧠", color: "#a855f7" },
  day_trader:            { label: "Day Trader", emoji: "📈", color: "#f97316" },
  dual_engine:           { label: "Dual",       emoji: "⚡", color: "#eab308" },
};

function engineMeta(id) {
  return ENGINE_META[id] || { label: id, emoji: "⚙️", color: "#6b7280" };
}

// ─── Gauge ring ───────────────────────────────────────────────────────────────
function GaugeRing({ value, max = 1, size = 96, label, sub, color = "#f59e0b", decimals = 2 }) {
  const r = (size - 12) / 2;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(Math.max(value / max, 0), 1);
  const dash = pct * circ;

  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} className="rotate-[-90deg]">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke="#27272a" strokeWidth={8} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none"
          stroke={color} strokeWidth={8}
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          style={{ transition: "stroke-dasharray 0.6s ease" }} />
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
          fill="white" fontSize={size < 80 ? 11 : 14} fontWeight="bold"
          style={{ transform: "rotate(90deg)", transformOrigin: "50% 50%" }}>
          {typeof value === "number" ? value.toFixed(decimals) : "—"}
        </text>
      </svg>
      <span className="text-xs font-semibold text-zinc-300">{label}</span>
      {sub && <span className="text-[10px] text-zinc-500">{sub}</span>}
    </div>
  );
}

// ─── Alpha bar ────────────────────────────────────────────────────────────────
function AlphaBar({ engine, alpha, alphaMag, S, wr, delta, independence, tradeCount, regimeGate }) {
  const meta = engineMeta(engine);
  const maxAlpha = 0.5;
  const pct = Math.min(Math.abs(alphaMag) / maxAlpha * 100, 100);
  const direction = alpha > 0 ? "LONG" : alpha < 0 ? "SHORT" : "—";
  const dirColor = alpha > 0 ? "#22c55e" : alpha < 0 ? "#ef4444" : "#6b7280";
  const silenced = regimeGate === 0 || tradeCount < 5;

  return (
    <div className={`rounded-lg border p-3 transition-all ${
      silenced ? "border-zinc-800/40 opacity-50" : "border-zinc-700/50"
    }`} style={{ background: silenced ? "#18181b" : `${meta.color}08` }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-base">{meta.emoji}</span>
          <span className="text-sm font-semibold text-zinc-200">{meta.label}</span>
          {silenced && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-500">
              {regimeGate === 0 ? "ADX Regime Gate" : "NO DATA"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 text-xs text-zinc-400">
          <span style={{ color: dirColor }} className="font-bold">{direction}</span>
          <span>WR {(wr * 100).toFixed(0)}%</span>
          <span className="text-zinc-500">S={S.toFixed(3)}</span>
        </div>
      </div>

      {/* Alpha amplitude bar */}
      <div className="w-full bg-zinc-800 rounded-full h-2 mb-1">
        <div
          className="h-2 rounded-full transition-all duration-700"
          style={{ width: `${pct}%`, background: meta.color }}
        />
      </div>

      <div className="flex justify-between text-[10px] text-zinc-500">
        <span>α = {alphaMag.toFixed(4)}</span>
        <span>δ = {delta.toFixed(3)}</span>
        <span>indep = {independence.toFixed(2)}</span>
        <span>{tradeCount} trades</span>
      </div>
    </div>
  );
}

// ─── Trend sparkline (simple SVG) ─────────────────────────────────────────────
function Sparkline({ data, color = "#f59e0b", height = 32, width = 120 }) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * width;
    const y = height - ((v - min) / range) * height;
    return `${x},${y}`;
  }).join(" ");

  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5}
        strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ─── Omega fix card ───────────────────────────────────────────────────────────
function OmegaFix({ fix }) {
  const typeColor = fix.fix_type === "Lθ" ? "#3b82f6"
    : fix.fix_type === "LΣ" ? "#f59e0b" : "#a855f7";
  const dH = fix.delta_H || 0;
  const ts = fix.timestamp ? new Date(fix.timestamp).toLocaleString() : "—";

  return (
    <div className="rounded-lg border border-zinc-800 p-3 bg-zinc-900/50">
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold px-2 py-0.5 rounded"
            style={{ background: `${typeColor}20`, color: typeColor }}>
            {fix.fix_type}
          </span>
          <span className="text-xs font-semibold text-zinc-200">
            {fix.engine?.toUpperCase()}
          </span>
        </div>
        <span className={`text-xs font-bold ${dH >= 0 ? "text-green-400" : "text-red-400"}`}>
          ΔH {dH >= 0 ? "+" : ""}{dH.toFixed(4)}
        </span>
      </div>
      <p className="text-[11px] text-zinc-400 leading-relaxed line-clamp-2">{fix.fix_desc}</p>
      <div className="flex justify-between text-[10px] text-zinc-600 mt-1">
        <span>{fix.diagnosis}</span>
        <span>{ts}</span>
      </div>
    </div>
  );
}

// ─── Web intelligence card ────────────────────────────────────────────────────
function WebDoc({ doc }) {
  const score = doc.relevance || 0;
  const barColor = score >= 0.7 ? "#22c55e" : score >= 0.5 ? "#f59e0b" : "#6b7280";
  const typeLabel = doc.type === "research_paper" ? "PAPER"
    : doc.type === "sentiment" ? "SENTIMENT"
    : doc.type === "open_source" ? "REPO"
    : doc.type === "macro" ? "MACRO" : "WEB";

  return (
    <div className="rounded-lg border border-zinc-800 p-3 bg-zinc-900/50">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
          {typeLabel}
        </span>
        <div className="flex items-center gap-1.5">
          <div className="w-16 bg-zinc-800 rounded-full h-1">
            <div className="h-1 rounded-full" style={{ width: `${score * 100}%`, background: barColor }} />
          </div>
          <span className="text-[10px] text-zinc-400">{score.toFixed(2)}</span>
        </div>
      </div>
      <p className="text-xs text-zinc-200 leading-snug line-clamp-2 mt-1">{doc.title}</p>
      <p className="text-[10px] text-zinc-500 mt-1">{doc.source}</p>
    </div>
  );
}

// ─── Memory retrieve panel ────────────────────────────────────────────────────
function MemoryPanel() {
  const [params, setParams] = useState({
    direction: "LONG", confidence: 80, regime: "trending",
    adx: 30, rsi: 60, vol_ratio: 1.5, leverage: 50,
  });
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);

  const query = useCallback(async () => {
    setLoading(true);
    try {
      const res = await axios.get(`${API}/quantum/memory/retrieve`, { params: { ...params, n: 8 } });
      setResults(res.data.results || []);
    } catch { setResults([]); }
    finally { setLoading(false); }
  }, [params]);

  const set = (k, v) => setParams(p => ({ ...p, [k]: v }));

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase">Direction</span>
          <select value={params.direction} onChange={e => set("direction", e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white">
            <option>LONG</option><option>SHORT</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase">Regime</span>
          <select value={params.regime} onChange={e => set("regime", e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white">
            <option>trending</option><option>ranging</option>
          </select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase">Confidence %</span>
          <input type="number" value={params.confidence} min={50} max={100}
            onChange={e => set("confidence", +e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-[10px] text-zinc-500 uppercase">ADX</span>
          <input type="number" value={params.adx} min={0} max={100}
            onChange={e => set("adx", +e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1.5 text-xs text-white" />
        </label>
      </div>

      <button onClick={query} disabled={loading}
        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 text-sm font-semibold hover:bg-amber-500/20 transition-colors disabled:opacity-50">
        {loading ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Search className="w-3.5 h-3.5" />}
        Retrieve similar setups
      </button>

      {results.length > 0 && (
        <div className="space-y-2">
          {results.map((r, i) => {
            const dH = r.pnl_pct > 0;
            return (
              <div key={i} className="rounded-lg border border-zinc-800 p-3 bg-zinc-900/50 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded ${dH ? "bg-green-500/10 text-green-400" : "bg-red-500/10 text-red-400"}`}>
                    {r.outcome}
                  </span>
                  <div className="min-w-0">
                    <p className="text-xs text-zinc-200 font-semibold truncate">
                      {r.symbol} {r.direction} — {r.engine}
                    </p>
                    <p className="text-[10px] text-zinc-500">
                      conf {r.confidence?.toFixed(0)}% • {r.leverage}x • {r.regime} • ADX {r.adx?.toFixed(0)}
                    </p>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <p className={`text-sm font-bold ${dH ? "text-green-400" : "text-red-400"}`}>
                    {r.pnl_pct > 0 ? "+" : ""}{r.pnl_pct?.toFixed(2)}%
                  </p>
                  <p className="text-[10px] text-zinc-500">sim {r.similarity?.toFixed(3)}</p>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}


// ─── Mini equity curve SVG ────────────────────────────────────────────────────
function EquityCurve({ data = [], color = "#22c55e", height = 80 }) {
  if (!data.length) return (
    <div className="flex items-center justify-center h-20 text-zinc-600 text-xs">No trade data yet</div>
  );
  const vals = data.map(d => d.cumulative_pnl);
  const minV = Math.min(...vals);
  const maxV = Math.max(...vals);
  const range = maxV - minV || 1;
  const w = 400;
  const pts = vals.map((v, i) => {
    const x = (i / (vals.length - 1 || 1)) * w;
    const y = height - ((v - minV) / range) * (height - 8) - 4;
    return `${x},${y}`;
  }).join(" ");
  const lastVal = vals[vals.length - 1];
  const isPos = lastVal >= 0;
  const lineColor = isPos ? "#22c55e" : "#ef4444";

  return (
    <svg viewBox={`0 0 ${w} ${height}`} className="w-full" style={{ height }}>
      <polyline points={pts} fill="none" stroke={lineColor} strokeWidth="2"
        strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

// ─── Single account card ──────────────────────────────────────────────────────
const ACCT_META = {
  REAL_LIFE:  { emoji: "💰", label: "Real Life",  color: "#22c55e" },
  THE_PROOF:  { emoji: "🎯", label: "The Proof",  color: "#a855f7" },
  BENCHMARK:  { emoji: "📊", label: "Benchmark",  color: "#3b82f6" },
};

function AccountCard({ id, curve = [], weekly = {} }) {
  const meta = ACCT_META[id] || { emoji: "📊", label: id, color: "#6b7280" };
  const bal = weekly.balance ?? 0;
  const wpnl = weekly.weekly_pnl ?? 0;
  const wpct = weekly.weekly_pnl_pct ?? 0;
  const pnlColor = wpnl >= 0 ? "text-green-400" : "text-red-400";

  return (
    <Card className="bg-zinc-900/60 border-zinc-800">
      <CardContent className="p-4 space-y-3">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-xl">{meta.emoji}</span>
            <div>
              <p className="text-sm font-bold text-white">{meta.label}</p>
              <p className="text-xs text-zinc-500 font-mono">{id}</p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-base font-bold text-white">${bal.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
            <p className={`text-xs font-semibold ${pnlColor}`}>
              {wpnl >= 0 ? "+" : ""}{wpnl.toFixed(2)} ({wpct >= 0 ? "+" : ""}{wpct.toFixed(1)}%) this week
            </p>
          </div>
        </div>

        {/* Equity curve */}
        <EquityCurve data={curve} color={meta.color} />

        {/* Extra stats */}
        <div className="grid grid-cols-2 gap-2 text-[11px]">
          {id === "REAL_LIFE" && (
            <>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">Total Deposited</p>
                <p className="text-white font-bold">${(weekly.total_deposited ?? 0).toLocaleString("en-US", { maximumFractionDigits: 0 })}</p>
              </div>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">Crossover Week</p>
                <p className={`font-bold ${(weekly.crossover_pct ?? 0) >= 100 ? "text-green-400" : "text-yellow-400"}`}>
                  {(weekly.crossover_pct ?? 0).toFixed(0)}% there
                </p>
              </div>
            </>
          )}
          {id === "THE_PROOF" && (
            <>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">Target ($680)</p>
                <p className={`font-bold ${(weekly.target_pct ?? 0) >= 100 ? "text-green-400" : "text-purple-400"}`}>
                  {(weekly.target_pct ?? 0).toFixed(1)}% there
                </p>
              </div>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">17x Status</p>
                <p className={`font-bold ${weekly.target_hit_at ? "text-green-400" : "text-zinc-400"}`}>
                  {weekly.target_hit_at ? `🏆 ${String(weekly.target_hit_at).slice(0, 10)}` : "In progress"}
                </p>
              </div>
            </>
          )}
          {id === "BENCHMARK" && (
            <>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">Win Rate</p>
                <p className="text-white font-bold">{(weekly.win_rate ?? 0).toFixed(1)}%</p>
              </div>
              <div className="bg-zinc-800/60 rounded p-2">
                <p className="text-zinc-500">Total Trades</p>
                <p className="text-white font-bold">{weekly.total_trades ?? 0}</p>
              </div>
            </>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Accounts tab ─────────────────────────────────────────────────────────────
function AccountsTab({ curves, weekly }) {
  const accounts = ["REAL_LIFE", "THE_PROOF", "BENCHMARK"];
  return (
    <div className="space-y-4">
      <p className="text-xs text-zinc-500">
        size(t) = base × C(t) × (1 − S_norm) &nbsp;·&nbsp; MEXC 0.15% fee &nbsp;·&nbsp; Weekly report every Monday 08:00 UTC
      </p>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {accounts.map(id => (
          <AccountCard key={id} id={id} curve={curves[id] || []} weekly={weekly[id] || {}} />
        ))}
      </div>
    </div>
  );
}


// ─── Main dashboard ───────────────────────────────────────────────────────────
export default function QuantumDashboard() {
  const [state, setState]           = useState(null);
  const [history, setHistory]       = useState([]);
  const [omegaStatus, setOmega]     = useState(null);
  const [omegaFixes, setFixes]      = useState([]);
  const [webDocs, setWebDocs]       = useState([]);
  const [memorySummary, setMemSum]  = useState(null);
  const [equityCurves, setEquity]   = useState({});
  const [weeklySummary, setWeekly]  = useState({});
  const [loading, setLoading]       = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [activeTab, setActiveTab]   = useState("state");
  const timerRef = useRef(null);

  const fetchAll = useCallback(async () => {
    try {
      const [stateRes, histRes, omegaRes, fixRes, webRes, memRes, eqRes, wkRes] = await Promise.allSettled([
        axios.get(`${API}/quantum/state`),
        axios.get(`${API}/quantum/history?limit=60`),
        axios.get(`${API}/quantum/omega/status`),
        axios.get(`${API}/quantum/omega/history?limit=10`),
        axios.get(`${API}/quantum/web/lphi?n=8&since_hours=48`),
        axios.get(`${API}/quantum/memory/summary?last_n=200`),
        axios.get(`${API}/paper/equity-curves`),
        axios.get(`${API}/paper/weekly-summary`),
      ]);

      if (stateRes.status === "fulfilled") setState(stateRes.value.data);
      if (histRes.status === "fulfilled")  setHistory(histRes.value.data.history || []);
      if (omegaRes.status === "fulfilled") setOmega(omegaRes.value.data);
      if (fixRes.status === "fulfilled")   setFixes(fixRes.value.data.fixes || []);
      if (webRes.status === "fulfilled")   setWebDocs(webRes.value.data.candidates || []);
      if (memRes.status === "fulfilled")   setMemSum(memRes.value.data);
      if (eqRes.status === "fulfilled")    setEquity(eqRes.value.data.curves || {});
      if (wkRes.status === "fulfilled")    setWeekly(wkRes.value.data || {});

      setLastUpdate(new Date());
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => {
    fetchAll();
    timerRef.current = setInterval(fetchAll, POLL_MS);
    return () => clearInterval(timerRef.current);
  }, [fetchAll]);

  // ── Derived values ────────────────────────────────────────────────────────
  const H     = state?.H ?? 0;
  const C     = state?.C ?? 0;
  const S     = state?.S_norm ?? 0;
  const size  = state?.position_multiplier ?? 0;
  const adx   = state?.adx ?? 0;
  const regime = state?.regime ?? "unknown";
  const nActive = state?.n_active ?? 0;
  const engines = state?.engine_states ?? [];

  const H_trend = history.map(h => h.H || 0);
  const C_trend = history.map(h => h.C || 0);
  const H_color = H >= 2 ? "#22c55e" : H >= 1 ? "#f59e0b" : "#ef4444";
  const C_color = C >= 0.6 ? "#22c55e" : C >= 0.4 ? "#f59e0b" : "#ef4444";
  const S_color = S <= 0.4 ? "#22c55e" : S <= 0.7 ? "#f59e0b" : "#ef4444";

  const regimeIcon = regime === "trending"
    ? <TrendingUp className="w-4 h-4 text-green-400" />
    : regime === "ranging"
    ? <Minus className="w-4 h-4 text-yellow-400" />
    : <Activity className="w-4 h-4 text-zinc-500" />;

  const tabs = [
    { id: "state",    label: "|Ψ⟩ State"    },
    { id: "engines",  label: "αᵢ Amplitudes" },
    { id: "omega",    label: "Ω Cycle"       },
    { id: "memory",   label: "Memory"        },
    { id: "web",      label: "Web Intel"     },
    { id: "accounts", label: "Accounts"      },
  ];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-3">
            <span className="text-3xl">Ψ</span>
            AEON Quantum State
          </h1>
          <p className="text-sm text-zinc-500 mt-0.5 font-mono">
            A(t) = Ω(|Ψ⟩, E, M, L)
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdate && (
            <span className="text-xs text-zinc-600 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <button onClick={fetchAll}
            className="p-2 rounded-lg bg-zinc-800 border border-zinc-700 text-zinc-400 hover:text-white transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* ── Top gauges ── */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4 flex flex-col items-center gap-3">
            <GaugeRing value={H} max={5} size={96} label="Health H"
              sub={H >= 1 ? "AEON profitable" : "spending > earning"}
              color={H_color} decimals={3} />
            <Sparkline data={H_trend} color={H_color} width={80} />
            {H < 1 && (
              <span className="text-[10px] text-red-400 flex items-center gap-1">
                <AlertTriangle className="w-3 h-3" /> H &lt; 1 — Ω triggered
              </span>
            )}
          </CardContent>
        </Card>

        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4 flex flex-col items-center gap-3">
            <GaugeRing value={C} max={1} size={96} label="Coherence C"
              sub={C >= 0.6 ? "engines aligned" : C >= 0.4 ? "moderate" : "diverging"}
              color={C_color} />
            <Sparkline data={C_trend} color={C_color} width={80} />
          </CardContent>
        </Card>

        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4 flex flex-col items-center gap-3">
            <GaugeRing value={S} max={1} size={96} label="Entropy S"
              sub={S <= 0.4 ? "clear signal" : S <= 0.7 ? "moderate noise" : "high uncertainty"}
              color={S_color} />
            <span className="text-[10px] text-zinc-500 text-center">
              size = base × C × (1−S)
            </span>
          </CardContent>
        </Card>

        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardContent className="p-4 flex flex-col items-center gap-3">
            <GaugeRing value={size} max={1} size={96} label="Size ×"
              sub={`$${(size * 1000).toFixed(0)} of $1,000 base`}
              color="#f59e0b" />
            <div className="flex items-center gap-2 text-xs">
              {regimeIcon}
              <span className={regime === "trending" ? "text-green-400" : "text-yellow-400"}>
                {regime.toUpperCase()} · ADX {adx.toFixed(1)}
              </span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ── Identity equation ── */}
      <Card className="bg-zinc-900/30 border-zinc-800/50">
        <CardContent className="p-4">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-6 font-mono text-center">
            {[
              { label: "H  (health)",    val: H.toFixed(4),    ok: H >= 1,   note: "H > 1" },
              { label: "C  (coherence)", val: C.toFixed(4),    ok: C >= 0.4, note: "C ≥ 0.4" },
              { label: "S  (entropy)",   val: S.toFixed(4),    ok: S <= 0.7, note: "S ≤ 0.7" },
              { label: "n  (active)",    val: `${nActive}/7`,  ok: nActive >= 3, note: "n ≥ 3" },
            ].map(({ label, val, ok, note }) => (
              <div key={label}>
                <div className="text-[10px] text-zinc-500 uppercase mb-1">{label}</div>
                <div className={`text-xl font-bold ${ok ? "text-green-400" : "text-red-400"}`}>{val}</div>
                <div className="text-[10px] text-zinc-600 mt-0.5">{note}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* ── Tabs ── */}
      <div className="flex gap-1 border-b border-zinc-800">
        {tabs.map(t => (
          <button key={t.id}
            onClick={() => setActiveTab(t.id)}
            className={`px-4 py-2 text-sm font-semibold transition-colors border-b-2 -mb-px ${
              activeTab === t.id
                ? "border-amber-500 text-amber-400"
                : "border-transparent text-zinc-500 hover:text-zinc-300"
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Tab: State ── */}
      {activeTab === "state" && (
        <div className="space-y-4">
          <p className="text-xs text-zinc-500">
            |Ψ⟩ = Σ αᵢ(t)|Eᵢ⟩ &nbsp;·&nbsp; αᵢ = Sᵢ · e^(−λδᵢ) · 𝟙[ADX&gt;20] · (1−ρᵢ_max)
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
            {engines.map(e => (
              <AlphaBar key={e.engine}
                engine={e.engine}
                alpha={e.alpha}
                alphaMag={e.alpha_mag}
                S={e.S}
                wr={e.win_rate}
                delta={e.delta}
                independence={e.independence}
                tradeCount={e.trade_count}
                regimeGate={e.regime_gate}
              />
            ))}
          </div>
        </div>
      )}

      {/* ── Tab: αᵢ full detail ── */}
      {activeTab === "engines" && (
        <div className="space-y-3">
          <div className="overflow-x-auto rounded-xl border border-zinc-800">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500">
                  {["Engine","α","S","WR","RR","PF","δ","Indep","Gate","Trades"].map(h => (
                    <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {engines.map(e => {
                  const meta = engineMeta(e.engine);
                  const alive = e.alpha_mag > 0.01 && e.regime_gate === 1;
                  return (
                    <tr key={e.engine} className={`border-b border-zinc-800/50 ${alive ? "" : "opacity-40"}`}>
                      <td className="px-3 py-2 font-semibold" style={{ color: meta.color }}>
                        {meta.emoji} {meta.label}
                      </td>
                      <td className={`px-3 py-2 font-mono ${e.alpha >= 0 ? "text-green-400" : "text-red-400"}`}>
                        {e.alpha.toFixed(4)}
                      </td>
                      <td className={`px-3 py-2 font-mono ${e.S > 0 ? "text-green-400" : "text-red-400"}`}>
                        {e.S.toFixed(3)}
                      </td>
                      <td className="px-3 py-2">{(e.win_rate * 100).toFixed(0)}%</td>
                      <td className="px-3 py-2">{e.reward_risk.toFixed(2)}</td>
                      <td className="px-3 py-2">{e.profit_factor.toFixed(2)}</td>
                      <td className="px-3 py-2">{e.delta.toFixed(3)}</td>
                      <td className="px-3 py-2">{e.independence.toFixed(2)}</td>
                      <td className="px-3 py-2">
                        <span className={e.regime_gate === 1 ? "text-green-400" : "text-zinc-600"}>
                          {e.regime_gate === 1 ? "ON" : "OFF"}
                        </span>
                      </td>
                      <td className="px-3 py-2">{e.trade_count}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Tab: Ω Cycle ── */}
      {activeTab === "omega" && (
        <div className="space-y-4">
          {omegaStatus && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              {[
                { label: "Cycles run",    val: omegaStatus.cycle_count },
                { label: "Decline count", val: omegaStatus.decline_count, warn: omegaStatus.decline_count >= 2 },
                { label: "Low-C count",   val: omegaStatus.low_C_count,   warn: omegaStatus.low_C_count >= 1 },
                { label: "Last run",      val: omegaStatus.last_cycle_at
                  ? new Date(omegaStatus.last_cycle_at).toLocaleTimeString() : "pending" },
              ].map(({ label, val, warn }) => (
                <Card key={label} className="bg-zinc-900/50 border-zinc-800">
                  <CardContent className="p-3">
                    <div className="text-[10px] text-zinc-500 uppercase mb-1">{label}</div>
                    <div className={`text-lg font-bold ${warn ? "text-amber-400" : "text-white"}`}>{val}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-xs text-zinc-500 font-semibold uppercase tracking-wide">Recent Ω actions</p>
            {omegaFixes.length === 0
              ? <p className="text-sm text-zinc-600 py-4 text-center">No fixes recorded yet — first cycle in 5 min after startup.</p>
              : omegaFixes.map((f, i) => <OmegaFix key={i} fix={f} />)
            }
          </div>
        </div>
      )}

      {/* ── Tab: Memory ── */}
      {activeTab === "memory" && (
        <div className="space-y-6">
          {memorySummary && memorySummary.total > 0 && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
              {[
                { label: "Total memories",   val: memorySummary.total },
                { label: "Win rate",         val: `${(memorySummary.win_rate * 100).toFixed(1)}%` },
                { label: "Avg PnL",          val: `${memorySummary.avg_pnl_pct > 0 ? "+" : ""}${memorySummary.avg_pnl_pct?.toFixed(2)}%` },
                { label: "Liquidations",     val: memorySummary.liquidations },
              ].map(({ label, val }) => (
                <Card key={label} className="bg-zinc-900/50 border-zinc-800">
                  <CardContent className="p-3">
                    <div className="text-[10px] text-zinc-500 uppercase mb-1">{label}</div>
                    <div className="text-lg font-bold text-white">{val}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}

          <div>
            <p className="text-xs text-zinc-500 font-semibold uppercase tracking-wide mb-3">
              retrieve(pattern, n=8) — find similar historical setups
            </p>
            <MemoryPanel />
          </div>
        </div>
      )}

      {/* ── Tab: Accounts ── */}
      {activeTab === "accounts" && (
        <AccountsTab curves={equityCurves} weekly={weeklySummary} />
      )}

      {/* ── Tab: Web Intel ── */}
      {activeTab === "web" && (
        <div className="space-y-4">
          <div className="flex items-center gap-2 text-xs text-zinc-500">
            <Globe className="w-4 h-4" />
            relevance(w) = sim(w, |Ψ⟩) × novelty(w) × credibility(w)
            &nbsp;·&nbsp; LΦ floor = 0.50 &nbsp;·&nbsp; crawls every 24h
          </div>
          {webDocs.length === 0
            ? (
              <div className="text-center py-12 text-zinc-600">
                <Globe className="w-8 h-8 mx-auto mb-3 opacity-40" />
                <p className="text-sm">First crawl in 10 min after startup.</p>
                <p className="text-xs mt-1">Sources: arXiv, GitHub, Fear&amp;Greed, CoinGecko</p>
              </div>
            )
            : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {webDocs.map((d, i) => <WebDoc key={i} doc={d} />)}
              </div>
            )
          }
        </div>
      )}

    </div>
  );
}
