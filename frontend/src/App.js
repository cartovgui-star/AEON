import { useEffect, useState, useCallback, useRef, Component } from "react";
import "@/App.css";

class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }
  componentDidCatch(error, info) {
    console.error("Component error:", error, info);
  }
  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-zinc-950 flex items-center justify-center text-white p-8">
          <div className="text-center max-w-md">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-xl font-bold text-orange-400 mb-2">Something went wrong</h2>
            <p className="text-zinc-400 text-sm mb-4">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false, error: null })}
              className="px-4 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-sm font-medium"
            >
              Try Again
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
import axios from "axios";
import { Card, CardContent } from "./components/ui/card";
import { ScrollArea } from "./components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import {
  MessageCircle, Users, Activity, Clock, Zap, Bot, ExternalLink, Send,
  TrendingUp, TrendingDown, BarChart3, Brain, Target, Trophy, Phone,
  Settings, History, PieChart, Home, Menu, X, BookOpen, Layers, Bell, BellRing,
  Wallet, HelpCircle, FlaskConical, Shield, Sun, Eye, Atom, Search
} from "lucide-react";
import VoiceConversation from "./components/VoiceConversation";
import TradeHistory from "./components/TradeHistory";
import SettingsPanel from "./components/SettingsPanel";
import TradeAnalytics from "./components/TradeAnalytics";
import SMCAnalysis from "./components/SMCAnalysis";
import Journal from "./components/Journal";
import Trading from "./components/Trading";
import CommandsReference from "./components/CommandsReference";
import QuickScanModal from "./components/QuickScanModal";
import PriceAlerts from "./components/PriceAlerts";
import Backtesting from "./components/Backtesting";
import BacktestV21 from "./components/BacktestV21";
import Intelligence from "./components/Intelligence";
import SystemHealth from "./components/SystemHealth";
import EnginesDashboard from "./components/EnginesDashboard";
import Dashboard from "./components/Dashboard";
import ScalperDashboard from "./components/ScalperDashboard";
import MobileNav from "./components/MobileNav";
import PaperTrading from "./components/PaperTrading";
import VolumeProfile from "./components/VolumeProfile";
import QuantAnalyzer from "./components/QuantAnalyzer";
import PerformanceAnalytics from "./components/PerformanceAnalytics";
import MorningBriefing from "./components/MorningBriefing";
import WeeklyReport from "./components/WeeklyReport";
import LearningEngine from "./components/LearningEngine";
import OracleDashboard from "./components/OracleDashboard";
import QuantumDashboard from "./components/QuantumDashboard";
import NewsFeed from "./components/NewsFeed";
import CommandPalette from "./components/CommandPalette";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';

// Set default axios timeout and API key for all requests
axios.defaults.timeout = 10000;
axios.defaults.headers.common['X-API-Key'] = process.env.REACT_APP_API_KEY || '';

// Inject API key header into all native fetch() calls to /api routes
const _origFetch = window.fetch;
window.fetch = (url, options = {}) => {
  const apiKey = process.env.REACT_APP_API_KEY;
  if (apiKey && typeof url === 'string' && url.includes('/api')) {
    options = { ...options, headers: { 'X-API-Key': apiKey, ...options.headers } };
  }
  return _origFetch(url, options);
};

// Browser notification permission
const requestNotificationPermission = async () => {
  if ('Notification' in window && Notification.permission === 'default') {
    await Notification.requestPermission();
  }
};

// Show browser notification
const showNotification = (title, body, icon = '🔔') => {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification(title, {
      body,
      icon: '/favicon.ico',
      tag: 'aeon-alert',
      requireInteraction: false
    });
  }
};

// Fetch with a timeout so hung requests don't block indefinitely
const fetchWithTimeout = (url, options = {}, timeoutMs = 10000) => {
  const controller = new AbortController();
  const id = setTimeout(() => controller.abort(), timeoutMs);
  return fetch(url, { ...options, signal: controller.signal })
    .finally(() => clearTimeout(id));
};

// Play notification sound
const playNotificationSound = () => {
  try {
    const audio = new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2teleS0AGI/L6cxxOwMzhNCnYSQDP4LU/Yl2KAIUdrz/m38tBhZzt/+fgy0GF3K1/6OFLQYZZLL/poYtBRlks/+nhiwFF2S0/6mIKwUWZLX/qogrBRZktf+qiCsFGGW2/6mIKwQYZrf/qIgrBBhmuf+oiCsEGGa5/6eIKwQYZ7r/pogrBBhnu/+liCsEGGi8/6SIKwQYaL3/pIgrBBhovv+jiCsEGWm//6KIKwQZar//oYgrBBlqwP+hiCsEGWvB/6CIKwQZa8L/oIgrBBlrwv+fiCsEGWvD/5+IKwQZa8T/n4grBBlsxf+eiCsEGWzF/56IKwQZbcb/nYgrBBltx/+diCsEGW3H/52IKwQZbcj/nYgrBBltx/+diCsEGW3I/5yIKwQZbcn/nIgrBBltx/+diCsEGW3I/52IKwMZbsn/nIgrBBltx/+diCsE');
    audio.volume = 0.3;
    audio.play();
  } catch (e) {
    console.log('Could not play notification sound');
  }
};

function App() {
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [botStatus, setBotStatus] = useState(null);
  const [mexcData, setMexcData] = useState(null);
  const [tradingStats, setTradingStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");
  const [showVoice, setShowVoice] = useState(false);
  const [currentPage, setCurrentPage] = useState("dashboard");
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [unreadAlerts, setUnreadAlerts] = useState(0);
  const [notificationsEnabled, setNotificationsEnabled] = useState(false);
  const [quickScanCoin, setQuickScanCoin] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const wsRef = useRef(null);

  const fetchData = async () => {
    try {
      const [statsRes, messagesRes, testRes, mexcRes, tradingRes] = await Promise.all([
        axios.get(`${API}/bot/stats`),
        axios.get(`${API}/bot/messages?limit=30`),
        axios.get(`${API}/bot/test`),
        axios.get(`${API}/mexc/live`),
        axios.get(`${API}/trading/summary`)
      ]);
      setStats(statsRes.data);
      setMessages(messagesRes.data);
      setBotStatus(testRes.data);
      setMexcData(mexcRes.data);
      setTradingStats(tradingRes.data);
    } catch (e) {
      console.error("Error fetching data:", e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const formatRelativeTime = (timestamp) => {
    if (!timestamp) return "Never";
    const now = new Date();
    const date = new Date(timestamp);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  // Command palette keyboard shortcut (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handler = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setPaletteOpen(open => !open);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  // WebSocket connection for real-time alerts
  useEffect(() => {
    let reconnectAttempts = 0;
    let reconnectTimer = null;
    let unmounted = false;

    const connectWebSocket = () => {
      if (unmounted) return;
      try {
        wsRef.current = new WebSocket(WS_URL);

        wsRef.current.onopen = () => {
          console.log('WebSocket connected');
          reconnectAttempts = 0;
          setWsConnected(true);
        };

        wsRef.current.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            if (data.type === 'alert') {
              setUnreadAlerts(prev => prev + 1);
              if (notificationsEnabled) {
                playNotificationSound();
                showNotification(
                  `${data.alert_type.replace('_', ' ').toUpperCase()}: ${data.symbol?.replace('/USDT', '')}`,
                  data.message?.substring(0, 100)
                );
              }
            }
          } catch (e) {
            console.error('WebSocket message parse error:', e);
          }
        };

        wsRef.current.onclose = () => {
          if (unmounted) return;
          setWsConnected(false);
          reconnectAttempts++;
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
          console.log(`WebSocket disconnected, reconnecting in ${delay / 1000}s (attempt ${reconnectAttempts})`);
          reconnectTimer = setTimeout(connectWebSocket, delay);
        };

        wsRef.current.onerror = (error) => {
          console.error('WebSocket error:', error);
        };
      } catch (e) {
        console.error('WebSocket connection failed:', e);
      }
    };

    connectWebSocket();

    return () => {
      unmounted = true;
      clearTimeout(reconnectTimer);
      if (wsRef.current) {
        wsRef.current.onclose = null; // Prevent reconnect on intentional close
        wsRef.current.close();
      }
    };
  }, [notificationsEnabled]);
  
  // Request notification permission on mount
  useEffect(() => {
    requestNotificationPermission().then(() => {
      if ('Notification' in window && Notification.permission === 'granted') {
        setNotificationsEnabled(true);
      }
    });
  }, []);

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home },
    { id: 'trading', label: 'Trading', icon: Wallet },
    { id: 'paper', label: 'Paper', icon: Target },
    { id: 'scalper', label: 'Scalper', icon: Zap },
    { id: 'trades', label: 'History', icon: History },
    { id: 'alerts', label: 'Alerts', icon: Bell },
    { id: 'backtest', label: 'Backtest', icon: FlaskConical },
    { id: 'backtest-v21', label: 'V2.1 Test', icon: Target },
    { id: 'intel', label: 'Intel', icon: Brain },
    { id: 'news', label: 'News', icon: Bell },
    { id: 'charts', label: 'Analytics', icon: BarChart3 },
    { id: 'smc', label: 'SMC', icon: Layers },
    { id: 'journal', label: 'Journal', icon: BookOpen },
    { id: 'commands', label: 'Commands', icon: HelpCircle },
    { id: 'engines', label: 'Engines', icon: Zap },
    { id: 'vp', label: 'Hyper Accuracy', icon: BarChart3 },
    { id: 'quant', label: 'Quant Analyzer', icon: BarChart3 },
    { id: 'perf', label: 'Performance', icon: BarChart3 },
    { id: 'health', label: 'Health', icon: Shield },
    { id: 'settings', label: 'Settings', icon: Settings },
    { id: 'briefing', label: 'Briefing', icon: Sun },
    { id: 'weekly', label: 'Weekly', icon: BarChart3 },
    { id: 'learning', label: 'Learning', icon: Brain },
    { id: 'oracle', label: 'ORACLE', icon: Eye },
    { id: 'quantum', label: 'Quantum', icon: Atom },
    { id: 'analysis', label: 'Analysis', icon: Bell },
  ];

  return (
    <ErrorBoundary>
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 text-white">
      {paletteOpen && (
        <CommandPalette
          navItems={navItems}
          onNavigate={setCurrentPage}
          onClose={() => setPaletteOpen(false)}
        />
      )}
      {/* Navigation */}
      <nav className="sticky top-0 z-40 bg-zinc-950/80 backdrop-blur-xl border-b border-zinc-800/50">
        <div className="max-w-7xl mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            {/* Logo & Nav */}
            <div className="flex items-center gap-8">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <div>
                  <h1 className="text-lg font-bold text-white">Aeon</h1>
                  <p className="text-xs text-zinc-500">Trading Intelligence</p>
                </div>
              </div>
              
              {/* Desktop Nav - Scrollable */}
              <div className="hidden lg:flex items-center gap-1">
                {navItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setCurrentPage(item.id)}
                    data-testid={`nav-${item.id}`}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg transition-all whitespace-nowrap ${
                      currentPage === item.id
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                    }`}
                  >
                    <item.icon className="w-4 h-4" />
                    <span className="text-xs font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Command palette trigger */}
              <button
                onClick={() => setPaletteOpen(true)}
                className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 border border-zinc-700/50 rounded-lg text-zinc-500 hover:text-zinc-300 hover:border-zinc-600 transition-all text-xs"
                title="Search pages (Ctrl+K)"
              >
                <Search className="w-3.5 h-3.5" />
                <span>Search</span>
                <kbd className="bg-zinc-900 px-1 py-0.5 rounded text-zinc-600 text-xs">⌘K</kbd>
              </button>

              {/* WebSocket Status */}
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg">
                <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-green-500' : 'bg-yellow-500 animate-pulse'}`} />
                <span className="text-xs text-zinc-400">
                  {wsConnected ? 'Live' : 'Connecting'}
                </span>
              </div>
              
              {/* Notification Toggle */}
              <button
                onClick={() => {
                  if (notificationsEnabled) {
                    setNotificationsEnabled(false);
                  } else {
                    requestNotificationPermission().then(() => {
                      setNotificationsEnabled(Notification.permission === 'granted');
                    });
                  }
                }}
                className={`p-2 rounded-lg transition-all ${
                  notificationsEnabled ? 'bg-orange-500/20 text-orange-400' : 'bg-zinc-800/50 text-zinc-400'
                }`}
                title={notificationsEnabled ? 'Notifications On' : 'Enable Notifications'}
              >
                {notificationsEnabled ? <BellRing className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
              </button>
              
              {/* Status Indicator */}
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg">
                <div className={`w-2 h-2 rounded-full ${botStatus?.status === 'success' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                <span className="text-xs text-zinc-400">
                  {tradingStats?.active ? 'Trading Active' : 'Monitoring'}
                </span>
              </div>
              
              <button
                onClick={() => setShowVoice(true)}
                className="flex items-center gap-2 px-3 sm:px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 rounded-lg transition-all text-white shadow-lg shadow-orange-500/20"
              >
                <Phone className="w-4 h-4" />
                <span className="hidden sm:inline text-sm font-medium">Talk to Aeon</span>
              </button>
              
              <a
                href="https://t.me/ObsidianCabalbot"
                target="_blank"
                rel="noopener noreferrer"
                className="hidden sm:flex items-center gap-2 px-4 py-2 bg-zinc-800/50 hover:bg-zinc-800 rounded-lg transition-all text-zinc-300 hover:text-white"
              >
                <Send className="w-4 h-4" />
                <span className="text-sm">Telegram</span>
              </a>

              {/* Mobile Menu Button */}
              <button
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                className="lg:hidden p-2 text-zinc-400 hover:text-white"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>

          {/* Mobile Nav */}
          {mobileMenuOpen && (
            <div className="lg:hidden pt-4 pb-2 border-t border-zinc-800 mt-3">
              <div className="grid grid-cols-3 gap-1">
                {navItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => { setCurrentPage(item.id); setMobileMenuOpen(false); }}
                    data-testid={`mobile-nav-${item.id}`}
                    className={`flex flex-col items-center gap-1.5 px-2 py-3 rounded-lg transition-all ${
                      currentPage === item.id
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    <item.icon className="w-5 h-5" />
                    <span className="text-xs font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-3 sm:px-4 py-4 sm:py-8 pb-24 lg:pb-8">
        {/* Page: Dashboard */}
        {currentPage === 'dashboard' && (
          <Dashboard 
            stats={stats}
            tradingStats={tradingStats}
            mexcData={mexcData}
            messages={messages}
            formatRelativeTime={formatRelativeTime}
            onQuickScan={setQuickScanCoin}
            onNavigate={setCurrentPage}
          />
        )}

        {/* Page: Trade History */}
        {currentPage === 'trades' && <TradeHistory />}

        {/* Page: Trading */}
        {currentPage === 'trading' && <Trading />}

        {/* Page: Paper Trading */}
        {currentPage === 'paper' && <PaperTrading />}

        {/* Page: Scalper */}
        {currentPage === 'scalper' && <ScalperDashboard />}

        {/* Page: Price Alerts */}
        {currentPage === 'alerts' && <PriceAlerts />}

        {/* Page: Backtesting */}
        {currentPage === 'backtest' && <Backtesting />}

        {/* Page: V2.1 Backtest */}
        {currentPage === 'backtest-v21' && <BacktestV21 />}

        {/* Page: Intelligence */}
        {currentPage === 'intel' && <Intelligence />}

        {/* Page: News Feed */}
        {currentPage === 'news' && <NewsFeed />}

        {/* Page: Settings */}
        {currentPage === 'settings' && <SettingsPanel />}

        {/* Page: SMC Analysis */}
        {currentPage === 'smc' && <SMCAnalysis />}

        {/* Page: Journal */}
        {currentPage === 'journal' && <Journal />}

        {/* Page: Commands Reference */}
        {currentPage === 'commands' && <CommandsReference />}

        {/* Page: Engines Dashboard */}
        {currentPage === 'engines' && <EnginesDashboard />}

        {/* Page: System Health */}
        {currentPage === 'health' && <SystemHealth />}
        {currentPage === 'vp' && <VolumeProfile />}
        {currentPage === 'quant' && <QuantAnalyzer />}
        {currentPage === 'perf' && <PerformanceAnalytics />}

        {/* Page: Trade Analytics (Charts) */}
        {currentPage === 'charts' && <TradeAnalytics />}

        {/* Page: Morning Briefing */}
        {currentPage === 'briefing' && <MorningBriefing />}

        {/* Page: Weekly Report */}
        {currentPage === 'weekly' && <WeeklyReport />}

        {/* Page: Learning Engine */}
        {currentPage === 'learning' && <LearningEngine />}

        {/* Page: ORACLE */}
        {currentPage === 'oracle' && <OracleDashboard />}

        {/* Page: Quantum */}
        {currentPage === 'quantum' && <QuantumDashboard />}

        {/* Page: Analysis — removed (redundant with Alerts + TradeAnalytics) */}
      </main>

      {/* Mobile Bottom Navigation */}
      <MobileNav currentPage={currentPage} onNavigate={setCurrentPage} />

      {/* Voice Modal */}
      {showVoice && <VoiceConversation onClose={() => setShowVoice(false)} />}

      {/* Quick Scan Modal */}
      {quickScanCoin && <QuickScanModal coin={quickScanCoin} onClose={() => setQuickScanCoin(null)} />}
    </div>
    </ErrorBoundary>
  );
}

export default App;
