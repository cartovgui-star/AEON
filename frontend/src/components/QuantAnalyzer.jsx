import { useState, useCallback } from "react";
import axios from "axios";
import {
  TrendingUp, TrendingDown, Minus, Target, BarChart3,
  RefreshCw, Search, ChevronDown, ChevronRight, AlertTriangle,
  Activity, Layers, Zap
} from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const DEFAULT_SYMBOLS = "BTC/USDT,ETH/USDT,SOL/USDT,BNB/USDT,XRP/USDT,AVAX/USDT,DOGE/USDT,LINK/USDT,DOT/USDT,ADA/USDT";

// ── helpers ───────────────────────────────────────────────────────────────────

const signalColor = (sig) => {
  if (!sig) return "text-zinc-400";
  const s = sig.toLowerCase();
  if (s.includes("strong buy"))  return "text-emerald-400";
  if (s.includes("buy"))         return "text-green-400";
  if (s.includes("strong sell")) return "text-red-500";
  if (s.includes("sell"))        return "text-red-400";
  return "text-zinc-400";
};

const signalBg = (sig) => {
  if (!sig) return "bg-zinc-800 border-zinc-700";
  const s = sig.toLowerCase();
  if (s.includes("strong buy"))  return "bg-emerald-500/10 border-emerald-500/30";
  if (s.includes("buy"))         return "bg-green-500/10 border-green-500/30";
  if (s.includes("strong sell")) return "bg-red-600/10 border-red-600/30";
  if (s.includes("sell"))        return "bg-red-500/10 border-red-500/30";
  return "bg-zinc-800/50 border-zinc-700/50";
};

const scoreColor = (score) => {
  if (score >= 8)  return "text-emerald-400";
  if (score >= 6.5) return "text-green-400";
  if (score >= 5)  return "text-yellow-400";
  if (score >= 3.5) return "text-orange-400";
  return "text-red-400";
};

const dirIcon = (direction) => {
  if (direction === "BULLISH") return <TrendingUp className="w-3 h-3 text-emerald-400 inline" />;
  if (direction === "BEARISH") return <TrendingDown className="w-3 h-3 text-red-400 inline" />;
  return <Minus className="w-3 h-3 text-zinc-400 inline" />;
};

const fmt = (v, decimals = 4) => {
  if (v == null) return "—";
  const n = parseFloat(v);
  if (isNaN(n)) return "—";
  if (n >= 1000) return n.toLocaleString("en-US", { maximumFractionDigits: 2 });
  return n.toFixed(decimals);
};

const pct = (v) => v != null ? `${v > 0 ? "+" : ""}${parseFloat(v).toFixed(2)}%` : "—";

// ── sub-components ────────────────────────────────────────────────────────────

function ScoreBar({ score }) {
  const w = Math.round((score / 10) * 100);
  const color =
    score >= 8  ? "bg-emerald-500" :
    score >= 6.5 ? "bg-green-500" :
    score >= 5  ? "bg-yellow-500" :
    score >= 3.5 ? "bg-orange-500" : "bg-red-500";
  return (
    <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-1">
      <div className={`${color} h-1.5 rounded-full transition-all duration-500`} style={{ width: `${w}%` }} />
    </div>
  );
}

function TrendRow({ label, dir, strength, slope }) {
  const c = dir === "BULLISH" ? "text-emerald-400" : dir === "BEARISH" ? "text-red-400" : "text-zinc-400";
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-zinc-500 text-xs w-14">{label}</span>
      <span className={`text-xs font-medium ${c} flex items-center gap-1`}>
        {dirIcon(dir)} {dir}
      </span>
      <span className="text-zinc-500 text-xs">{strength}</span>
      <span className="text-zinc-600 text-xs">{slope != null ? pct(slope) : ""}</span>
    </div>
  );
}

function Section({ title, icon: Icon, children, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-zinc-800/60 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2 bg-zinc-900/60 hover:bg-zinc-800/60 transition-colors"
      >
        <div className="flex items-center gap-2 text-zinc-300 text-xs font-semibold">
          {Icon && <Icon className="w-3.5 h-3.5 text-orange-400" />}
          {title}
        </div>
        {open ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500" />}
      </button>
      {open && <div className="px-3 py-2 bg-zinc-950/40">{children}</div>}
    </div>
  );
}

function TradePlanBlock({ plan }) {
  if (!plan || plan.side === "NEUTRAL") {
    return <p className="text-zinc-500 text-xs">{plan?.note || "No directional bias."}</p>;
  }
  const isLong = plan.side === "LONG";
  return (
    <div className="space-y-2">
      <div className={`inline-block text-xs px-2 py-0.5 rounded font-bold ${isLong ? "bg-emerald-500/20 text-emerald-400" : "bg-red-500/20 text-red-400"}`}>
        {plan.side}
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div>
          <span className="text-zinc-500">Entry</span>
          <span className="ml-2 text-white font-mono">{fmt(plan.entry)}</span>
        </div>
        <div>
          <span className="text-zinc-500">Stop</span>
          <span className="ml-2 text-red-400 font-mono">{fmt(plan.stop)}</span>
        </div>
        <div>
          <span className="text-zinc-500">TP1</span>
          <span className="ml-2 text-emerald-400 font-mono">{fmt(plan.tp1)}</span>
          <span className="ml-1 text-zinc-600 text-xs">({plan.rr1}R)</span>
        </div>
        <div>
          <span className="text-zinc-500">TP2</span>
          <span className="ml-2 text-emerald-400 font-mono">{fmt(plan.tp2)}</span>
          <span className="ml-1 text-zinc-600 text-xs">({plan.rr2}R)</span>
        </div>
        <div>
          <span className="text-zinc-500">TP3</span>
          <span className="ml-2 text-emerald-400 font-mono">{fmt(plan.tp3)}</span>
          <span className="ml-1 text-zinc-600 text-xs">({plan.rr3}R)</span>
        </div>
      </div>
    </div>
  );
}

function CoinCard({ report }) {
  const { symbol, price, score, signal, trend_structure, key_levels, moving_averages,
          momentum, volume, chart_patterns, fibonacci, volatility, trade_plan } = report;

  return (
    <div className={`rounded-xl border p-4 space-y-3 ${signalBg(signal)}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-white font-bold text-lg">{symbol.replace("/USDT", "")}<span className="text-zinc-500 text-sm">/USDT</span></h3>
          <p className="text-zinc-400 text-xs font-mono">${fmt(price, price >= 1 ? 2 : 6)}</p>
        </div>
        <div className="text-right">
          <p className={`text-xl font-bold ${scoreColor(score)}`}>{score}<span className="text-zinc-500 text-sm">/10</span></p>
          <p className={`text-xs font-semibold ${signalColor(signal)}`}>{signal}</p>
          <ScoreBar score={score} />
        </div>
      </div>

      {/* Trend alignment badge */}
      <div className="text-xs text-zinc-400 bg-zinc-900/50 rounded px-2 py-1">
        {trend_structure?.alignment} — <span className="text-zinc-500">{trend_structure?.tf_summary}</span>
      </div>

      {/* Sections */}
      <div className="space-y-1.5">

        {/* Trend Structure */}
        <Section title="Trend Structure" icon={Activity} defaultOpen>
          <div className="space-y-0.5">
            {trend_structure?.timeframes && Object.entries(trend_structure.timeframes).map(([tf, t]) => (
              <TrendRow key={tf} label={tf} dir={t.direction} strength={t.strength} slope={t.slope_pct} />
            ))}
          </div>
        </Section>

        {/* Key Levels */}
        <Section title="Key Levels" icon={Layers}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <div>
              <p className="text-zinc-500 mb-1">Resistances</p>
              {key_levels?.resistances?.slice(0, 3).map((r, i) => (
                <p key={i} className="text-red-400 font-mono">{fmt(r)}</p>
              ))}
            </div>
            <div>
              <p className="text-zinc-500 mb-1">Supports</p>
              {key_levels?.supports?.slice(-3).reverse().map((s, i) => (
                <p key={i} className="text-emerald-400 font-mono">{fmt(s)}</p>
              ))}
            </div>
            {key_levels?.critical_level && (
              <div className="col-span-2 mt-1 border-t border-zinc-800 pt-1">
                <span className="text-zinc-500">Critical {key_levels.critical_type}: </span>
                <span className="text-orange-400 font-mono font-bold">{fmt(key_levels.critical_level)}</span>
              </div>
            )}
          </div>
        </Section>

        {/* Moving Averages */}
        <Section title="Moving Averages" icon={BarChart3}>
          <div className="space-y-1">
            <div className="flex gap-2 flex-wrap">
              {moving_averages?.positions && Object.entries(moving_averages.positions).map(([ema, data]) => (
                <div key={ema} className="text-xs">
                  <span className="text-zinc-500">{ema.toUpperCase()}: </span>
                  <span className={data.price_vs === "above" ? "text-emerald-400" : "text-red-400"}>
                    {data.price_vs} ({pct(data.gap_pct)})
                  </span>
                </div>
              ))}
            </div>
            <p className="text-xs">
              <span className="text-zinc-500">Stack: </span>
              <span className={moving_averages?.stack === "bullish" ? "text-emerald-400" : moving_averages?.stack === "bearish" ? "text-red-400" : "text-yellow-400"}>
                {moving_averages?.stack}
              </span>
            </p>
            {moving_averages?.crossovers?.length > 0 && (
              <div className="text-xs space-y-0.5">
                {moving_averages.crossovers.map((xo, i) => (
                  <p key={i} className={xo.type === "golden" ? "text-emerald-400" : "text-red-400"}>
                    {xo.type === "golden" ? "🟡 Golden" : "💀 Death"} Cross EMA{xo.fast}/EMA{xo.slow}
                    {xo.bars_ago > 0 && ` (${xo.bars_ago} bars ago)`}
                  </p>
                ))}
              </div>
            )}
          </div>
        </Section>

        {/* Momentum */}
        <Section title="Momentum" icon={Zap}>
          <div className="space-y-1.5 text-xs">
            {/* RSI */}
            <div>
              <span className="text-zinc-500">RSI(14): </span>
              <span className={momentum?.rsi?.value >= 70 ? "text-red-400" : momentum?.rsi?.value <= 30 ? "text-emerald-400" : "text-yellow-400"}>
                {momentum?.rsi?.value}
              </span>
              <span className="text-zinc-500 ml-2">— {momentum?.rsi?.state}</span>
              {momentum?.rsi?.divergence !== "none" && (
                <span className="ml-2 text-orange-400">⚡ {momentum.rsi.divergence}</span>
              )}
            </div>
            {/* MACD */}
            <p className="text-zinc-400">{momentum?.macd?.interpretation}</p>
            {/* Stoch */}
            <p className="text-zinc-400">{momentum?.stoch_rsi?.interpretation}
              {" "}K={momentum?.stoch_rsi?.k} D={momentum?.stoch_rsi?.d}
            </p>
          </div>
        </Section>

        {/* Volume */}
        <Section title="Volume" icon={BarChart3}>
          <p className="text-xs text-zinc-300">{volume?.interpretation}</p>
          {volume?.anomaly && (
            <p className="text-xs text-orange-400 mt-1 flex items-center gap-1">
              <AlertTriangle className="w-3 h-3" /> {volume.anomaly}
            </p>
          )}
        </Section>

        {/* Chart Patterns */}
        {chart_patterns?.length > 0 && (
          <Section title={`Chart Patterns (${chart_patterns.length})`} icon={Target}>
            <div className="space-y-2">
              {chart_patterns.map((p, i) => (
                <div key={i} className={`rounded p-2 text-xs ${p.direction === "BULLISH" ? "bg-emerald-500/10" : "bg-red-500/10"}`}>
                  <p className="font-semibold text-white">{p.name} <span className="text-zinc-500">({p.status})</span></p>
                  <p className="text-zinc-400 mt-0.5">{p.notes}</p>
                  {p.target && <p className="text-zinc-500 mt-0.5">Target: <span className="font-mono text-white">{fmt(p.target)}</span></p>}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* Fibonacci */}
        <Section title="Fibonacci" icon={Layers}>
          <div className="text-xs space-y-1">
            <p className="text-zinc-500">
              Swing: <span className="text-white font-mono">{fmt(fibonacci?.swing_low)} → {fmt(fibonacci?.swing_high)}</span>
              <span className="ml-2">{dirIcon(fibonacci?.direction === "up" ? "BULLISH" : "BEARISH")}</span>
            </p>
            <div className="grid grid-cols-3 gap-1 mt-1">
              {fibonacci?.retracements && Object.entries(fibonacci.retracements).slice(1, 6).map(([lvl, price]) => (
                <div key={lvl} className="bg-zinc-900/50 rounded px-1.5 py-0.5">
                  <span className="text-zinc-500">{(parseFloat(lvl) * 100).toFixed(1)}%</span>
                  <span className="ml-1 text-white font-mono">{fmt(price)}</span>
                </div>
              ))}
            </div>
            <p className="text-zinc-500 mt-1">Nearest: <span className="text-orange-400">{(parseFloat(fibonacci?.nearest_level || 0) * 100).toFixed(1)}%</span> @ <span className="font-mono text-white">{fmt(fibonacci?.nearest_price)}</span></p>
          </div>
        </Section>

        {/* Volatility */}
        <Section title="Volatility" icon={Activity}>
          <div className="text-xs space-y-1">
            <p><span className="text-zinc-500">BB Width: </span><span className="text-white">{volatility?.bb_width_pct}%</span><span className="text-zinc-600 ml-1">({volatility?.bb_width_percentile}th pct)</span></p>
            <p><span className="text-zinc-500">ATR: </span><span className="text-white font-mono">{fmt(volatility?.atr)}</span><span className="text-zinc-500 ml-1">({volatility?.atr_pct}%)</span></p>
            <p className="text-orange-400">{volatility?.regime}</p>
          </div>
        </Section>

        {/* Trade Plan */}
        <Section title="Trade Plan" icon={Target} defaultOpen>
          <TradePlanBlock plan={trade_plan} />
        </Section>

      </div>
    </div>
  );
}

// ── watchlist table ────────────────────────────────────────────────────────────

function WatchlistTable({ rows }) {
  if (!rows?.length) return null;
  return (
    <div className="overflow-x-auto rounded-xl border border-zinc-800">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-zinc-800 bg-zinc-900/60">
            {["Coin","Signal","Score","Entry","Stop","TP1","R:R1","Alignment"].map(h => (
              <th key={h} className="px-3 py-2 text-left text-zinc-400 font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-zinc-800/40 hover:bg-zinc-800/20">
              <td className="px-3 py-2 text-white font-semibold">{r.coin?.replace("/USDT","")}</td>
              <td className={`px-3 py-2 font-medium ${signalColor(r.signal)}`}>{r.signal}</td>
              <td className={`px-3 py-2 font-bold ${scoreColor(r.score)}`}>{r.score}</td>
              <td className="px-3 py-2 font-mono text-zinc-300">{fmt(r.entry)}</td>
              <td className="px-3 py-2 font-mono text-red-400">{fmt(r.stop)}</td>
              <td className="px-3 py-2 font-mono text-emerald-400">{fmt(r.tp1)}</td>
              <td className="px-3 py-2 text-zinc-300">{r.rr1 != null ? `${r.rr1}R` : "—"}</td>
              <td className="px-3 py-2 text-zinc-500">{r.trend_alignment?.includes("✅") ? "✅ Aligned" : "⚠️ Mixed"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function QuantAnalyzer() {
  const [symbols, setSymbols]   = useState(DEFAULT_SYMBOLS);
  const [loading, setLoading]   = useState(false);
  const [data, setData]         = useState(null);
  const [error, setError]       = useState(null);
  const [view, setView]         = useState("ranked"); // "ranked" | "watchlist"

  const run = useCallback(async () => {
    if (!symbols.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const encoded = encodeURIComponent(symbols);
      const res = await axios.get(`${API}/quant/analyze?symbols=${encoded}`, { timeout: 120000 });
      setData(res.data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, [symbols]);

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-7 h-7 text-orange-400" />
            Quant Analyzer
          </h1>
          <p className="text-zinc-400 text-sm mt-0.5">
            Multi-factor technical scoring — trend, momentum, patterns, Fibonacci, volatility
          </p>
        </div>
        {data && (
          <div className="text-xs text-zinc-500">
            {data.total_analyzed} coins analyzed · {new Date(data.generated_at).toLocaleTimeString()}
          </div>
        )}
      </div>

      {/* Input row */}
      <div className="flex flex-col sm:flex-row gap-2">
        <div className="flex-1 relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            value={symbols}
            onChange={e => setSymbols(e.target.value)}
            onKeyDown={e => e.key === "Enter" && run()}
            placeholder="BTC/USDT, ETH/USDT, SOL/USDT ..."
            className="w-full pl-9 pr-4 py-2.5 bg-zinc-900 border border-zinc-700 rounded-lg text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-orange-500"
          />
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="flex items-center gap-2 px-5 py-2.5 bg-orange-500 hover:bg-orange-600 disabled:bg-zinc-700 disabled:text-zinc-500 text-white rounded-lg text-sm font-semibold transition-colors"
        >
          {loading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
          {loading ? "Analyzing..." : "Analyze"}
        </button>
      </div>

      {error && (
        <div className="flex items-center gap-2 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-3 text-red-400 text-sm">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          {error}
        </div>
      )}

      {loading && (
        <div className="text-center py-16">
          <RefreshCw className="w-10 h-10 text-orange-400 animate-spin mx-auto mb-4" />
          <p className="text-zinc-400 text-sm">Running multi-factor analysis across all timeframes…</p>
          <p className="text-zinc-600 text-xs mt-1">This can take 30–60 seconds for many coins</p>
        </div>
      )}

      {data && !loading && (
        <div className="space-y-4">
          {/* View toggle */}
          <div className="flex gap-2">
            {["ranked","watchlist"].map(v => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-colors capitalize ${
                  view === v ? "bg-orange-500 text-white" : "bg-zinc-800 text-zinc-400 hover:text-white"
                }`}
              >
                {v === "ranked" ? "Ranked Reports" : "Watchlist Table"}
              </button>
            ))}
          </div>

          {/* Errors */}
          {data.errors?.length > 0 && (
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg px-4 py-3">
              <p className="text-zinc-500 text-xs font-medium mb-1">Failed / No data:</p>
              <div className="flex flex-wrap gap-2">
                {data.errors.map((e, i) => (
                  <span key={i} className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded">
                    {e.symbol} — {e.error}
                  </span>
                ))}
              </div>
            </div>
          )}

          {view === "ranked" && (
            <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
              {data.ranked_reports.map((report, i) => (
                <div key={report.symbol} className="relative">
                  {i === 0 && (
                    <div className="absolute -top-2 -right-2 z-10 bg-orange-500 text-white text-xs px-2 py-0.5 rounded-full font-bold shadow">
                      #1 Setup
                    </div>
                  )}
                  <CoinCard report={report} />
                </div>
              ))}
            </div>
          )}

          {view === "watchlist" && <WatchlistTable rows={data.watchlist_table} />}
        </div>
      )}

      {!data && !loading && !error && (
        <div className="text-center py-20 text-zinc-600">
          <BarChart3 className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm">Enter coins and click Analyze to run the quant engine</p>
        </div>
      )}
    </div>
  );
}
