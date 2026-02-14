import React, { useState, useEffect } from 'react';
import { 
  X, TrendingUp, TrendingDown, Activity, Zap, Target, AlertCircle,
  RefreshCw, ArrowUpRight, ArrowDownRight, BarChart2, Gauge, Clock,
  DollarSign, Percent, Eye, LineChart
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function QuickScanModal({ coin, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (coin) {
      fetchScan();
    }
  }, [coin]);

  const fetchScan = async () => {
    setLoading(true);
    setError('');
    try {
      const [scanRes, taRes] = await Promise.all([
        fetch(`${API_URL}/api/scan/${coin}USDT`),
        fetch(`${API_URL}/api/ta/${coin}USDT?timeframe=1h`)
      ]);
      
      const scanData = await scanRes.json();
      const taData = await taRes.json();
      
      setData({ scan: scanData, ta: taData });
    } catch (err) {
      setError('Failed to fetch data');
      console.error(err);
    }
    setLoading(false);
  };

  if (!coin) return null;

  const scan = data?.scan || {};
  const ta = data?.ta || {};
  const indicators = ta.indicators || {};
  
  const price = scan.price || ta.price || 0;
  const change24h = scan.price_change_24h || 0;
  const volume = scan.volume_24h || 0;
  const bias = scan.overall_bias || 'neutral';
  
  const rsi = indicators.rsi || 50;
  const macd = indicators.macd_histogram || 0;
  const trend = scan.technical?.trend || indicators.trend || 'neutral';

  // Determine signal strength
  const getSignalStrength = () => {
    if (!data) return { strength: 0, text: 'Loading...', color: 'zinc' };
    
    let score = 0;
    
    // RSI contribution
    if (rsi < 30) score += 2; // Oversold = bullish
    else if (rsi > 70) score -= 2; // Overbought = bearish
    else if (rsi < 45) score += 1;
    else if (rsi > 55) score -= 1;
    
    // MACD contribution
    if (macd > 0) score += 1;
    else if (macd < 0) score -= 1;
    
    // Trend contribution
    if (trend === 'bullish' || trend === 'uptrend') score += 2;
    else if (trend === 'bearish' || trend === 'downtrend') score -= 2;
    
    // Bias contribution
    if (bias === 'bullish') score += 1;
    else if (bias === 'bearish') score -= 1;
    
    if (score >= 4) return { strength: score, text: 'Strong Buy', color: 'green' };
    if (score >= 2) return { strength: score, text: 'Buy', color: 'green' };
    if (score <= -4) return { strength: score, text: 'Strong Sell', color: 'red' };
    if (score <= -2) return { strength: score, text: 'Sell', color: 'red' };
    return { strength: score, text: 'Neutral', color: 'yellow' };
  };

  const signal = getSignalStrength();

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-zinc-700 bg-zinc-800/50">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-orange-500/20 flex items-center justify-center">
              <BarChart2 className="w-5 h-5 text-orange-400" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-white">{coin}/USDT</h2>
              <p className="text-sm text-zinc-400">Quick Market Scan</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchScan}
              disabled={loading}
              className="p-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-white transition-colors"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={onClose}
              className="p-2 rounded-lg bg-zinc-700 hover:bg-zinc-600 text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content */}
        <div className="p-6 overflow-y-auto max-h-[calc(90vh-80px)]">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
            </div>
          ) : error ? (
            <div className="text-center py-12">
              <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
              <p className="text-red-400">{error}</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Price & Signal */}
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-zinc-800/50 rounded-xl p-4 border border-zinc-700/50">
                  <p className="text-zinc-400 text-sm mb-1">Current Price</p>
                  <p className="text-2xl font-bold text-white">${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</p>
                  <div className={`flex items-center gap-1 mt-1 ${change24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {change24h >= 0 ? <ArrowUpRight className="w-4 h-4" /> : <ArrowDownRight className="w-4 h-4" />}
                    <span className="text-sm font-medium">{change24h >= 0 ? '+' : ''}{change24h.toFixed(2)}% (24h)</span>
                  </div>
                </div>
                
                <div className={`rounded-xl p-4 border ${
                  signal.color === 'green' ? 'bg-green-500/10 border-green-500/30' :
                  signal.color === 'red' ? 'bg-red-500/10 border-red-500/30' :
                  'bg-yellow-500/10 border-yellow-500/30'
                }`}>
                  <p className="text-zinc-400 text-sm mb-1">Signal</p>
                  <p className={`text-2xl font-bold ${
                    signal.color === 'green' ? 'text-green-400' :
                    signal.color === 'red' ? 'text-red-400' :
                    'text-yellow-400'
                  }`}>{signal.text}</p>
                  <p className="text-sm text-zinc-400 mt-1">Score: {signal.strength}</p>
                </div>
              </div>

              {/* Key Indicators */}
              <div className="grid grid-cols-3 gap-3">
                <IndicatorCard
                  icon={Gauge}
                  label="RSI (14)"
                  value={rsi.toFixed(1)}
                  status={rsi < 30 ? 'Oversold' : rsi > 70 ? 'Overbought' : 'Neutral'}
                  color={rsi < 30 ? 'green' : rsi > 70 ? 'red' : 'zinc'}
                />
                <IndicatorCard
                  icon={LineChart}
                  label="MACD"
                  value={macd > 0 ? 'Bullish' : macd < 0 ? 'Bearish' : 'Flat'}
                  status={macd.toFixed(4)}
                  color={macd > 0 ? 'green' : macd < 0 ? 'red' : 'zinc'}
                />
                <IndicatorCard
                  icon={TrendingUp}
                  label="Trend"
                  value={trend.charAt(0).toUpperCase() + trend.slice(1)}
                  status={bias.toUpperCase()}
                  color={trend === 'bullish' || trend === 'uptrend' ? 'green' : trend === 'bearish' || trend === 'downtrend' ? 'red' : 'zinc'}
                />
              </div>

              {/* Technical Details */}
              <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden">
                <div className="px-4 py-3 border-b border-zinc-700/50 bg-zinc-800/30">
                  <h3 className="text-white font-semibold flex items-center gap-2">
                    <Activity className="w-4 h-4 text-orange-400" />
                    Technical Details
                  </h3>
                </div>
                <div className="p-4 grid grid-cols-2 gap-4">
                  <DetailRow label="EMA 20" value={`$${(indicators.ema_20 || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <DetailRow label="EMA 50" value={`$${(indicators.ema_50 || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <DetailRow label="BB Upper" value={`$${(indicators.bb_upper || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <DetailRow label="BB Lower" value={`$${(indicators.bb_lower || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`} />
                  <DetailRow label="ATR" value={(indicators.atr || 0).toFixed(2)} />
                  <DetailRow label="24h Volume" value={`$${(volume / 1000000).toFixed(2)}M`} />
                </div>
              </div>

              {/* Signals from scan */}
              {scan.signals && scan.signals.length > 0 && (
                <div className="bg-zinc-800/50 rounded-xl border border-zinc-700/50 overflow-hidden">
                  <div className="px-4 py-3 border-b border-zinc-700/50 bg-zinc-800/30">
                    <h3 className="text-white font-semibold flex items-center gap-2">
                      <Zap className="w-4 h-4 text-orange-400" />
                      Active Signals
                    </h3>
                  </div>
                  <div className="p-4 space-y-2">
                    {scan.signals.slice(0, 5).map((sig, i) => (
                      <div key={i} className="flex items-center gap-3 p-2 rounded-lg bg-zinc-900/50">
                        <div className={`w-2 h-2 rounded-full ${
                          sig[1]?.toLowerCase().includes('bull') || sig[1]?.toLowerCase().includes('buy') ? 'bg-green-400' :
                          sig[1]?.toLowerCase().includes('bear') || sig[1]?.toLowerCase().includes('sell') ? 'bg-red-400' :
                          'bg-yellow-400'
                        }`} />
                        <span className="text-zinc-300 text-sm">{sig[0]}: {sig[1]}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Indicator Card Component
function IndicatorCard({ icon: Icon, label, value, status, color }) {
  const colorClasses = {
    green: 'text-green-400',
    red: 'text-red-400',
    yellow: 'text-yellow-400',
    zinc: 'text-zinc-400'
  };

  return (
    <div className="bg-zinc-800/50 rounded-xl p-3 border border-zinc-700/50">
      <div className="flex items-center gap-2 mb-2">
        <Icon className="w-4 h-4 text-orange-400" />
        <span className="text-xs text-zinc-400">{label}</span>
      </div>
      <p className={`text-lg font-bold ${colorClasses[color]}`}>{value}</p>
      <p className="text-xs text-zinc-500 mt-0.5">{status}</p>
    </div>
  );
}

// Detail Row Component
function DetailRow({ label, value }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-zinc-400">{label}</span>
      <span className="text-sm text-white font-mono">{value}</span>
    </div>
  );
}
