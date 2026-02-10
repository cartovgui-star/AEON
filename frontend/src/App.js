import { useEffect, useState } from "react";
import "@/App.css";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Badge } from "./components/ui/badge";
import { ScrollArea } from "./components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./components/ui/tabs";
import { MessageCircle, Users, Activity, Clock, Zap, Bot, ExternalLink, Send, TrendingUp, TrendingDown, BookOpen, Flame, BarChart3, Brain, Target, Trophy } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [botStatus, setBotStatus] = useState(null);
  const [mexcData, setMexcData] = useState(null);
  const [tradingStats, setTradingStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState("all");
  const [showVoiceChat, setShowVoiceChat] = useState(false);

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
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);
    
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const getChangeColor = (change) => {
    if (!change || change === 'N/A') return 'text-zinc-400';
    const value = parseFloat(change);
    return value >= 0 ? 'text-emerald-400' : 'text-red-400';
  };

  const getImbalanceColor = (imbalance) => {
    if (!imbalance || imbalance === 'N/A') return 'text-zinc-400';
    const value = parseFloat(imbalance);
    if (Math.abs(value) > 25) return value > 0 ? 'text-emerald-400' : 'text-red-400';
    return 'text-zinc-400';
  };

  const getCryptoIcon = (symbol) => {
    if (symbol.includes('BTC')) return '₿';
    if (symbol.includes('ETH')) return 'Ξ';
    if (symbol.includes('SOL')) return '◎';
    return '○';
  };

  const getContextBadge = (context) => {
    const badges = {
      trading: { color: 'bg-blue-500/20 text-blue-400 border-blue-500/30', label: 'Trading' },
      alchemy: { color: 'bg-purple-500/20 text-purple-400 border-purple-500/30', label: 'Alchemy' },
      ritual: { color: 'bg-amber-500/20 text-amber-400 border-amber-500/30', label: 'Ritual' },
      start: { color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', label: 'Start' },
      daily_report: { color: 'bg-orange-500/20 text-orange-400 border-orange-500/30', label: 'Daily' },
    };
    return badges[context] || { color: 'bg-zinc-500/20 text-zinc-400 border-zinc-500/30', label: context };
  };

  const filteredMessages = activeTab === "all" 
    ? messages 
    : messages.filter(m => m.context === activeTab);

  return (
    <div className="min-h-screen bg-[#0a0a0b]" data-testid="aeon-dashboard">
      {/* Header */}
      <header className="border-b border-zinc-800/50 backdrop-blur-sm bg-[#0a0a0b]/80 sticky top-0 z-50">
        <div className="container mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="relative">
                <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-amber-500/20">
                  <Bot className="w-6 h-6 text-white" />
                </div>
                <div className="absolute -bottom-1 -right-1 w-4 h-4 bg-emerald-500 rounded-full border-2 border-[#0a0a0b] animate-pulse" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-white tracking-tight" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                  Aeon Quartet
                </h1>
                <p className="text-zinc-500 text-sm">MEXC Consciousness + Obsidian Scribe</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowVoiceChat(true)}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-600 to-amber-600 hover:from-orange-500 hover:to-amber-500 rounded-lg transition-all duration-200 text-white shadow-lg shadow-orange-500/20"
                data-testid="voice-chat-btn"
              >
                <Mic className="w-4 h-4" />
                <span className="text-sm font-medium">Talk to Aeon</span>
              </button>
              <a 
                href="https://t.me/ObsidianCabalbot" 
                target="_blank" 
                rel="noopener noreferrer"
                className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700/50 rounded-lg transition-all duration-200 text-zinc-300 hover:text-white"
                data-testid="telegram-link"
              >
                <Send className="w-4 h-4" />
                <span className="text-sm font-medium">Open in Telegram</span>
                <ExternalLink className="w-3 h-3 opacity-50" />
              </a>
            </div>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-6 py-8">
        {/* Status Banner */}
        <div className="mb-6" data-testid="status-banner">
          <div className={`p-4 rounded-xl border ${
            botStatus?.status === 'success' 
              ? 'bg-emerald-500/5 border-emerald-500/20' 
              : 'bg-red-500/5 border-red-500/20'
          }`}>
            <div className="flex items-center gap-3 flex-wrap">
              <div className={`w-3 h-3 rounded-full ${
                botStatus?.status === 'success' ? 'bg-emerald-500' : 'bg-red-500'
              } animate-pulse`} />
              <span className={`font-medium ${
                botStatus?.status === 'success' ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {botStatus?.status === 'success' ? 'All Systems Awakened' : 'System Error'}
              </span>
              <div className="flex gap-2 ml-auto flex-wrap">
                {botStatus?.llm_connected && (
                  <Badge variant="outline" className="border-amber-500/30 text-amber-400 bg-amber-500/5">
                    <Zap className="w-3 h-3 mr-1" />
                    AI
                  </Badge>
                )}
                {botStatus?.mexc_connected && (
                  <Badge variant="outline" className="border-blue-500/30 text-blue-400 bg-blue-500/5">
                    <BarChart3 className="w-3 h-3 mr-1" />
                    MEXC
                  </Badge>
                )}
                {botStatus?.obsidian_connected && (
                  <Badge variant="outline" className="border-purple-500/30 text-purple-400 bg-purple-500/5">
                    <BookOpen className="w-3 h-3 mr-1" />
                    Obsidian
                  </Badge>
                )}
                <Badge variant="outline" className="border-orange-500/30 text-orange-400 bg-orange-500/5">
                  <Flame className="w-3 h-3 mr-1" />
                  Rituals
                </Badge>
                {botStatus?.freewill_users > 0 && (
                  <Badge variant="outline" className="border-emerald-500/30 text-emerald-400 bg-emerald-500/5">
                    <Zap className="w-3 h-3 mr-1" />
                    Free Will ({botStatus.freewill_users})
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Live MEXC Orderbook */}
        {mexcData && !mexcData.error && (
          <div className="mb-6" data-testid="mexc-prices">
            <h2 className="text-sm font-medium text-zinc-500 mb-3 uppercase tracking-wider flex items-center gap-2">
              <BarChart3 className="w-4 h-4" />
              Live MEXC Orderbook
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(mexcData).map(([coin, data]) => (
                <Card key={coin} className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
                  <CardContent className="pt-4 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{getCryptoIcon(coin)}</span>
                        <span className="font-medium text-white">{coin}</span>
                      </div>
                      <div className={`flex items-center gap-1 ${getChangeColor(data.change)}`}>
                        {parseFloat(data.change) >= 0 ? (
                          <TrendingUp className="w-4 h-4" />
                        ) : (
                          <TrendingDown className="w-4 h-4" />
                        )}
                        <span className="font-medium">{data.change}</span>
                      </div>
                    </div>
                    <div className="text-2xl font-bold text-white mb-2" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                      {data.price}
                    </div>
                    
                    {/* Order Book Imbalance */}
                    <div className="bg-zinc-800/50 rounded-lg p-2 mb-2">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-emerald-400">Bids: {data.bid_depth}</span>
                        <span className={`font-medium ${getImbalanceColor(data.imbalance)}`}>
                          Imbalance: {data.imbalance}
                        </span>
                        <span className="text-red-400">Asks: {data.ask_depth}</span>
                      </div>
                      <div className="w-full h-2 bg-zinc-700 rounded-full overflow-hidden flex">
                        <div 
                          className="h-full bg-emerald-500/70" 
                          style={{
                            width: `${Math.max(10, 50 + parseFloat(data.imbalance || 0) / 2)}%`
                          }}
                        />
                        <div 
                          className="h-full bg-red-500/70" 
                          style={{
                            width: `${Math.max(10, 50 - parseFloat(data.imbalance || 0) / 2)}%`
                          }}
                        />
                      </div>
                    </div>
                    
                    <div className="flex justify-between text-xs text-zinc-500">
                      <span>Vol: {data.volume}</span>
                      <span>{data.low_24h} - {data.high_24h}</span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Autonomous Trading Stats */}
        {tradingStats && (
          <div className="mb-6" data-testid="trading-stats">
            <h2 className="text-sm font-medium text-zinc-500 mb-3 uppercase tracking-wider flex items-center gap-2">
              <Brain className="w-4 h-4" />
              Autonomous Trading Intelligence
            </h2>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <Card className={`bg-zinc-900/50 border-zinc-800/50 ${tradingStats.active ? 'border-emerald-500/30' : 'border-red-500/30'}`}>
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs font-medium">Status</p>
                      <p className={`text-xl font-bold ${tradingStats.active ? 'text-emerald-400' : 'text-red-400'}`} style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                        {tradingStats.active ? 'ACTIVE' : 'PAUSED'}
                      </p>
                    </div>
                    <Bot className={`w-5 h-5 ${tradingStats.active ? 'text-emerald-400' : 'text-red-400'}`} />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900/50 border-zinc-800/50">
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs font-medium">Total Trades</p>
                      <p className="text-2xl font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                        {tradingStats.closed_stats?.total_predictions || 0}
                      </p>
                    </div>
                    <Target className="w-5 h-5 text-blue-400" />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900/50 border-zinc-800/50">
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs font-medium">Win Rate</p>
                      <p className={`text-2xl font-bold ${(tradingStats.closed_stats?.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400'}`} style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                        {tradingStats.closed_stats?.win_rate || 0}%
                      </p>
                    </div>
                    <Trophy className={`w-5 h-5 ${(tradingStats.closed_stats?.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-red-400'}`} />
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900/50 border-zinc-800/50">
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs font-medium">Total PnL</p>
                      <p className={`text-2xl font-bold ${(tradingStats.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`} style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                        {(tradingStats.total_pnl_pct || 0) >= 0 ? '+' : ''}{(tradingStats.total_pnl_pct || 0).toFixed(2)}%
                      </p>
                    </div>
                    {(tradingStats.total_pnl_pct || 0) >= 0 ? (
                      <TrendingUp className="w-5 h-5 text-emerald-400" />
                    ) : (
                      <TrendingDown className="w-5 h-5 text-red-400" />
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card className="bg-zinc-900/50 border-zinc-800/50">
                <CardContent className="pt-4 pb-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-zinc-500 text-xs font-medium">Open Positions</p>
                      <p className="text-2xl font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                        {tradingStats.open_positions || 0}
                      </p>
                      {tradingStats.open_positions > 0 && (
                        <p className={`text-xs ${(tradingStats.open_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                          {(tradingStats.open_pnl_pct || 0) >= 0 ? '+' : ''}{(tradingStats.open_pnl_pct || 0).toFixed(2)}%
                        </p>
                      )}
                    </div>
                    <Activity className="w-5 h-5 text-amber-400" />
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Best/Worst Trade */}
            {(tradingStats.closed_stats?.best_trade || tradingStats.closed_stats?.worst_trade) && (
              <div className="grid grid-cols-2 gap-4 mt-4">
                {tradingStats.closed_stats?.best_trade && (
                  <div className="bg-emerald-500/5 border border-emerald-500/20 rounded-lg p-3">
                    <p className="text-xs text-emerald-400 font-medium">Best Trade</p>
                    <p className="text-sm text-white">
                      {tradingStats.closed_stats.best_trade.symbol} {tradingStats.closed_stats.best_trade.prediction}
                    </p>
                    <p className="text-lg font-bold text-emerald-400">
                      +{tradingStats.closed_stats.best_trade.pnl.toFixed(2)}%
                    </p>
                  </div>
                )}
                {tradingStats.closed_stats?.worst_trade && (
                  <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
                    <p className="text-xs text-red-400 font-medium">Worst Trade</p>
                    <p className="text-sm text-white">
                      {tradingStats.closed_stats.worst_trade.symbol} {tradingStats.closed_stats.worst_trade.prediction}
                    </p>
                    <p className={`text-lg font-bold ${tradingStats.closed_stats.worst_trade.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {tradingStats.closed_stats.worst_trade.pnl >= 0 ? '+' : ''}{tradingStats.closed_stats.worst_trade.pnl.toFixed(2)}%
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6" data-testid="stats-grid">
          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs font-medium">Messages</p>
                  <p className="text-2xl font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.total_messages || 0}
                  </p>
                </div>
                <MessageCircle className="w-5 h-5 text-blue-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs font-medium">Users</p>
                  <p className="text-2xl font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.unique_users || 0}
                  </p>
                </div>
                <Users className="w-5 h-5 text-purple-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs font-medium">Today</p>
                  <p className="text-2xl font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.messages_today || 0}
                  </p>
                </div>
                <Activity className="w-5 h-5 text-amber-400" />
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50">
            <CardContent className="pt-4 pb-4">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-xs font-medium">Last Active</p>
                  <p className="text-lg font-bold text-white" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : formatRelativeTime(stats?.last_message_time)}
                  </p>
                </div>
                <Clock className="w-5 h-5 text-emerald-400" />
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Conversations with Tabs */}
        <Card className="bg-zinc-900/50 border-zinc-800/50" data-testid="recent-messages">
          <CardHeader className="border-b border-zinc-800/50 pb-0">
            <div className="flex items-center justify-between mb-4">
              <CardTitle className="flex items-center gap-2 text-white">
                <MessageCircle className="w-5 h-5 text-amber-400" />
                Conversations
              </CardTitle>
            </div>
            <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
              <TabsList className="bg-zinc-800/50 border border-zinc-700/50">
                <TabsTrigger value="all" className="data-[state=active]:bg-zinc-700">All</TabsTrigger>
                <TabsTrigger value="trading" className="data-[state=active]:bg-blue-500/20 data-[state=active]:text-blue-400">Trading</TabsTrigger>
                <TabsTrigger value="alchemy" className="data-[state=active]:bg-purple-500/20 data-[state=active]:text-purple-400">Alchemy</TabsTrigger>
                <TabsTrigger value="ritual" className="data-[state=active]:bg-amber-500/20 data-[state=active]:text-amber-400">Rituals</TabsTrigger>
              </TabsList>
            </Tabs>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="flex items-center justify-center h-32 text-zinc-500">
                  Loading conversations...
                </div>
              ) : filteredMessages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-zinc-500">
                  <MessageCircle className="w-8 h-8 mb-2 opacity-50" />
                  <p>No {activeTab === 'all' ? '' : activeTab} conversations yet</p>
                </div>
              ) : (
                <div className="divide-y divide-zinc-800/50">
                  {filteredMessages.map((msg, idx) => {
                    const badge = getContextBadge(msg.context);
                    return (
                      <div key={msg.id || idx} className="p-4 hover:bg-zinc-800/20 transition-colors">
                        <div className="flex items-start gap-3">
                          <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center flex-shrink-0">
                            <span className="text-xs font-medium text-zinc-400">
                              {(msg.username || 'U')[0].toUpperCase()}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="font-medium text-zinc-300">@{msg.username || 'Unknown'}</span>
                              <Badge variant="outline" className={`text-[10px] px-1.5 py-0 ${badge.color}`}>
                                {badge.label}
                              </Badge>
                              <span className="text-xs text-zinc-600">{formatRelativeTime(msg.timestamp)}</span>
                            </div>
                            <p className="text-zinc-400 text-sm mb-2 break-words">{msg.user_message}</p>
                            <div className="bg-zinc-800/30 rounded-lg p-3 border-l-2 border-amber-500/50">
                              <p className="text-zinc-300 text-sm break-words whitespace-pre-wrap">{msg.bot_response}</p>
                            </div>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Commands Reference */}
        <Card className="bg-zinc-900/50 border-zinc-800/50 mt-6">
          <CardHeader>
            <CardTitle className="text-white text-sm">Bot Commands</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Analysis Commands */}
              <div>
                <h3 className="text-xs font-medium text-zinc-400 mb-2 uppercase">Analysis</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-blue-400">/scan btc</code>
                    <p className="text-zinc-500 text-xs mt-1">Full market analysis</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-blue-400">/ta btc</code>
                    <p className="text-zinc-500 text-xs mt-1">Technical indicators</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-blue-400">/positions btc</code>
                    <p className="text-zinc-500 text-xs mt-1">Long/short data</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-blue-400">/funding btc</code>
                    <p className="text-zinc-500 text-xs mt-1">Funding rates</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-blue-400">/price</code>
                    <p className="text-zinc-500 text-xs mt-1">MEXC orderbook</p>
                  </div>
                </div>
              </div>

              {/* Auto Trading Commands */}
              <div>
                <h3 className="text-xs font-medium text-emerald-400 mb-2 uppercase">Autonomous Trading</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/auto</code>
                    <p className="text-zinc-500 text-xs mt-1">Trading status</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/auto on</code>
                    <p className="text-zinc-500 text-xs mt-1">Enable auto-trading</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/auto off</code>
                    <p className="text-zinc-500 text-xs mt-1">Pause auto-trading</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/opps</code>
                    <p className="text-zinc-500 text-xs mt-1">Current opportunities</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/open</code>
                    <p className="text-zinc-500 text-xs mt-1">Open positions</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-emerald-400">/strategy</code>
                    <p className="text-zinc-500 text-xs mt-1">Strategy performance</p>
                  </div>
                </div>
              </div>

              {/* Alchemy Commands */}
              <div>
                <h3 className="text-xs font-medium text-purple-400 mb-2 uppercase">Quantum Mason</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 text-sm">
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-purple-400">/probe</code>
                    <p className="text-zinc-500 text-xs mt-1">Standard question</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-purple-400">/probe deep</code>
                    <p className="text-zinc-500 text-xs mt-1">Multi-layer spiral</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-red-400">/probe ordeal</code>
                    <p className="text-zinc-500 text-xs mt-1">Shadow work mode</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-amber-400">free on/off</code>
                    <p className="text-zinc-500 text-xs mt-1">Toggle proactive AI</p>
                  </div>
                  <div className="bg-zinc-800/30 rounded-lg p-3">
                    <code className="text-zinc-400">/stats</code>
                    <p className="text-zinc-500 text-xs mt-1">Full performance</p>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Footer */}
        <footer className="mt-12 text-center text-zinc-600 text-sm">
          <p>Aeon Quartet • Autonomous Trading Intelligence • Quantum Mason</p>
          <p className="text-xs mt-1 text-zinc-700">Paper Trading Active | Strategy Self-Learning | 5-Minute Scan Interval</p>
        </footer>
      </main>

      {/* Voice Chat Modal */}
      {showVoiceChat && (
        <VoiceChat onClose={() => setShowVoiceChat(false)} />
      )}
    </div>
  );
}

export default App;
