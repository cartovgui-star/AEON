import React, { useState } from 'react';
import { 
  MessageSquare, TrendingUp, Wallet, Globe, Newspaper, Calculator, 
  Bot, Target, Bell, BookOpen, Brain, Settings, ChevronDown, ChevronRight,
  Copy, Check, Zap, Moon, Rocket, BarChart3, LineChart, Activity,
  DollarSign, Layers, RefreshCw, Shield
} from 'lucide-react';

const CommandCategory = ({ title, icon: Icon, commands, color, isOpen, onToggle, badge }) => {
  const [copiedCmd, setCopiedCmd] = useState(null);
  
  const copyCommand = (cmd) => {
    navigator.clipboard.writeText(cmd);
    setCopiedCmd(cmd);
    setTimeout(() => setCopiedCmd(null), 2000);
  };

  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden mb-3">
      <button 
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Icon className={`w-5 h-5 ${color}`} />
          <span className="font-medium text-white">{title}</span>
          {badge && (
            <span className={`text-xs px-2 py-0.5 rounded ${badge.color}`}>
              {badge.text}
            </span>
          )}
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-zinc-400" /> : <ChevronRight className="w-4 h-4 text-zinc-400" />}
      </button>
      
      {isOpen && (
        <div className="p-4 bg-zinc-950/50 space-y-2">
          {commands.map((cmd, idx) => (
            <div key={idx} className="flex items-start justify-between gap-4 py-2 border-b border-zinc-800/50 last:border-0">
              <div className="flex-1">
                <div className="flex items-center gap-2 flex-wrap">
                  <code className="text-orange-400 font-mono text-sm bg-zinc-800/50 px-2 py-0.5 rounded">
                    {cmd.command}
                  </code>
                  {cmd.hot && (
                    <span className="text-xs bg-red-500/20 text-red-300 px-1.5 py-0.5 rounded">HOT</span>
                  )}
                  {cmd.new && (
                    <span className="text-xs bg-green-500/20 text-green-300 px-1.5 py-0.5 rounded">NEW</span>
                  )}
                  <button 
                    onClick={() => copyCommand(cmd.command)}
                    className="p-1 hover:bg-zinc-700 rounded transition-colors"
                  >
                    {copiedCmd === cmd.command ? 
                      <Check className="w-3 h-3 text-green-400" /> : 
                      <Copy className="w-3 h-3 text-zinc-500" />
                    }
                  </button>
                </div>
                <p className="text-zinc-400 text-sm mt-1">{cmd.description}</p>
                {cmd.example && (
                  <p className="text-zinc-500 text-xs mt-1 font-mono">
                    Example: {cmd.example}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export const CommandsReference = () => {
  const [openCategories, setOpenCategories] = useState(['engines', 'paper', 'analysis']);

  const toggleCategory = (cat) => {
    setOpenCategories(prev => 
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const categories = [
    {
      id: 'engines',
      title: 'Trading Engines',
      icon: Rocket,
      color: 'text-red-400',
      badge: { text: '7 ENGINES', color: 'bg-red-500/20 text-red-300' },
      commands: [
        { command: '/auto', description: 'Main Autonomous Trader v2 status (80% conf, 3 confirms)', hot: true },
        { command: '/auto on', description: 'Enable autonomous trading' },
        { command: '/auto off', description: 'Pause autonomous trading' },
        { command: '/mode easy', description: 'Set Easy mode (70% conf, 2 confirms) - more trades', new: true },
        { command: '/mode balanced', description: 'Set Balanced mode (80% conf, 3 confirms) - default' },
        { command: '/mode strict', description: 'Set Strict mode (85% conf, 4 confirms) - selective' },
        { command: '/mode elite', description: 'Set Elite mode (90% conf, 5 confirms) - ultra selective' },
        { command: '/fw', description: 'Free Will Engine status (75% conf, 2 confirms)' },
        { command: '/fw on', description: 'Enable Free Will proactive alerts' },
        { command: '/dual', description: 'Dual Engine status (Day Trader + Long Term)' },
        { command: '/yolo', description: 'YOLO Engine status (50% conf, 1 confirm) - MAX aggression', hot: true },
        { command: '/yolo scan', description: 'Run immediate YOLO scan across all markets' },
        { command: '/yolo on', description: 'Enable YOLO Engine' },
        { command: '/vwap', description: 'VWAP Scalper status (70% conf, EMA cross + RSI)', new: true },
        { command: '/vwap scan', description: 'Run VWAP scan for signals' },
        { command: '/vwap btc', description: 'Analyze specific symbol with VWAP strategy', example: '/vwap eth' },
        { command: '/elite', description: 'Elite Strategy status (90% conf, 5 confirms)' },
      ]
    },
    {
      id: 'paper',
      title: 'Paper Trading',
      icon: Wallet,
      color: 'text-green-400',
      badge: { text: 'LIVE', color: 'bg-green-500/20 text-green-300' },
      commands: [
        { command: '/accounts', description: 'View both paper accounts (PRO $50K + STARTER $1.5K)', hot: true },
        { command: '/pro', description: 'View PRO account details & positions' },
        { command: '/starter', description: 'View STARTER account details & positions' },
        { command: '/paper btc', description: 'View paper position for specific symbol', example: '/paper eth' },
        { command: '/addmargin pro 1000', description: 'Add margin to account', example: '/addmargin starter 500' },
        { command: '/open', description: 'View all open positions across accounts' },
        { command: '/close btc', description: 'Manually close a position' },
        { command: '/tp btc 72000', description: 'Set take profit price', example: '/tp eth 2500' },
        { command: '/sl btc 65000', description: 'Set stop loss price', example: '/sl eth 1800' },
        { command: '/trail btc 5', description: 'Set trailing stop percentage', example: '/trail eth 3' },
      ]
    },
    {
      id: 'analysis',
      title: 'Market Analysis',
      icon: TrendingUp,
      color: 'text-blue-400',
      commands: [
        { command: '/scan btc', description: 'Full SMC analysis with entry, targets, stop-loss', hot: true },
        { command: '/ta btc 1h', description: 'Technical indicators (RSI, MACD, BB, EMA)', example: '/ta eth 4h' },
        { command: '/mtf btc', description: 'Multi-timeframe confluence (1h + 4h + 1d)' },
        { command: '/smc btc', description: 'Smart Money Concepts - order blocks, FVG, liquidity' },
        { command: '/structure btc', description: 'Market structure analysis (HH/HL/LH/LL)' },
        { command: '/sentiment btc', description: 'Sentiment analysis with score' },
        { command: '/divergence btc', description: 'RSI/MACD divergence detection' },
        { command: '/price', description: 'Live MEXC prices for major coins' },
      ]
    },
    {
      id: 'derivatives',
      title: 'Derivatives Data',
      icon: LineChart,
      color: 'text-purple-400',
      commands: [
        { command: '/funding btc', description: 'Funding rates from OKX, Bitget, KuCoin, Gate.io' },
        { command: '/deriv btc', description: 'Full derivatives report (funding + OI + L/S ratio)' },
        { command: '/positions btc', description: 'Long/short ratio and positioning data' },
        { command: '/liqs btc', description: 'Liquidation data and market stress levels' },
        { command: '/options btc', description: 'Max pain & Put/Call ratio' },
        { command: '/cvd btc', description: 'Order flow / Cumulative Volume Delta' },
        { command: '/cg btc', description: 'Coinglass data (requires API key)' },
      ]
    },
    {
      id: 'intel',
      title: 'Market Intelligence',
      icon: Globe,
      color: 'text-cyan-400',
      commands: [
        { command: '/market', description: 'Global market summary with BTC dominance' },
        { command: '/fear', description: 'Fear & Greed Index with interpretation' },
        { command: '/top100', description: 'Top 10 coins by market cap' },
        { command: '/movers', description: 'Top gainers and losers (24h)' },
        { command: '/trending', description: 'Most searched/trending coins' },
        { command: '/opps', description: 'Current market opportunities (85%+ confidence)', hot: true },
      ]
    },
    {
      id: 'news',
      title: 'News & On-Chain',
      icon: Newspaper,
      color: 'text-yellow-400',
      commands: [
        { command: '/news', description: 'Latest crypto headlines with sentiment' },
        { command: '/whales', description: 'Whale activity (transactions >10 BTC)' },
        { command: '/onchain', description: 'BTC network stats (fees, hashrate, mempool)' },
      ]
    },
    {
      id: 'calculators',
      title: 'Futures Calculators',
      icon: Calculator,
      color: 'text-pink-400',
      commands: [
        { command: '/calc 65000 68000 1000 10 long', description: 'Calculate PnL, ROI, liquidation', example: '/calc entry exit size leverage direction' },
        { command: '/calcsize 10000 2 65000 63000 10', description: 'Position size from risk %', example: '/calcsize balance risk% entry stop leverage' },
      ]
    },
    {
      id: 'alerts',
      title: 'Price Alerts',
      icon: Bell,
      color: 'text-red-400',
      commands: [
        { command: '/alerts', description: 'View current alerts' },
        { command: '/alert add btc above 70000', description: 'Add price alert' },
        { command: '/alert remove [id]', description: 'Remove an alert' },
      ]
    },
    {
      id: 'learning',
      title: '24/7 Learning',
      icon: Brain,
      color: 'text-violet-400',
      badge: { text: 'AI', color: 'bg-violet-500/20 text-violet-300' },
      commands: [
        { command: '/learn', description: 'Learning engine status & patterns learned', new: true },
        { command: '/insights', description: 'AI-generated trading insights' },
        { command: '/journal', description: 'Performance stats and trade history' },
        { command: '/strat btc', description: 'Run all strategies on a coin' },
      ]
    },
    {
      id: 'personas',
      title: 'Personas & Modes',
      icon: MessageSquare,
      color: 'text-amber-400',
      commands: [
        { command: 'alchemy mode', description: 'Mystical trading wisdom - symbols, riddles, probing questions' },
        { command: 'philosopher mode', description: 'Same as alchemy mode' },
        { command: 'casual mode', description: 'Return to default sharp trading buddy' },
        { command: 'just talk', description: 'Exit mystical mode, casual conversation' },
        { command: '/probe', description: 'Standard introspection question' },
        { command: '/probe deep', description: 'Multi-layer spiral questions' },
        { command: '/probe ordeal', description: 'Shadow work / harsh truth mode' },
      ]
    },
    {
      id: 'system',
      title: 'System & Health',
      icon: Shield,
      color: 'text-emerald-400',
      commands: [
        { command: '/status', description: 'Overall system health & all engines status' },
        { command: '/stats', description: 'Trading statistics summary' },
        { command: '/health', description: 'Self-healer status & service monitoring' },
        { command: '/help', description: 'Quick command reference' },
      ]
    },
  ];

  return (
    <div className="space-y-6" data-testid="commands-reference">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <Settings className="w-5 h-5 text-orange-400" />
          Command Reference
        </h2>
        <div className="flex gap-2">
          <button 
            onClick={() => setOpenCategories(categories.map(c => c.id))}
            className="text-xs text-zinc-400 hover:text-white px-2 py-1 border border-zinc-700 rounded"
          >
            Expand All
          </button>
          <button 
            onClick={() => setOpenCategories([])}
            className="text-xs text-zinc-400 hover:text-white px-2 py-1 border border-zinc-700 rounded"
          >
            Collapse All
          </button>
        </div>
      </div>

      {/* Quick Stats Banner */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 text-center">
          <Rocket className="w-5 h-5 text-red-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-white">7</p>
          <p className="text-xs text-zinc-500">Trading Engines</p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 text-center">
          <Activity className="w-5 h-5 text-green-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-white">80+</p>
          <p className="text-xs text-zinc-500">Commands</p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 text-center">
          <DollarSign className="w-5 h-5 text-amber-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-white">2</p>
          <p className="text-xs text-zinc-500">Paper Accounts</p>
        </div>
        <div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-3 text-center">
          <Brain className="w-5 h-5 text-purple-400 mx-auto mb-1" />
          <p className="text-lg font-bold text-white">24/7</p>
          <p className="text-xs text-zinc-500">AI Learning</p>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="bg-gradient-to-r from-orange-500/10 to-red-500/10 border border-orange-500/30 rounded-lg p-4">
        <div className="flex items-center gap-2 mb-3">
          <Zap className="w-4 h-4 text-orange-400" />
          <span className="text-sm font-medium text-white">Quick Start Commands</span>
        </div>
        <div className="flex flex-wrap gap-2">
          <code className="text-xs bg-zinc-800 text-orange-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/auto</code>
          <code className="text-xs bg-zinc-800 text-green-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/accounts</code>
          <code className="text-xs bg-zinc-800 text-blue-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/scan btc</code>
          <code className="text-xs bg-zinc-800 text-red-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/yolo</code>
          <code className="text-xs bg-zinc-800 text-purple-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/opps</code>
          <code className="text-xs bg-zinc-800 text-cyan-300 px-2 py-1 rounded cursor-pointer hover:bg-zinc-700">/market</code>
        </div>
      </div>

      {/* Command Categories */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {categories.map(cat => (
          <CommandCategory
            key={cat.id}
            {...cat}
            isOpen={openCategories.includes(cat.id)}
            onToggle={() => toggleCategory(cat.id)}
          />
        ))}
      </div>

      {/* Supported Pairs */}
      <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-white mb-2">Supported Trading Pairs (44 Total)</h3>
        <div className="text-xs text-zinc-400 space-y-1">
          <p><span className="text-orange-400">Major:</span> BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, SHIB, DOT</p>
          <p><span className="text-blue-400">DeFi/L1:</span> LINK, TRX, BCH, LTC, NEAR, UNI, APT, ICP, ETC, FIL, ATOM, XLM</p>
          <p><span className="text-green-400">L2/Infra:</span> ARB, OP, INJ, HBAR, VET, GRT, AAVE, ALGO</p>
          <p><span className="text-pink-400">Gaming:</span> SAND, AXS, MANA, ENJ, CHZ, FLOW</p>
          <p><span className="text-yellow-400">Others:</span> XTZ, NEO, SNX, CRV, RUNE, ZEC, DASH, COMP</p>
        </div>
      </div>

      {/* Scheduled Events */}
      <div className="bg-gradient-to-r from-purple-500/10 to-blue-500/10 border border-purple-500/30 rounded-lg p-4">
        <h3 className="text-sm font-medium text-purple-300 mb-2 flex items-center gap-2">
          <RefreshCw className="w-4 h-4" />
          Automated Schedules
        </h3>
        <ul className="text-xs text-zinc-300 space-y-1">
          <li>06:00 AM CT - Daily market briefing</li>
          <li>08:00 PM CT (Sunday) - Weekly performance report</li>
          <li>Every 30 sec - Paper trading price updates</li>
          <li>Every 3 min - YOLO Engine scan</li>
          <li>Every 5 min - VWAP Scalper scan</li>
          <li>Every 2 hours - Free Will proactive alerts</li>
          <li>Hourly - Learning engine pattern analysis</li>
        </ul>
      </div>
    </div>
  );
};

export default CommandsReference;
