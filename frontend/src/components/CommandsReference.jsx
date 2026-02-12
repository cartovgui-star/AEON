import React, { useState } from 'react';
import { 
  MessageSquare, TrendingUp, Wallet, Globe, Newspaper, Calculator, 
  Bot, Target, Bell, BookOpen, Brain, Settings, ChevronDown, ChevronRight,
  Copy, Check, Zap, Moon, Sun
} from 'lucide-react';

const CommandCategory = ({ title, icon: Icon, commands, color, isOpen, onToggle }) => {
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
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-zinc-400" /> : <ChevronRight className="w-4 h-4 text-zinc-400" />}
      </button>
      
      {isOpen && (
        <div className="p-4 bg-zinc-950/50 space-y-2">
          {commands.map((cmd, idx) => (
            <div key={idx} className="flex items-start justify-between gap-4 py-2 border-b border-zinc-800/50 last:border-0">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <code className="text-orange-400 font-mono text-sm bg-zinc-800/50 px-2 py-0.5 rounded">
                    {cmd.command}
                  </code>
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
  const [openCategories, setOpenCategories] = useState(['personas', 'analysis']);

  const toggleCategory = (cat) => {
    setOpenCategories(prev => 
      prev.includes(cat) ? prev.filter(c => c !== cat) : [...prev, cat]
    );
  };

  const categories = [
    {
      id: 'personas',
      title: 'Personas',
      icon: MessageSquare,
      color: 'text-purple-400',
      commands: [
        { command: 'alchemy mode', description: 'Mystical trading wisdom - symbols, riddles, probing questions' },
        { command: 'philosopher mode', description: 'Same as alchemy mode' },
        { command: 'casual mode', description: 'Return to default sharp trading buddy' },
        { command: 'just talk', description: 'Exit mystical mode, casual conversation' },
      ]
    },
    {
      id: 'analysis',
      title: 'Market Analysis',
      icon: TrendingUp,
      color: 'text-blue-400',
      commands: [
        { command: '/scan btc', description: 'Full market analysis with entry, target, and stop-loss levels' },
        { command: '/ta btc 1h', description: 'Technical indicators (RSI, MACD, BB, EMA, Stoch)', example: '/ta eth 4h' },
        { command: '/mtf btc', description: 'Multi-timeframe confluence analysis (1h, 4h, 1d)' },
        { command: '/sentiment btc', description: 'Sentiment analysis with score and signals' },
        { command: '/price', description: 'Live MEXC orderbook for BTC, ETH, SOL' },
      ]
    },
    {
      id: 'derivatives',
      title: 'Derivatives Data',
      icon: Wallet,
      color: 'text-green-400',
      commands: [
        { command: '/funding btc', description: 'Aggregated funding rates from OKX, Bitget, KuCoin, Gate.io' },
        { command: '/deriv btc', description: 'Full derivatives report (funding + OI + L/S ratio)' },
        { command: '/positions btc', description: 'Long/short ratio and positioning data' },
        { command: '/liqs btc', description: 'Liquidation data and market stress levels' },
        { command: '/cg btc', description: 'Coinglass data (requires API key)' },
      ]
    },
    {
      id: 'intel',
      title: 'Market Intelligence',
      icon: Globe,
      color: 'text-cyan-400',
      commands: [
        { command: '/market', description: 'Global market summary' },
        { command: '/fear', description: 'Fear & Greed Index with interpretation' },
        { command: '/top100', description: 'Top 10 coins by market cap' },
        { command: '/movers', description: 'Top gainers and losers (24h)' },
        { command: '/trending', description: 'Most searched/trending coins' },
      ]
    },
    {
      id: 'news',
      title: 'News & On-Chain',
      icon: Newspaper,
      color: 'text-yellow-400',
      commands: [
        { command: '/news', description: 'Latest crypto headlines with clickable links + sentiment' },
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
        { command: '/calc 65000 68000 1000 10 long', description: 'Calculate PnL, ROI, liquidation price', example: '/calc entry exit size leverage direction' },
        { command: '/calcsize 10000 2 65000 63000 10', description: 'Calculate position size from risk', example: '/calcsize balance risk% entry stop leverage' },
      ]
    },
    {
      id: 'auto',
      title: 'Autonomous Trading',
      icon: Bot,
      color: 'text-orange-400',
      commands: [
        { command: '/auto', description: 'Trading status & paper trading stats' },
        { command: '/auto on', description: 'Enable autonomous trading' },
        { command: '/auto off', description: 'Pause autonomous trading' },
        { command: '/opps', description: 'Current market opportunities (85%+ confidence)' },
        { command: '/open', description: 'View open positions' },
        { command: '/close btc', description: 'Manually close a position' },
        { command: '/trail btc 5', description: 'Set trailing stop to 5%' },
        { command: '/tp btc 72000', description: 'Set take profit price' },
      ]
    },
    {
      id: 'freewill',
      title: 'Free Will Engine (24/7)',
      icon: Zap,
      color: 'text-amber-400',
      commands: [
        { command: '/fw', description: 'View Free Will status & stats' },
        { command: '/fwconf 80', description: 'Set minimum confidence (50-95%)', example: '/fwconf 70' },
        { command: 'free on', description: 'Enable proactive alerts' },
        { command: 'free off', description: 'Disable proactive alerts' },
      ]
    },
    {
      id: 'smc',
      title: 'Smart Money (SMC)',
      icon: Target,
      color: 'text-indigo-400',
      commands: [
        { command: '/smc btc', description: 'Full SMC analysis - order blocks, FVG, liquidity' },
        { command: '/structure btc', description: 'Market structure (HH/HL/LH/LL)' },
        { command: '/vwap btc', description: 'VWAP levels' },
        { command: '/cvd btc', description: 'Order flow / Cumulative Volume Delta' },
        { command: '/options btc', description: 'Max pain & Put/Call ratio' },
      ]
    },
    {
      id: 'alerts',
      title: 'Price Alerts',
      icon: Bell,
      color: 'text-red-400',
      commands: [
        { command: '/alerts', description: 'View current alert status' },
        { command: '/alert add btc above 70000', description: 'Add price alert' },
        { command: '/alert remove [id]', description: 'Remove an alert' },
      ]
    },
    {
      id: 'journal',
      title: 'Journal & Memory',
      icon: BookOpen,
      color: 'text-emerald-400',
      commands: [
        { command: '/journal', description: 'Performance stats and history' },
        { command: '/insights', description: 'AI-generated trading insights' },
        { command: '/strat btc', description: 'Run all strategies on a coin' },
      ]
    },
    {
      id: 'advanced',
      title: 'Advanced Analysis',
      icon: Brain,
      color: 'text-violet-400',
      commands: [
        { command: '/divergence btc', description: 'RSI/MACD divergence detection' },
        { command: '/probe', description: 'Standard introspection question' },
        { command: '/probe deep', description: 'Multi-layer spiral questions' },
        { command: '/probe ordeal', description: 'Shadow work / harsh truth mode' },
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

      <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4 mb-4">
        <div className="flex items-center gap-2 mb-2">
          <Moon className="w-4 h-4 text-purple-400" />
          <span className="text-sm font-medium text-white">Quick Mode Toggle</span>
        </div>
        <p className="text-zinc-400 text-sm">
          Say <code className="text-purple-400 bg-zinc-800 px-1 rounded">"alchemy mode"</code> for mystical wisdom or 
          <code className="text-orange-400 bg-zinc-800 px-1 rounded ml-1">"casual mode"</code> to return to normal.
        </p>
      </div>

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

      <div className="bg-zinc-900/30 border border-zinc-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-white mb-2">Supported Pairs (44 Total)</h3>
        <p className="text-xs text-zinc-400">
          <span className="text-orange-400">Major:</span> BTC, ETH, BNB, SOL, XRP, DOGE, ADA, AVAX, SHIB, DOT
          <br />
          <span className="text-blue-400">DeFi/L1:</span> LINK, TRX, BCH, LTC, NEAR, UNI, APT, ICP, ETC, FIL, ATOM, XLM
          <br />
          <span className="text-green-400">L2/Infra:</span> ARB, OP, INJ, HBAR, VET, GRT, AAVE, ALGO
          <br />
          <span className="text-pink-400">Gaming:</span> SAND, AXS, MANA, ENJ, CHZ, FLOW
          <br />
          <span className="text-yellow-400">Others:</span> XTZ, NEO, SNX, CRV, RUNE, ZEC, DASH, COMP
        </p>
      </div>

      <div className="bg-gradient-to-r from-orange-500/10 to-amber-500/10 border border-orange-500/30 rounded-lg p-4">
        <h3 className="text-sm font-medium text-orange-400 mb-2">Scheduled Rituals</h3>
        <ul className="text-xs text-zinc-300 space-y-1">
          <li>6:00 AM CST - Daily crypto market summary</li>
          <li>Proactive messages every 2 hours when Free Will is ON</li>
        </ul>
      </div>
    </div>
  );
};

export default CommandsReference;
