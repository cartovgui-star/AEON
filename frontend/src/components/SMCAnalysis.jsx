import React, { useState, useEffect, useCallback } from 'react';
import { Target, TrendingUp, TrendingDown, Layers, BarChart3, Droplets, RefreshCw, ChevronDown, ChevronUp } from 'lucide-react';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function SMCAnalysis() {
  const [smc, setSmc] = useState(null);
  const [confluence, setConfluence] = useState(null);
  const [selectedSymbol, setSelectedSymbol] = useState('BTC');
  const [selectedTimeframe, setSelectedTimeframe] = useState('4h');
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('smc');
  const [expandedSection, setExpandedSection] = useState(null);

  const symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP', 'DOGE', 'ADA', 'AVAX'];
  const timeframes = ['1h', '4h', '1d'];

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [smcRes, confRes] = await Promise.all([
        fetch(`${API_URL}/api/smc/analysis/${selectedSymbol}?timeframe=${selectedTimeframe}`),
        fetch(`${API_URL}/api/confluence/${selectedSymbol}?timeframe=${selectedTimeframe}`)
      ]);
      
      const smcData = await smcRes.json();
      const confData = await confRes.json();
      
      setSmc(smcData);
      setConfluence(confData);
    } catch (err) {
      console.error('Failed to fetch SMC data:', err);
    }
    setLoading(false);
  }, [selectedSymbol, selectedTimeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const getSignalColor = (signal) => {
    if (!signal) return 'text-zinc-400';
    if (signal.includes('BUY')) return 'text-green-400';
    if (signal.includes('SELL')) return 'text-red-400';
    return 'text-zinc-400';
  };

  const getSignalBg = (signal) => {
    if (!signal) return 'bg-zinc-700/50';
    if (signal.includes('BUY')) return 'bg-green-500/20';
    if (signal.includes('SELL')) return 'bg-red-500/20';
    return 'bg-zinc-700/50';
  };

  const toggleSection = (section) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="space-y-4 md:space-y-6" data-testid="smc-page">
      {/* Header Controls */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 sm:gap-4">
        <div className="flex bg-zinc-800/50 rounded-lg p-1">
          {['smc', 'confluence'].map(t => (
            <button key={t} onClick={() => setActiveTab(t)}
              className={`px-3 py-1.5 sm:px-4 sm:py-2 rounded-md text-xs sm:text-sm font-medium transition-all ${
                activeTab === t ? 'bg-orange-500 text-white' : 'text-zinc-400 hover:text-white'
              }`}
              data-testid={`tab-${t}`}
            >
              {t === 'smc' ? 'SMC Analysis' : 'Confluence'}
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-2 w-full sm:w-auto">
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className="flex-1 sm:flex-none bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
          >
            {symbols.map(s => (
              <option key={s} value={s}>{s}/USDT</option>
            ))}
          </select>
          
          <select
            value={selectedTimeframe}
            onChange={(e) => setSelectedTimeframe(e.target.value)}
            className="bg-zinc-800/50 border border-zinc-700 rounded-lg px-3 py-2 text-white text-sm"
          >
            {timeframes.map(tf => (
              <option key={tf} value={tf}>{tf}</option>
            ))}
          </select>
          
          <button onClick={fetchData} className="p-2 bg-zinc-800/50 rounded-lg text-zinc-400 hover:text-white">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* SMC Analysis Tab */}
      {activeTab === 'smc' && smc && !smc.error && (
        <div className="space-y-4">
          {/* Overall Signal Card */}
          <div className={`rounded-xl p-4 sm:p-6 border ${getSignalBg(smc.overall_signal)} border-zinc-700/50`}>
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

          {/* Collapsible Sections */}
          <div className="space-y-3">
            {/* Market Structure */}
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <button 
                onClick={() => toggleSection('structure')}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <div className="flex items-center gap-3">
                  <BarChart3 className="w-5 h-5 text-blue-400" />
                  <span className="text-white font-medium">Market Structure</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-sm ${
                    smc.market_structure?.trend === 'BULLISH' ? 'text-green-400' :
                    smc.market_structure?.trend === 'BEARISH' ? 'text-red-400' : 'text-zinc-400'
                  }`}>
                    {smc.market_structure?.trend || 'N/A'}
                  </span>
                  {expandedSection === 'structure' ? 
                    <ChevronUp className="w-4 h-4 text-zinc-400" /> : 
                    <ChevronDown className="w-4 h-4 text-zinc-400" />
                  }
                </div>
              </button>
              
              {expandedSection === 'structure' && (
                <div className="px-4 pb-4 space-y-2 border-t border-zinc-700/50 pt-3">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-zinc-900/50 rounded-lg p-2">
                      <p className="text-zinc-500 text-xs">Higher Highs/Lows</p>
                      <p className="text-green-400">{smc.market_structure?.hh_hl || 'N/A'}</p>
                    </div>
                    <div className="bg-zinc-900/50 rounded-lg p-2">
                      <p className="text-zinc-500 text-xs">Lower Highs/Lows</p>
                      <p className="text-red-400">{smc.market_structure?.lh_ll || 'N/A'}</p>
                    </div>
                  </div>
                  {smc.market_structure?.bos && (
                    <div className="bg-orange-500/20 rounded-lg p-2 text-sm">
                      <p className="text-orange-400">BOS: {smc.market_structure.bos}</p>
                    </div>
                  )}
                  {smc.market_structure?.choch && (
                    <div className="bg-purple-500/20 rounded-lg p-2 text-sm">
                      <p className="text-purple-400">CHoCH: {smc.market_structure.choch}</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {/* Premium/Discount */}
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <button 
                onClick={() => toggleSection('zones')}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <div className="flex items-center gap-3">
                  <Layers className="w-5 h-5 text-purple-400" />
                  <span className="text-white font-medium">Premium/Discount</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`text-sm ${
                    smc.premium_discount?.zone?.includes('DISCOUNT') ? 'text-green-400' :
                    smc.premium_discount?.zone?.includes('PREMIUM') ? 'text-red-400' : 'text-zinc-400'
                  }`}>
                    {smc.premium_discount?.zone || 'N/A'}
                  </span>
                  {expandedSection === 'zones' ? 
                    <ChevronUp className="w-4 h-4 text-zinc-400" /> : 
                    <ChevronDown className="w-4 h-4 text-zinc-400" />
                  }
                </div>
              </button>
              
              {expandedSection === 'zones' && (
                <div className="px-4 pb-4 border-t border-zinc-700/50 pt-3">
                  <div className="grid grid-cols-3 gap-2 text-sm text-center">
                    <div className="bg-zinc-900/50 rounded-lg p-2">
                      <p className="text-zinc-500 text-xs">Position</p>
                      <p className="text-white">{smc.premium_discount?.position || '50%'}</p>
                    </div>
                    <div className="bg-zinc-900/50 rounded-lg p-2">
                      <p className="text-zinc-500 text-xs">Equilibrium</p>
                      <p className="text-white">${smc.premium_discount?.equilibrium?.toLocaleString() || 'N/A'}</p>
                    </div>
                    <div className="bg-zinc-900/50 rounded-lg p-2">
                      <p className="text-zinc-500 text-xs">Bias</p>
                      <p className={getSignalColor(smc.premium_discount?.bias)}>{smc.premium_discount?.bias || 'N/A'}</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Order Blocks */}
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <button 
                onClick={() => toggleSection('orderblocks')}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <div className="flex items-center gap-3">
                  <Target className="w-5 h-5 text-orange-400" />
                  <span className="text-white font-medium">Order Blocks</span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-sm text-zinc-400">
                    {(smc.order_blocks?.bullish || 0) + (smc.order_blocks?.bearish || 0)} active
                  </span>
                  {expandedSection === 'orderblocks' ? 
                    <ChevronUp className="w-4 h-4 text-zinc-400" /> : 
                    <ChevronDown className="w-4 h-4 text-zinc-400" />
                  }
                </div>
              </button>
              
              {expandedSection === 'orderblocks' && (
                <div className="px-4 pb-4 border-t border-zinc-700/50 pt-3">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="bg-green-500/10 rounded-lg p-2 border border-green-500/30">
                      <p className="text-green-400 font-medium">{smc.order_blocks?.bullish || 0} Bullish OBs</p>
                    </div>
                    <div className="bg-red-500/10 rounded-lg p-2 border border-red-500/30">
                      <p className="text-red-400 font-medium">{smc.order_blocks?.bearish || 0} Bearish OBs</p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Liquidity */}
            <div className="bg-zinc-800/30 rounded-xl border border-zinc-700/50 overflow-hidden">
              <button 
                onClick={() => toggleSection('liquidity')}
                className="w-full flex items-center justify-between p-4 text-left"
              >
                <div className="flex items-center gap-3">
                  <Droplets className="w-5 h-5 text-cyan-400" />
                  <span className="text-white font-medium">Liquidity Zones</span>
                </div>
                {expandedSection === 'liquidity' ? 
                  <ChevronUp className="w-4 h-4 text-zinc-400" /> : 
                  <ChevronDown className="w-4 h-4 text-zinc-400" />
                }
              </button>
              
              {expandedSection === 'liquidity' && (
                <div className="px-4 pb-4 border-t border-zinc-700/50 pt-3 space-y-2">
                  {smc.liquidity?.nearest_buy_side && (
                    <div className="bg-green-500/10 rounded-lg p-2 border border-green-500/30 text-sm">
                      <p className="text-zinc-400 text-xs">Buy-side Liquidity</p>
                      <p className="text-green-400">${smc.liquidity.nearest_buy_side.price?.toLocaleString()}</p>
                    </div>
                  )}
                  {smc.liquidity?.nearest_sell_side && (
                    <div className="bg-red-500/10 rounded-lg p-2 border border-red-500/30 text-sm">
                      <p className="text-zinc-400 text-xs">Sell-side Liquidity</p>
                      <p className="text-red-400">${smc.liquidity.nearest_sell_side.price?.toLocaleString()}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Entry Points */}
          {smc.entry_points && smc.entry_points.length > 0 && (
            <div className="bg-zinc-800/30 rounded-xl p-4 border border-orange-500/30">
              <h3 className="text-orange-400 font-medium mb-3 flex items-center gap-2">
                <Target className="w-5 h-5" />
                Entry Points
              </h3>
              <div className="space-y-2">
                {smc.entry_points.map((ep, i) => (
                  <div key={i} className="bg-zinc-900/50 rounded-lg p-3 text-sm">
                    <p className="text-white font-medium">{ep.type?.replace('_', ' ')}</p>
                    <p className="text-zinc-400">Zone: {ep.zone}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Confluence Tab */}
      {activeTab === 'confluence' && confluence && !confluence.error && (
        <div className="space-y-4">
          {/* Signal Card */}
          <div className={`rounded-xl p-4 sm:p-6 border ${getSignalBg(confluence.final_signal)} border-zinc-700/50`}>
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
              <div>
                <p className="text-zinc-400 text-xs sm:text-sm mb-1">Confluence Signal</p>
                <p className={`text-2xl sm:text-3xl font-bold ${getSignalColor(confluence.final_signal)}`}>
                  {confluence.final_signal || 'NEUTRAL'}
                </p>
              </div>
              <div className="text-left sm:text-right">
                <p className="text-zinc-500 text-xs">Confluence Score</p>
                <p className="text-xl sm:text-2xl font-bold text-white">{confluence.confluence_score || 0}/100</p>
              </div>
            </div>
          </div>

          {/* Confluence Factors */}
          <div className="bg-zinc-800/30 rounded-xl p-4 border border-zinc-700/50">
            <h3 className="text-white font-medium mb-3">Confluence Factors</h3>
            <div className="space-y-2">
              {confluence.confluence_factors?.map((factor, i) => (
                <div key={i} className={`rounded-lg p-3 border ${
                  factor.status === 'ALIGNED' || factor.status === 'OPTIMAL' || factor.status === 'PRESENT' 
                    ? 'bg-green-500/10 border-green-500/30' 
                    : factor.status === 'PARTIAL' ? 'bg-yellow-500/10 border-yellow-500/30'
                    : 'bg-zinc-900/50 border-zinc-700/50'
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="text-white text-sm font-medium">{factor.factor}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${
                      factor.status === 'ALIGNED' || factor.status === 'OPTIMAL' || factor.status === 'PRESENT'
                        ? 'bg-green-500/20 text-green-400'
                        : factor.status === 'PARTIAL' ? 'bg-yellow-500/20 text-yellow-400'
                        : 'bg-zinc-700/50 text-zinc-400'
                    }`}>
                      +{factor.score}
                    </span>
                  </div>
                  <p className="text-zinc-400 text-xs mt-1">{factor.detail}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Trade Setup */}
          {confluence.trade_setup && confluence.trade_setup.action !== 'WAIT' && (
            <div className={`rounded-xl p-4 border ${
              confluence.trade_setup.action === 'LONG' ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30'
            }`}>
              <h3 className={`font-medium mb-3 ${
                confluence.trade_setup.action === 'LONG' ? 'text-green-400' : 'text-red-400'
              }`}>
                Trade Setup: {confluence.trade_setup.action}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-zinc-500 text-xs">Entry Zone</p>
                  <p className="text-white">{confluence.trade_setup.entry_zone}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Stop Loss</p>
                  <p className="text-red-400">{confluence.trade_setup.stop_loss}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Target</p>
                  <p className="text-green-400">{confluence.trade_setup.target}</p>
                </div>
                <div>
                  <p className="text-zinc-500 text-xs">Risk/Reward</p>
                  <p className="text-white">{confluence.trade_setup.risk_reward}</p>
                </div>
              </div>
              <p className="text-zinc-400 text-xs mt-3">{confluence.trade_setup.reason}</p>
            </div>
          )}
        </div>
      )}

      {/* Error State */}
      {(smc?.error || confluence?.error) && (
        <div className="bg-red-500/20 rounded-xl p-4 border border-red-500/30 text-center">
          <p className="text-red-400">Error loading data. Please try again.</p>
        </div>
      )}
    </div>
  );
}
