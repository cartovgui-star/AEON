import { useState, useEffect } from "react";
import { Card, CardContent } from "./ui/card";
import { BarChart3, Send, Eye, RefreshCw, TrendingUp, TrendingDown, Trophy, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function WeeklyReport() {
  const [status, setStatus] = useState(null);
  const [preview, setPreview] = useState(null);
  const [strategyStats, setStrategyStats] = useState(null);
  const [coinPerf, setCoinPerf] = useState(null);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [activeSection, setActiveSection] = useState("overview");

  const fetchAll = async () => {
    try {
      const [statusRes, stratRes, coinRes] = await Promise.all([
        axios.get(`${API}/report/status`),
        axios.get(`${API}/report/strategy-stats`),
        axios.get(`${API}/report/coin-performance`),
      ]);
      setStatus(statusRes.data);
      setStrategyStats(stratRes.data);
      setCoinPerf(coinRes.data);
    } catch (e) {
      console.error("Weekly report error:", e);
    } finally {
      setLoading(false);
    }
  };

  const loadPreview = async () => {
    setPreviewLoading(true);
    try {
      const res = await axios.get(`${API}/report/preview`);
      setPreview(res.data);
      setShowPreview(true);
    } catch (e) {
      console.error("Preview error:", e);
    } finally {
      setPreviewLoading(false);
    }
  };

  const sendTest = async () => {
    setSendLoading(true);
    setSendResult(null);
    try {
      const res = await axios.post(`${API}/report/test`);
      setSendResult({ success: true, message: res.data.message });
    } catch (e) {
      setSendResult({ success: false, message: e.response?.data?.detail || "Send failed" });
    } finally {
      setSendLoading(false);
    }
  };

  const toggleReport = async () => {
    if (!status) return;
    try {
      const res = await axios.post(`${API}/report/toggle?enabled=${!status.enabled}`);
      setStatus(prev => ({ ...prev, enabled: res.data.enabled }));
    } catch (e) {
      console.error("Toggle error:", e);
    }
  };

  useEffect(() => {
    fetchAll();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  const topCoins = coinPerf?.top_performers || [];
  const worstCoins = coinPerf?.worst_performers || [];
  const strategies = strategyStats?.strategies || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 flex items-center justify-center">
            <BarChart3 className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Weekly Report</h1>
            <p className="text-zinc-400 text-sm">Performance summary every Sunday via Telegram</p>
          </div>
        </div>
        <button
          onClick={toggleReport}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            status?.enabled ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : "bg-zinc-700 text-zinc-400 hover:bg-zinc-600"
          }`}
        >
          {status?.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          {status?.enabled ? "Enabled" : "Disabled"}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">This Week's Trades</p>
            <p className="text-xl font-bold text-white">{strategyStats?.total_trades ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Strategies Tracked</p>
            <p className="text-xl font-bold text-white">{Object.keys(strategies).length}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Top Coin</p>
            <p className="text-xl font-bold text-green-400">{topCoins[0]?.coin?.replace("/USDT", "") || "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Status</p>
            <p className={`font-semibold ${status?.enabled ? "text-green-400" : "text-zinc-400"}`}>
              {status?.enabled ? "Active" : "Paused"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={loadPreview}
          disabled={previewLoading}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {previewLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
          {previewLoading ? "Generating..." : "Preview Report"}
        </button>
        <button
          onClick={sendTest}
          disabled={sendLoading}
          className="flex items-center gap-2 px-4 py-2 bg-purple-500 hover:bg-purple-600 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {sendLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          {sendLoading ? "Sending..." : "Send Now"}
        </button>
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {sendResult && (
        <div className={`px-4 py-3 rounded-lg text-sm ${sendResult.success ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
          {sendResult.message}
        </div>
      )}

      {/* Preview */}
      {preview && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className="w-full flex items-center justify-between text-white font-semibold mb-2"
            >
              <span>Report Preview</span>
              {showPreview ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
            </button>
            {showPreview && (
              <pre className="whitespace-pre-wrap text-zinc-300 text-sm font-mono bg-zinc-950 rounded-lg p-4 mt-2 overflow-auto max-h-96">
                {preview.preview}
              </pre>
            )}
            <p className="text-xs text-zinc-500 mt-2">{preview.length} chars · Generated {new Date(preview.generated_at).toLocaleTimeString()}</p>
          </CardContent>
        </Card>
      )}

      {/* Section Tabs */}
      <div className="flex gap-2 border-b border-zinc-800 pb-2">
        {["overview", "strategies", "coins"].map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              activeSection === s ? "bg-purple-500/20 text-purple-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Overview */}
      {activeSection === "overview" && status && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-white font-semibold">Week at a Glance</h3>
            <div className="space-y-2 text-sm">
              {Object.entries(status).filter(([k]) => !["enabled"].includes(k)).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-zinc-400 capitalize">{k.replace(/_/g, " ")}</span>
                  <span className="text-white">{typeof v === "object" ? JSON.stringify(v) : String(v)}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Strategies */}
      {activeSection === "strategies" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Strategy Performance This Week</h3>
          {Object.keys(strategies).length === 0 ? (
            <p className="text-zinc-500 text-sm">No trade data for this week yet.</p>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {Object.entries(strategies).map(([name, stats]) => {
                const wr = stats.win_rate ?? (stats.trades > 0 ? Math.round((stats.wins / stats.trades) * 100) : 0);
                return (
                  <Card key={name} className="bg-zinc-900/60 border-zinc-800">
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between mb-3">
                        <span className="text-white font-medium">{name}</span>
                        <span className={`text-sm font-bold ${wr >= 55 ? "text-green-400" : wr >= 45 ? "text-yellow-400" : "text-red-400"}`}>
                          {wr}% WR
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-xs text-center">
                        <div>
                          <p className="text-zinc-500">Trades</p>
                          <p className="text-white font-medium">{stats.trades ?? (stats.wins + stats.losses)}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500">Wins</p>
                          <p className="text-green-400 font-medium">{stats.wins}</p>
                        </div>
                        <div>
                          <p className="text-zinc-500">PnL</p>
                          <p className={`font-medium ${(stats.total_pnl ?? 0) >= 0 ? "text-green-400" : "text-red-400"}`}>
                            {(stats.total_pnl ?? 0) >= 0 ? "+" : ""}{(stats.total_pnl ?? 0).toFixed(2)}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Coins */}
      {activeSection === "coins" && (
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-green-400" />
              <h3 className="text-white font-semibold">Best Performers</h3>
            </div>
            {topCoins.length === 0 ? (
              <p className="text-zinc-500 text-sm">No data yet.</p>
            ) : (
              <div className="space-y-2">
                {topCoins.map((c, i) => (
                  <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                    <CardContent className="p-3 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        {i === 0 && <Trophy className="w-4 h-4 text-yellow-400" />}
                        <span className="text-white text-sm font-medium">{c.coin?.replace("/USDT", "")}</span>
                        <span className="text-zinc-500 text-xs">{c.total} trades</span>
                      </div>
                      <div className="text-right">
                        <p className="text-green-400 text-sm font-medium">{c.win_rate}% WR</p>
                        <p className={`text-xs ${c.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {c.total_pnl >= 0 ? "+" : ""}{c.total_pnl?.toFixed(2)}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-3">
              <TrendingDown className="w-4 h-4 text-red-400" />
              <h3 className="text-white font-semibold">Worst Performers</h3>
            </div>
            {worstCoins.length === 0 ? (
              <p className="text-zinc-500 text-sm">No data yet.</p>
            ) : (
              <div className="space-y-2">
                {worstCoins.map((c, i) => (
                  <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                    <CardContent className="p-3 flex items-center justify-between">
                      <div>
                        <span className="text-white text-sm font-medium">{c.coin?.replace("/USDT", "")}</span>
                        <span className="text-zinc-500 text-xs ml-2">{c.total} trades</span>
                      </div>
                      <div className="text-right">
                        <p className="text-red-400 text-sm font-medium">{c.win_rate}% WR</p>
                        <p className={`text-xs ${c.total_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                          {c.total_pnl >= 0 ? "+" : ""}{c.total_pnl?.toFixed(2)}
                        </p>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
