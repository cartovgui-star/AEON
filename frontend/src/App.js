import { useEffect, useState, useCallback, useRef } from "react";
import "@/App.css";
import axios from "axios";
import { Card, CardContent } from "./components/ui/card";
import { ScrollArea } from "./components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { 
  MessageCircle, Users, Activity, Clock, Zap, Bot, ExternalLink, Send, 
  TrendingUp, TrendingDown, BarChart3, Brain, Target, Trophy, Phone,
  Settings, History, PieChart, Home, Menu, X, BookOpen, Layers, Bell, BellRing
} from "lucide-react";
import VoiceConversation from "./components/VoiceConversation";
import TradeHistory from "./components/TradeHistory";
import SettingsPanel from "./components/SettingsPanel";
import Analytics from "./components/Analytics";
import SMCAnalysis from "./components/SMCAnalysis";
import Journal from "./components/Journal";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const WS_URL = BACKEND_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws';

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

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: Home },
    { id: 'trades', label: 'Trades', icon: History },
    { id: 'analytics', label: 'Analytics', icon: PieChart },
    { id: 'settings', label: 'Settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-950 text-white">
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
              
              {/* Desktop Nav */}
              <div className="hidden md:flex items-center gap-1">
                {navItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => setCurrentPage(item.id)}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg transition-all ${
                      currentPage === item.id
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'text-zinc-400 hover:text-white hover:bg-zinc-800/50'
                    }`}
                  >
                    <item.icon className="w-4 h-4" />
                    <span className="text-sm font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Right Actions */}
            <div className="flex items-center gap-3">
              {/* Status Indicator */}
              <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-zinc-800/50 rounded-lg">
                <div className={`w-2 h-2 rounded-full ${botStatus?.status === 'success' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                <span className="text-xs text-zinc-400">
                  {tradingStats?.active ? 'Trading Active' : 'Monitoring'}
                </span>
              </div>
              
              <button
                onClick={() => setShowVoice(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 hover:from-orange-600 hover:to-amber-700 rounded-lg transition-all text-white shadow-lg shadow-orange-500/20"
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
                className="md:hidden p-2 text-zinc-400 hover:text-white"
              >
                {mobileMenuOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
              </button>
            </div>
          </div>

          {/* Mobile Nav */}
          {mobileMenuOpen && (
            <div className="md:hidden pt-4 pb-2 border-t border-zinc-800 mt-3">
              <div className="flex flex-col gap-1">
                {navItems.map(item => (
                  <button
                    key={item.id}
                    onClick={() => { setCurrentPage(item.id); setMobileMenuOpen(false); }}
                    className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all ${
                      currentPage === item.id
                        ? 'bg-orange-500/20 text-orange-400'
                        : 'text-zinc-400 hover:text-white'
                    }`}
                  >
                    <item.icon className="w-5 h-5" />
                    <span className="font-medium">{item.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </nav>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-8">
        {/* Page: Dashboard */}
        {currentPage === 'dashboard' && (
          <div className="space-y-8">
            {/* Quick Stats */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs">Status</p>
                      <p className={`text-lg font-bold ${tradingStats?.active ? 'text-green-400' : 'text-zinc-400'}`}>
                        {tradingStats?.active ? 'ACTIVE' : 'PAUSED'}
                      </p>
                    </div>
                    <Bot className="w-8 h-8 text-orange-400" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs">Win Rate</p>
                      <p className="text-lg font-bold text-green-400">{tradingStats?.win_rate || 0}%</p>
                    </div>
                    <Target className="w-8 h-8 text-green-400" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs">Total PnL</p>
                      <p className={`text-lg font-bold ${(tradingStats?.total_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {(tradingStats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(tradingStats?.total_pnl_pct || 0).toFixed(2)}%
                      </p>
                    </div>
                    <TrendingUp className="w-8 h-8 text-orange-400" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs">Open Trades</p>
                      <p className="text-lg font-bold text-orange-400">{tradingStats?.open_trades || 0}</p>
                    </div>
                    <Activity className="w-8 h-8 text-orange-400" />
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs">Users</p>
                      <p className="text-lg font-bold text-white">{stats?.unique_users || 0}</p>
                    </div>
                    <Users className="w-8 h-8 text-blue-400" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Market Data */}
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-orange-400" />
                Live Market Data
              </h2>
              <div className="grid md:grid-cols-3 gap-4">
                {mexcData?.symbols?.map((sym, i) => (
                  <Card key={i} className="bg-zinc-800/30 border-zinc-700/50">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="font-semibold text-white">{sym.symbol?.replace('/USDT', '')}</span>
                        <span className={`text-sm font-medium ${
                          (sym.change_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                        }`}>
                          {(sym.change_24h || 0) >= 0 ? '↗' : '↘'} {Math.abs(sym.change_24h || 0).toFixed(2)}%
                        </span>
                      </div>
                      <p className="text-2xl font-bold text-white">
                        ${(sym.price || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                      </p>
                      <div className="mt-3 flex items-center gap-2">
                        <div className="flex-1 h-2 bg-zinc-700 rounded-full overflow-hidden">
                          <div 
                            className={`h-full ${sym.imbalance >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${50 + (sym.imbalance || 0) / 2}%` }}
                          />
                        </div>
                        <span className="text-xs text-zinc-500">{(sym.imbalance || 0).toFixed(0)}%</span>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Trading Intelligence */}
            <div className="grid md:grid-cols-2 gap-6">
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <Brain className="w-5 h-5 text-orange-400" />
                    AI Engine Status
                  </h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                      <span className="text-zinc-400">Market Regime</span>
                      <span className={`font-medium px-2 py-1 rounded ${
                        tradingStats?.market_regime === 'TRENDING' ? 'bg-green-500/20 text-green-400' :
                        tradingStats?.market_regime === 'VOLATILE' ? 'bg-red-500/20 text-red-400' :
                        'bg-zinc-700 text-zinc-300'
                      }`}>{tradingStats?.market_regime || 'Unknown'}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                      <span className="text-zinc-400">BTC Bias</span>
                      <span className={`font-medium ${
                        tradingStats?.btc_bias === 'BULLISH' ? 'text-green-400' :
                        tradingStats?.btc_bias === 'BEARISH' ? 'text-red-400' : 'text-zinc-400'
                      }`}>{tradingStats?.btc_bias || 'Neutral'}</span>
                    </div>
                    <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                      <span className="text-zinc-400">Fear & Greed</span>
                      <span className={`font-medium ${
                        (tradingStats?.fear_greed || 50) > 60 ? 'text-green-400' :
                        (tradingStats?.fear_greed || 50) < 40 ? 'text-red-400' : 'text-yellow-400'
                      }`}>{tradingStats?.fear_greed || 50}</span>
                    </div>
                    <div className="flex items-center justify-between py-2">
                      <span className="text-zinc-400">Min Confidence</span>
                      <span className="font-medium text-orange-400">{tradingStats?.min_confidence || 85}%</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Recent Messages */}
              <Card className="bg-zinc-800/30 border-zinc-700/50">
                <CardContent className="p-6">
                  <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                    <MessageCircle className="w-5 h-5 text-orange-400" />
                    Recent Activity
                  </h3>
                  <ScrollArea className="h-64">
                    <div className="space-y-3">
                      {messages.slice(0, 10).map((msg, i) => (
                        <div key={i} className="flex gap-3 p-2 rounded-lg hover:bg-zinc-800/50 transition-colors">
                          <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0">
                            <span className="text-xs">{msg.username?.[0]?.toUpperCase() || '?'}</span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2">
                              <span className="text-sm font-medium text-white">{msg.username || 'User'}</span>
                              <span className="text-xs text-zinc-600">{formatRelativeTime(msg.timestamp)}</span>
                            </div>
                            <p className="text-sm text-zinc-400 truncate">{msg.text}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </ScrollArea>
                </CardContent>
              </Card>
            </div>
          </div>
        )}

        {/* Page: Trade History */}
        {currentPage === 'trades' && <TradeHistory />}

        {/* Page: Analytics */}
        {currentPage === 'analytics' && <Analytics />}

        {/* Page: Settings */}
        {currentPage === 'settings' && <SettingsPanel />}
      </main>

      {/* Voice Modal */}
      {showVoice && <VoiceConversation onClose={() => setShowVoice(false)} />}
    </div>
  );
}

export default App;
