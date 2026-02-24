import React, { useState, useEffect } from 'react';
import { 
  Bot, Activity, TrendingUp, Target, Users, BarChart3, 
  MessageCircle, Brain, Zap, AlertTriangle, Radio, Power,
  Flame, ChevronRight, Ban, ThumbsUp, ThumbsDown, Timer, Scale, FlaskConical, Bell
} from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import BacktestV21Modal from './BacktestV21Modal';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export default function Dashboard({ 
  stats, 
  tradingStats, 
  mexcData, 
  messages, 
  formatRelativeTime,
  onQuickScan,
  onNavigate
}) {
  const [livePositions, setLivePositions] = useState([]);
  const [dashboardStats, setDashboardStats] = useState(null);
  const [pnlGoal, setPnlGoal] = useState({ daily: 5, weekly: 25 });
  const [showKillSwitch, setShowKillSwitch] = useState(false);

  // Fetch live positions for quick view
  useEffect(() => {
    const fetchPositions = async () => {
      try {
        const res = await fetch(`${API_URL}/api/trading/v2/live-positions`);
        const data = await res.json();
        setLivePositions(data.positions || []);
      } catch (err) {
        console.error('Failed to fetch positions:', err);
      }
    };
    fetchPositions();
    const interval = setInterval(fetchPositions, 10000);
    return () => clearInterval(interval);
  }, []);

  // Fetch dashboard stats (best/worst pairs, blacklist, scaling)
  useEffect(() => {
    const fetchDashboardStats = async () => {
      try {
        const res = await fetch(`${API_URL}/api/stats/dashboard`);
        const data = await res.json();
        setDashboardStats(data);
      } catch (err) {
        console.error('Failed to fetch dashboard stats:', err);
      }
    };
    fetchDashboardStats();
    const interval = setInterval(fetchDashboardStats, 30000);
    return () => clearInterval(interval);
  }, []);

  // Calculate total leverage exposure
  const totalLeverageExposure = livePositions.reduce((sum, p) => 
    sum + ((p.position_size || 1000) * (p.leverage || 10) / 1000), 0
  );

  // Kill Switch - Close all positions
  const handleKillSwitch = async () => {
    if (!window.confirm('EMERGENCY: Close ALL positions immediately?')) return;
    try {
      await fetch(`${API_URL}/api/trading/v2/close-all`, { method: 'POST' });
      setShowKillSwitch(false);
      alert('All positions closed!');
    } catch (err) {
      console.error('Kill switch failed:', err);
      alert('Failed to close positions. Try manually.');
    }
  };

  // Calculate daily progress
  const dailyProgress = Math.min(100, ((tradingStats?.total_pnl_pct || 0) / pnlGoal.daily) * 100);

  return (
    <div className="space-y-6" data-testid="dashboard-page">
      {/* Quick Actions Bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <button
          onClick={() => onNavigate('trading')}
          data-testid="quick-trading-btn"
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-orange-500 to-amber-600 rounded-lg text-white font-medium hover:from-orange-600 hover:to-amber-700 transition-all"
        >
          <Zap className="w-4 h-4" />
          Quick Trade
        </button>
        <button
          onClick={() => onNavigate('alerts')}
          className="flex items-center gap-2 px-4 py-2 bg-zinc-800/50 rounded-lg text-zinc-300 hover:bg-zinc-700 transition-all"
        >
          <Bell className="w-4 h-4" />
          View Alerts
        </button>
        <button
          onClick={() => setShowKillSwitch(true)}
          data-testid="kill-switch-btn"
          className="flex items-center gap-2 px-4 py-2 bg-red-500/20 border border-red-500/30 rounded-lg text-red-400 hover:bg-red-500/30 transition-all ml-auto"
        >
          <Power className="w-4 h-4" />
          Kill Switch
        </button>
      </div>

      {/* Kill Switch Modal */}
      {showKillSwitch && (
        <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-zinc-900 border border-red-500/50 rounded-2xl p-6 max-w-md w-full">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-3 bg-red-500/20 rounded-xl">
                <AlertTriangle className="w-8 h-8 text-red-400" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-white">Emergency Kill Switch</h3>
                <p className="text-zinc-400 text-sm">Close ALL {livePositions.length} open positions</p>
              </div>
            </div>
            <p className="text-zinc-300 mb-6">
              This will immediately close all open positions at market price. This action cannot be undone.
            </p>
            <div className="flex gap-3">
              <button
                onClick={handleKillSwitch}
                className="flex-1 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-bold transition-all"
              >
                CLOSE ALL POSITIONS
              </button>
              <button
                onClick={() => setShowKillSwitch(false)}
                className="px-6 py-3 bg-zinc-700 hover:bg-zinc-600 text-white rounded-lg transition-all"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Status</p>
                <p className={`text-lg font-bold ${tradingStats?.active ? 'text-green-400' : 'text-zinc-400'}`}>
                  {tradingStats?.active ? 'ACTIVE' : 'PAUSED'}
                </p>
              </div>
              <Bot className={`w-8 h-8 ${tradingStats?.active ? 'text-orange-400' : 'text-zinc-600'}`} />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Win Rate</p>
                <p className="text-lg font-bold text-green-400">{tradingStats?.win_rate || 0}%</p>
              </div>
              <Target className="w-8 h-8 text-green-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Total PnL</p>
                <p className={`text-lg font-bold ${(tradingStats?.total_pnl_pct || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                  {(tradingStats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(tradingStats?.total_pnl_pct || 0).toFixed(2)}%
                </p>
              </div>
              <TrendingUp className="w-8 h-8 text-orange-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Open Trades</p>
                <p className="text-lg font-bold text-orange-400">{livePositions.length}</p>
              </div>
              <Activity className="w-8 h-8 text-orange-400" />
            </div>
          </CardContent>
        </Card>

        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Leverage</p>
                <p className={`text-lg font-bold ${totalLeverageExposure > 50 ? 'text-red-400' : totalLeverageExposure > 20 ? 'text-yellow-400' : 'text-green-400'}`}>
                  {totalLeverageExposure.toFixed(0)}x
                </p>
              </div>
              <Flame className="w-8 h-8 text-yellow-400" />
            </div>
          </CardContent>
        </Card>
        
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-zinc-500 text-xs">Users</p>
                <p className="text-lg font-bold text-white">{stats?.unique_users || 0}</p>
              </div>
              <Users className="w-8 h-8 text-blue-400" />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* PnL Goal Tracker */}
      <Card className="bg-gradient-to-r from-zinc-800/50 to-zinc-900/50 border-zinc-700/50">
        <CardContent className="p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-orange-400" />
              <span className="text-white font-medium">Daily Goal Progress</span>
            </div>
            <span className={`text-sm font-bold ${dailyProgress >= 100 ? 'text-green-400' : 'text-orange-400'}`}>
              {dailyProgress >= 100 ? 'GOAL REACHED!' : `${dailyProgress.toFixed(0)}%`}
            </span>
          </div>
          <div className="h-3 bg-zinc-700 rounded-full overflow-hidden">
            <div 
              className={`h-full transition-all duration-500 ${dailyProgress >= 100 ? 'bg-green-500' : 'bg-gradient-to-r from-orange-500 to-amber-500'}`}
              style={{ width: `${Math.min(100, dailyProgress)}%` }}
            />
          </div>
          <div className="flex justify-between mt-2 text-xs text-zinc-500">
            <span>Current: {(tradingStats?.total_pnl_pct || 0).toFixed(2)}%</span>
            <span>Target: +{pnlGoal.daily}%</span>
          </div>
        </CardContent>
      </Card>

      {/* Live Positions Preview */}
      {livePositions.length > 0 && (
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Radio className="w-5 h-5 text-green-400 animate-pulse" />
                <span className="text-white font-medium">Live Positions</span>
              </div>
              <button 
                onClick={() => onNavigate('trading')}
                className="text-orange-400 text-sm hover:text-orange-300 flex items-center gap-1"
              >
                View All <ChevronRight className="w-4 h-4" />
              </button>
            </div>
            <div className="space-y-2">
              {livePositions.slice(0, 4).map((pos, i) => {
                const pnlWithLev = (pos.pnl_pct || 0) * (pos.leverage || 10);
                return (
                  <div 
                    key={i}
                    className={`flex items-center justify-between p-3 rounded-lg border ${
                      pos.direction === 'LONG' ? 'bg-green-500/5 border-green-500/20' : 'bg-red-500/5 border-red-500/20'
                    }`}
                  >
                    <div className="flex items-center gap-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                        pos.direction === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                      }`}>
                        {pos.direction}
                      </span>
                      <span className="text-white font-medium">{pos.symbol?.replace('/USDT', '')}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        pos.trade_type === 'SCALP' ? 'bg-purple-500/20 text-purple-400' :
                        pos.trade_type === 'DAY' ? 'bg-blue-500/20 text-blue-400' : 'bg-amber-500/20 text-amber-400'
                      }`}>
                        {pos.trade_type || 'SWING'}
                      </span>
                      <span className="text-orange-400 text-xs">{pos.leverage || 10}x</span>
                    </div>
                    <span className={`font-bold ${pnlWithLev >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {pnlWithLev >= 0 ? '+' : ''}{pnlWithLev.toFixed(2)}%
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Performance & Risk Management Stats */}
      {dashboardStats && (
        <div className="grid md:grid-cols-3 gap-4" data-testid="dashboard-stats">
          {/* Best Performing Pairs */}
          <Card className="bg-zinc-800/30 border-zinc-700/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <ThumbsUp className="w-5 h-5 text-green-400" />
                <span className="text-white font-medium">Best Pairs</span>
              </div>
              <div className="space-y-2">
                {dashboardStats.best_pairs?.length > 0 ? (
                  dashboardStats.best_pairs.map((pair, i) => (
                    <div key={i} className="flex items-center justify-between py-1 border-b border-zinc-800 last:border-0">
                      <span className="text-zinc-300">{pair.symbol?.replace('/USDT', '')}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-green-400 font-medium">{pair.win_rate?.toFixed(0)}%</span>
                        <span className="text-zinc-500 text-xs">({pair.trades} trades)</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-zinc-500 text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Worst Performing Pairs */}
          <Card className="bg-zinc-800/30 border-zinc-700/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <ThumbsDown className="w-5 h-5 text-red-400" />
                <span className="text-white font-medium">Worst Pairs</span>
              </div>
              <div className="space-y-2">
                {dashboardStats.worst_pairs?.length > 0 ? (
                  dashboardStats.worst_pairs.map((pair, i) => (
                    <div key={i} className="flex items-center justify-between py-1 border-b border-zinc-800 last:border-0">
                      <span className="text-zinc-300">{pair.symbol?.replace('/USDT', '')}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-red-400 font-medium">{pair.win_rate?.toFixed(0)}%</span>
                        <span className="text-zinc-500 text-xs">({pair.trades} trades)</span>
                      </div>
                    </div>
                  ))
                ) : (
                  <p className="text-zinc-500 text-sm">No data yet</p>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Blacklist & Cooldowns */}
          <Card className="bg-zinc-800/30 border-zinc-700/50">
            <CardContent className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Ban className="w-5 h-5 text-yellow-400" />
                <span className="text-white font-medium">Risk Management</span>
              </div>
              <div className="space-y-3">
                {/* Blacklisted */}
                <div>
                  <p className="text-zinc-500 text-xs mb-1">Auto-Blacklisted ({dashboardStats.blacklisted_pairs?.length || 0})</p>
                  {dashboardStats.blacklisted_pairs?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {dashboardStats.blacklisted_pairs.map((pair, i) => (
                        <span key={i} className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">
                          {pair.replace('/USDT', '')}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-green-400 text-xs">None</p>
                  )}
                </div>
                
                {/* Cooldowns */}
                <div>
                  <p className="text-zinc-500 text-xs mb-1">On Cooldown ({dashboardStats.pairs_on_cooldown?.length || 0})</p>
                  {dashboardStats.pairs_on_cooldown?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {dashboardStats.pairs_on_cooldown.map((pair, i) => (
                        <span key={i} className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded flex items-center gap-1">
                          <Timer className="w-3 h-3" />
                          {pair.symbol?.replace('/USDT', '')} ({pair.minutes_left}m)
                        </span>
                      ))}
                    </div>
                  ) : (
                    <p className="text-green-400 text-xs">None</p>
                  )}
                </div>

                {/* Position Scaling */}
                <div className="pt-2 border-t border-zinc-700">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1">
                      <Scale className="w-3 h-3 text-cyan-400" />
                      <span className="text-zinc-400 text-xs">Position Scaling</span>
                    </div>
                    <span className={`text-xs font-medium ${dashboardStats.position_scaling?.enabled ? 'text-green-400' : 'text-zinc-500'}`}>
                      {dashboardStats.position_scaling?.enabled ? 'ON' : 'OFF'}
                    </span>
                  </div>
                  {dashboardStats.position_scaling?.pending_scale_ins > 0 && (
                    <p className="text-cyan-400 text-xs mt-1">
                      {dashboardStats.position_scaling.pending_scale_ins} positions awaiting scale-in
                    </p>
                  )}
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Market Data */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-white flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-orange-400" />
          Live Market Data
          <span className="text-xs text-zinc-500 font-normal ml-2">Click any coin for instant analysis</span>
        </h2>
        <div className="grid md:grid-cols-3 gap-4">
          {mexcData?.symbols?.map((sym, i) => (
            <Card 
              key={i} 
              className="bg-zinc-800/30 border-zinc-700/50 cursor-pointer hover:bg-zinc-800/50 hover:border-orange-500/30 transition-all group"
              onClick={() => onQuickScan(sym.symbol?.replace('/USDT', '').replace('USDT', ''))}
              data-testid={`market-card-${sym.symbol?.replace('/USDT', '').replace('USDT', '')}`}
            >
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="font-semibold text-white group-hover:text-orange-400 transition-colors">{sym.symbol?.replace('/USDT', '')}</span>
                  <span className={`text-sm font-medium ${
                    (sym.change_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {(sym.change_24h || 0) >= 0 ? '↗' : '↘'} {Math.abs(sym.change_24h || 0).toFixed(2)}%
                  </span>
                </div>
                <p className="text-2xl font-bold text-white">
                  ${(sym.price || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                </p>
                <div className="mt-3 flex items-center gap-2">
                  <div className="flex-1 h-2 bg-zinc-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full ${sym.imbalance >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                      style={{ width: `${50 + (sym.imbalance || 0) / 2}%` }}
                    />
                  </div>
                  <span className="text-xs text-zinc-500">{(sym.imbalance || 0).toFixed(0)}%</span>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Trading Intelligence & Activity */}
      <div className="grid md:grid-cols-2 gap-6">
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Brain className="w-5 h-5 text-orange-400" />
              AI Engine Status
            </h3>
            <div className="space-y-4">
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Market Regime</span>
                <span className={`font-medium px-2 py-1 rounded ${
                  tradingStats?.market_regime === 'TRENDING_UP' ? 'bg-green-500/20 text-green-400' :
                  tradingStats?.market_regime === 'TRENDING_DOWN' ? 'bg-red-500/20 text-red-400' :
                  tradingStats?.market_regime === 'VOLATILE' ? 'bg-yellow-500/20 text-yellow-400' :
                  'bg-zinc-700 text-zinc-300'
                }`}>{tradingStats?.market_regime || 'Unknown'}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">BTC Bias</span>
                <span className={`font-medium ${
                  tradingStats?.btc_bias === 'BULLISH' ? 'text-green-400' :
                  tradingStats?.btc_bias === 'BEARISH' ? 'text-red-400' : 'text-zinc-400'
                }`}>{tradingStats?.btc_bias || 'Neutral'}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Fear & Greed</span>
                <span className={`font-medium ${
                  (tradingStats?.fear_greed || 50) > 60 ? 'text-green-400' :
                  (tradingStats?.fear_greed || 50) < 40 ? 'text-red-400' : 'text-yellow-400'
                }`}>{tradingStats?.fear_greed || 50}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-zinc-400">Trade Styles</span>
                <div className="flex gap-1">
                  <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">SCALP</span>
                  <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">DAY</span>
                  <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">SWING</span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Recent Messages */}
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-orange-400" />
              Recent Activity
            </h3>
            <ScrollArea className="h-64">
              <div className="space-y-3">
                {messages?.slice(0, 10).map((msg, i) => (
                  <div key={i} className="flex gap-3 p-2 rounded-lg hover:bg-zinc-800/50 transition-colors">
                    <div className="w-8 h-8 rounded-full bg-zinc-700 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs">{msg.username?.[0]?.toUpperCase() || '?'}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-white">{msg.username || 'User'}</span>
                        <span className="text-xs text-zinc-600">{formatRelativeTime(msg.timestamp)}</span>
                      </div>
                      <p className="text-sm text-zinc-400 truncate">{msg.text}</p>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Bell icon component (since it's not in the imports)
const Bell = ({ className }) => (
  <svg className={className} fill="none" viewBox="0 0 24 24" stroke="currentColor">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
  </svg>
);
