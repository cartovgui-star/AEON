import { useState, useEffect, useRef } from "react";
import { Card, CardContent } from "./ui/card";
import { Eye, RefreshCw, Search, TrendingUp, TrendingDown, Minus, Zap, ToggleLeft, ToggleRight, ChevronDown, ChevronUp } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const BiasTag = ({ bias, score }) => {
  const color = bias === "BULLISH" ? "text-green-400 bg-green-500/20" :
                bias === "BEARISH" ? "text-red-400 bg-red-500/20" :
                "text-zinc-400 bg-zinc-700";
  const icon = bias === "BULLISH" ? <TrendingUp className="w-3 h-3" /> :
               bias === "BEARISH" ? <TrendingDown className="w-3 h-3" /> :
               <Minus className="w-3 h-3" />;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${color}`}>
      {icon}{bias} {score != null ? `${score}` : ""}
    </span>
  );
};

const ConfidenceBar = ({ score }) => {
  const width = Math.max(0, Math.min(100, score));
  const color = score >= 75 ? "bg-green-500" : score >= 55 ? "bg-yellow-500" : "bg-zinc-600";
  return (
    <div className="w-full bg-zinc-800 rounded-full h-1.5 mt-1">
      <div className={`h-1.5 rounded-full transition-all ${color}`} style={{ width: `${width}%` }} />
    </div>
  );
};

export default function OracleDashboard() {
  const [status, setStatus] = useState(null);
  const [scanResults, setScanResults] = useState(null);
  const [scanStatus, setScanStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [symbolInput, setSymbolInput] = useState("");
  const [symbolResult, setSymbolResult] = useState(null);
  const [symbolLoading, setSymbolLoading] = useState(false);
  const [minScore, setMinScore] = useState(60);
  const [biasFilter, setBiasFilter] = useState("ALL");
  const [activeSection, setActiveSection] = useState("overview");
  const [scanPolling, setScanPolling] = useState(false);
  const pollRef = useRef(null);

  const fetchStatus = async () => {
    try {
      const res = await axios.get(`${API}/oracle/status`);
      setStatus(res.data);
    } catch (e) {
      console.error("ORACLE status error:", e);
    }
  };

  const fetchScanResults = async () => {
    try {
      const res = await axios.get(`${API}/oracle/scan/results`);
      setScanResults(res.data);
    } catch (e) {
      console.error("ORACLE scan results error:", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchScanStatus = async () => {
    try {
      const res = await axios.get(`${API}/oracle/scan/status`);
      setScanStatus(res.data);
      return res.data;
    } catch (e) {
      return null;
    }
  };

  const triggerFullScan = async () => {
    setScanLoading(true);
    try {
      await axios.get(`${API}/oracle/scan/full`);
      setScanPolling(true);
    } catch (e) {
      console.error("Scan trigger error:", e);
      setScanLoading(false);
    }
  };

  const analyzeSymbol = async () => {
    if (!symbolInput.trim()) return;
    setSymbolLoading(true);
    setSymbolResult(null);
    try {
      const symbol = symbolInput.trim().toUpperCase().replace("/USDT", "").replace("USDT", "");
      const res = await axios.get(`${API}/oracle/bias/${symbol}`);
      setSymbolResult(res.data);
    } catch (e) {
      setSymbolResult({ error: e.response?.data?.detail || "Analysis failed" });
    } finally {
      setSymbolLoading(false);
    }
  };

  const toggleOracle = async () => {
    if (!status) return;
    try {
      const res = await axios.post(`${API}/oracle/toggle?active=${!status.active}`);
      setStatus(prev => ({ ...prev, active: res.data.active }));
    } catch (e) {
      console.error("Toggle error:", e);
    }
  };

  useEffect(() => {
    Promise.all([fetchStatus(), fetchScanResults(), fetchScanStatus()]);
  }, []);

  useEffect(() => {
    if (!scanPolling) return;
    pollRef.current = setInterval(async () => {
      const s = await fetchScanStatus();
      if (s && !s.in_progress) {
        setScanPolling(false);
        setScanLoading(false);
        clearInterval(pollRef.current);
        await fetchScanResults();
        await fetchStatus();
      }
    }, 3000);
    return () => clearInterval(pollRef.current);
  }, [scanPolling]);

  const filteredResults = () => {
    if (!scanResults?.results) return [];
    return scanResults.results.filter(r => {
      const scoreOk = (r.score ?? 0) >= minScore;
      const biasOk = biasFilter === "ALL" || r.bias === biasFilter;
      return scoreOk && biasOk;
    });
  };

  const scoreDistribution = status?.score_distribution || {};

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500 to-purple-700 flex items-center justify-center">
            <Eye className="w-6 h-6 text-white" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-white">ORACLE</h1>
            <p className="text-zinc-400 text-sm">5-Layer Market Intelligence · Never trades</p>
          </div>
        </div>
        <button
          onClick={toggleOracle}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            status?.active ? "bg-green-500/20 text-green-400 hover:bg-green-500/30" : "bg-zinc-700 text-zinc-400 hover:bg-zinc-600"
          }`}
        >
          {status?.active ? <ToggleRight className="w-5 h-5" /> : <ToggleLeft className="w-5 h-5" />}
          {status?.active ? "Active" : "Paused"}
        </button>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Pairs Scanned</p>
            <p className="text-xl font-bold text-white">{scanResults?.total_pairs ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Score ≥70</p>
            <p className="text-xl font-bold text-orange-400">{scoreDistribution?.high ?? "—"}</p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Bullish</p>
            <p className="text-xl font-bold text-green-400">
              {scanResults?.results?.filter(r => r.bias === "BULLISH").length ?? "—"}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-zinc-900/60 border-zinc-800">
          <CardContent className="p-4">
            <p className="text-xs text-zinc-500 mb-1">Bearish</p>
            <p className="text-xl font-bold text-red-400">
              {scanResults?.results?.filter(r => r.bias === "BEARISH").length ?? "—"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Scan Controls */}
      <div className="flex flex-wrap gap-3 items-center">
        <button
          onClick={triggerFullScan}
          disabled={scanLoading}
          className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
        >
          {scanLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
          {scanLoading ? `Scanning... ${scanStatus?.percent ?? 0}%` : "Trigger Full Scan"}
        </button>
        <button
          onClick={() => { fetchStatus(); fetchScanResults(); fetchScanStatus(); }}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800 hover:bg-zinc-700 rounded-lg text-sm font-medium text-white transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Scan Progress */}
      {scanStatus?.in_progress && (
        <Card className="bg-violet-500/10 border-violet-500/30">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-violet-300 text-sm font-medium">Scan in progress</span>
              <span className="text-violet-300 text-sm">{scanStatus.scanned}/{scanStatus.total} pairs · {scanStatus.percent}%</span>
            </div>
            <div className="w-full bg-zinc-800 rounded-full h-2">
              <div className="h-2 rounded-full bg-violet-500 transition-all" style={{ width: `${scanStatus.percent}%` }} />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Symbol Analysis */}
      <Card className="bg-zinc-900/60 border-zinc-800">
        <CardContent className="p-4">
          <h3 className="text-white font-semibold mb-3">Analyze Symbol</h3>
          <div className="flex gap-2">
            <input
              type="text"
              value={symbolInput}
              onChange={e => setSymbolInput(e.target.value)}
              onKeyDown={e => e.key === "Enter" && analyzeSymbol()}
              placeholder="BTC, ETH, SOL..."
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm placeholder-zinc-500 focus:outline-none focus:border-violet-500"
            />
            <button
              onClick={analyzeSymbol}
              disabled={symbolLoading}
              className="flex items-center gap-2 px-4 py-2 bg-violet-600 hover:bg-violet-700 rounded-lg text-sm font-medium text-white transition-colors disabled:opacity-50"
            >
              {symbolLoading ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
              Analyze
            </button>
          </div>
          {symbolResult && (
            <div className="mt-4">
              {symbolResult.error ? (
                <p className="text-red-400 text-sm">{symbolResult.error}</p>
              ) : (
                <div className="bg-zinc-950/50 rounded-lg p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-white font-semibold">{symbolResult.symbol?.replace("/USDT", "")}</span>
                    <BiasTag bias={symbolResult.bias} score={symbolResult.score} />
                  </div>
                  <ConfidenceBar score={symbolResult.score ?? 0} />
                  <p className="text-zinc-400 text-xs">{symbolResult.confidence} confidence · {symbolResult.reason}</p>
                  {symbolResult.layers && (
                    <div className="grid grid-cols-5 gap-2 mt-3">
                      {Object.entries(symbolResult.layers).map(([layer, data]) => (
                        <div key={layer} className="text-center">
                          <p className="text-zinc-500 text-xs capitalize">{layer.replace("_", " ")}</p>
                          <p className="text-white text-sm font-medium">{data?.score ?? data ?? "—"}</p>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Section Tabs */}
      <div className="flex flex-wrap gap-2 border-b border-zinc-800 pb-2">
        {["overview", "opportunities", "all"].map(s => (
          <button
            key={s}
            onClick={() => setActiveSection(s)}
            className={`px-4 py-2 rounded-lg text-sm font-medium capitalize transition-colors ${
              activeSection === s ? "bg-violet-500/20 text-violet-400" : "text-zinc-400 hover:text-white"
            }`}
          >
            {s === "all" ? "All Results" : s}
          </button>
        ))}
      </div>

      {/* Filters */}
      {(activeSection === "opportunities" || activeSection === "all") && (
        <div className="flex flex-wrap gap-3 items-center">
          <div className="flex items-center gap-2">
            <label className="text-zinc-400 text-sm">Min Score:</label>
            <input
              type="number"
              value={minScore}
              onChange={e => setMinScore(Number(e.target.value))}
              min={0} max={100}
              className="w-20 bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-white text-sm"
            />
          </div>
          <div className="flex gap-1">
            {["ALL", "BULLISH", "BEARISH", "NEUTRAL"].map(b => (
              <button
                key={b}
                onClick={() => setBiasFilter(b)}
                className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                  biasFilter === b
                    ? b === "BULLISH" ? "bg-green-500/30 text-green-400" : b === "BEARISH" ? "bg-red-500/30 text-red-400" : "bg-violet-500/20 text-violet-400"
                    : "bg-zinc-800 text-zinc-400 hover:text-white"
                }`}
              >
                {b}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Overview */}
      {activeSection === "overview" && (
        <div className="space-y-4">
          <h3 className="text-white font-semibold">Last Scan Summary</h3>
          {!scanResults?.results?.length ? (
            <p className="text-zinc-500 text-sm">No scan results yet. Trigger a full scan to analyze all MEXC pairs.</p>
          ) : (
            <>
              <p className="text-zinc-400 text-sm">
                Last scan: {scanResults.scan_time ? new Date(scanResults.scan_time).toLocaleString() : "—"} · {scanResults.total_pairs} pairs
              </p>
              <div className="grid md:grid-cols-2 gap-4">
                {/* Top Bullish */}
                <Card className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingUp className="w-4 h-4 text-green-400" />
                      <span className="text-white font-medium">Top Bullish</span>
                    </div>
                    <div className="space-y-2">
                      {scanResults.results.filter(r => r.bias === "BULLISH").slice(0, 5).map((r, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <span className="text-zinc-300 text-sm">{r.symbol?.replace("/USDT", "")}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-24 bg-zinc-800 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-green-500" style={{ width: `${r.score}%` }} />
                            </div>
                            <span className="text-green-400 text-xs w-8 text-right">{r.score}</span>
                          </div>
                        </div>
                      ))}
                      {!scanResults.results.filter(r => r.bias === "BULLISH").length && (
                        <p className="text-zinc-500 text-sm">None found</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
                {/* Top Bearish */}
                <Card className="bg-zinc-900/60 border-zinc-800">
                  <CardContent className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <TrendingDown className="w-4 h-4 text-red-400" />
                      <span className="text-white font-medium">Top Bearish</span>
                    </div>
                    <div className="space-y-2">
                      {scanResults.results.filter(r => r.bias === "BEARISH").slice(0, 5).map((r, i) => (
                        <div key={i} className="flex items-center justify-between">
                          <span className="text-zinc-300 text-sm">{r.symbol?.replace("/USDT", "")}</span>
                          <div className="flex items-center gap-2">
                            <div className="w-24 bg-zinc-800 rounded-full h-1.5">
                              <div className="h-1.5 rounded-full bg-red-500" style={{ width: `${r.score}%` }} />
                            </div>
                            <span className="text-red-400 text-xs w-8 text-right">{r.score}</span>
                          </div>
                        </div>
                      ))}
                      {!scanResults.results.filter(r => r.bias === "BEARISH").length && (
                        <p className="text-zinc-500 text-sm">None found</p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </div>
            </>
          )}
        </div>
      )}

      {/* Opportunities / All */}
      {(activeSection === "opportunities" || activeSection === "all") && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-white font-semibold">
              {activeSection === "opportunities" ? "Opportunities" : "All Results"}
            </h3>
            <span className="text-zinc-400 text-sm">{filteredResults().length} pairs</span>
          </div>
          {loading ? (
            <div className="flex justify-center py-8">
              <RefreshCw className="w-6 h-6 text-orange-400 animate-spin" />
            </div>
          ) : !filteredResults().length ? (
            <p className="text-zinc-500 text-sm">No pairs match the current filters. Lower the min score or trigger a scan.</p>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-3">
              {filteredResults().map((r, i) => (
                <Card key={i} className="bg-zinc-900/60 border-zinc-800 hover:border-zinc-700 transition-colors">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-white font-medium">{r.symbol?.replace("/USDT", "")}</span>
                      <BiasTag bias={r.bias} score={r.score} />
                    </div>
                    <ConfidenceBar score={r.score ?? 0} />
                    <p className="text-zinc-500 text-xs mt-2">{r.confidence} · {r.reason?.substring(0, 60)}</p>
                    {r.layers && (
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {Object.entries(r.layers).map(([layer, data]) => (
                          <span key={layer} className="text-xs text-zinc-500 bg-zinc-800 rounded px-1.5 py-0.5">
                            {layer.replace("_", "").substring(0, 4).toUpperCase()}: {data?.score ?? data}
                          </span>
                        ))}
                      </div>
                    )}
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
