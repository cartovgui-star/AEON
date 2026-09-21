const API_URL = process.env.REACT_APP_BACKEND_URL || "";

const endpointMap = {
  stats: "/api/bot/stats",
  trading: "/api/trading/summary",
  openPositions: "/api/positions",
  portfolio: "/api/portfolio/summary",
  health: "/api/system/health",
  governance: "/api/engine/governance",
  engines: "/api/engines/status",
  regime: "/api/regime/global",
  fw: "/api/engine/fw_v2/report",
};

const fallbackSnapshot = {
  stats: { oracle_gate: true },
  trading: { active: false },
  openPositions: { total_open: 0 },
  portfolio: {
    aggregate_portfolio_heat: 0,
    total_balance: 0,
    total_open_positions: 0,
    accounts_list: [],
  },
  health: { overall: "unknown", services: {} },
  governance: { states: [] },
  engines: { engines: {} },
  regime: { regime: "unknown", H: null },
  fw: { status: "unknown", health_7d: {}, malformed_rejects_30d: 0 },
};

async function getJson(path) {
  const response = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

export async function fetchHubSnapshot() {
  const entries = await Promise.allSettled(
    Object.entries(endpointMap).map(async ([key, path]) => [key, await getJson(path)])
  );

  const snapshot = { ...fallbackSnapshot };
  const adapterState = {};

  entries.forEach((entry) => {
    if (entry.status === "fulfilled") {
      const [key, value] = entry.value;
      snapshot[key] = value;
      adapterState[key] = "live";
    } else {
      const key = Object.keys(endpointMap)[entries.indexOf(entry)];
      adapterState[key] = "fallback";
    }
  });

  return normalizeHubSnapshot(snapshot, adapterState);
}

function normalizeEngineList(engines, governance) {
  const rawEngines = engines?.engines || engines || {};
  const govByName = new Map(
    (governance?.states || []).map((state) => [
      String(state.engine || state.name || state.engine_name || "").toLowerCase(),
      state,
    ])
  );

  return Object.entries(rawEngines).map(([key, value]) => {
    const gov =
      govByName.get(String(key).toLowerCase()) ||
      govByName.get(String(value?.name || "").toLowerCase()) ||
      {};
    const config = value?.config || {};
    const stats = value?.stats || {};
    const recommendation = String(
      gov.current_recommendation || gov.recommendation || "monitor"
    ).toLowerCase();

    return {
      id: key,
      label: value?.label || value?.name || key.replaceAll("_", " "),
      active: config.active !== false && value?.active !== false,
      openCount: Number(value?.open_count || value?.openCount || 0),
      pnl: Number(stats.total_pnl || value?.pnl || 0),
      winRate: Number(stats.win_rate || value?.win_rate || 0),
      recommendation,
      tier: gov.current_tier || gov.tier || "n/a",
      score: gov.current_score ?? gov.score ?? null,
      lastSignal: stats.last_signal_time || value?.last_signal_time || null,
    };
  });
}

export function normalizeHubSnapshot(raw, adapterState = {}) {
  const health = raw.health || fallbackSnapshot.health;
  const portfolio = raw.portfolio || fallbackSnapshot.portfolio;
  const governance = raw.governance || fallbackSnapshot.governance;
  const fw = raw.fw || fallbackSnapshot.fw;
  const services = Object.values(health.services || {});
  const engines = normalizeEngineList(raw.engines, governance);
  const restrictedEngines = engines.filter((engine) =>
    ["restrict", "restricted", "sandbox", "sandbox_only", "disabled", "disable_candidate"].includes(
      engine.recommendation
    )
  );
  const accounts = Array.isArray(portfolio.accounts_list) ? portfolio.accounts_list : [];
  const hottestAccount = [...accounts].sort(
    (a, b) => Number(b.portfolio_heat || 0) - Number(a.portfolio_heat || 0)
  )[0];
  const openPositions =
    raw.openPositions?.total_open ??
    raw.openPositions?.total ??
    (Array.isArray(raw.openPositions) ? raw.openPositions.length : portfolio.total_open_positions || 0);

  return {
    adapterState,
    mode: raw.trading?.active ? "ACTIVE" : "PAUSED",
    oracleOpen: raw.stats?.oracle_gate !== false,
    systemOverall: health.overall || "unknown",
    degradedServices: services.filter((service) => service.status && service.status !== "healthy"),
    portfolioHeat: Number(portfolio.aggregate_portfolio_heat || 0),
    totalBalance: Number(portfolio.total_balance || 0),
    openPositions: Number(openPositions || 0),
    accounts,
    hottestAccount,
    engines,
    restrictedEngines,
    regime: raw.regime?.regime || raw.regime?.state || "unknown",
    entropy: raw.regime?.H ?? raw.regime?.entropy ?? null,
    fwStatus: fw.status || "unknown",
    fwTier: fw.health_7d?.tier || "n/a",
    fwScore: fw.health_7d?.score,
    malformedRejects: Number(fw.malformed_rejects_30d || 0),
    warnings: [
      services.filter((service) => service.status && service.status !== "healthy").length
        ? `${services.filter((service) => service.status && service.status !== "healthy").length} degraded service(s)`
        : null,
      hottestAccount
        ? `${hottestAccount.account_id || "Account"} at ${(Number(hottestAccount.portfolio_heat || 0) * 100).toFixed(1)}% heat`
        : null,
      restrictedEngines.length ? `${restrictedEngines.length} constrained engine(s)` : null,
      fw.malformed_rejects_30d ? `${fw.malformed_rejects_30d} malformed rejects over 30d` : null,
    ].filter(Boolean),
  };
}

export async function setTradingActive(active) {
  const response = await fetch(`${API_URL}/api/trading/toggle?active=${active ? "true" : "false"}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) throw new Error(`trading toggle ${response.status}`);
  return response.json();
}
