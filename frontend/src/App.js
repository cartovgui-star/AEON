import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import "@/App.css";
import axios from "axios";
import AeonLoader from "./components/AeonLoader";
import VoiceConversation from "./components/VoiceConversation";
import AeonHub from "./components/hub/AeonHub";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL
  ? `${BACKEND_URL.replace("https://", "wss://").replace("http://", "ws://")}/ws`
  : "";

const requestNotificationPermission = async () => {
  if ("Notification" in window && Notification.permission === "default") {
    await Notification.requestPermission();
  }
};

const showNotification = (title, body) => {
  if ("Notification" in window && Notification.permission === "granted") {
    new Notification(title, {
      body,
      icon: "/favicon.ico",
      tag: "aeon-alert",
      requireInteraction: false,
    });
  }
};

const playNotificationSound = () => {
  try {
    const audio = new Audio("data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleS0AGI/L6cxxOwMzhNCnYSQDP4LU/Yl2KAIUdrz/m38tBhZzt/+fgy0GF3K1/6OFLQYZZLL/poYtBRlks/+nhiwFF2S0/6mIKwUWZLX/qogrBRZktf+qiCsFGGW2/6mIKwQYZrf/qIgrBBhmuf+oiCsEGGa5/6eIKwQYZ7r/pogrBBhnu/+liCsEGGi8/6SIKwQYaL3/pIgrBBhovv+jiCsEGWm//6KIKwQZar//oYgrBBlqwP+hiCsEGWvB/6CIKwQZa8L/oIgrBBlrwv+fiCsEGWvD/5+IKwQZa8T/n4grBBlsxf+eiCsEGWzF/56IKwQZbcb/nYgrBBltx/+diCsEGW3H/52IKwQZbcj/nYgrBBltx/+diCsEGW3I/5yIKwQZbcn/nIgrBBltx/+diCsEGW3I/52IKwMZbsn/nIgrBBltx/+diCsE");
    audio.volume = 0.3;
    audio.play();
  } catch {
    // Browsers can block audio before user interaction.
  }
};

const normalizeWarnings = ({ system, portfolio, governance, fw }) => {
  const services = Object.values(system?.services || {});
  const degradedCount = services.filter((service) => service.status && service.status !== "healthy").length;
  const states = governance?.states || [];
  const restrictedEngines = states.filter((state) =>
    ["restricted", "sandbox", "disabled"].includes(String(state.current_recommendation || "").toLowerCase())
  );
  const hottestAccount = [...(portfolio?.accounts_list || [])].sort(
    (a, b) => Number(b.portfolio_heat || 0) - Number(a.portfolio_heat || 0)
  )[0];

  return {
    warnings: [
      degradedCount ? `${degradedCount} service(s) degraded` : null,
      hottestAccount ? `${hottestAccount.account_id} at ${(Number(hottestAccount.portfolio_heat || 0) * 100).toFixed(1)}% heat` : null,
      restrictedEngines.length ? `${restrictedEngines.length} engine(s) constrained` : null,
      fw?.malformed_rejects_30d ? `${fw.malformed_rejects_30d} malformed rejects in last 30d` : null,
    ].filter(Boolean).slice(0, 5),
    summary: {
      systemOverall: system?.overall || "unknown",
      degradedCount,
      portfolioHeat: portfolio?.aggregate_portfolio_heat || 0,
      totalOpenPositions: portfolio?.total_open_positions || 0,
      fwStatus: fw?.status || "unknown",
      fwTier: fw?.health_7d?.tier || "n/a",
      fwScore: fw?.health_7d?.score,
      malformedRejects: fw?.malformed_rejects_30d || 0,
      restrictedEngines: restrictedEngines.length,
      hottestAccount: hottestAccount?.account_id || "n/a",
    },
  };
};

function App() {
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [botStatus, setBotStatus] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [tradingStats, setTradingStats] = useState(null);
  const [systemHealth, setSystemHealth] = useState(null);
  const [portfolioSummary, setPortfolioSummary] = useState(null);
  const [governanceSummary, setGovernanceSummary] = useState(null);
  const [fwSummary, setFwSummary] = useState(null);
  const [operatorSummary, setOperatorSummary] = useState(null);
  const [operatorWarnings, setOperatorWarnings] = useState([]);
  const [btcPrice, setBtcPrice] = useState(null);
  const [openPositions, setOpenPositions] = useState(0);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [regimeBanner, setRegimeBanner] = useState(null);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [showVoice, setShowVoice] = useState(false);
  const wsRef = useRef(null);

  const fetchData = useCallback(async ({ quiet = false } = {}) => {
    if (!quiet) setRefreshing(true);
    try {
      const [
        statsRes,
        messagesRes,
        testRes,
        marketRes,
        tradingRes,
        systemRes,
        portfolioRes,
        govRes,
        fwRes,
        positionsRes,
      ] = await Promise.allSettled([
        axios.get(`${API}/bot/stats`),
        axios.get(`${API}/bot/messages?limit=30`),
        axios.get(`${API}/bot/test`),
        axios.get(`${API}/okx/live`),
        axios.get(`${API}/trading/summary`),
        axios.get(`${API}/system/health`),
        axios.get(`${API}/portfolio/summary`),
        axios.get(`${API}/engine/governance`),
        axios.get(`${API}/engine/fw_v2/report`),
        axios.get(`${API}/trading/v2/open`),
      ]);

      if (statsRes.status === "fulfilled") setStats(statsRes.value.data);
      if (messagesRes.status === "fulfilled") setMessages(messagesRes.value.data);
      if (testRes.status === "fulfilled") setBotStatus(testRes.value.data);
      if (tradingRes.status === "fulfilled") setTradingStats(tradingRes.value.data);

      if (marketRes.status === "fulfilled") {
        const market = marketRes.value.data;
        setMarketData(market);
        const btcSymbol = market?.symbols?.find((symbol) => ["BTC/USDT", "BTCUSDT"].includes(symbol.symbol));
        if (btcSymbol?.price) setBtcPrice(btcSymbol.price);
      }

      const system = systemRes.status === "fulfilled" ? systemRes.value.data : null;
      const portfolio = portfolioRes.status === "fulfilled" ? portfolioRes.value.data : null;
      const governance = govRes.status === "fulfilled" ? govRes.value.data : null;
      const fw = fwRes.status === "fulfilled" ? fwRes.value.data : null;

      if (system) setSystemHealth(system);
      if (portfolio) setPortfolioSummary(portfolio);
      if (governance) setGovernanceSummary(governance);
      if (fw) setFwSummary(fw);

      if (system || portfolio || governance || fw) {
        const normalized = normalizeWarnings({ system, portfolio, governance, fw });
        setOperatorWarnings(normalized.warnings);
        setOperatorSummary(normalized.summary);
      }

      if (positionsRes.status === "fulfilled") {
        const payload = positionsRes.value.data;
        setOpenPositions(payload?.total_open ?? (Array.isArray(payload) ? payload.length : 0));
      }
    } catch (error) {
      console.error("AEON Hub data adapter failed:", error);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData({ quiet: true }), 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    requestNotificationPermission().then(() => {
      if ("Notification" in window && Notification.permission === "granted") setNotificationsEnabled(true);
    });
  }, []);

  useEffect(() => {
    if (!WS_URL) return undefined;

    let wsRetryDelay = 1000;
    let retryTimeout = null;

    const connectWebSocket = () => {
      try {
        wsRef.current = new WebSocket(WS_URL);

        wsRef.current.onopen = () => {
          wsRetryDelay = 1000;
          setWsConnected(true);
        };

        wsRef.current.onmessage = (event) => {
          const data = JSON.parse(event.data);

          if (data.type === "alert") {
            setUnreadAlerts((value) => value + 1);
            if (notificationsEnabled) {
              playNotificationSound();
              showNotification(
                `${String(data.alert_type || "alert").replace("_", " ").toUpperCase()}: ${String(data.symbol || "AEON").replace("/USDT", "")}`,
                String(data.message || "New AEON alert").substring(0, 100)
              );
            }
          }

          if (data.type === "regime_change") {
            setRegimeBanner({ from: data.from_regime, to: data.to_regime, H: data.H });
            if (notificationsEnabled) {
              playNotificationSound();
              showNotification("Regime Change", data.message);
            }
            setTimeout(() => setRegimeBanner(null), 8000);
          }
        };

        wsRef.current.onclose = () => {
          setWsConnected(false);
          wsRetryDelay = Math.min(wsRetryDelay * 2, 30000);
          retryTimeout = setTimeout(connectWebSocket, wsRetryDelay);
        };

        wsRef.current.onerror = () => {};
      } catch {
        wsRetryDelay = Math.min(wsRetryDelay * 2, 30000);
        retryTimeout = setTimeout(connectWebSocket, wsRetryDelay);
      }
    };

    connectWebSocket();
    return () => {
      if (retryTimeout) clearTimeout(retryTimeout);
      if (wsRef.current) wsRef.current.close();
    };
  }, [notificationsEnabled]);

  const actions = useMemo(() => ({
    refresh: () => fetchData(),
    resumeTrading: async () => {
      await axios.post(`${API}/trading/toggle?active=true`);
      await fetchData();
    },
    pauseTrading: async () => {
      await axios.post(`${API}/trading/toggle?active=false`);
      await fetchData();
    },
    runScan: async () => fetchData(),
    openVoice: () => setShowVoice(true),
    clearAlerts: () => setUnreadAlerts(0),
    toggleNotifications: async () => {
      if (notificationsEnabled) {
        setNotificationsEnabled(false);
        return;
      }
      await requestNotificationPermission();
      setNotificationsEnabled("Notification" in window && Notification.permission === "granted");
    },
  }), [fetchData, notificationsEnabled]);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#05070d] flex items-center justify-center">
        <AeonLoader message="Booting AEON Hub..." fullScreen size="lg" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#05070d] text-white">
      <AeonHub
        stats={stats}
        botStatus={botStatus}
        tradingStats={tradingStats}
        marketData={marketData}
        messages={messages}
        operatorSummary={operatorSummary}
        operatorWarnings={operatorWarnings}
        portfolioSummary={portfolioSummary}
        governanceSummary={governanceSummary}
        systemHealth={systemHealth}
        fwSummary={fwSummary}
        openPositions={openPositions}
        btcPrice={btcPrice}
        wsConnected={wsConnected}
        unreadAlerts={unreadAlerts}
        regimeBanner={regimeBanner}
        notificationsEnabled={notificationsEnabled}
        refreshing={refreshing}
        actions={actions}
      />

      {showVoice ? <VoiceConversation onClose={() => setShowVoice(false)} /> : null}
    </div>
  );
}

export default App;
