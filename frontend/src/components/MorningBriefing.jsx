import { useState, useEffect } from "react";
import { Card, CardContent } from "./ui/card";
import { Sun, Send, RefreshCw, Eye, TrendingUp, TrendingDown, Clock, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function MorningBriefing() {
  const [status, setStatus] = useState(null);
  const [preview, setPreview] = useState(null);
  const [movers, setMovers] = useState(null);
  const [structure, setStructure] = useState(null);
  const [setups, setSetups] = useState(null);
  const [loading, setLoading] = useState(true);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sendLoading, setSendLoading] = useState(false);
  const [sendResult, setSendResult] = useState(null);
  const [showPreview, setShowPreview] = useState(false);
  const [activeSection, setActiveSection] = useState("overview");

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/briefing/status`);
      setStatus(res.data);
    } catch (e) {
      console.error("Briefing status error:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchMovers = async () => {
    try {
      const res = await axios.get(`${API}/briefing/movers`);
      setMovers(res.data);
    } catch (e) {
      console.error("Movers error:", e);
    }
  };

  const fetchStructure = async () => {
    try {
      const res = await axios.get(`${API}/briefing/structure`);
      setStructure(res.data);
    } catch (e) {
      console.error("Structure error:", e);
    }
  };

  const fetchSetups = async () => {
    try {
      const res = await axios.get(`${API}/briefing/setups`);
      setSetups(res.data);
    } catch (e) {
      console.error("Setups error:", e);
    }
  };

  const loadPreview = async () => {
    setPreviewLoading(true);
    try {
      const res = await axios.get(`${API}/briefing/preview`);
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
      const res = await axios.post(`${API}/briefing/test`);
      setSendResult({ success: true, message: res.data.message });
    } catch (e) {
      setSendResult({ success: false, message: e.response?.data?.detail || "Send failed" });
    } finally {
      setSendLoading(false);
    }
  };

  const toggleBriefing = async () => {
    if (!status) return;
    try {
      const res = await axios.post(`${API}/briefing/toggle?enabled=${!status.enabled}`);
      setStatus(prev => ({ ...prev, enabled: res.data.enabled }));
    } catch (e) {
      console.error("Toggle error:", e);
    }
  };

  useEffect(() => {
    fetchStatus();
    fetchMovers();
    fetchStructure();
    fetchSetups();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-yellow-500 to-orange-500 flex items-center justify-center">
            <Sun className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">Morning Briefing</h1>
            <p className="text-zinc-400 text-sm">Daily 6:00 AM CT market overview via Telegram</p>
          </div>
        </div>
        <button
          onClick={toggleBriefing}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            status?.enabled ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : "bg-zinc-700 text-zinc-400 hover:bg-zinc-600"
          }`}
        >
          {status?.enabled ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          {status?.enabled ? "Enabled" : "Disabled"}
        </button>
      </div>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Status</p>
            <p className={`font-semibold ${status?.enabled ? "text-green-400" : "text-zinc-400"}`}>
              {status?.enabled ? "Active" : "Paused"}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Scheduled</p>
            <p className="font-semibold text-white">{status?.scheduled_time || "6:00 AM CT"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Next Briefing</p>
            <p className="font-semibold text-orange-400 text-sm">{status?.next_briefing || "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Active Users</p>
            <p className="font-semibold text-white">{status?.active_users ?? "—"}</p>
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
          {previewLoading ? "Generating..." : "Preview Briefing"}
        </button>
        <button
          onClick={sendTest}
          disabled={sendLoading}
          className="flex items-center gap-2 px-4 py-2 bg-orange-500 hover:bg-orange-600 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {sendLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          {sendLoading ? "Sending..." : "Send Test Now"}
        </button>
      </div>

      {sendResult && (
        <div className={`px-4 py-3 rounded-lg text-sm ${sendResult.success ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"}`}>
          {sendResult.message}
        </div>
      )}

      {/* Preview Panel */}
      {preview && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <button
              onClick={() => setShowPreview(!showPreview)}
              className="w-full flex items-center justify-between text-white font-semibold mb-2"
            >
              <span>Briefing Preview</span>
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
        {["overview", "movers", "structure", "setups"].map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              activeSection === s ? "bg-orange-500/20 text-orange-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {/* Movers */}
      {activeSection === "movers" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Overnight Movers</h3>
          {!movers ? (
            <p className="text-zinc-500 text-sm">Loading movers data...</p>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {movers.gainers?.length > 0 && (
                <Card className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      <span className="text-white font-medium">Top Gainers</span>
                    </div>
                    <div className="space-y-2">
                      {movers.gainers.slice(0, 5).map((g, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-zinc-300">{g.symbol?.replace("/USDT", "")}</span>
                          <span className="text-green-400">+{g.change?.toFixed(2)}%</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
              {movers.losers?.length > 0 && (
                <Card className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingDown className="w-4 h-4 text-red-400" />
                      <span className="text-white font-medium">Top Losers</span>
                    </div>
                    <div className="space-y-2">
                      {movers.losers.slice(0, 5).map((g, i) => (
                        <div key={i} className="flex justify-between text-sm">
                          <span className="text-zinc-300">{g.symbol?.replace("/USDT", "")}</span>
                          <span className="text-red-400">{g.change?.toFixed(2)}%</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </div>
      )}

      {/* Structure */}
      {activeSection === "structure" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Market Structure</h3>
          {!structure ? (
            <p className="text-zinc-500 text-sm">Loading structure data...</p>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {Object.entries(structure).map(([key, val]) => (
                <Card key={key} className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <p className="text-xs text-zinc-500 mb-1 uppercase">{key.replace(/_/g, " ")}</p>
                    <p className="text-white text-sm font-medium">
                      {typeof val === "object" ? JSON.stringify(val) : String(val)}
                    </p>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Setups */}
      {activeSection === "setups" && (
        <div className="space-y-3">
          <h3 className="text-white font-semibold">Setups to Watch</h3>
          {!setups ? (
            <p className="text-zinc-500 text-sm">Loading setups...</p>
          ) : setups.setups?.length === 0 ? (
            <p className="text-zinc-500 text-sm">No setups at this time.</p>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {setups.setups?.map((s, i) => (
                <Card key={i} className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">{s.symbol?.replace("/USDT", "")}</span>
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                        s.direction === "LONG" ? "bg-green-500/20 text-green-400" : "bg-red-500/20 text-red-400"
                      }`}>{s.direction}</span>
                    </div>
                    <p className="text-zinc-400 text-sm">{s.reason || s.note}</p>
                    {s.entry && <p className="text-zinc-500 text-xs mt-1">Entry: {s.entry}</p>}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Overview */}
      {activeSection === "overview" && (
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4 space-y-3">
            <h3 className="text-white font-semibold flex items-center gap-2">
              <Clock className="w-4 h-4 text-orange-400" />
              Schedule Overview
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-zinc-400">Current Time (CT)</span>
                <span className="text-white">{status?.current_time_ct || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Timezone</span>
                <span className="text-white">{status?.timezone || "—"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Last Sent</span>
                <span className="text-white">{status?.last_sent ? new Date(status.last_sent).toLocaleDateString() : "Never"}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-400">Next Briefing</span>
                <span className="text-orange-400">{status?.next_briefing || "—"}</span>
              </div>
            </div>
            <p className="text-zinc-500 text-xs pt-2 border-t border-zinc-800">
              The morning briefing auto-sends at 6:00 AM CT every day via Telegram with market structure, overnight movers, funding rates, and potential setups.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
