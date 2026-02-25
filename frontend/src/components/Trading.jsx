import React, { useState, useEffect, useCallback } from 'react';
import { 
  Activity, TrendingUp, TrendingDown, DollarSign, Target, 
  Play, Pause, RefreshCw, X, Settings2, Zap, Radio, BarChart3,
  AlertTriangle, Shield, Flame, Clock, ChevronRight, Percent,
  ArrowUpRight, ArrowDownRight, Crosshair, LineChart, CandlestickChart
} from 'lucide-react';
import TradingChart from './TradingChart';
import PositionCard from './PositionCard';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Coin logo mapping
const COIN_LOGOS = {
  BTC: 'https://assets.coingecko.com/coins/images/1/small/bitcoin.png',
  ETH: 'https://assets.coingecko.com/coins/images/279/small/ethereum.png',
  SOL: 'https://assets.coingecko.com/coins/images/4128/small/solana.png',
  AVAX: 'https://assets.coingecko.com/coins/images/12559/small/Avalanche_Circle_RedWhite_Trans.png',
  BNB: 'https://assets.coingecko.com/coins/images/825/small/bnb-icon2_2x.png',
  XRP: 'https://assets.coingecko.com/coins/images/44/small/xrp-symbol-white-128.png',
  ADA: 'https://assets.coingecko.com/coins/images/975/small/cardano.png',
  DOGE: 'https://assets.coingecko.com/coins/images/5/small/dogecoin.png',
  DOT: 'https://assets.coingecko.com/coins/images/12171/small/polkadot.png',
  MATIC: 'https://assets.coingecko.com/coins/images/4713/small/matic-token-icon.png',
  LINK: 'https://assets.coingecko.com/coins/images/877/small/chainlink-new-logo.png',
  UNI: 'https://assets.coingecko.com/coins/images/12504/small/uniswap-uni.png',
  LTC: 'https://assets.coingecko.com/coins/images/2/small/litecoin.png',
  ATOM: 'https://assets.coingecko.com/coins/images/1481/small/cosmos_hub.png',
  ARB: 'https://assets.coingecko.com/coins/images/16547/small/photo_2023-03-29_21.47.00.jpeg',
  OP: 'https://assets.coingecko.com/coins/images/25244/small/Optimism.png',
  INJ: 'https://assets.coingecko.com/coins/images/12882/small/Secondary_Symbol.png',
  SUI: 'https://assets.coingecko.com/coins/images/26375/small/sui_asset.jpeg',
  APT: 'https://assets.coingecko.com/coins/images/26455/small/aptos_round.png',
  NEAR: 'https://assets.coingecko.com/coins/images/10365/small/near.jpg',
};

// Professional Position Card Modal Component
const PositionCardModal = ({ position, onClose, onCloseTrade, onSetTrailing }) => {
  const [partialCloseAmount, setPartialCloseAmount] = useState(100);
  const [showTrailingInput, setShowTrailingInput] = useState(false);
  const [trailingPct, setTrailingPct] = useState(5);
  
  if (!position) return null;
  
  const symbol = position.symbol?.replace('/USDT', '') || '';
  const isLong = position.direction === 'LONG';
  const pnlPct = (position.pnl_pct || 0) * (position.leverage || 10);
  const pnlUsd = (pnlPct / 100) * (position.position_size || 1000);
  const isProfitable = pnlPct >= 0;
  
  // Calculate risk metrics
  const entryPrice = position.entry_price || 0;
  const currentPrice = position.current_price || 0;
  const stopPrice = position.stop_price || 0;
  const targetPrice = position.target_price || 0;
  const leverage = position.leverage || 10;
  const margin = (position.position_size || 1000) / leverage;
  
  // Liquidation price estimation (simplified)
  const liqDistance = isLong 
    ? ((currentPrice - stopPrice) / currentPrice * 100)
    : ((stopPrice - currentPrice) / currentPrice * 100);
  
  // Progress to target/stop
  const totalRange = Math.abs(targetPrice - stopPrice);
  const currentProgress = isLong 
    ? ((currentPrice - stopPrice) / totalRange * 100)
    : ((stopPrice - currentPrice) / totalRange * 100);
  
  // Risk level
  const riskLevel = liqDistance < 2 ? 'HIGH' : liqDistance < 5 ? 'MEDIUM' : 'LOW';
  const riskColor = riskLevel === 'HIGH' ? 'red' : riskLevel === 'MEDIUM' ? 'amber' : 'green';
  
  // Time in position
  const timeHeld = position.entry_time 
    ? Math.floor((new Date() - new Date(position.entry_time)) / (1000 * 60 * 60))
    : 0;
  
  // ROI threshold for fire animation
  const isOnFire = Math.abs(pnlPct) > 50;

  return (
    <div 
      className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center z-50 p-4" 
      onClick={onClose}
    >
      <div 
        className="w-full max-w-lg overflow-hidden rounded-2xl shadow-2xl"
        onClick={(e) => e.stopPropagation()}
        style={{
          background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f0f23 100%)',
          border: `1px solid ${isLong ? 'rgba(34, 197, 94, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
        }}
      >
        {/* Header - Exchange Style */}
        <div className="relative px-5 py-4 border-b border-zinc-800/50">
          {/* Live indicator */}
          <div className="absolute top-3 right-3 flex items-center gap-1.5">
            <span className="relative flex h-2 w-2">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isLong ? 'bg-green-400' : 'bg-red-400'}`}></span>
              <span className={`relative inline-flex rounded-full h-2 w-2 ${isLong ? 'bg-green-500' : 'bg-red-500'}`}></span>
            </span>
            <span className="text-xs text-zinc-400">LIVE</span>
          </div>
          
          <div className="flex items-center gap-3">
            {/* Coin Logo */}
            <div className="relative">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${isLong ? 'bg-green-500/10' : 'bg-red-500/10'} border ${isLong ? 'border-green-500/30' : 'border-red-500/30'}`}>
                {COIN_LOGOS[symbol] ? (
                  <img src={COIN_LOGOS[symbol]} alt={symbol} className="w-8 h-8 rounded-full" />
                ) : (
                  <span className="text-lg font-bold text-white">{symbol.slice(0, 2)}</span>
                )}
              </div>
              {/* Direction badge */}
              <div className={`absolute -bottom-1 -right-1 px-1.5 py-0.5 rounded text-[10px] font-bold ${isLong ? 'bg-green-500 text-white' : 'bg-red-500 text-white'}`}>
                {isLong ? 'L' : 'S'}
              </div>
            </div>
            
            {/* Symbol & Info */}
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="text-xl font-bold text-white">{symbol}/USDT</h3>
                <span className={`px-2 py-0.5 rounded text-xs font-semibold ${isLong ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                  {position.direction}
                </span>
                <span className="px-2 py-0.5 rounded text-xs font-semibold bg-orange-500/20 text-orange-400">
                  {leverage}x
                </span>
              </div>
              <div className="flex items-center gap-2 mt-0.5 text-xs text-zinc-400">
                <span className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {timeHeld}h
                </span>
                <span>•</span>
                <span>{position.timeframe}</span>
                <span>•</span>
                <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                  position.trade_type === 'SCALP' ? 'bg-purple-500/20 text-purple-400' :
                  position.trade_type === 'DAY' ? 'bg-blue-500/20 text-blue-400' :
                  'bg-amber-500/20 text-amber-400'
                }`}>
                  {position.trade_type || 'SWING'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* PnL Section - Large with Glow */}
        <div className={`px-5 py-4 ${isProfitable ? 'bg-green-500/5' : 'bg-red-500/5'}`}>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-xs text-zinc-400 mb-1">Unrealized PnL</p>
              <div className="flex items-baseline gap-2">
                <span 
                  className={`text-3xl font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}
                  style={{
                    textShadow: isProfitable 
                      ? '0 0 20px rgba(34, 197, 94, 0.5)' 
                      : '0 0 20px rgba(239, 68, 68, 0.5)'
                  }}
                >
                  {isProfitable ? '+' : ''}{pnlPct.toFixed(2)}%
                </span>
                {isOnFire && (
                  <Flame className={`w-6 h-6 ${isProfitable ? 'text-green-400' : 'text-red-400'} animate-pulse`} />
                )}
              </div>
              <p className={`text-lg font-semibold ${isProfitable ? 'text-green-400/80' : 'text-red-400/80'}`}>
                {isProfitable ? '+' : ''}${pnlUsd.toFixed(2)} USDT
              </p>
            </div>
            
            {/* ROI Badge */}
            <div className={`px-4 py-3 rounded-xl ${isProfitable ? 'bg-green-500/10 border border-green-500/30' : 'bg-red-500/10 border border-red-500/30'}`}>
              <p className="text-xs text-zinc-400 text-center mb-1">ROI</p>
              <p className={`text-2xl font-bold text-center ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                {isProfitable ? '+' : ''}{pnlPct.toFixed(1)}%
              </p>
            </div>
          </div>
          
          {/* Progress to Target */}
          <div className="mt-4">
            <div className="flex justify-between text-xs mb-1">
              <span className="text-red-400">SL ${stopPrice?.toLocaleString()}</span>
              <span className="text-zinc-400">Progress</span>
              <span className="text-green-400">TP ${targetPrice?.toLocaleString()}</span>
            </div>
            <div className="h-2 bg-zinc-800 rounded-full overflow-hidden relative">
              <div 
                className={`h-full rounded-full transition-all duration-500 ${isProfitable ? 'bg-gradient-to-r from-green-600 to-green-400' : 'bg-gradient-to-r from-red-600 to-red-400'}`}
                style={{ width: `${Math.min(Math.max(currentProgress, 0), 100)}%` }}
              />
              {/* Current position marker */}
              <div 
                className="absolute top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full border-2 border-zinc-900 shadow-lg"
                style={{ left: `${Math.min(Math.max(currentProgress, 2), 98)}%`, transform: 'translate(-50%, -50%)' }}
              />
            </div>
          </div>
        </div>

        {/* Key Stats Bar */}
        <div className="grid grid-cols-4 border-y border-zinc-800/50">
          <div className="px-3 py-3 text-center border-r border-zinc-800/50">
            <p className="text-[10px] text-zinc-500 uppercase">Entry</p>
            <p className="text-sm font-semibold text-white">${entryPrice?.toLocaleString()}</p>
          </div>
          <div className="px-3 py-3 text-center border-r border-zinc-800/50">
            <p className="text-[10px] text-zinc-500 uppercase">Mark</p>
            <p className={`text-sm font-semibold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
              ${currentPrice?.toLocaleString()}
            </p>
          </div>
          <div className="px-3 py-3 text-center border-r border-zinc-800/50">
            <p className="text-[10px] text-zinc-500 uppercase">Size</p>
            <p className="text-sm font-semibold text-white">${(position.position_size || 1000).toLocaleString()}</p>
          </div>
          <div className="px-3 py-3 text-center">
            <p className="text-[10px] text-zinc-500 uppercase">Margin</p>
            <p className="text-sm font-semibold text-cyan-400">${margin.toFixed(2)}</p>
          </div>
        </div>

        {/* Risk Metrics Panel */}
        <div className="px-5 py-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-zinc-400">Risk Assessment</span>
            <span className={`px-2 py-0.5 rounded text-xs font-bold flex items-center gap-1
              ${riskLevel === 'HIGH' ? 'bg-red-500/20 text-red-400' : 
                riskLevel === 'MEDIUM' ? 'bg-amber-500/20 text-amber-400' : 
                'bg-green-500/20 text-green-400'}`}
            >
              {riskLevel === 'HIGH' && <AlertTriangle className="w-3 h-3" />}
              {riskLevel === 'LOW' && <Shield className="w-3 h-3" />}
              {riskLevel} RISK
            </span>
          </div>
          
          {/* Margin Ratio Bar */}
          <div>
            <div className="flex justify-between text-xs mb-1">
              <span className="text-zinc-400">Margin Ratio</span>
              <span className="text-white">{(100 / leverage).toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full ${
                  100/leverage > 10 ? 'bg-green-500' : 
                  100/leverage > 5 ? 'bg-amber-500' : 'bg-red-500'
                }`}
                style={{ width: `${Math.min(100/leverage * 5, 100)}%` }}
              />
            </div>
          </div>
          
          {/* Distance to Stop */}
          <div className="flex justify-between items-center">
            <span className="text-xs text-zinc-400">Distance to Stop</span>
            <span className={`text-sm font-semibold ${liqDistance > 5 ? 'text-green-400' : liqDistance > 2 ? 'text-amber-400' : 'text-red-400'}`}>
              {liqDistance.toFixed(2)}%
            </span>
          </div>
          
          {/* Confidence */}
          <div className="flex justify-between items-center">
            <span className="text-xs text-zinc-400">Signal Confidence</span>
            <div className="flex items-center gap-2">
              <div className="w-20 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                <div 
                  className="h-full rounded-full bg-gradient-to-r from-cyan-500 to-blue-500"
                  style={{ width: `${position.confidence || 85}%` }}
                />
              </div>
              <span className="text-sm font-semibold text-cyan-400">{position.confidence || 85}%</span>
            </div>
          </div>
        </div>

        {/* Price Ladder Visualization */}
        <div className="px-5 py-3 border-t border-zinc-800/50">
          <p className="text-xs text-zinc-400 mb-3">Price Levels</p>
          <div className="relative h-24 flex items-center">
            {/* Vertical line */}
            <div className="absolute left-8 top-0 bottom-0 w-0.5 bg-zinc-700" />
            
            {/* TP Level */}
            <div className="absolute left-0 top-0 flex items-center gap-2 w-full">
              <div className="w-4 h-4 rounded-full bg-green-500 flex items-center justify-center">
                <Target className="w-2.5 h-2.5 text-white" />
              </div>
              <div className="h-0.5 w-4 bg-green-500" />
              <div className="flex-1 flex justify-between items-center">
                <span className="text-xs text-green-400">Take Profit</span>
                <span className="text-sm font-semibold text-green-400">${targetPrice?.toLocaleString()}</span>
              </div>
            </div>
            
            {/* Current Price */}
            <div className="absolute left-0 top-1/2 -translate-y-1/2 flex items-center gap-2 w-full">
              <div className={`w-4 h-4 rounded-full ${isProfitable ? 'bg-green-500' : 'bg-red-500'} flex items-center justify-center animate-pulse`}>
                <Crosshair className="w-2.5 h-2.5 text-white" />
              </div>
              <div className={`h-0.5 w-4 ${isProfitable ? 'bg-green-500' : 'bg-red-500'}`} />
              <div className="flex-1 flex justify-between items-center">
                <span className="text-xs text-white">Current</span>
                <span className={`text-sm font-bold ${isProfitable ? 'text-green-400' : 'text-red-400'}`}>
                  ${currentPrice?.toLocaleString()}
                </span>
              </div>
            </div>
            
            {/* Entry Level */}
            <div className="absolute left-0 bottom-6 flex items-center gap-2 w-full">
              <div className="w-4 h-4 rounded-full bg-blue-500 flex items-center justify-center">
                <ArrowUpRight className="w-2.5 h-2.5 text-white" />
              </div>
              <div className="h-0.5 w-4 bg-blue-500" />
              <div className="flex-1 flex justify-between items-center">
                <span className="text-xs text-blue-400">Entry</span>
                <span className="text-sm font-semibold text-blue-400">${entryPrice?.toLocaleString()}</span>
              </div>
            </div>
            
            {/* SL Level */}
            <div className="absolute left-0 bottom-0 flex items-center gap-2 w-full">
              <div className="w-4 h-4 rounded-full bg-red-500 flex items-center justify-center">
                <X className="w-2.5 h-2.5 text-white" />
              </div>
              <div className="h-0.5 w-4 bg-red-500" />
              <div className="flex-1 flex justify-between items-center">
                <span className="text-xs text-red-400">Stop Loss</span>
                <span className="text-sm font-semibold text-red-400">${stopPrice?.toLocaleString()}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Confirmations */}
        {position.confirmations && position.confirmations.length > 0 && (
          <div className="px-5 py-3 border-t border-zinc-800/50">
            <p className="text-xs text-zinc-400 mb-2">Signal Confirmations</p>
            <div className="flex flex-wrap gap-1.5">
              {position.confirmations.slice(0, 5).map((conf, idx) => (
                <span key={idx} className="px-2 py-1 bg-cyan-500/10 text-cyan-400 rounded text-xs border border-cyan-500/20">
                  ✓ {conf}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Quick Actions */}
        <div className="px-5 py-4 border-t border-zinc-800/50 space-y-3">
          {/* Partial Close */}
          <div>
            <p className="text-xs text-zinc-400 mb-2">Quick Close</p>
            <div className="flex gap-2">
              {[25, 50, 75, 100].map((pct) => (
                <button
                  key={pct}
                  onClick={() => setPartialCloseAmount(pct)}
                  className={`flex-1 py-2 rounded-lg text-sm font-semibold transition-all ${
                    partialCloseAmount === pct 
                      ? 'bg-red-500 text-white' 
                      : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'
                  }`}
                >
                  {pct}%
                </button>
              ))}
            </div>
          </div>
          
          {/* Trailing Stop */}
          {!showTrailingInput ? (
            <button
              onClick={() => setShowTrailingInput(true)}
              className="w-full py-2.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 rounded-lg text-sm font-semibold hover:bg-amber-500/20 transition-all flex items-center justify-center gap-2"
            >
              <LineChart className="w-4 h-4" />
              Set Trailing Stop
            </button>
          ) : (
            <div className="flex gap-2">
              <input
                type="number"
                value={trailingPct}
                onChange={(e) => setTrailingPct(Number(e.target.value))}
                className="flex-1 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-white text-sm"
                placeholder="Trail %"
              />
              <button
                onClick={() => {
                  onSetTrailing && onSetTrailing(position.symbol, trailingPct);
                  setShowTrailingInput(false);
                }}
                className="px-4 py-2 bg-amber-500 text-white rounded-lg text-sm font-semibold"
              >
                Set {trailingPct}%
              </button>
              <button
                onClick={() => setShowTrailingInput(false)}
                className="px-3 py-2 bg-zinc-700 text-zinc-400 rounded-lg"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}
          
          {/* Main Actions */}
          <div className="flex gap-2">
            <button
              onClick={() => {
                onCloseTrade && onCloseTrade(position.symbol, partialCloseAmount);
                if (partialCloseAmount === 100) onClose();
              }}
              data-testid="modal-close-position-btn"
              className="flex-1 py-3 bg-gradient-to-r from-red-600 to-red-500 hover:from-red-500 hover:to-red-400 text-white rounded-xl font-semibold transition-all shadow-lg shadow-red-500/20"
            >
              Close {partialCloseAmount}% Position
            </button>
            <button
              onClick={onClose}
              data-testid="modal-back-btn"
              className="px-5 py-3 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl font-semibold transition-all"
            >
              Back
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

// Simple PnL Chart Component
const PnLChart = ({ data }) => {
  if (!data || data.length === 0) {
    return (
      <div className="h-32 flex items-center justify-center text-zinc-500 text-sm">
        No trade history yet
      </div>
    );
  }

  const maxPnl = Math.max(...data.map(d => d.cumulative_pnl), 0);
  const minPnl = Math.min(...data.map(d => d.cumulative_pnl), 0);
  const range = Math.max(maxPnl - minPnl, 1);
  const height = 120;
  const width = 100;

  const points = data.map((d, i) => {
    const x = (i / (data.length - 1 || 1)) * width;
    const y = height - ((d.cumulative_pnl - minPnl) / range) * height;
    return `${x},${y}`;
  }).join(' ');

  const isPositive = data[data.length - 1]?.cumulative_pnl >= 0;

  return (
    <div className="relative h-32">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full h-full" preserveAspectRatio="none">
        {/* Zero line */}
        <line 
          x1="0" 
          y1={height - ((0 - minPnl) / range) * height} 
          x2={width} 
          y2={height - ((0 - minPnl) / range) * height} 
          stroke="#52525b" 
          strokeWidth="0.5" 
          strokeDasharray="2,2"
        />
        {/* PnL line */}
        <polyline
          fill="none"
          stroke={isPositive ? "#22c55e" : "#ef4444"}
          strokeWidth="2"
          points={points}
        />
        {/* Area fill */}
        <polygon
          fill={isPositive ? "rgba(34, 197, 94, 0.1)" : "rgba(239, 68, 68, 0.1)"}
          points={`0,${height} ${points} ${width},${height}`}
        />
      </svg>
      {/* Labels */}
      <div className="absolute top-0 right-0 text-xs text-zinc-500">
        {maxPnl > 0 && `+${maxPnl.toFixed(1)}%`}
      </div>
      <div className="absolute bottom-0 right-0 text-xs text-zinc-500">
        {minPnl < 0 && `${minPnl.toFixed(1)}%`}
      </div>
    </div>
  );
};

export default function Trading() {
  const [stats, setStats] = useState(null);
  const [livePositions, setLivePositions] = useState([]);
  const [closedTrades, setClosedTrades] = useState([]);
  const [opportunities, setOpportunities] = useState([]);
  const [pnlHistory, setPnlHistory] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('positions');
  const [confidence, setConfidence] = useState(70);
  const [selectedPosition, setSelectedPosition] = useState(null);
  const [showPositionModal, setShowPositionModal] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      // Fetch critical data first (fast endpoints)
      const [statsRes, liveRes, closedRes, historyRes] = await Promise.all([
        fetch(`${API_URL}/api/trading/v2/stats`),
        fetch(`${API_URL}/api/trading/v2/live-positions`),
        fetch(`${API_URL}/api/trading/v2/closed`),
        fetch(`${API_URL}/api/trading/v2/pnl-history`)
      ]);
      
      const statsData = await statsRes.json();
      const liveData = await liveRes.json();
      const closedData = await closedRes.json();
      const historyData = await historyRes.json();
      
      // Update state with critical data immediately
      setStats(statsData);
      setLivePositions(liveData.positions || []);
      setClosedTrades(closedData.closed_trades || []);
      setPnlHistory(historyData.history || []);
      setConfidence(statsData.min_confidence || 70);
      setLoading(false);
      
      // Fetch opportunities in background (slow endpoint - can take 30-50s)
      fetch(`${API_URL}/api/trading/opportunities`)
        .then(res => res.json())
        .then(oppsData => {
          setOpportunities(Array.isArray(oppsData) ? oppsData : []);
        })
        .catch(() => {
          setOpportunities([]);
        });
        
    } catch (err) {
      console.error('Failed to fetch trading data:', err);
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000); // Refresh every 15s for live data
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleTrading = async () => {
    try {
      const newState = !stats?.active;
      await fetch(`${API_URL}/api/trading/toggle?active=${newState}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Toggle failed:', err);
    }
  };

  const updateConfidence = async (val) => {
    try {
      await fetch(`${API_URL}/api/trading/v2/confidence?min_conf=${val}`, { method: 'POST' });
      setConfidence(val);
    } catch (err) {
      console.error('Update confidence failed:', err);
    }
  };

  const closeTrade = async (symbol, percentage = 100) => {
    try {
      const cleanSymbol = symbol.replace('/USDT', '');
      await fetch(`${API_URL}/api/trading/v2/close/${cleanSymbol}`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ percentage })
      });
      fetchData();
    } catch (err) {
      console.error('Close trade failed:', err);
    }
  };

  const setTrailingStop = async (symbol, trailPct) => {
    try {
      const cleanSymbol = symbol.replace('/USDT', '');
      await fetch(`${API_URL}/api/trading/v2/trail/${cleanSymbol}`, { 
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trail_pct: trailPct })
      });
      fetchData();
    } catch (err) {
      console.error('Set trailing stop failed:', err);
    }
  };

  // Calculate total live PnL
  const totalLivePnl = livePositions.reduce((sum, p) => sum + (p.pnl_pct || 0), 0);

  return (
    <div className="space-y-3 sm:space-y-4 md:space-y-6" data-testid="trading-page">
      {/* Live Data Banner - Mobile Compact */}
      <div className="flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 glass-card border-emerald-500/20">
        <div className="relative">
          <Radio className="w-3 sm:w-4 h-3 sm:h-4 text-emerald-400" />
          <span className="absolute -top-0.5 -right-0.5 w-1.5 sm:w-2 h-1.5 sm:h-2 bg-emerald-400 rounded-full animate-ping" />
        </div>
        <span className="text-emerald-400 text-xs sm:text-sm font-medium">Live MEXC</span>
        <span className="text-zinc-500 text-[10px] sm:text-xs ml-auto">Paper Mode</span>
      </div>

      {/* Header Stats - Mobile Grid */}
      <div className="grid grid-cols-3 sm:grid-cols-3 md:grid-cols-5 gap-2 sm:gap-3">
        <div className="glass-card-hover p-2.5 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Status</p>
              <p className={`text-sm sm:text-xl font-display font-bold ${stats?.active ? 'text-emerald-400' : 'text-rose-400'}`}>
                {stats?.active ? 'ON' : 'OFF'}
              </p>
            </div>
            <button 
              onClick={toggleTrading}
              data-testid="toggle-trading-btn"
              className={`p-1.5 sm:p-2.5 rounded-lg sm:rounded-xl transition-all touch-target ${stats?.active ? 'bg-emerald-500/20 text-emerald-400 hover:bg-emerald-500/30 glow-green' : 'bg-rose-500/20 text-rose-400 hover:bg-rose-500/30 glow-red'}`}
            >
              {stats?.active ? <Pause className="w-4 sm:w-5 h-4 sm:h-5" /> : <Play className="w-4 sm:w-5 h-4 sm:h-5" />}
            </button>
          </div>
        </div>

        <div className="glass-card-hover p-2.5 sm:p-4">
          <p className="data-label">Positions</p>
          <p className="text-sm sm:text-xl font-display font-bold text-white">{livePositions.length}</p>
        </div>

        <div className="glass-card-hover p-2.5 sm:p-4">
          <p className="data-label">Live PnL</p>
          <p className={`text-sm sm:text-xl font-mono font-bold ${totalLivePnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {totalLivePnl >= 0 ? '+' : ''}{totalLivePnl.toFixed(1)}%
          </p>
          <p className={`text-[10px] sm:text-xs font-mono ${totalLivePnl >= 0 ? 'text-emerald-400/60' : 'text-rose-400/60'} hidden sm:block`}>
            {totalLivePnl >= 0 ? '+' : ''}${(totalLivePnl * 10).toFixed(2)}
          </p>
        </div>

        <div className="glass-card-hover p-2.5 sm:p-4 hidden sm:block">
          <p className="data-label">Win Rate</p>
          <p className={`text-xl font-mono font-bold ${(stats?.win_rate || 0) >= 50 ? 'text-emerald-400' : 'text-orange-400'}`}>
            {stats?.win_rate || 0}%
          </p>
        </div>

        <div className="glass-card-hover p-2.5 sm:p-4 hidden sm:block col-span-1">
          <p className="data-label">Trades</p>
          <p className="text-xl font-mono font-bold">
            <span className="text-emerald-400">{stats?.wins || 0}W</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-rose-400">{stats?.losses || 0}L</span>
          </p>
        </div>
      </div>

      {/* PnL Chart - Hidden on Mobile */}
      <div className="glass-card p-3 sm:p-4 hidden sm:block">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-orange-400" />
            <span className="text-white text-sm font-medium font-display">Performance</span>
          </div>
          <span className={`text-sm font-mono font-bold ${(stats?.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
            {(stats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(stats?.total_pnl_pct || 0).toFixed(2)}% Total
          </span>
        </div>
        <PnLChart data={pnlHistory} />
      </div>

      {/* Market Conditions - Compact on Mobile */}
      <div className="grid grid-cols-4 gap-1.5 sm:gap-3">
        <div className="glass-card p-2 sm:p-3">
          <p className="data-label text-[8px] sm:text-xs">Regime</p>
          <p className={`text-[10px] sm:text-sm font-medium font-display truncate ${
            stats?.market_regime === 'TRENDING_UP' || stats?.market_regime === 'TRENDING_DOWN' ? 'text-emerald-400' :
            stats?.market_regime === 'VOLATILE' ? 'text-orange-400' : 'text-zinc-400'
          }`}>{(stats?.market_regime || 'N/A').replace('TRENDING_', '')}</p>
        </div>
        <div className="glass-card p-2 sm:p-3">
          <p className="data-label text-[8px] sm:text-xs">BTC</p>
          <p className={`text-[10px] sm:text-sm font-medium font-display ${
            stats?.btc_bias === 'BULLISH' ? 'text-emerald-400' :
            stats?.btc_bias === 'BEARISH' ? 'text-rose-400' : 'text-zinc-400'
          }`}>{stats?.btc_bias || 'NEUTRAL'}</p>
        </div>
        <div className="glass-card p-2 sm:p-3">
          <p className="data-label text-[8px] sm:text-xs">F&G</p>
          <p className={`text-[10px] sm:text-sm font-mono font-medium ${
            (stats?.fear_greed || 50) < 30 ? 'text-rose-400' :
            (stats?.fear_greed || 50) > 70 ? 'text-emerald-400' : 'text-orange-400'
          }`}>{stats?.fear_greed || 50}</p>
        </div>
        <div className="glass-card p-2 sm:p-3">
          <p className="data-label text-[8px] sm:text-xs">Session</p>
          <p className="text-[10px] sm:text-sm font-medium text-white font-display truncate">{(stats?.current_session || 'N/A').replace('_SESSION', '')}</p>
        </div>
      </div>

      {/* Confidence Slider - Compact on Mobile */}
      <div className="glass-card p-3 sm:p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <Settings2 className="w-4 h-4 text-orange-400" />
            <span className="text-white text-xs sm:text-sm font-medium font-display">Confidence</span>
          </div>
          <span className="text-orange-400 font-bold text-sm">{confidence}%</span>
        </div>
        <input
          type="range"
          min="60"
          max="95"
          value={confidence}
          onChange={(e) => setConfidence(parseInt(e.target.value))}
          onMouseUp={(e) => updateConfidence(parseInt(e.target.value))}
          onTouchEnd={(e) => updateConfidence(parseInt(e.target.value))}
          className="w-full h-2 bg-zinc-700 rounded-lg appearance-none cursor-pointer accent-orange-500"
          data-testid="confidence-slider"
        />
        <div className="flex justify-between text-[10px] sm:text-xs text-zinc-500 mt-1">
          <span>More (60%)</span>
          <span>Elite (95%)</span>
        </div>
      </div>

      {/* Tabs - Mobile Scrollable */}
      <div className="flex items-center gap-2 overflow-x-auto -mx-3 px-3 sm:mx-0 sm:px-0 no-scrollbar">
        <div className="flex bg-zinc-800/50 rounded-lg p-1 min-w-max">
          {['chart', 'positions', 'opportunities', 'history'].map(t => (
            <button 
              key={t} 
              onClick={() => setActiveTab(t)}
              data-testid={`tab-${t}`}
              className={`px-2.5 sm:px-3 py-1.5 rounded-md text-xs font-medium transition-all flex items-center gap-1 touch-target ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
            >
              {t === 'chart' && <CandlestickChart className="w-3.5 h-3.5" />}
              <span className="hidden sm:inline">{t.charAt(0).toUpperCase() + t.slice(1)}</span>
              <span className="sm:hidden">{t === 'opportunities' ? 'Opps' : t.charAt(0).toUpperCase() + t.slice(1)}</span>
            </button>
          ))}
        </div>
        <button 
          onClick={fetchData} 
          data-testid="refresh-btn"
          className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white transition-all"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Chart Tab - TradingView Style */}
      {activeTab === 'chart' && (
        <TradingChart 
          symbol="BTC" 
          trades={closedTrades}
          positions={livePositions}
          height={450}
          showControls={true}
        />
      )}

      {/* Live Positions Tab */}
      {activeTab === 'positions' && (
        <div className="space-y-3" data-testid="positions-list">
          {livePositions.length > 0 ? (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {livePositions.map((position, i) => (
                <PositionCard
                  key={position.id || i}
                  position={position}
                  onClose={() => closeTrade(position.symbol)}
                  onViewDetails={() => {
                    setSelectedPosition(position);
                    setShowPositionModal(true);
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="glass-card p-8 text-center">
              <Activity className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-400 font-medium">No open positions</p>
              <p className="text-zinc-600 text-sm mt-1">Aeon is scanning MEXC for high-probability setups...</p>
            </div>
          )}
        </div>
      )}

      {/* Opportunities Tab */}
      {activeTab === 'opportunities' && (
        <div className="space-y-3" data-testid="opportunities-list">
          {opportunities.length > 0 ? (
            opportunities.slice(0, 10).map((opp, i) => (
              <div 
                key={i} 
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  opp.direction === 'LONG' ? 'border-green-500/30' : 'border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-3">
                    <Zap className={`w-5 h-5 ${opp.direction === 'LONG' ? 'text-green-400' : 'text-red-400'}`} />
                    <span className="text-white font-medium">{opp.symbol?.replace('/USDT', '')}</span>
                    <span className={`text-xs px-2 py-0.5 rounded font-bold ${
                      opp.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {opp.direction}
                    </span>
                  </div>
                  <span className="text-orange-400 font-bold">{opp.confidence}%</span>
                </div>
                <div className="grid grid-cols-3 gap-4 mt-2 text-xs">
                  <div>
                    <span className="text-zinc-500">Entry:</span>
                    <span className="text-white ml-1">${opp.entry?.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Target:</span>
                    <span className="text-green-400 ml-1">${opp.target?.toLocaleString()}</span>
                  </div>
                  <div>
                    <span className="text-zinc-500">Stop:</span>
                    <span className="text-red-400 ml-1">${opp.stop?.toLocaleString()}</span>
                  </div>
                </div>
                
                {/* Reasoning */}
                {opp.reasoning && (
                  <div className="mt-3 p-2 bg-zinc-900/60 rounded-lg border border-zinc-700/50">
                    <p className="text-xs text-zinc-400 font-semibold mb-1">Why {opp.direction}:</p>
                    <p className="text-xs text-zinc-300">{opp.reasoning}</p>
                  </div>
                )}
                
                {/* Confirmations */}
                {opp.confirmations && opp.confirmations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {opp.confirmations.slice(0, 4).map((conf, idx) => (
                      <span key={idx} className="text-xs px-2 py-0.5 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/20">
                        ✓ {conf}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <Target className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No opportunities right now</p>
              <p className="text-zinc-600 text-sm">Lower confidence threshold or wait for setups</p>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="space-y-3" data-testid="history-list">
          {closedTrades.length > 0 ? (
            closedTrades.slice().reverse().map((trade, i) => (
              <div 
                key={i} 
                className={`bg-zinc-800/30 rounded-xl p-4 border ${
                  (trade.pnl_pct || 0) >= 0 ? 'border-green-500/30' : 'border-red-500/30'
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <span className={`px-2 py-1 rounded text-xs font-bold ${
                      trade.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>{trade.direction}</span>
                    <span className="text-white font-medium">{trade.symbol?.replace('/USDT', '')}</span>
                    <span className={`px-2 py-0.5 rounded text-xs ${
                      (trade.pnl_pct || 0) >= 0 ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.exit_reason}
                    </span>
                  </div>
                  <span className={`text-lg font-bold ${(trade.pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {(trade.pnl_pct || 0) >= 0 ? '+' : ''}{(trade.pnl_pct || 0).toFixed(2)}%
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-4 mt-2 text-xs text-zinc-500">
                  <div>Entry: ${trade.entry_price?.toLocaleString()}</div>
                  <div>Exit: ${trade.exit_price?.toLocaleString()}</div>
                </div>
              </div>
            ))
          ) : (
            <div className="bg-zinc-800/30 rounded-xl p-8 border border-zinc-700/50 text-center">
              <DollarSign className="w-12 h-12 text-zinc-600 mx-auto mb-3" />
              <p className="text-zinc-500">No trade history yet</p>
              <p className="text-zinc-600 text-sm">Completed trades will appear here</p>
            </div>
          )}
        </div>
      )}

      {/* Position Details Modal - Professional Exchange Style */}
      {showPositionModal && selectedPosition && (
        <PositionCardModal
          position={selectedPosition}
          onClose={() => setShowPositionModal(false)}
          onCloseTrade={closeTrade}
          onSetTrailing={setTrailingStop}
        />
      )}
    </div>
  );
}
