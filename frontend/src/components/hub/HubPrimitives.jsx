import React from "react";
import { Activity, AlertTriangle, CheckCircle2, Radio, Shield, Zap } from "lucide-react";

export function HubPanel({ children, className = "", glow = "cyan" }) {
  return (
    <section className={`aeon-hub-panel aeon-hub-glow-${glow} ${className}`}>
      {children}
    </section>
  );
}

export function StatusChip({ status = "stable", children }) {
  const normalized = String(status).toLowerCase();
  const Icon = normalized.includes("restricted") || normalized.includes("danger")
    ? AlertTriangle
    : normalized.includes("healthy") || normalized.includes("stable")
      ? CheckCircle2
      : Activity;

  return (
    <span className={`aeon-status-chip aeon-status-${normalized}`}>
      <Icon className="h-3.5 w-3.5" />
      {children || status}
    </span>
  );
}

export function MetricPill({ label, value, subvalue, tone = "cyan" }) {
  return (
    <div className={`aeon-metric-pill aeon-metric-${tone}`}>
      <div className="text-[10px] uppercase tracking-[0.2em] text-zinc-500">{label}</div>
      <div className="mt-1 font-mono text-lg font-semibold text-white">{value}</div>
      {subvalue ? <div className="text-[11px] text-zinc-500">{subvalue}</div> : null}
    </div>
  );
}

export function BarMeter({ value, tone = "cyan", className = "" }) {
  const width = Math.max(0, Math.min(100, Number(value) || 0));
  return (
    <div className={`h-2 overflow-hidden rounded-full bg-white/[0.06] ${className}`}>
      <div className={`h-full rounded-full aeon-bar-${tone}`} style={{ width: `${width}%` }} />
    </div>
  );
}

export function SystemOrb({ health = 72, regime = "RANGING", riskState = "guarded" }) {
  const score = Math.max(0, Math.min(100, Number(health) || 0));
  const deg = Math.round(score * 3.6);

  return (
    <div className="aeon-orb-wrap">
      <div className="aeon-orb-ring" style={{ "--orb-deg": `${deg}deg` }}>
        <div className="aeon-orb-core">
          <Radio className="h-6 w-6 text-cyan-200" />
          <div className="mt-2 font-mono text-4xl font-semibold text-white">{score}</div>
          <div className="text-[10px] uppercase tracking-[0.3em] text-cyan-200/80">health</div>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap justify-center gap-2">
        <StatusChip status={riskState}>{riskState}</StatusChip>
        <StatusChip status="stable">{regime}</StatusChip>
      </div>
    </div>
  );
}

export function FeedItem({ item }) {
  return (
    <div className={`aeon-feed-item aeon-feed-${item.tone || "cyan"}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-current shadow-[0_0_16px_currentColor]" />
            <div className="truncate text-xs uppercase tracking-[0.22em] text-zinc-400">{item.title}</div>
          </div>
          <div className="mt-1 line-clamp-2 text-sm text-zinc-100">{item.body}</div>
        </div>
        <Zap className="h-4 w-4 flex-none text-zinc-500" />
      </div>
    </div>
  );
}

export function ControlBlock({ icon: Icon = Shield, title, description, actions = [], danger = false }) {
  return (
    <HubPanel glow={danger ? "red" : "amber"} className="p-4">
      <div className="flex items-start gap-3">
        <div className={`flex h-11 w-11 flex-none items-center justify-center rounded-2xl border ${danger ? "border-rose-400/25 bg-rose-500/10 text-rose-200" : "border-amber-400/20 bg-amber-500/10 text-amber-200"}`}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="font-display text-base font-semibold text-white">{title}</div>
          <div className="mt-1 text-sm text-zinc-400">{description}</div>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {actions.map((action) => (
          <button key={action} className={`rounded-2xl border px-3 py-3 text-sm font-semibold transition active:scale-[0.98] ${danger ? "border-rose-400/20 bg-rose-500/10 text-rose-100 hover:bg-rose-500/20" : "border-white/10 bg-white/[0.04] text-zinc-100 hover:bg-white/[0.08]"}`}>
            {action}
          </button>
        ))}
      </div>
    </HubPanel>
  );
}
