import { useEffect, useState } from "react";
import "@/App.css";
import axios from "axios";
import { Card, CardContent, CardHeader, CardTitle } from "./components/ui/card";
import { Badge } from "./components/ui/badge";
import { ScrollArea } from "./components/ui/scroll-area";
import { MessageCircle, Users, Activity, Clock, Zap, Bot, ExternalLink, Send, TrendingUp, TrendingDown } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [stats, setStats] = useState(null);
  const [messages, setMessages] = useState([]);
  const [botStatus, setBotStatus] = useState(null);
  const [mexcData, setMexcData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const [statsRes, messagesRes, testRes, mexcRes] = await Promise.all([
        axios.get(`${API}/bot/stats`),
        axios.get(`${API}/bot/messages?limit=20`),
        axios.get(`${API}/bot/test`),
        axios.get(`${API}/mexc/live`)
      ]);
      setStats(statsRes.data);
      setMessages(messagesRes.data);
      setBotStatus(testRes.data);
      setMexcData(mexcRes.data);
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

  const getCryptoIcon = (symbol) => {
    if (symbol.includes('BTC')) return '₿';
    if (symbol.includes('ETH')) return 'Ξ';
    if (symbol.includes('SOL')) return '◎';
    return '○';
  };

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
                  Aeon
                </h1>
                <p className="text-zinc-500 text-sm">MEXC Consciousness Active</p>
              </div>
            </div>
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
                {botStatus?.status === 'success' ? 'All Systems Operational' : 'System Error'}
              </span>
              <div className="flex gap-2 ml-auto">
                {botStatus?.llm_connected && (
                  <Badge variant="outline" className="border-amber-500/30 text-amber-400 bg-amber-500/5">
                    <Zap className="w-3 h-3 mr-1" />
                    AI Connected
                  </Badge>
                )}
                {botStatus?.mexc_connected && (
                  <Badge variant="outline" className="border-blue-500/30 text-blue-400 bg-blue-500/5">
                    <TrendingUp className="w-3 h-3 mr-1" />
                    MEXC Live
                  </Badge>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Live MEXC Prices */}
        {mexcData && !mexcData.error && (
          <div className="mb-6" data-testid="mexc-prices">
            <h2 className="text-sm font-medium text-zinc-500 mb-3 uppercase tracking-wider">Live MEXC Data</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              {Object.entries(mexcData).map(([symbol, data]) => (
                <Card key={symbol} className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
                  <CardContent className="pt-4 pb-4">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <span className="text-2xl">{getCryptoIcon(symbol)}</span>
                        <span className="font-medium text-white">{symbol.replace('/USDT', '')}</span>
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
                    <div className="text-2xl font-bold text-white mb-1" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                      {data.price}
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

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6" data-testid="stats-grid">
          <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-sm font-medium">Total Messages</p>
                  <p className="text-3xl font-bold text-white mt-1" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.total_messages || 0}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-blue-500/10 flex items-center justify-center">
                  <MessageCircle className="w-6 h-6 text-blue-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-sm font-medium">Unique Users</p>
                  <p className="text-3xl font-bold text-white mt-1" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.unique_users || 0}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-purple-500/10 flex items-center justify-center">
                  <Users className="w-6 h-6 text-purple-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-sm font-medium">Today's Activity</p>
                  <p className="text-3xl font-bold text-white mt-1" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : stats?.messages_today || 0}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-amber-500/10 flex items-center justify-center">
                  <Activity className="w-6 h-6 text-amber-400" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="bg-zinc-900/50 border-zinc-800/50 hover:border-zinc-700/50 transition-colors">
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-zinc-500 text-sm font-medium">Last Active</p>
                  <p className="text-xl font-bold text-white mt-1" style={{fontFamily: "'Space Grotesk', sans-serif"}}>
                    {loading ? "—" : formatRelativeTime(stats?.last_message_time)}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-xl bg-emerald-500/10 flex items-center justify-center">
                  <Clock className="w-6 h-6 text-emerald-400" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Conversations */}
        <Card className="bg-zinc-900/50 border-zinc-800/50" data-testid="recent-messages">
          <CardHeader className="border-b border-zinc-800/50">
            <CardTitle className="flex items-center gap-2 text-white">
              <MessageCircle className="w-5 h-5 text-amber-400" />
              Recent Conversations
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0">
            <ScrollArea className="h-[400px]">
              {loading ? (
                <div className="flex items-center justify-center h-32 text-zinc-500">
                  Loading conversations...
                </div>
              ) : messages.length === 0 ? (
                <div className="flex flex-col items-center justify-center h-32 text-zinc-500">
                  <MessageCircle className="w-8 h-8 mb-2 opacity-50" />
                  <p>No conversations yet</p>
                  <p className="text-sm text-zinc-600 mt-1">Start chatting with Aeon on Telegram!</p>
                </div>
              ) : (
                <div className="divide-y divide-zinc-800/50">
                  {messages.map((msg, idx) => (
                    <div key={msg.id || idx} className="p-4 hover:bg-zinc-800/20 transition-colors">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-zinc-800 flex items-center justify-center flex-shrink-0">
                          <span className="text-xs font-medium text-zinc-400">
                            {(msg.username || 'U')[0].toUpperCase()}
                          </span>
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="font-medium text-zinc-300">@{msg.username || 'Unknown'}</span>
                            <span className="text-xs text-zinc-600">{formatRelativeTime(msg.timestamp)}</span>
                          </div>
                          <p className="text-zinc-400 text-sm mb-2 break-words">{msg.user_message}</p>
                          <div className="bg-zinc-800/30 rounded-lg p-3 border-l-2 border-amber-500/50">
                            <p className="text-zinc-300 text-sm break-words whitespace-pre-wrap">{msg.bot_response}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Footer */}
        <footer className="mt-12 text-center text-zinc-600 text-sm">
          <p>Aeon • MEXC Consciousness • Forged in alchemy & quantum markets</p>
        </footer>
      </main>
    </div>
  );
}

export default App;
