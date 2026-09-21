import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  Bell,
  Bot,
  Brain,
  Command,
  Cpu,
  Gauge,
  Lock,
  Menu,
  Phone,
  Power,
  Radar,
  Radio,
  RefreshCw,
  Send,
  Shield,
  Sparkles,
  Wallet,
  X,
} from "lucide-react";
import { fetchHubSnapshot, setTradingActive } from "./hubData";
import EnginesDashboard from "../EnginesDashboard";
import TradingHub from "../TradingHub";
import MarketRegime from "../MarketRegime";
import QuantAnalyzer from "../QuantAnalyzer";
import SystemHealth from "../SystemHealth";
import SettingsPanel from "../SettingsPanel";
import TradeHistory from "../TradeHistory";
import TradeAnalytics from "../TradeAnalytics";
import CommandsReference from "../CommandsReference";
import VoiceConversation from "../VoiceConversation";
import CrisisModeOverlay from "../CrisisModeOverlay";
import SoundAlertSystem from "../SoundAlertSystem";
import AeonLoader from "../AeonLoader";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const WS_URL = BACKEND_URL
  ? `${BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")}/ws`
  : "";

const navItems = [
  { id: "hub", label: "Hub", icon: Command, intent: "core" },
  { id: "engines", label: "Engines", icon: Cpu, intent: "logic" },
  { id: "exposure", label: "Exposure", icon: Wallet, intent: "risk" },
  { id: "oracle", label: "Oracle", icon: Brain, intent: "signal" },
  { id: "control", label: "Control", icon: Shield, intent: "guard" },
];

const formatPct = (value, digits = 1) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
const formatMoney = (value) =>
  `$${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;

function StatusPill({ active, label, value }) {
  return (
    <div className={`hub-status-pill ${active ? "is-live" : ""}`}>
      <span className="hub-status-dot" />
      <span>{label}</span>
      {value ? <strong>{value}</strong> : null}
    </div>
  );
}

function MetricNode({ label, value, subvalue, icon: Icon, tone = "cyan" }) {
  return (
    <div className={`hub-node hub-node-${tone}`}>
      <div className="hub-node-topline">
        <Icon className="h-4 w-4" />
        <span>{label}</span>
      </div>
      <div className="hub-node-value">{value}</div>
      {subvalue ? <div className="hub-node-subvalue">{subvalue}</div> : null}
    </div>
  );
}

function MotionField({ snapshot }) {
  const heat = Math.min(1, Math.max(0, Number(snapshot?.portfolioHeat || 0)));
  const engineLoad = Math.min(1, (snapshot?.engines?.filter((engine) => engine.active).length || 0) / 10);
  const constraint = Math.min(1, (snapshot?.restrictedEngines?.length || 0) / 6);

  return (
    <div className="hub-orbit" aria-hidden="true">
      <div className="hub-orbit-ring hub-orbit-ring-a" />
      <div className="hub-orbit-ring hub-orbit-ring-b" />
      <div className="hub-orbit-core">
        <div className="hub-core-title">AEON</div>
        <div className="hub-core-subtitle">HUB</div>
      </div>
      <div className="hub-vector hub-vector-heat" style={{ "--strength": heat }} />
      <div className="hub-vector hub-vector-engines" style={{ "--strength": engineLoad }} />
      <div className="hub-vector hub-vector-constraint" style={{ "--strength": constraint }} />
      <div className="hub-scanline" />
    </div>
  );
}

function HubScreen({ snapshot, onNavigate }) {
  const engineCount = snapshot.engines.length;
  const liveEngines = snapshot.engines.filter((engine) => engine.active).length;

  return (
    <section className="hub-screen-grid">
      <div className="hub-hero-panel">
        <div className="hub-hero-copy">
          <div className="hub-kicker">Private trading operating system</div>
          <h1>AEON Hub</h1>
          <p>
            One command surface for engine logic, exposure pressure, oracle context, and
            control-plane trust.
          </p>
        </div>
        <MotionField snapshot={snapshot} />
      </div>

      <div className="hub-command-stack">
        <MetricNode label="System Trust" value={snapshot.systemOverall} subvalue={`${snapshot.degradedServices.length} degraded service(s)`} icon={Shield} tone="cyan" />
        <MetricNode label="Exposure Heat" value={formatPct(snapshot.portfolioHeat)} subvalue={`${snapshot.openPositions} open position(s)`} icon={Gauge} tone="orange" />
        <MetricNode label="Engine Load" value={`${liveEngines}/${engineCount || 0}`} subvalue={`${snapshot.restrictedEngines.length} constrained`} icon={Cpu} tone="violet" />
        <MetricNode label="Oracle Gate" value={snapshot.oracleOpen ? "OPEN" : "BLOCKING"} subvalue={`Regime ${snapshot.regime}`} icon={Brain} tone={snapshot.oracleOpen ? "emerald" : "rose"} />
      </div>

      <div className="hub-flow-panel hub-span-2">
        <div className="hub-panel-header">
          <div>
            <span>Command Flow</span>
            <h2>Operate by pressure, not page hierarchy.</h2>
          </div>
          <Sparkles className="h-5 w-5 text-cyan-200" />
        </div>
        <div className="hub-flow-map">
          {navItems.slice(1).map((item, index) => (
            <button key={item.id} className={`hub-flow-step hub-flow-${item.intent}`} onClick={() => onNavigate(item.id)}>
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
              <small>{["strategy stack", "book pressure", "regime truth", "hard gates"][index]}</small>
            </button>
          ))}
        </div>
      </div>

      <div className="hub-feed-panel">
        <div className="hub-panel-header">
          <div>
            <span>Warnings</span>
            <h2>Operator queue</h2>
          </div>
          <Bell className="h-5 w-5 text-orange-200" />
        </div>
        <div className="hub-feed-list">
          {snapshot.warnings.length ? (
            snapshot.warnings.map((warning) => <div key={warning} className="hub-feed-item">{warning}</div>)
          ) : (
            <div className="hub-feed-item is-calm">No material pressure showing.</div>
          )}
        </div>
      </div>

      <div className="hub-mini-panel">
        <div className="hub-kicker">Adapter state</div>
        <div className="hub-adapter-grid">
          {Object.entries(snapshot.adapterState || {}).map(([key, state]) => (
            <span key={key} className={state === "live" ? "is-live" : "is-fallback"}>
              {key}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

function EnginesScreen({ snapshot }) {
  const topEngines = snapshot.engines.slice(0, 8);

  return (
    <section className="hub-module-screen">
      <div className="hub-section-brief">
        <div>
          <div className="hub-kicker">Engines</div>
          <h1>Strategy stack under governance.</h1>
          <p>Engine state is presented as command logic: active load, constraints, recommendations, tier, and recent signal pressure.</p>
        </div>
        <MetricNode label="Constrained" value={snapshot.restrictedEngines.length} subvalue="restricted, sandboxed, disabled" icon={Lock} tone="rose" />
      </div>

      <div className="hub-engine-strip">
        {topEngines.map((engine) => (
          <div key={engine.id} className={`hub-engine-tile ${engine.active ? "is-active" : ""}`}>
            <div className="hub-engine-status">{engine.active ? "LIVE" : "OFF"}</div>
            <strong>{engine.label}</strong>
            <span>{engine.recommendation} / Tier {engine.tier}</span>
            <small>{engine.score != null ? `Score ${Number(engine.score).toFixed(1)}` : "Score n/a"}</small>
          </div>
        ))}
        {!topEngines.length ? <div className="hub-empty">Engine adapter has no live rows yet.</div> : null}
      </div>

      <div className="hub-docked-module">
        <EnginesDashboard />
      </div>
    </section>
  );
}

function ExposureScreen({ snapshot }) {
  return (
    <section className="hub-module-screen">
      <div className="hub-section-brief">
        <div>
          <div className="hub-kicker">Exposure</div>
          <h1>Book heat before opportunity.</h1>
          <p>Positions, accounts, and execution surfaces are framed by aggregate heat, concentration, and live trading posture.</p>
        </div>
        <MetricNode label="Book Balance" value={formatMoney(snapshot.totalBalance)} subvalue={snapshot.hottestAccount ? `Hottest ${snapshot.hottestAccount.account_id}` : "No heat leader"} icon={Wallet} tone="emerald" />
      </div>

      <div className="hub-account-rail">
        {snapshot.accounts.slice(0, 5).map((account) => (
          <div key={account.account_id} className="hub-account-row">
            <div>
              <strong>{account.account_id}</strong>
              <span>{account.open_count || 0} open / {(account.symbols || []).join(", ") || "no symbols"}</span>
            </div>
            <div>{formatPct(account.portfolio_heat || 0)}</div>
          </div>
        ))}
        {!snapshot.accounts.length ? <div className="hub-empty">Portfolio adapter has no account rows yet.</div> : null}
      </div>

      <div className="hub-docked-module">
        <TradingHub />
      </div>
    </section>
  );
}

function OracleScreen({ snapshot }) {
  return (
    <section className="hub-module-screen">
      <div className="hub-section-brief">
        <div>
          <div className="hub-kicker">Oracle</div>
          <h1>Regime, signal, and model context.</h1>
          <p>Oracle is the interpretation layer: regime state, entropy, quant signal, and decision context before execution.</p>
        </div>
        <MetricNode label="Regime" value={snapshot.regime} subvalue={snapshot.entropy == null ? "Entropy n/a" : `H ${snapshot.entropy}`} icon={Radar} tone="violet" />
      </div>

      <div className="hub-oracle-grid">
        <div className="hub-docked-module">
          <MarketRegime />
        </div>
        <div className="hub-docked-module">
          <QuantAnalyzer />
        </div>
      </div>
    </section>
  );
}

function ControlScreen({ snapshot }) {
  return (
    <section className="hub-module-screen">
      <div className="hub-section-brief">
        <div>
          <div className="hub-kicker">Control</div>
          <h1>Trust gates and operator controls.</h1>
          <p>Control owns system health, settings, command references, history, and analytics as supporting operator surfaces.</p>
        </div>
        <MetricNode label="FW_V2" value={snapshot.fwStatus} subvalue={`Tier ${snapshot.fwTier} / ${snapshot.malformedRejects} rejects`} icon={Shield} tone="cyan" />
      </div>

      <div className="hub-control-grid">
        <div className="hub-docked-module"><SystemHealth /></div>
        <div className="hub-docked-module"><SettingsPanel /></div>
        <div className="hub-docked-module"><TradeAnalytics /></div>
        <div className="hub-docked-module"><TradeHistory /></div>
        <div className="hub-docked-module hub-control-wide"><CommandsReference /></div>
      </div>
    </section>
  );
}

function activeScreen(page, snapshot, setPage) {
  if (page === "engines") return <EnginesScreen snapshot={snapshot} />;
  if (page === "exposure") return <ExposureScreen snapshot={snapshot} />;
  if (page === "oracle") return <OracleScreen snapshot={snapshot} />;
  if (page === "control") return <ControlScreen snapshot={snapshot} />;
  return <HubScreen snapshot={snapshot} onNavigate={setPage} />;
}

export default function AeonHubShell() {
  const [page, setPage] = useState("hub");
  const [snapshot, setSnapshot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [wsEvents, setWsEvents] = useState(0);
  const wsRef = useRef(null);

  const activeNav = useMemo(() => navItems.find((item) => item.id === page) || navItems[0], [page]);

  const loadSnapshot = async (quiet = false) => {
    if (!quiet) setRefreshing(true);
    try {
      const next = await fetchHubSnapshot();
      setSnapshot(next);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadSnapshot(true);
    const interval = setInterval(() => loadSnapshot(true), 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!WS_URL) return undefined;
    let retry = null;
    let delay = 1000;

    const connect = () => {
      wsRef.current = new WebSocket(WS_URL);
      wsRef.current.onopen = () => {
        delay = 1000;
        setWsConnected(true);
      };
      wsRef.current.onmessage = () => setWsEvents((value) => value + 1);
      wsRef.current.onclose = () => {
        setWsConnected(false);
        delay = Math.min(delay * 2, 30000);
        retry = setTimeout(connect, delay);
      };
      wsRef.current.onerror = () => {};
    };

    connect();
    return () => {
      if (retry) clearTimeout(retry);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const handleResume = async () => {
    await setTradingActive(true);
    await loadSnapshot();
  };

  if (loading || !snapshot) {
    return (
      <div className="min-h-screen bg-[#03050a] text-white flex items-center justify-center">
        <AeonLoader message="Booting AEON Hub..." fullScreen={false} size="lg" />
      </div>
    );
  }

  return (
    <div className="aeon-hub-shell">
      <div className="hub-ambient-grid" />
      <div className="hub-ambient-glow hub-ambient-glow-a" />
      <div className="hub-ambient-glow hub-ambient-glow-b" />

      <header className="hub-topbar">
        <button className="hub-brand" onClick={() => setPage("hub")} aria-label="AEON Hub home">
          <span className="hub-brand-mark"><Bot className="h-5 w-5" /></span>
          <span>
            <strong>AEON Hub</strong>
            <small>private command OS</small>
          </span>
        </button>

        <nav className="hub-desktop-nav" aria-label="AEON Hub navigation">
          {navItems.map((item) => (
            <button key={item.id} onClick={() => setPage(item.id)} className={page === item.id ? "is-active" : ""}>
              <item.icon className="h-4 w-4" />
              <span>{item.label}</span>
            </button>
          ))}
        </nav>

        <div className="hub-top-actions">
          <StatusPill active={wsConnected} label={wsConnected ? "Live" : "Sync"} value={`${wsEvents}`} />
          <button onClick={() => loadSnapshot()} className="hub-icon-action" aria-label="Refresh Hub data">
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
          <button onClick={() => setShowVoice(true)} className="hub-icon-action" aria-label="Open voice command">
            <Phone className="h-4 w-4" />
          </button>
          <a href="https://t.me/ObsidianCabalbot" target="_blank" rel="noopener noreferrer" className="hub-icon-action" aria-label="Open Telegram">
            <Send className="h-4 w-4" />
          </a>
          <button onClick={() => setMenuOpen((value) => !value)} className="hub-menu-toggle" aria-label="Open navigation">
            {menuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
        </div>
      </header>

      <div className="hub-status-rail">
        <StatusPill active={snapshot.mode === "ACTIVE"} label="Mode" value={snapshot.mode} />
        <StatusPill active={snapshot.oracleOpen} label="Oracle" value={snapshot.oracleOpen ? "Open" : "Blocking"} />
        <StatusPill active={!snapshot.degradedServices.length} label="System" value={snapshot.systemOverall} />
        <StatusPill active={snapshot.portfolioHeat < 0.75} label="Heat" value={formatPct(snapshot.portfolioHeat)} />
        {snapshot.mode !== "ACTIVE" ? (
          <button className="hub-resume-button" onClick={handleResume}>
            <Power className="h-4 w-4" />
            Resume
          </button>
        ) : null}
      </div>

      {menuOpen ? (
        <div className="hub-mobile-drawer">
          {navItems.map((item) => (
            <button key={item.id} onClick={() => { setPage(item.id); setMenuOpen(false); }} className={page === item.id ? "is-active" : ""}>
              <item.icon className="h-5 w-5" />
              <span>{item.label}</span>
            </button>
          ))}
        </div>
      ) : null}

      <main className="hub-main">
        <div className="hub-page-marker">
          <activeNav.icon className="h-4 w-4" />
          <span>{activeNav.label}</span>
          <Radio className="h-4 w-4" />
          <span>{wsConnected ? "stream locked" : "local adapter"}</span>
        </div>
        {activeScreen(page, snapshot, setPage)}
      </main>

      <nav className="hub-bottom-nav" aria-label="AEON Hub mobile navigation">
        {navItems.map((item) => (
          <button key={item.id} onClick={() => setPage(item.id)} className={page === item.id ? "is-active" : ""}>
            <item.icon className="h-5 w-5" />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      {showVoice ? <VoiceConversation onClose={() => setShowVoice(false)} /> : null}
      <CrisisModeOverlay wsConnected={wsConnected} />
      <SoundAlertSystem wsRef={wsRef} />
    </div>
  );
}
