import React, { useState, useEffect } from 'react';
import { 
  Target, TrendingUp, TrendingDown, Layers, BarChart3, RefreshCw, 
  AlertCircle, CheckCircle2, Info, Zap, Shield
} from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SMCAnalysis() {
  const [smc, setSmc] = useState(null);
  const [confluence, setConfluence] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState('BTC');
  const [selectedTimeframe, setSelectedTimeframe] = useState('4h');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('smc');

  const symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP'];
  const timeframes = ['1h', '4h', '1d'];

  useEffect(() => {
    fetchData();
  }, [selectedSymbol, selectedTimeframe]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const smcRes = await fetch(`${API_URL}/api/smc/analysis/${selectedSymbol}?timeframe=${selectedTimeframe}`);
      const confRes = await fetch(`${API_URL}/api/confluence/${selectedSymbol}?timeframe=${selectedTimeframe}`);
      setSmc(await smcRes.json());
      setConfluence(await confRes.json());
    } catch (err) {
      console.error('Failed to fetch SMC data:', err);
    }
    setLoading(false);
  };

  const getSignalColor = (signal) => {
    if (!signal) return 'text-zinc-400';
    if (signal.includes('BUY') || signal.includes('LONG')) return 'text-green-400';
    if (signal.includes('SELL') || signal.includes('SHORT')) return 'text-red-400';
    return 'text-zinc-400';
  };

  const getSignalBg = (signal) => {
    if (!signal) return 'bg-zinc-700/50 border-zinc-700/50';
    if (signal.includes('BUY') || signal.includes('LONG')) return 'bg-green-500/10 border-green-500/30';
    if (signal.includes('SELL') || signal.includes('SHORT')) return 'bg-red-500/10 border-red-500/30';
    return 'bg-zinc-700/50 border-zinc-700/50';
  };

  // Generate detailed reasoning based on SMC data
  const generateReasoning = (data, type) => {
    if (!data) return null;
    
    const reasons = [];
    
    if (type === 'smc') {
      // Market Structure reasoning
      if (data.market_structure?.trend === 'BULLISH') {
        reasons.push({
          type: 'bullish',
          text: `Market structure is bullish with ${data.market_structure?.hh_hl || 'multiple'} higher highs/higher lows`
        });
      } else if (data.market_structure?.trend === 'BEARISH') {
        reasons.push({
          type: 'bearish',
          text: `Market structure is bearish with ${data.market_structure?.lh_ll || 'multiple'} lower highs/lower lows`
        });
      }
      
      // BOS reasoning
      if (data.market_structure?.bos) {
        const bosType = data.market_structure.bos.includes('BULLISH') ? 'bullish' : 'bearish';
        reasons.push({
          type: bosType,
          text: `Break of Structure (BOS) detected: ${data.market_structure.bos}`
        });
      }
      
      // Premium/Discount reasoning
      if (data.premium_discount?.zone?.includes('DISCOUNT')) {
        reasons.push({
          type: 'bullish',
          text: `Price is in discount zone (${data.premium_discount?.position || 'below equilibrium'}) - favorable for longs`
        });
      } else if (data.premium_discount?.zone?.includes('PREMIUM')) {
        reasons.push({
          type: 'bearish',
          text: `Price is in premium zone (${data.premium_discount?.position || 'above equilibrium'}) - favorable for shorts`
        });
      }
      
      // Order Blocks reasoning
      if (data.order_blocks?.bullish > 0) {
        reasons.push({
          type: 'bullish',
          text: `${data.order_blocks.bullish} bullish order block(s) nearby providing support`
        });
      }
      if (data.order_blocks?.bearish > 0) {
        reasons.push({
          type: 'bearish',
          text: `${data.order_blocks.bearish} bearish order block(s) nearby providing resistance`
        });
      }
      
      // FVG reasoning
      if (data.fvgs?.bullish > 0) {
        reasons.push({
          type: 'bullish',
          text: `${data.fvgs.bullish} bullish fair value gap(s) - potential support zones`
        });
      }
      if (data.fvgs?.bearish > 0) {
        reasons.push({
          type: 'bearish',
          text: `${data.fvgs.bearish} bearish fair value gap(s) - potential resistance zones`
        });
      }
    }
    
    return reasons;
  };

  const reasoning = generateReasoning(smc, 'smc');

  return (
    <div className="space-y-4 md:space-y-6" data-testid="smc-page">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          <button 
            onClick={() => setActiveTab('smc')}
            data-testid="tab-smc"
            className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-md text-xs sm:text-sm font-medium transition-all ${
              activeTab === 'smc' ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            SMC Analysis
          </button>
          <button 
            onClick={() => setActiveTab('confluence')}
            data-testid="tab-confluence"
            className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-md text-xs sm:text-sm font-medium transition-all ${
              activeTab === 'confluence' ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
            }`}
          >
            Confluence
          </button>
        </div>
        
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            data-testid="symbol-select"
            className="flex-1 sm:flex-none bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:border-orange-500 focus:outline-none"
          >
            {symbols.map(s => <option key={s} value={s}>{s}/USDT</option>)}
          </select>
          
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            data-testid="timeframe-select"
            className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm focus:border-orange-500 focus:outline-none"
          >
            {timeframes.map(tf => <option key={tf} value={tf}>{tf}</option>)}
          </select>
          
          <button 
            onClick={fetchData} 
            data-testid="refresh-btn"
            className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white hover:bg-zinc-700 transition-all"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* SMC Tab */}
      {activeTab === 'smc' && smc && !smc.error && (
        <div className="space-y-4">
          {/* Signal Card */}
          <div className={`rounded-xl p-4 sm:p-6 border ${getSignalBg(smc.overall_signal)}`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <p className="text-zinc-400 text-xs sm:text-sm mb-1">SMC Signal for {selectedSymbol}/USDT</p>
                <p className={`text-2xl sm:text-3xl font-bold ${getSignalColor(smc.overall_signal)}`}>
                  {smc.overall_signal || 'NEUTRAL'}
                </p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-zinc-500 text-xs">Confidence</p>
                <p className="text-xl sm:text-2xl font-bold text-white">{smc.confidence || 50}%</p>
              </div>
            </div>
            
            <div className="flex items-center gap-4 sm:gap-6 mt-4 text-sm">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-4 h-4 text-green-400" />
                <span className="text-green-400">{smc.bullish_factors || 0} Bullish</span>
              </div>
              <div className="flex items-center gap-2">
                <TrendingDown className="w-4 h-4 text-red-400" />
                <span className="text-red-400">{smc.bearish_factors || 0} Bearish</span>
              </div>
            </div>
          </div>

          {/* Detailed Reasoning Section - NEW */}
          {reasoning && reasoning.length > 0 && (
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-3 bg-zinc-800/50 border-b border-zinc-700/50">
                <Info className="w-5 h-5 text-cyan-400" />
                <span className="text-white font-medium">Why This Signal?</span>
              </div>
              <div className="p-4 space-y-2">
                {reasoning.map((reason, idx) => (
                  <div 
                    key={idx} 
                    className={`flex items-start gap-3 p-3 rounded-lg border ${
                      reason.type === 'bullish' 
                        ? 'bg-green-500/5 border-green-500/20' 
                        : 'bg-red-500/5 border-red-500/20'
                    }`}
                  >
                    {reason.type === 'bullish' ? (
                      <TrendingUp className="w-4 h-4 text-green-400 mt-0.5 flex-shrink-0" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-red-400 mt-0.5 flex-shrink-0" />
                    )}
                    <p className={`text-sm ${reason.type === 'bullish' ? 'text-green-300' : 'text-red-300'}`}>
                      {reason.text}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Info Cards */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <div className="flex items-center gap-2 mb-3">
                <BarChart3 className="w-5 h-5 text-blue-400" />
                <span className="text-white font-medium">Market Structure</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">Trend</span>
                  <span className={`px-2 py-0.5 rounded font-medium ${
                    smc.market_structure?.trend === 'BULLISH' ? 'bg-green-500/20 text-green-400' :
                    smc.market_structure?.trend === 'BEARISH' ? 'bg-red-500/20 text-red-400' : 'bg-zinc-700 text-zinc-400'
                  }`}>{smc.market_structure?.trend || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">HH/HL Count</span>
                  <span className="text-green-400 font-medium">{smc.market_structure?.hh_hl || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">LH/LL Count</span>
                  <span className="text-red-400 font-medium">{smc.market_structure?.lh_ll || 'N/A'}</span>
                </div>
                {smc.market_structure?.bos && (
                  <div className="mt-2 p-3 bg-orange-500/10 rounded-lg border border-orange-500/30">
                    <div className="flex items-center gap-2">
                      <Zap className="w-4 h-4 text-orange-400" />
                      <span className="text-orange-400 text-sm font-medium">BOS Detected</span>
                    </div>
                    <p className="text-orange-300 text-xs mt-1">{smc.market_structure.bos}</p>
                  </div>
                )}
              </div>
            </div>

            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-5 h-5 text-purple-400" />
                <span className="text-white font-medium">Premium/Discount</span>
              </div>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">Zone</span>
                  <span className={`px-2 py-0.5 rounded font-medium ${
                    smc.premium_discount?.zone?.includes('DISCOUNT') ? 'bg-green-500/20 text-green-400' :
                    smc.premium_discount?.zone?.includes('PREMIUM') ? 'bg-red-500/20 text-red-400' : 'bg-zinc-700 text-zinc-400'
                  }`}>{smc.premium_discount?.zone || 'N/A'}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">Position</span>
                  <span className="text-white font-medium">{smc.premium_discount?.position || '50%'}</span>
                </div>
                <div className="flex justify-between items-center p-2 bg-zinc-900/50 rounded-lg">
                  <span className="text-zinc-400">Equilibrium</span>
                  <span className="text-white font-medium">${smc.premium_discount?.equilibrium?.toLocaleString() || 'N/A'}</span>
                </div>
              </div>
            </div>
          </div>

          {/* Order Blocks & FVG */}
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <div className="flex items-center gap-2 mb-3">
                <Target className="w-5 h-5 text-orange-400" />
                <span className="text-white font-medium">Order Blocks</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-green-500/10 rounded-xl p-3 border border-green-500/30 text-center">
                  <p className="text-2xl font-bold text-green-400">{smc.order_blocks?.bullish || 0}</p>
                  <p className="text-zinc-400 text-xs mt-1">Bullish OBs</p>
                </div>
                <div className="bg-red-500/10 rounded-xl p-3 border border-red-500/30 text-center">
                  <p className="text-2xl font-bold text-red-400">{smc.order_blocks?.bearish || 0}</p>
                  <p className="text-zinc-400 text-xs mt-1">Bearish OBs</p>
                </div>
              </div>
            </div>

            <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
              <div className="flex items-center gap-2 mb-3">
                <Layers className="w-5 h-5 text-cyan-400" />
                <span className="text-white font-medium">Fair Value Gaps</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-green-500/10 rounded-xl p-3 border border-green-500/30 text-center">
                  <p className="text-2xl font-bold text-green-400">{smc.fvgs?.bullish || 0}</p>
                  <p className="text-zinc-400 text-xs mt-1">Bullish FVGs</p>
                </div>
                <div className="bg-red-500/10 rounded-xl p-3 border border-red-500/30 text-center">
                  <p className="text-2xl font-bold text-red-400">{smc.fvgs?.bearish || 0}</p>
                  <p className="text-zinc-400 text-xs mt-1">Bearish FVGs</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Confluence Tab */}
      {activeTab === 'confluence' && confluence && !confluence.error && (
        <div className="space-y-4">
          <div className={`rounded-xl p-4 sm:p-6 border ${getSignalBg(confluence.final_signal)}`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <p className="text-zinc-400 text-xs sm:text-sm mb-1">Confluence Signal</p>
                <p className={`text-2xl sm:text-3xl font-bold ${getSignalColor(confluence.final_signal)}`}>
                  {confluence.final_signal || 'NEUTRAL'}
                </p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-zinc-500 text-xs">Score</p>
                <p className="text-xl sm:text-2xl font-bold text-white">{confluence.confluence_score || 0}/100</p>
              </div>
            </div>
          </div>

          {/* Confluence Factors with Enhanced Reasoning */}
          <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-zinc-800/50 border-b border-zinc-700/50">
              <Shield className="w-5 h-5 text-purple-400" />
              <h3 className="text-white font-medium">Confluence Factors</h3>
              <span className="ml-auto text-xs text-zinc-400">{confluence.confluence_factors?.length || 0} factors analyzed</span>
            </div>
            <div className="p-4 space-y-2">
              {confluence.confluence_factors?.map((factor, i) => {
                const isPositive = factor.status === 'ALIGNED' || factor.status === 'OPTIMAL' || factor.status === 'PRESENT';
                const isPartial = factor.status === 'PARTIAL';
                
                return (
                  <div 
                    key={i} 
                    className={`rounded-xl p-4 border transition-all ${
                      isPositive ? 'bg-green-500/5 border-green-500/30' : 
                      isPartial ? 'bg-yellow-500/5 border-yellow-500/30' :
                      'bg-zinc-900/50 border-zinc-700/50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        {isPositive ? (
                          <CheckCircle2 className="w-5 h-5 text-green-400 mt-0.5" />
                        ) : isPartial ? (
                          <AlertCircle className="w-5 h-5 text-yellow-400 mt-0.5" />
                        ) : (
                          <AlertCircle className="w-5 h-5 text-zinc-500 mt-0.5" />
                        )}
                        <div>
                          <p className={`font-medium ${
                            isPositive ? 'text-green-400' : isPartial ? 'text-yellow-400' : 'text-zinc-400'
                          }`}>{factor.factor}</p>
                          <p className="text-zinc-400 text-sm mt-1">{factor.detail}</p>
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded-lg text-xs font-bold ${
                        isPositive ? 'bg-green-500/20 text-green-400' :
                        isPartial ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-zinc-700/50 text-zinc-400'
                      }`}>+{factor.score}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Trade Setup with Reasoning */}
          {confluence.trade_setup && confluence.trade_setup.action !== 'WAIT' && (
            <div className={`rounded-xl border overflow-hidden ${
              confluence.trade_setup.action === 'LONG' ? 'bg-green-500/5 border-green-500/30' : 'bg-red-500/5 border-red-500/30'
            }`}>
              <div className={`px-4 py-3 border-b ${
                confluence.trade_setup.action === 'LONG' ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'
              }`}>
                <div className="flex items-center gap-2">
                  {confluence.trade_setup.action === 'LONG' ? (
                    <TrendingUp className="w-5 h-5 text-green-400" />
                  ) : (
                    <TrendingDown className="w-5 h-5 text-red-400" />
                  )}
                  <h3 className={`font-bold ${
                    confluence.trade_setup.action === 'LONG' ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {confluence.trade_setup.action} Setup Identified
                  </h3>
                </div>
              </div>
              
              <div className="p-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <div className="bg-zinc-900/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs mb-1">Entry Zone</p>
                    <p className="text-white font-semibold">{confluence.trade_setup.entry_zone}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs mb-1">Stop Loss</p>
                    <p className="text-red-400 font-semibold">{confluence.trade_setup.stop_loss}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs mb-1">Target</p>
                    <p className="text-green-400 font-semibold">{confluence.trade_setup.target}</p>
                  </div>
                  <div className="bg-zinc-900/50 rounded-lg p-3">
                    <p className="text-zinc-500 text-xs mb-1">Risk:Reward</p>
                    <p className="text-orange-400 font-semibold">{confluence.trade_setup.risk_reward}</p>
                  </div>
                </div>
                
                {/* Generated Reasoning for Trade Setup */}
                <div className="mt-4 p-3 bg-zinc-900/50 rounded-lg border border-zinc-700/50">
                  <p className="text-zinc-400 text-xs mb-2 font-semibold flex items-center gap-1">
                    <Info className="w-3 h-3" /> Why This Trade?
                  </p>
                  <p className="text-zinc-300 text-sm">
                    {confluence.trade_setup.action === 'LONG' 
                      ? `${confluence.confluence_score}% confluence score with multiple bullish factors aligned. Entry at ${confluence.trade_setup.entry_zone} offers favorable risk:reward of ${confluence.trade_setup.risk_reward}.`
                      : `${confluence.confluence_score}% confluence score with multiple bearish factors aligned. Entry at ${confluence.trade_setup.entry_zone} offers favorable risk:reward of ${confluence.trade_setup.risk_reward}.`
                    }
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Error State */}
      {(smc?.error || confluence?.error) && (
        <div className="bg-red-500/10 rounded-xl p-6 border border-red-500/30 text-center">
          <AlertCircle className="w-12 h-12 text-red-400 mx-auto mb-3" />
          <p className="text-red-400 font-medium">Error loading data</p>
          <p className="text-zinc-500 text-sm mt-1">Please try again or select a different symbol</p>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <RefreshCw className="w-8 h-8 text-orange-400 animate-spin" />
        </div>
      )}
    </div>
  );
}
