import { useState, useEffect } from "react";
import { Card, CardContent } from "./ui/card";
import { Brain, RefreshCw, Zap, TrendingUp, TrendingDown, Clock, ToggleLeft, ToggleRight, Send, Eye } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function LearningEngine() {
  const [status, setStatus] = useState(null);
  const [patterns, setPatterns] = useState(null);
  const [coins, setCoins] = useState(null);
  const [sessions, setSessions] = useState(null);
  const [insights, setInsights] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [forceLoading, setForceLoading] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [preview, setPreview] = useState(null);
  const [activeSection, setActiveSection] = useState("status");
  const [actionResult, setActionResult] = useState(null);

  const fetchAll = async () => {
    try {
      const [statusRes, patternsRes, coinsRes, sessionsRes, insightsRes, recsRes] = await Promise.all([
        axios.get(`${API}/learning/status`),
        axios.get(`${API}/learning/patterns`),
        axios.get(`${API}/learning/coins`),
        axios.get(`${API}/learning/sessions`),
        axios.get(`${API}/learning/insights`),
        axios.get(`${API}/learning/recommendations`),
      ]);
      setStatus(statusRes.data);
      setPatterns(patternsRes.data);
      setCoins(coinsRes.data);
      setSessions(sessionsRes.data);
      setInsights(insightsRes.data);
      setRecommendations(recsRes.data);
    } catch (e) {
      console.error("Learning engine error:", e);
    } finally {
      setLoading(false);
    }
  };

  const forceCycle = async () => {
    setForceLoading(true);
    setActionResult(null);
    try {
      const res = await axios.post(`${API}/learning/force-cycle`);
      setActionResult({ success: true, message: "Learning cycle completed" });
      await fetchAll();
    } catch (e) {
      setActionResult({ success: false, message: e.response?.data?.detail || "Force cycle failed" });
    } finally {
      setForceLoading(false);
    }
  };

  const loadPreview = async () => {
    setPreviewLoading(true);
    try {
      const res = await axios.get(`${API}/learning/summary/preview`);
      setPreview(res.data);
    } catch (e) {
      console.error("Preview error:", e);
    } finally {
      setPreviewLoading(false);
    }
  };

  const sendSummary = async () => {
    setActionResult(null);
    try {
      const res = await axios.post(`${API}/learning/summary/send`);
      setActionResult({ success: true, message: res.data.message });
    } catch (e) {
      setActionResult({ success: false, message: e.response?.data?.detail || "Send failed" });
    }
  };

  const toggleLearning = async () => {
    if (!status) return;
    try {
      const res = await axios.post(`${API}/learning/toggle?enabled=${!status.active}`);
      setStatus(prev => ({ ...prev, active: res.data.enabled }));
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

  const sections = ["status", "patterns", "coins", "sessions", "insights"];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
            <Brain className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Learning Engine</h1>
            <p className="text-zinc-400 text-sm">Continuous AI learning from trade outcomes</p>
          </div>
        </div>
        <button
          onClick={toggleLearning}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            status?.active ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : "bg-zinc-700 text-zinc-400 hover:bg-zinc-600"
          }`}
        >
          {status?.active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          {status?.active ? "Active" : "Paused"}
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Patterns Learned</p>
            <p className="text-xl font-bold text-white">{patterns?.total_patterns ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Coins Tracked</p>
            <p className="text-xl font-bold text-white">{coins?.total_coins ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Today's Insights</p>
            <p className="text-xl font-bold text-white">{insights?.count ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Best Coin Win Rate</p>
            <p className="text-xl font-bold text-green-400">
              {coins?.best_performers?.[0]?.win_rate != null ? `${coins.best_performers[0].win_rate}%` : "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={forceCycle}
          disabled={forceLoading}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-500 hover:bg-emerald-600 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {forceLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {forceLoading ? "Running..." : "Force Learning Cycle"}
        </button>
        <button
          onClick={loadPreview}
          disabled={previewLoading}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {previewLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Eye className="w-4 h-4" />}
          Preview Summary
        </button>
        <button
          onClick={sendSummary}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors"
        >
          <Send className="w-4 h-4" />
          Send Summary
        </button>
        <button
          onClick={fetchAll}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {actionResult && (
        <div className={`px-4 py-3 rounded-lg text-sm ${actionResult.success ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
          {actionResult.message}
        </div>
      )}

      {preview && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-white font-semibold mb-2">Daily Summary Preview</p>
            <pre className="whitespace-pre-wrap text-zinc-300 text-sm font-mono bg-zinc-950 rounded-lg p-4 overflow-auto max-h-80">
              {preview.preview}
            </pre>
            <p className="text-xs text-zinc-500 mt-2">{preview.length} chars</p>
          </CardContent>
        </Card>
      )}

      {/* Section Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-zinc-800 pb-2">
        {sections.map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              activeSection === s ? "bg-emerald-500/20 text-emerald-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Status */}
      {activeSection === "status" && status && (
        <div className="grid md:grid-cols-2 gap-4">
          <Card className="bg-zinc-900/60 border-zinc-800">
            <CardContent className="p-4 space-y-2">
              <h3 className="text-white font-semibold mb-3">Engine Status</h3>
              {Object.entries(status).map(([k, v]) => (
                <div key={k} className="flex justify-between text-sm">
                  <span className="text-zinc-400 capitalize">{k.replace(/_/g, " ")}</span>
                  <span className={`font-medium ${k === "active" ? (v ? "text-green-400" : "text-zinc-400") : "text-white"}`}>
                    {typeof v === "boolean" ? (v ? "Yes" : "No") : typeof v === "object" ? JSON.stringify(v) : String(v ?? "—")}
                  </span>
                </div>
              ))}
            </CardContent>
          </Card>
          {recommendations && (
            <Card className="bg-zinc-900/60 border-zinc-800">
              <CardContent className="p-4">
                <h3 className="text-white font-semibold mb-3">Recommendations</h3>
                {Array.isArray(recommendations) ? (
                  <div className="space-y-2">
                    {recommendations.slice(0, 5).map((r, i) => (
                      <div key={i} className="text-sm text-zinc-300 bg-zinc-950/50 rounded p-2">{typeof r === "string" ? r : JSON.stringify(r)}</div>
                    ))}
                    {recommendations.length === 0 && <p className="text-zinc-500 text-sm">No recommendations yet.</p>}
                  </div>
                ) : (
                  <div className="space-y-2 text-sm">
                    {Object.entries(recommendations).slice(0, 5).map(([k, v]) => (
                      <div key={k} className="text-zinc-300 bg-zinc-950/50 rounded p-2">
                        <span className="text-zinc-400 capitalize">{k.replace(/_/g, " ")}: </span>
                        {typeof v === "object" ? JSON.stringify(v) : String(v)}
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Patterns */}
      {activeSection === "patterns" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Learned Trading Patterns</h3>
          {!patterns?.patterns?.length ? (
            <p className="text-zinc-500 text-sm">No patterns learned yet — needs more trade data.</p>
          ) : (
            <div className="grid md:grid-cols-2 gap-3">
              {patterns.patterns.map((p, i) => (
                <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white text-sm font-medium">{p.pattern}</span>
                      <span className={`text-sm font-bold ${p.win_rate >= 55 ? "text-green-400" : p.win_rate >= 45 ? "text-yellow-400" : "text-red-400"}`}>
                        {p.win_rate}% WR
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs text-center">
                      <div><p className="text-zinc-500">Total</p><p className="text-white">{p.total}</p></div>
                      <div><p className="text-zinc-500">Wins</p><p className="text-green-400">{p.wins}</p></div>
                      <div><p className="text-zinc-500">PnL</p>
                        <p className={p.total_pnl >= 0 ? "text-green-400" : "text-red-400"}>
                          {p.total_pnl >= 0 ? "+" : ""}{p.total_pnl?.toFixed(2)}
                        </p>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Coins */}
      {activeSection === "coins" && (
        <div className="space-y-4">
          {coins?.best_performers?.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingUp className="w-4 h-4 text-green-400" />
                <h3 className="text-white font-semibold">Best Performers</h3>
              </div>
              <div className="grid md:grid-cols-3 gap-3">
                {coins.best_performers.map((c, i) => (
                  <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-white font-medium">{c.coin?.replace("/USDT", "")}</p>
                          <p className="text-zinc-500 text-xs">{c.total} trades</p>
                        </div>
                        <p className="text-green-400 font-bold">{c.win_rate}%</p>
                      </div>
                      <p className={`text-xs mt-1 ${c.avg_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        Avg {c.avg_pnl >= 0 ? "+" : ""}{c.avg_pnl?.toFixed(2)} per trade
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
          {coins?.worst_performers?.length > 0 && (
            <div>
              <div className="flex items-center gap-2 mb-3">
                <TrendingDown className="w-4 h-4 text-red-400" />
                <h3 className="text-white font-semibold">Avoid These</h3>
              </div>
              <div className="grid md:grid-cols-3 gap-3">
                {coins.worst_performers.map((c, i) => (
                  <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                    <CardContent className="p-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-white font-medium">{c.coin?.replace("/USDT", "")}</p>
                          <p className="text-zinc-500 text-xs">{c.total} trades</p>
                        </div>
                        <p className="text-red-400 font-bold">{c.win_rate}%</p>
                      </div>
                      <p className={`text-xs mt-1 ${c.avg_pnl >= 0 ? "text-green-400" : "text-red-400"}`}>
                        Avg {c.avg_pnl >= 0 ? "+" : ""}{c.avg_pnl?.toFixed(2)} per trade
                      </p>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          )}
          {!coins?.best_performers?.length && !coins?.worst_performers?.length && (
            <p className="text-zinc-500 text-sm">No coin performance data yet — needs more closed trades.</p>
          )}
        </div>
      )}

      {/* Sessions */}
      {activeSection === "sessions" && (
        <div className="grid md:grid-cols-2 gap-6">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-orange-400" />
              <h3 className="text-white font-semibold">Best Hours</h3>
            </div>
            {!sessions?.best_hours?.length ? (
              <p className="text-zinc-500 text-sm">No hourly data yet.</p>
            ) : (
              <div className="space-y-2">
                {sessions.best_hours.map((h, i) => (
                  <div key={i} className="flex items-center justify-between bg-zinc-900/60 rounded-lg p-3 border border-zinc-800">
                    <span className="text-zinc-300 text-sm">{h.hour}:00 UTC</span>
                    <div className="text-right">
                      <p className="text-green-400 text-sm font-medium">{h.win_rate}% WR</p>
                      <p className="text-zinc-500 text-xs">{h.trades} trades</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Clock className="w-4 h-4 text-red-400" />
              <h3 className="text-white font-semibold">Best Days</h3>
            </div>
            {!sessions?.best_days?.length ? (
              <p className="text-zinc-500 text-sm">No daily data yet.</p>
            ) : (
              <div className="space-y-2">
                {sessions.best_days.map((d, i) => (
                  <div key={i} className="flex items-center justify-between bg-zinc-900/60 rounded-lg p-3 border border-zinc-800">
                    <span className="text-zinc-300 text-sm">{d.day}</span>
                    <div className="text-right">
                      <p className={`text-sm font-medium ${d.win_rate >= 55 ? "text-green-400" : "text-yellow-400"}`}>{d.win_rate}% WR</p>
                      <p className="text-zinc-500 text-xs">{d.trades} trades</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Insights */}
      {activeSection === "insights" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Today's Insights</h3>
          {!insights?.insights?.length ? (
            <p className="text-zinc-500 text-sm">No insights generated yet today. Run a learning cycle to generate them.</p>
          ) : (
            <div className="space-y-2">
              {insights.insights.map((insight, i) => (
                <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <p className="text-zinc-300 text-sm">{typeof insight === "string" ? insight : JSON.stringify(insight)}</p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
