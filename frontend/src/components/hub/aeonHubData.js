export const hubTabs = ["hub", "engines", "exposure", "oracle", "control"];

const pct = (value, fallback = 0) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

const engineFallbacks = [
  { name: "Autonomous V2", status: "healthy", tier: "A", winRate: 61, edge: 72, heat: 42 },
  { name: "Free Will V2", status: "restricted", tier: "C", winRate: 32, edge: 28, heat: 76 },
  { name: "VWAP Scalper", status: "healthy", tier: "B", winRate: 55, edge: 63, heat: 49 },
  { name: "YOLO Engine", status: "low-data", tier: "D", winRate: 0, edge: 18, heat: 31 },
  { name: "Elite Strategy V3", status: "low-data", tier: "C", winRate: 0, edge: 42, heat: 28 },
  { name: "Institutional Scalper", status: "cooling", tier: "B", winRate: 52, edge: 58, heat: 68 },
  { name: "TCN Neural", status: "healthy", tier: "B", winRate: 57, edge: 61, heat: 44 },
  { name: "Quant Analyzer", status: "healthy", tier: "A", winRate: 64, edge: 78, heat: 35 },
  { name: "Oracle Gate", status: "healthy", tier: "A", winRate: 69, edge: 82, heat: 24 },
];

export function buildAeonHubState({
  stats,
  tradingStats,
  marketData,
  messages,
  operatorSummary,
  portfolioSummary,
  governanceSummary,
  systemHealth,
  fwSummary,
  openPositions,
  btcPrice,
  wsConnected,
}) {
  const services = Object.values(systemHealth?.services || {});
  const healthyServices = services.filter((service) => service.status === "healthy").length;
  const serviceHealth = services.length ? Math.round((healthyServices / services.length) * 100) : 86;
  const portfolioHeat = pct(operatorSummary?.portfolioHeat ?? portfolioSummary?.aggregate_portfolio_heat, 0.38);
  const restrictedEngines = pct(operatorSummary?.restrictedEngines, 1);
  const activeEngines = services.filter((service) =>
    ["engine", "scalper", "trading", "oracle", "quantum", "vwap", "yolo", "tcn", "elite"].some((key) =>
      String(service.name || "").includes(key)
    ) && service.status === "healthy"
  ).length || 7;
  const totalEngines = Math.max(9, activeEngines + restrictedEngines);
  const healthScore = Math.max(0, Math.min(100, Math.round(serviceHealth - portfolioHeat * 18 - restrictedEngines * 4)));

  const governanceStates = governanceSummary?.states || [];
  const engines = engineFallbacks.map((engine) => {
    const match = governanceStates.find((state) =>
      String(state.engine || state.name || "").toLowerCase().includes(engine.name.split(" ")[0].toLowerCase())
    );
    const recommendation = String(match?.current_recommendation || "").toLowerCase();
    const mappedStatus = recommendation.includes("disable")
      ? "stale"
      : recommendation.includes("restrict")
        ? "restricted"
        : recommendation.includes("sandbox")
          ? "cooling"
          : engine.status;

    return {
      ...engine,
      status: mappedStatus,
      edge: Math.round(pct(match?.edge_score, engine.edge)),
      heat: Math.round(pct(match?.portfolio_heat, engine.heat)),
    };
  });

  const accounts = (portfolioSummary?.accounts_list || [
    { account_id: "PRO", portfolio_heat: 0.42, balance: 49860 },
    { account_id: "STARTER", portfolio_heat: 0.31, balance: 1468 },
    { account_id: "REAL_LIFE", portfolio_heat: 0.27, balance: 686 },
    { account_id: "THE_PROOF", portfolio_heat: 0.19, balance: 39 },
    { account_id: "BENCHMARK", portfolio_heat: 0.35, balance: 50120 },
  ]).slice(0, 5);

  const openCount = pct(openPositions ?? operatorSummary?.totalOpenPositions ?? portfolioSummary?.total_open_positions, 48);
  const longPct = 38;
  const shortPct = 62;

  return {
    system: {
      healthScore,
      overall: operatorSummary?.systemOverall || systemHealth?.overall || "operational",
      regime: stats?.regime || stats?.market_regime || "RANGING",
      activeEngines,
      totalEngines,
      todayPnl: tradingStats?.today_pnl ?? portfolioSummary?.today_pnl ?? -156.03,
      riskState: portfolioHeat > 0.65 ? "elevated" : restrictedEngines ? "guarded" : "stable",
      btcPrice,
      wsConnected,
    },
    engines,
    exposure: {
      openCount,
      longPct,
      shortPct,
      portfolioHeat: Math.round(portfolioHeat * 100),
      symbols: [
        { symbol: "BNB", heat: 84 },
        { symbol: "ADA", heat: 73 },
        { symbol: "BTC", heat: 67 },
        { symbol: "ETH", heat: 61 },
        { symbol: "LINK", heat: 55 },
      ],
      accounts,
    },
    oracle: {
      H: pct(stats?.H ?? stats?.health, 0.22),
      C: pct(stats?.C ?? stats?.coherence, 0.889),
      S: pct(stats?.S ?? stats?.entropy, 0.946),
      confidence: 74,
      volatility: "compressed",
      notes: [
        "Range regime active. Prefer tight confirmation and reduced impulse chasing.",
        "Free Will edge remains under watch. Let governance constrain size.",
        "OKX live data confirmed. Legacy MEXC labels should remain adapter-only.",
      ],
      blindspots: [
        { label: "Regime blindspot", engine: "Free Will V2", severity: 74 },
        { label: "Compound exposure", engine: "Portfolio", severity: 61 },
        { label: "Low sample strategy", engine: "YOLO / Elite", severity: 47 },
      ],
    },
    feed: (messages || []).slice(0, 5).map((message, index) => ({
      id: message.id || `${message.timestamp || index}`,
      title: message.context || message.type || "dispatch",
      body: message.message || message.text || "Signal packet received",
      time: message.timestamp || message.created_at || new Date().toISOString(),
      tone: index % 3 === 0 ? "cyan" : index % 3 === 1 ? "amber" : "green",
    })),
  };
}
