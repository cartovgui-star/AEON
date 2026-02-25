import React, { useState, useEffect } from 'react';
import { 
  Bot, Activity, TrendingUp, Target, Users, BarChart3, 
  MessageCircle, Brain, Zap, AlertTriangle, Radio, Power,
  Flame, ChevronRight, Ban, ThumbsUp, ThumbsDown, Timer, Scale, FlaskConical, Bell,
  Sparkles, Link2, Calendar, BookOpen, Lightbulb
} from 'lucide-react';
import { Card, CardContent } from './ui/card';
import { ScrollArea } from './ui/scroll-area';
import BacktestV21Modal from './BacktestV21Modal';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Format price based on value
const formatPrice = (price) => {
  if (!price) return '0.00';
  if (price > 1000) return price.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (price > 1) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return price.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
};

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
  const [showBacktestModal, setShowBacktestModal] = useState(false);
  const [v2Settings, setV2Settings] = useState(null);
  const [scalperStatus, setScalperStatus] = useState(null);
  const [weeklyReport, setWeeklyReport] = useState(null);
  const [learningStatus, setLearningStatus] = useState(null);

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

  // Fetch V2.1 settings
  useEffect(() => {
    const fetchV2Settings = async () => {
      try {
        const res = await fetch(`${API_URL}/api/trading/v2/settings`);
        const data = await res.json();
        if (!data.error) {
          setV2Settings(data);
        }
      } catch (err) {
        console.error('Failed to fetch V2 settings:', err);
      }
    };
    fetchV2Settings();
  }, []);

  // Fetch Scalper status
  useEffect(() => {
    const fetchScalperStatus = async () => {
      try {
        const [statusRes, learningRes] = await Promise.all([
          fetch(`${API_URL}/api/scalper/status`),
          fetch(`${API_URL}/api/scalper/learning/status`)
        ]);
        const statusData = await statusRes.json();
        const learningData = await learningRes.json();
        setScalperStatus({
          ...statusData,
          learning: learningData
        });
      } catch (err) {
        console.error('Failed to fetch scalper status:', err);
      }
    };
    fetchScalperStatus();
    const interval = setInterval(fetchScalperStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  // Fetch Weekly Report status
  useEffect(() => {
    const fetchWeeklyReport = async () => {
      try {
        const res = await fetch(`${API_URL}/api/report/status`);
        const data = await res.json();
        setWeeklyReport(data);
      } catch (err) {
        console.error('Failed to fetch weekly report:', err);
      }
    };
    fetchWeeklyReport();
  }, []);

  // Fetch Learning Engine status
  useEffect(() => {
    const fetchLearningStatus = async () => {
      try {
        const res = await fetch(`${API_URL}/api/learning/status`);
        const data = await res.json();
        setLearningStatus(data);
      } catch (err) {
        console.error('Failed to fetch learning status:', err);
      }
    };
    fetchLearningStatus();
    const interval = setInterval(fetchLearningStatus, 60000); // Every minute
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
    <div className="space-y-4 sm:space-y-6" data-testid="dashboard-page">
      {/* Quick Actions Bar - Mobile Scrollable */}
      <div className="flex items-center gap-2 sm:gap-3 overflow-x-auto pb-2 -mx-3 px-3 sm:mx-0 sm:px-0 sm:overflow-visible sm:flex-wrap no-scrollbar">
        <button
          onClick={() => onNavigate('trading')}
          data-testid="quick-trading-btn"
          className="flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 bg-gradient-to-r from-orange-500 to-amber-600 rounded-xl text-white font-medium hover:from-orange-600 hover:to-amber-700 transition-all shadow-lg shadow-orange-500/20 whitespace-nowrap touch-target"
        >
          <Zap className="w-4 h-4" />
          <span className="text-sm">Trade</span>
        </button>
        <button
          onClick={() => onNavigate('alerts')}
          className="flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 glass-card hover:bg-zinc-800/80 rounded-xl text-zinc-300 transition-all whitespace-nowrap touch-target"
        >
          <Bell className="w-4 h-4" />
          <span className="text-sm">Alerts</span>
        </button>
        <button
          onClick={() => setShowBacktestModal(true)}
          data-testid="quick-backtest-btn"
          className="flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-xl text-amber-400 hover:bg-amber-500/20 transition-all whitespace-nowrap touch-target"
        >
          <FlaskConical className="w-4 h-4" />
          <span className="text-sm">Backtest</span>
        </button>
        <button
          onClick={() => setShowKillSwitch(true)}
          data-testid="kill-switch-btn"
          className="flex items-center gap-2 px-3 sm:px-4 py-2 sm:py-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-400 hover:bg-rose-500/20 transition-all whitespace-nowrap touch-target sm:ml-auto"
        >
          <Power className="w-4 h-4" />
          <span className="text-sm">Kill</span>
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

      {/* Main Stats Grid - Mobile Optimized */}
      <div className="grid grid-cols-3 sm:grid-cols-3 md:grid-cols-6 gap-2 sm:gap-3">
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Status</p>
              <p className={`text-sm sm:text-lg font-display font-bold ${tradingStats?.active ? 'text-emerald-400' : 'text-zinc-400'}`}>
                {tradingStats?.active ? 'ACTIVE' : 'PAUSED'}
              </p>
            </div>
            <Bot className={`w-6 sm:w-8 h-6 sm:h-8 ${tradingStats?.active ? 'text-orange-400' : 'text-zinc-600'}`} />
          </div>
        </div>
        
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Win Rate</p>
              <p className="text-sm sm:text-lg font-mono font-bold text-emerald-400">{tradingStats?.win_rate || 0}%</p>
            </div>
            <Target className="w-6 sm:w-8 h-6 sm:h-8 text-emerald-400 hidden sm:block" />
          </div>
        </div>
        
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Total PnL</p>
              <p className={`text-sm sm:text-lg font-mono font-bold ${(tradingStats?.total_pnl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                {(tradingStats?.total_pnl_pct || 0) >= 0 ? '+' : ''}{(tradingStats?.total_pnl_pct || 0).toFixed(1)}%
              </p>
            </div>
            <TrendingUp className="w-6 sm:w-8 h-6 sm:h-8 text-orange-400 hidden sm:block" />
          </div>
        </div>
        
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Trades</p>
              <p className="text-sm sm:text-lg font-mono font-bold text-orange-400">{livePositions.length}</p>
            </div>
            <Activity className="w-6 sm:w-8 h-6 sm:h-8 text-orange-400 hidden sm:block" />
          </div>
        </div>

        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Leverage</p>
              <p className={`text-sm sm:text-lg font-mono font-bold ${totalLeverageExposure > 50 ? 'text-rose-400' : totalLeverageExposure > 20 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {totalLeverageExposure.toFixed(0)}x
              </p>
            </div>
            <Flame className="w-6 sm:w-8 h-6 sm:h-8 text-amber-400 hidden sm:block" />
          </div>
        </div>
        
        <div className="glass-card-hover p-3 sm:p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="data-label">Users</p>
              <p className="text-sm sm:text-lg font-mono font-bold text-white">{stats?.unique_users || 0}</p>
            </div>
            <Users className="w-6 sm:w-8 h-6 sm:h-8 text-blue-400 hidden sm:block" />
          </div>
        </div>
      </div>

      {/* PnL Goal Tracker */}
      <div className="glass-card p-4 glow-orange">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Target className="w-5 h-5 text-orange-400" />
            <span className="text-white font-medium font-display">Daily Goal Progress</span>
          </div>
          <span className={`text-sm font-bold font-mono ${dailyProgress >= 100 ? 'text-emerald-400' : 'text-orange-400'}`}>
            {dailyProgress >= 100 ? 'GOAL REACHED!' : `${dailyProgress.toFixed(0)}%`}
          </span>
        </div>
        <div className="h-2 bg-zinc-800 rounded-full overflow-hidden">
          <div 
            className={`h-full transition-all duration-500 ${dailyProgress >= 100 ? 'bg-emerald-500' : 'bg-gradient-to-r from-orange-500 to-amber-500'}`}
            style={{ width: `${Math.min(100, dailyProgress)}%` }}
          />
        </div>
        <div className="flex justify-between mt-2 text-xs text-zinc-500">
          <span className="font-mono">Current: {(tradingStats?.total_pnl_pct || 0).toFixed(2)}%</span>
          <span className="font-mono">Target: +{pnlGoal.daily}%</span>
        </div>
      </div>

      {/* Live Positions Preview */}
      {livePositions.length > 0 && (
        <div className="glass-card p-4">
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
                    <span className={`font-bold font-mono ${pnlWithLev >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {pnlWithLev >= 0 ? '+' : ''}{pnlWithLev.toFixed(2)}%
                    </span>
                  </div>
                );
              })}
            </div>
        </div>
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
          <span className="text-xs text-zinc-500 font-normal ml-2">
            {mexcData?.total || mexcData?.symbols?.length || 0} coins tracked • Click any for instant analysis
          </span>
        </h2>
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {mexcData?.symbols?.map((sym, i) => (
            <Card 
              key={i} 
              className="bg-zinc-800/30 border-zinc-700/50 cursor-pointer hover:bg-zinc-800/50 hover:border-orange-500/30 transition-all group"
              onClick={() => onQuickScan(sym.symbol?.replace('/USDT', '').replace('USDT', ''))}
              data-testid={`market-card-${sym.symbol?.replace('/USDT', '').replace('USDT', '')}`}
            >
              <CardContent className="p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-semibold text-white group-hover:text-orange-400 transition-colors text-sm">{sym.symbol?.replace('/USDT', '')}</span>
                  <span className={`text-xs font-medium ${
                    (sym.change_24h || 0) >= 0 ? 'text-green-400' : 'text-red-400'
                  }`}>
                    {(sym.change_24h || 0) >= 0 ? '↗' : '↘'} {Math.abs(sym.change_24h || 0).toFixed(1)}%
                  </span>
                </div>
                <p className="text-lg font-bold text-white">
                  ${formatPrice(sym.price)}
                </p>
                <div className="mt-2 flex items-center gap-1">
                  <div className="flex-1 h-1.5 bg-zinc-700 rounded-full overflow-hidden">
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
        {/* V2.1 Strategy Settings */}
        <Card className="bg-zinc-800/30 border-zinc-700/50">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Target className="w-5 h-5 text-amber-400" />
              V2.1 Strategy Settings
              <span className={`ml-auto px-2 py-0.5 text-xs rounded ${v2Settings?.active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                {v2Settings?.active ? 'ACTIVE' : 'PAUSED'}
              </span>
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Min Confidence</span>
                <span className="font-medium text-amber-400">{v2Settings?.min_confidence || 90}%</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Confirmations</span>
                <span className="font-medium text-white">{v2Settings?.min_confirmations || 5}/5</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Min R:R Ratio</span>
                <span className="font-medium text-cyan-400">{v2Settings?.min_rr_ratio || 3.0}:1</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Max Open Trades</span>
                <span className="font-medium text-white">{v2Settings?.max_open_trades || 5}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-zinc-400">Filters Active</span>
                <div className="flex gap-1 flex-wrap justify-end">
                  {v2Settings?.ema_200_filter_enabled && <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">EMA</span>}
                  {v2Settings?.adx_filter_enabled && <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">ADX</span>}
                  {v2Settings?.volume_filter_enabled && <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">VOL</span>}
                  {v2Settings?.session_filter_enabled && <span className="px-2 py-0.5 bg-amber-500/20 text-amber-400 text-xs rounded">SESSION</span>}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* AI Engine Status */}
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
      </div>

      {/* Scalper & Reports Row */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Aggressive Scalper Widget */}
        <Card className="bg-zinc-800/30 border-purple-500/30">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-purple-400" />
              Aggressive Scalper
              <span className={`ml-auto px-2 py-0.5 text-xs rounded ${scalperStatus?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                {scalperStatus?.enabled ? 'ACTIVE' : 'PAUSED'}
              </span>
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Active Signals</span>
                <span className="font-medium text-purple-400">{scalperStatus?.active_signals || 0}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Settings</span>
                <div className="flex gap-1 flex-wrap justify-end">
                  <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                    Target: {scalperStatus?.settings_summary?.profit_target || '1.5%'}
                  </span>
                  <span className="px-2 py-0.5 bg-red-500/20 text-red-400 text-xs rounded">
                    Stop: {scalperStatus?.settings_summary?.stop_loss || '0.5%'}
                  </span>
                </div>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Auto-Learning</span>
                <span className={`px-2 py-0.5 text-xs rounded flex items-center gap-1 ${
                  scalperStatus?.learning?.auto_learn_enabled ? 'bg-emerald-500/20 text-emerald-400' : 'bg-zinc-700 text-zinc-400'
                }`}>
                  <Sparkles className="w-3 h-3" />
                  {scalperStatus?.learning?.auto_learn_enabled ? 'ON' : 'OFF'}
                </span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-zinc-400">V2.1 Integration</span>
                <span className={`px-2 py-0.5 text-xs rounded flex items-center gap-1 ${
                  scalperStatus?.learning?.v2_integration_enabled ? 'bg-blue-500/20 text-blue-400' : 'bg-zinc-700 text-zinc-400'
                }`}>
                  <Link2 className="w-3 h-3" />
                  {scalperStatus?.learning?.v2_integration_enabled ? 'CONNECTED' : 'DISABLED'}
                </span>
              </div>
            </div>
            <button
              onClick={() => onNavigate && onNavigate('scalper')}
              className="w-full mt-4 flex items-center justify-center gap-2 px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 rounded-lg text-purple-400 text-sm transition-colors"
            >
              <Zap className="w-4 h-4" />
              View Scalper Dashboard
              <ChevronRight className="w-4 h-4" />
            </button>
          </CardContent>
        </Card>

        {/* Weekly Report Widget */}
        <Card className="bg-zinc-800/30 border-amber-500/30">
          <CardContent className="p-6">
            <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
              <Calendar className="w-5 h-5 text-amber-400" />
              Weekly Performance Report
              <span className={`ml-auto px-2 py-0.5 text-xs rounded ${weeklyReport?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'}`}>
                {weeklyReport?.enabled ? 'ACTIVE' : 'PAUSED'}
              </span>
            </h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Schedule</span>
                <span className="font-medium text-amber-400">{weeklyReport?.scheduled_day} {weeklyReport?.scheduled_time}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Trades This Week</span>
                <span className="font-medium text-white">{weeklyReport?.trades_this_week || 0}</span>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-zinc-800">
                <span className="text-zinc-400">Next Report</span>
                <span className="font-medium text-cyan-400 text-sm">{weeklyReport?.next_report?.split(' ')[0] || '-'}</span>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-zinc-400">Recipients</span>
                <span className="font-medium text-white">{weeklyReport?.active_users || 0} users</span>
              </div>
            </div>
            <div className="flex gap-2 mt-4">
              <button
                onClick={() => onNavigate && onNavigate('settings')}
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/50 rounded-lg text-amber-400 text-sm transition-colors"
              >
                <Calendar className="w-4 h-4" />
                View Reports
              </button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* 24/7 Learning Engine */}
      <Card className="bg-gradient-to-r from-zinc-800/30 to-purple-900/20 border-purple-500/30">
        <CardContent className="p-6">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <Brain className="w-6 h-6 text-purple-400 animate-pulse" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                  24/7 Learning Engine
                  <span className={`px-2 py-0.5 text-xs rounded ${learningStatus?.active ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                    {learningStatus?.active ? 'LEARNING' : 'PAUSED'}
                  </span>
                </h3>
                <p className="text-zinc-500 text-sm">Continuously learning patterns, optimizing strategies</p>
              </div>
            </div>
            <div className="text-right">
              <p className="text-xs text-zinc-500">Next Summary</p>
              <p className="text-sm text-purple-400">{learningStatus?.next_daily_summary || '9 PM CT'}</p>
            </div>
          </div>
          
          <div className="grid grid-cols-4 gap-4 mt-6">
            <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <BookOpen className="w-4 h-4 text-purple-400" />
              </div>
              <p className="text-2xl font-bold text-white">{learningStatus?.knowledge_stats?.patterns_learned || 0}</p>
              <p className="text-xs text-zinc-500">Patterns</p>
            </div>
            <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Target className="w-4 h-4 text-cyan-400" />
              </div>
              <p className="text-2xl font-bold text-white">{learningStatus?.knowledge_stats?.coins_analyzed || 0}</p>
              <p className="text-xs text-zinc-500">Coins</p>
            </div>
            <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Lightbulb className="w-4 h-4 text-amber-400" />
              </div>
              <p className="text-2xl font-bold text-white">{learningStatus?.daily_insights_count || 0}</p>
              <p className="text-xs text-zinc-500">Insights</p>
            </div>
            <div className="bg-zinc-900/50 rounded-xl p-4 text-center">
              <div className="flex items-center justify-center gap-1 mb-1">
                <Sparkles className="w-4 h-4 text-green-400" />
              </div>
              <p className="text-2xl font-bold text-white">{learningStatus?.knowledge_stats?.optimizations_run || 0}</p>
              <p className="text-xs text-zinc-500">Optimizations</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4 mt-4 pt-4 border-t border-zinc-700/50 text-xs text-zinc-500">
            <span className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
              Pattern Learning: {learningStatus?.last_cycles?.pattern_learning ? new Date(learningStatus.last_cycles.pattern_learning).toLocaleTimeString() : 'Pending'}
            </span>
            <span className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
              Market Analysis: {learningStatus?.last_cycles?.market_analysis ? new Date(learningStatus.last_cycles.market_analysis).toLocaleTimeString() : 'Pending'}
            </span>
            <span className="flex items-center gap-1">
              <div className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
              Optimization: {learningStatus?.last_cycles?.optimization ? new Date(learningStatus.last_cycles.optimization).toLocaleTimeString() : 'Pending'}
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Recent Activity */}
      <div className="grid md:grid-cols-1 gap-6">
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

      {/* Backtest V2.1 Modal */}
      <BacktestV21Modal isOpen={showBacktestModal} onClose={() => setShowBacktestModal(false)} />
    </div>
  );
}
