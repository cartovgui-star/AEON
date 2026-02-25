import React from 'react';
import { 
  TrendingUp, TrendingDown, Clock, Target, Shield, 
  AlertTriangle, Flame, ChevronRight, Zap, X
} from 'lucide-react';

/**
 * Enhanced Position Card - Glass Cockpit Design
 * Shows all critical trading info: entry, current, SL, TP, liquidation, leverage, margin, PnL, time
 */
const PositionCard = ({ 
  position, 
  onClose, 
  onViewDetails,
  compact = false 
}) => {
  if (!position) return null;

  const symbol = position.symbol?.replace('/USDT', '') || 'N/A';
  const isLong = position.direction === 'LONG';
  const leverage = position.leverage || 10;
  
  // Price calculations
  const entryPrice = position.entry_price || 0;
  const currentPrice = position.current_price || entryPrice;
  const stopPrice = position.stop_price || 0;
  const targetPrice = position.target_price || 0;
  const liquidationPrice = position.liquidation_price || 0;
  
  // PnL calculations
  const pnlPct = position.pnl_pct || 0;
  const leveragedPnl = pnlPct * leverage;
  const positionSize = position.position_size || 1000;
  const margin = positionSize / leverage;
  const pnlUsd = (leveragedPnl / 100) * positionSize;
  const isProfitable = leveragedPnl >= 0;
  
  // Progress calculation (SL -> Entry -> TP)
  const totalRange = Math.abs(targetPrice - stopPrice);
  const currentProgress = totalRange > 0 
    ? ((currentPrice - stopPrice) / totalRange) * 100 
    : 50;
  const progressClamped = Math.max(0, Math.min(100, currentProgress));
  
  // Distance to liquidation
  const liqDistance = liquidationPrice > 0 
    ? Math.abs((currentPrice - liquidationPrice) / currentPrice * 100) 
    : 100;
  const liqRisk = liqDistance < 3 ? 'HIGH' : liqDistance < 8 ? 'MEDIUM' : 'LOW';
  
  // Time in position
  const timeHeld = position.entry_time 
    ? Math.floor((Date.now() - new Date(position.entry_time).getTime()) / (1000 * 60))
    : 0;
  const timeDisplay = timeHeld >= 60 
    ? `${Math.floor(timeHeld / 60)}h ${timeHeld % 60}m`
    : `${timeHeld}m`;
  
  // Trade type badge
  const tradeType = position.trade_type || 
    (position.timeframe === '5m' || position.timeframe === '15m' ? 'SCALP' : 
     position.timeframe === '1h' ? 'DAY' : 'SWING');

  if (compact) {
    return (
      <div 
        className={`glass-card-hover p-3 cursor-pointer ${
          isProfitable ? 'border-l-2 border-l-emerald-500' : 'border-l-2 border-l-rose-500'
        }`}
        onClick={onViewDetails}
        data-testid={`position-compact-${symbol}`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${isLong ? 'bg-emerald-500/10' : 'bg-rose-500/10'}`}>
              {isLong ? (
                <TrendingUp className="w-4 h-4 text-emerald-400" />
              ) : (
                <TrendingDown className="w-4 h-4 text-rose-400" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-semibold text-white">{symbol}</span>
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  isLong ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                }`}>
                  {isLong ? 'LONG' : 'SHORT'} {leverage}x
                </span>
              </div>
              <div className="text-xs text-zinc-500 font-mono">${currentPrice.toLocaleString()}</div>
            </div>
          </div>
          <div className="text-right">
            <div className={`font-mono font-bold ${isProfitable ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfitable ? '+' : ''}{leveragedPnl.toFixed(2)}%
            </div>
            <div className={`text-xs font-mono ${isProfitable ? 'text-emerald-400/70' : 'text-rose-400/70'}`}>
              {isProfitable ? '+' : ''}${pnlUsd.toFixed(2)}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div 
      className={`glass-card overflow-hidden ${isProfitable ? 'glow-green' : 'glow-red'}`}
      data-testid={`position-card-${symbol}`}
    >
      {/* Header */}
      <div className={`px-4 py-3 border-b border-zinc-800/50 ${
        isProfitable ? 'bg-emerald-500/5' : 'bg-rose-500/5'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`p-2.5 rounded-xl ${
              isLong ? 'bg-emerald-500/10 border border-emerald-500/20' : 'bg-rose-500/10 border border-rose-500/20'
            }`}>
              {isLong ? (
                <TrendingUp className="w-5 h-5 text-emerald-400" />
              ) : (
                <TrendingDown className="w-5 h-5 text-rose-400" />
              )}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-display font-bold text-lg text-white">{symbol}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                  isLong ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' 
                        : 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                }`}>
                  {isLong ? 'LONG' : 'SHORT'}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-orange-500/20 text-orange-400 border border-orange-500/30">
                  {leverage}x
                </span>
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="text-xs text-zinc-500">{tradeType}</span>
                <span className="text-zinc-600">•</span>
                <span className="text-xs text-zinc-500 flex items-center gap-1">
                  <Clock className="w-3 h-3" /> {timeDisplay}
                </span>
              </div>
            </div>
          </div>
          {onClose && (
            <button 
              onClick={(e) => { e.stopPropagation(); onClose(position); }}
              className="p-2 hover:bg-zinc-800 rounded-lg transition-colors"
              data-testid="close-position-btn"
            >
              <X className="w-4 h-4 text-zinc-400" />
            </button>
          )}
        </div>
      </div>

      {/* PnL Display */}
      <div className={`px-4 py-4 ${isProfitable ? 'bg-emerald-500/5' : 'bg-rose-500/5'}`}>
        <div className="flex items-center justify-between">
          <div>
            <div className="data-label mb-1">Unrealized PnL</div>
            <div className={`text-3xl font-mono font-bold ${isProfitable ? 'text-emerald-400' : 'text-rose-400'}`}>
              {isProfitable ? '+' : ''}{leveragedPnl.toFixed(2)}%
            </div>
            <div className={`text-sm font-mono ${isProfitable ? 'text-emerald-400/70' : 'text-rose-400/70'}`}>
              {isProfitable ? '+' : ''}${pnlUsd.toFixed(2)} USDT
            </div>
          </div>
          {Math.abs(leveragedPnl) > 30 && (
            <Flame className={`w-10 h-10 ${isProfitable ? 'text-emerald-400' : 'text-rose-400'} animate-pulse`} />
          )}
        </div>
      </div>

      {/* Progress Bar (SL → Current → TP) */}
      <div className="px-4 py-3 border-t border-b border-zinc-800/30">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="text-rose-400 font-mono">SL ${stopPrice.toLocaleString()}</span>
          <span className="text-emerald-400 font-mono">TP ${targetPrice.toLocaleString()}</span>
        </div>
        <div className="relative h-2 bg-zinc-800 rounded-full overflow-hidden">
          {/* Background gradient */}
          <div className="absolute inset-0 bg-gradient-to-r from-rose-500/20 via-zinc-700/20 to-emerald-500/20" />
          {/* Current position marker */}
          <div 
            className="absolute top-0 bottom-0 w-1 bg-white rounded-full shadow-lg shadow-white/50 transition-all duration-500"
            style={{ left: `calc(${progressClamped}% - 2px)` }}
          />
          {/* Entry position marker */}
          <div 
            className="absolute top-0 bottom-0 w-0.5 bg-blue-400/50"
            style={{ 
              left: `${totalRange > 0 ? ((entryPrice - stopPrice) / totalRange) * 100 : 50}%` 
            }}
          />
        </div>
        <div className="flex justify-center mt-1">
          <span className="text-xs text-zinc-500">
            Entry: <span className="font-mono text-blue-400">${entryPrice.toLocaleString()}</span>
          </span>
        </div>
      </div>

      {/* Price Grid */}
      <div className="grid grid-cols-2 gap-px bg-zinc-800/30">
        <div className="bg-zinc-900/50 px-4 py-3">
          <div className="data-label">Entry Price</div>
          <div className="data-value text-blue-400">${entryPrice.toLocaleString()}</div>
        </div>
        <div className="bg-zinc-900/50 px-4 py-3">
          <div className="data-label">Current Price</div>
          <div className="data-value text-white">${currentPrice.toLocaleString()}</div>
        </div>
        <div className="bg-zinc-900/50 px-4 py-3">
          <div className="data-label flex items-center gap-1">
            <Shield className="w-3 h-3 text-rose-400" /> Stop Loss
          </div>
          <div className="data-value text-rose-400">${stopPrice.toLocaleString()}</div>
        </div>
        <div className="bg-zinc-900/50 px-4 py-3">
          <div className="data-label flex items-center gap-1">
            <Target className="w-3 h-3 text-emerald-400" /> Take Profit
          </div>
          <div className="data-value text-emerald-400">${targetPrice.toLocaleString()}</div>
        </div>
      </div>

      {/* Liquidation & Risk */}
      <div className={`px-4 py-3 border-t border-zinc-800/30 ${
        liqRisk === 'HIGH' ? 'bg-rose-500/10' : liqRisk === 'MEDIUM' ? 'bg-amber-500/5' : 'bg-zinc-900/30'
      }`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertTriangle className={`w-4 h-4 ${
              liqRisk === 'HIGH' ? 'text-rose-400' : liqRisk === 'MEDIUM' ? 'text-amber-400' : 'text-zinc-500'
            }`} />
            <div>
              <div className="text-xs text-zinc-500">Liquidation Price</div>
              <div className={`font-mono font-semibold ${
                liqRisk === 'HIGH' ? 'text-rose-400' : liqRisk === 'MEDIUM' ? 'text-amber-400' : 'text-zinc-400'
              }`}>
                ${liquidationPrice > 0 ? liquidationPrice.toLocaleString() : 'N/A'}
              </div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-xs text-zinc-500">Distance</div>
            <div className={`font-mono font-semibold ${
              liqRisk === 'HIGH' ? 'text-rose-400' : liqRisk === 'MEDIUM' ? 'text-amber-400' : 'text-emerald-400'
            }`}>
              {liqDistance.toFixed(1)}%
            </div>
          </div>
        </div>
      </div>

      {/* Position Details Footer */}
      <div className="px-4 py-3 border-t border-zinc-800/30 grid grid-cols-3 gap-2">
        <div>
          <div className="data-label">Position Size</div>
          <div className="text-sm font-mono text-white">${positionSize.toLocaleString()}</div>
        </div>
        <div>
          <div className="data-label">Margin Used</div>
          <div className="text-sm font-mono text-white">${margin.toFixed(2)}</div>
        </div>
        <div>
          <div className="data-label">Leverage</div>
          <div className="text-sm font-mono text-orange-400">{leverage}x</div>
        </div>
      </div>

      {/* Action Button */}
      {onViewDetails && (
        <button 
          onClick={onViewDetails}
          className="w-full px-4 py-3 border-t border-zinc-800/30 flex items-center justify-center gap-2 text-sm text-zinc-400 hover:text-white hover:bg-zinc-800/30 transition-colors"
          data-testid="view-position-details"
        >
          <span>View Full Details</span>
          <ChevronRight className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};

export default PositionCard;
