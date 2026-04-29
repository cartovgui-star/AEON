import React, { useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  Bell,
  Brain,
  ChevronRight,
  CircleDot,
  Cpu,
  Gauge,
  Hexagon,
  Lock,
  Pause,
  Phone,
  Play,
  Power,
  Radio,
  RefreshCw,
  ScanLine,
  Send,
  Shield,
  Sparkles,
  Terminal,
  Waves,
  Zap,
} from "lucide-react";
import { buildAeonHubState, hubTabs } from "./aeonHubData";

const moduleMeta = {
  hub: {
    label: "Hub",
    icon: Hexagon,
    signal: "core",
    title: "AEON Hub",
    brief: "Central operating layer for private market command.",
  },
  engines: {
    label: "Engines",
    icon: Cpu,
    signal: "logic",
    title: "Engine Bay",
    brief: "Strategy units, edge pressure, tier health, and governance states.",
  },
  exposure: {
    label: "Exposure",
    icon: Gauge,
    signal: "heat",
    title: "Exposure Field",
    brief: "Portfolio heat, account pressure, directional balance, and concentration.",
  },
  oracle: {
    label: "Oracle",
    icon: Brain,
    signal: "sense",
    title: "Oracle Layer",
    brief: "Regime interpretation, entropy, confidence, and tactical blindspots.",
  },
  control: {
    label: "Control",
    icon: Shield,
    signal: "gates",
    title: "Control Room",
    brief: "Operator actions, trust gates, alerts, voice link, and hard stops.",
  },
};

const toneForRisk = (risk) => {
  if (String(risk).includes("elevated")) return "danger";
  if (String(risk).includes("guarded")) return "warning";
  return "live";
};

function formatMoney(value) {
  return `$${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

function ModuleDock({ active, setActive, data }) {
  const heat = Math.min(100, Math.max(0, Number(data.exposure.portfolioHeat || 0)));

  return (
    <nav className="aeon-os-dock" aria-label="AEON Hub modules">
      {hubTabs.map((tab) => {
        const meta = moduleMeta[tab];
        const Icon = meta.icon;
        const selected = active === tab;
        return (
          <button key={tab} onClick={() => setActive(tab)} className={selected ? "is-active" : ""}>
            <span className="aeon-os-dock-icon"><Icon className="h-5 w-5" /></span>
            <span className="aeon-os-dock-text">
              <strong>{meta.label}</strong>
              <small>{tab === "exposure" ? `${heat}% ${meta.signal}` : meta.signal}</small>
            </span>
            <span className="aeon-os-dock-pulse" />
          </button>
        );
      })}
    </nav>
  );
}

function OrbitalCore({ data, active, setActive }) {
  const { system, exposure } = data;
  const health = Math.max(0, Math.min(100, Number(system.healthScore || 0)));
  const riskTone = toneForRisk(system.riskState);
  const liveRatio = Math.max(0.08, Math.min(1, Number(system.activeEngines || 0) / Math.max(1, Number(system.totalEngines || 1))));
  const heatRatio = Math.max(0.08, Math.min(1, Number(exposure.portfolioHeat || 0) / 100));

  return (
    <section className={`aeon-os-core aeon-os-core-${riskTone}`}>
      <div className="aeon-os-core-grid" />
      <div className="aeon-os-radar-sweep" />
      <div className="aeon-os-orbit aeon-os-orbit-a" />
      <div className="aeon-os-orbit aeon-os-orbit-b" />
      <div className="aeon-os-orbit aeon-os-orbit-c" />
      <button className="aeon-os-core-orb" onClick={() => setActive("hub")} aria-label="Return to Hub core">
        <span className="aeon-os-orb-glass" />
        <span className="aeon-os-orb-title">AEON</span>
        <strong>{health}</strong>
        <small>HUB CORE</small>
      </button>
      <div className="aeon-os-vector aeon-os-vector-engines" style={{ "--load": liveRatio }} />
      <div className="aeon-os-vector aeon-os-vector-heat" style={{ "--load": heatRatio }} />
      {["engines", "exposure", "oracle", "control"].map((tab, index) => {
        const Icon = moduleMeta[tab].icon;
        return (
          <button
            key={tab}
            onClick={() => setActive(tab)}
            className={`aeon-os-satellite aeon-os-satellite-${index + 1} ${active === tab ? "is-active" : ""}`}
          >
            <Icon className="h-4 w-4" />
            <span>{moduleMeta[tab].label}</span>
          </button>
        );
      })}
    </section>
  );
}

function StatusStrip({ props, data }) {
  const { system, exposure } = data;
  return (
    <div className="aeon-os-status-strip">
      <div><span>Stream</span><strong className={props.wsConnected ? "is-live" : "is-warning"}>{props.wsConnected ? "LIVE" : "RELINK"}</strong></div>
      <div><span>Mode</span><strong className={props.tradingStats?.active ? "is-live" : "is-warning"}>{props.tradingStats?.active ? "ACTIVE" : "PAUSED"}</strong></div>
      <div><span>Risk</span><strong className={`is-${toneForRisk(system.riskState)}`}>{system.riskState}</strong></div>
      <div><span>Heat</span><strong>{exposure.portfolioHeat}%</strong></div>
      <div><span>Regime</span><strong>{system.regime}</strong></div>
    </div>
  );
}

function DispatchFeed({ feed, warnings = [], banner, unreadAlerts, onClear }) {
  const packets = [
    banner ? { id: "banner", tone: "danger", title: "REGIME SHIFT", body: `${banner.from} to ${banner.to}${banner.H ? ` / H ${banner.H}` : ""}` } : null,
    ...warnings.map((warning, index) => ({ id: `warning-${index}`, tone: "warning", title: "OPERATOR WARNING", body: warning })),
    ...feed,
  ].filter(Boolean).slice(0, 7);

  return (
    <section className="aeon-os-dispatch">
      <div className="aeon-os-section-head">
        <div>
          <span>Dispatch</span>
          <h2>Live command feed</h2>
        </div>
        {unreadAlerts ? <button onClick={onClear}>{unreadAlerts} clear</button> : <Activity className="h-5 w-5" />}
      </div>
      <div className="aeon-os-feed-line" />
      <div className="aeon-os-feed">
        {packets.length ? packets.map((item, index) => (
          <article key={item.id || index} className={`aeon-os-packet aeon-os-packet-${item.tone || "live"}`}>
            <CircleDot className="h-4 w-4" />
            <div>
              <strong>{item.title || "dispatch"}</strong>
              <p>{item.body || "Signal packet received."}</p>
            </div>
          </article>
        )) : (
          <article className="aeon-os-packet aeon-os-packet-live">
            <CircleDot className="h-4 w-4" />
            <div><strong>STANDBY</strong><p>No pressure packets in the current window.</p></div>
          </article>
        )}
      </div>
    </section>
  );
}

function StatBlade({ label, value, detail, tone = "live", icon: Icon = Zap }) {
  return (
    <div className={`aeon-os-blade aeon-os-blade-${tone}`}>
      <Icon className="h-5 w-5" />
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </div>
  );
}

function HubScreen({ data, props, setActive }) {
  const { system, exposure } = data;
  return (
    <div className="aeon-os-layout aeon-os-layout-hub">
      <OrbitalCore data={data} active="hub" setActive={setActive} />
      <div className="aeon-os-command-bank">
        <StatBlade icon={Cpu} label="Engine Load" value={`${system.activeEngines}/${system.totalEngines}`} detail="active strategy units" />
        <StatBlade icon={Gauge} label="Exposure" value={`${exposure.portfolioHeat}%`} detail={`${exposure.openCount} open positions`} tone={exposure.portfolioHeat > 65 ? "danger" : "warning"} />
        <StatBlade icon={Brain} label="Oracle" value={system.regime} detail="current regime read" tone="sense" />
        <StatBlade icon={Radio} label="Market" value={system.btcPrice ? formatMoney(system.btcPrice) : "SYNC"} detail="BTC reference feed" tone="signal" />
      </div>
      <div className="aeon-os-module-gates">
        {["engines", "exposure", "oracle", "control"].map((tab) => {
          const meta = moduleMeta[tab];
          const Icon = meta.icon;
          return (
            <button key={tab} onClick={() => setActive(tab)}>
              <Icon className="h-5 w-5" />
              <strong>{meta.label}</strong>
              <span>{meta.brief}</span>
              <ChevronRight className="h-4 w-4" />
            </button>
          );
        })}
      </div>
      <DispatchFeed feed={data.feed} warnings={props.operatorWarnings} banner={props.regimeBanner} unreadAlerts={props.unreadAlerts} onClear={props.actions?.clearAlerts} />
    </div>
  );
}

function EnginesScreen({ data }) {
  return (
    <div className="aeon-os-layout">
      <section className="aeon-os-engine-bay">
        {data.engines.map((engine, index) => (
          <article key={engine.name} className={`aeon-os-engine-unit aeon-os-engine-${engine.status}`}>
            <div className="aeon-os-engine-index">{String(index + 1).padStart(2, "0")}</div>
            <div>
              <strong>{engine.name}</strong>
              <span>{engine.status} / tier {engine.tier}</span>
            </div>
            <div className="aeon-os-engine-edge">{engine.edge}</div>
            <div className="aeon-os-meter"><i style={{ width: `${Math.max(8, Math.min(100, engine.heat))}%` }} /></div>
          </article>
        ))}
      </section>
      <section className="aeon-os-side-console">
        <StatBlade icon={Cpu} label="Stack" value={`${data.system.activeEngines}/${data.system.totalEngines}`} detail="live units" />
        <StatBlade icon={AlertTriangle} label="Constraint" value={data.engines.filter((engine) => ["restricted", "stale"].includes(engine.status)).length} detail="gated units" tone="danger" />
        <StatBlade icon={Sparkles} label="Edge" value={Math.round(data.engines.reduce((sum, engine) => sum + Number(engine.edge || 0), 0) / Math.max(1, data.engines.length))} detail="average signal score" tone="sense" />
      </section>
    </div>
  );
}

function ExposureScreen({ data }) {
  const { exposure } = data;
  return (
    <div className="aeon-os-layout">
      <section className="aeon-os-exposure-field">
        <div className="aeon-os-pressure-core">
          <Waves className="h-8 w-8" />
          <strong>{exposure.portfolioHeat}%</strong>
          <span>PORTFOLIO HEAT</span>
        </div>
        <div className="aeon-os-balance-line">
          <div><strong>{exposure.longPct}%</strong><span>long</span></div>
          <div><strong>{exposure.shortPct}%</strong><span>short</span></div>
        </div>
        <div className="aeon-os-symbols">
          {exposure.symbols.map((item) => (
            <div key={item.symbol}>
              <span>{item.symbol}</span>
              <i style={{ height: `${item.heat}%` }} />
              <strong>{item.heat}</strong>
            </div>
          ))}
        </div>
      </section>
      <section className="aeon-os-account-stack">
        {exposure.accounts.map((account) => {
          const heat = Math.round(Number(account.portfolio_heat || 0) * 100);
          return (
            <article key={account.account_id}>
              <div><strong>{account.account_id}</strong><span>{formatMoney(account.balance)}</span></div>
              <div className="aeon-os-meter"><i style={{ width: `${Math.max(4, heat)}%` }} /></div>
              <b>{heat}%</b>
            </article>
          );
        })}
      </section>
    </div>
  );
}

function OracleScreen({ data }) {
  const { oracle, system } = data;
  return (
    <div className="aeon-os-layout">
      <section className="aeon-os-oracle-scope">
        <div className="aeon-os-radar-disc" />
        <div className="aeon-os-oracle-read">
          <span>REGIME</span>
          <strong>{system.regime}</strong>
          <p>{oracle.volatility} volatility / {oracle.confidence}% confidence</p>
        </div>
        <div className="aeon-os-oracle-metrics">
          <StatBlade label="H" value={oracle.H.toFixed(3)} detail="entropy" tone="danger" />
          <StatBlade label="C" value={oracle.C.toFixed(3)} detail="coherence" tone="signal" />
          <StatBlade label="S" value={oracle.S.toFixed(3)} detail="structure" tone="warning" />
        </div>
      </section>
      <section className="aeon-os-intel-stack">
        {oracle.notes.map((note) => <article key={note}>{note}</article>)}
        {oracle.blindspots.map((blindspot) => (
          <article key={`${blindspot.label}-${blindspot.engine}`} className="is-blindspot">
            <strong>{blindspot.label}</strong>
            <span>{blindspot.engine} / severity {blindspot.severity}</span>
          </article>
        ))}
      </section>
    </div>
  );
}

function ControlScreen({ props }) {
  const actions = props.actions || {};
  const active = props.tradingStats?.active;
  const controls = [
    { icon: active ? Pause : Play, label: active ? "Pause Flow" : "Resume Flow", action: active ? actions.pauseTrading : actions.resumeTrading, danger: active },
    { icon: ScanLine, label: "Oracle Sweep", action: actions.runScan },
    { icon: Bell, label: "Alert Link", action: actions.toggleNotifications, active: props.notificationsEnabled },
    { icon: Phone, label: "Voice Link", action: actions.openVoice },
    { icon: RefreshCw, label: "Refresh Truth", action: actions.refresh },
  ];

  return (
    <div className="aeon-os-layout">
      <section className="aeon-os-control-matrix">
        {controls.map((control) => {
          const Icon = control.icon;
          return (
            <button key={control.label} onClick={control.action} className={`${control.danger ? "is-danger" : ""} ${control.active ? "is-active" : ""}`}>
              <Icon className="h-6 w-6" />
              <strong>{control.label}</strong>
              <span>{control.danger ? "armed live endpoint" : "operator command"}</span>
            </button>
          );
        })}
      </section>
      <section className="aeon-os-lock-stack">
        <StatBlade icon={Lock} label="Governance" value="GATED" detail="engine permissions active" tone="danger" />
        <StatBlade icon={Power} label="Mode" value={active ? "ACTIVE" : "PAUSED"} detail="execution posture" tone={active ? "live" : "warning"} />
        <a href="https://t.me/ObsidianCabalbot" target="_blank" rel="noopener noreferrer" className="aeon-os-telegram">
          <Send className="h-5 w-5" />
          <span>Telegram relay</span>
        </a>
      </section>
    </div>
  );
}

function ActiveScreen({ active, data, props, setActive }) {
  if (active === "engines") return <EnginesScreen data={data} />;
  if (active === "exposure") return <ExposureScreen data={data} />;
  if (active === "oracle") return <OracleScreen data={data} />;
  if (active === "control") return <ControlScreen props={props} />;
  return <HubScreen data={data} props={props} setActive={setActive} />;
}

export default function AeonHub(props) {
  const [active, setActive] = useState("hub");
  const data = useMemo(() => buildAeonHubState(props), [props]);
  const meta = moduleMeta[active];
  const Icon = meta.icon;

  return (
    <div className="aeon-os-shell">
      <div className="aeon-os-bg-grid" />
      <div className="aeon-os-bg-scan" />
      <div className="aeon-os-light aeon-os-light-a" />
      <div className="aeon-os-light aeon-os-light-b" />

      <ModuleDock active={active} setActive={setActive} data={data} />

      <main className="aeon-os-main">
        <header className="aeon-os-header">
          <div>
            <div className="aeon-os-kicker"><span /> AEON HUB / {meta.signal}</div>
            <h1><Icon className="h-7 w-7" /> {meta.title}</h1>
            <p>{meta.brief}</p>
          </div>
          <StatusStrip props={props} data={data} />
        </header>

        <ActiveScreen active={active} data={data} props={props} setActive={setActive} />
      </main>
    </div>
  );
}
