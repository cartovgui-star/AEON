import React, { useState, useEffect } from 'react';
import { 
  Wallet, TrendingUp, TrendingDown, Target, RefreshCw, 
  DollarSign, BarChart3, Activity, Zap, Crown, Leaf,
  X, ChevronDown, ChevronUp, AlertTriangle
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { ScrollArea } from './ui/scroll-area';

const API_URL = process.env.REACT_APP_BACKEND_URL;

// Format price based on value
const formatPrice = (price) => {
  if (!price && price !== 0) return '-';
  if (Math.abs(price) > 1000) return price.toLocaleString(undefined, { maximumFractionDigits: 0 });
  if (Math.abs(price) > 1) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  return price.toLocaleString(undefined, { minimumFractionDigits: 4, maximumFractionDigits: 4 });
};

// Strategy badge colors
const getStrategyColor = (strategy) => {
  const colors = {
    'FREE_WILL_V2': 'bg-purple-500/20 text-purple-300 border-purple-500/30',
    'YOLO': 'bg-red-500/20 text-red-300 border-red-500/30',
    'VWAP_SCALP': 'bg-blue-500/20 text-blue-300 border-blue-500/30',
    'DAY_TRADER': 'bg-orange-500/20 text-orange-300 border-orange-500/30',
    'LONG_TERM': 'bg-green-500/20 text-green-300 border-green-500/30',
    'ELITE': 'bg-yellow-500/20 text-yellow-300 border-yellow-500/30',
    'AUTONOMOUS_V2': 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30',
  };
  return colors[strategy] || 'bg-zinc-500/20 text-zinc-300 border-zinc-500/30';
};

export default function PaperTrading() {
  const [accounts, setAccounts] = useState([]);
  const [positions, setPositions] = useState([]);
  const [performance, setPerformance] = useState(null);
  const [healthStatus, setHealthStatus] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedAccount, setSelectedAccount] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [closeError, setCloseError] = useState(null);
  const [closingPosition, setClosingPosition] = useState(null);

  // Fetch all data
  const fetchData = async () => {
    try {
      const [accountsRes, positionsRes, perfRes, healthRes, eventsRes] = await Promise.all([
        fetch(`${API_URL}/api/paper/accounts`),
        fetch(`${API_URL}/api/paper/positions`),
        fetch(`${API_URL}/api/paper/performance`),
        fetch(`${API_URL}/api/paper/health`),
        fetch(`${API_URL}/api/paper/events?limit=10`)
      ]);
      
      const accountsData = await accountsRes.json();
      const positionsData = await positionsRes.json();
      const perfData = await perfRes.json();
      const healthData = await healthRes.json();
      const eventsData = await eventsRes.json();
      
      setAccounts(accountsData.accounts || []);
      setPositions(positionsData.positions || []);
      setPerformance(perfData);
      setHealthStatus(healthData);
      setEvents(eventsData.events || []);
    } catch (err) {
      console.error('Failed to fetch paper trading data:', err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Refresh every 15 seconds
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleRefresh = () => {
    setRefreshing(true);
    fetchData();
  };

  const handleResetAccount = async (accountId) => {
    if (!window.confirm(`Reset ${accountId} account to starting balance? This will close all positions.`)) {
      return;
    }
    
    try {
      await fetch(`${API_URL}/api/paper/reset/${accountId}`, { method: 'POST' });
      fetchData();
    } catch (err) {
      console.error('Failed to reset account:', err);
    }
  };

  const handleClosePosition = async (accountId, symbol) => {
    if (!window.confirm(`Close ${symbol} position in ${accountId}?`)) {
      return;
    }
    setCloseError(null);
    setClosingPosition(`${accountId}-${symbol}`);
    try {
      const cleanSymbol = symbol.replace('/USDT', '');
      const res = await fetch(`${API_URL}/api/paper/close/${accountId}/${cleanSymbol}`, { method: 'POST' });
      const data = await res.json();
      if (data?.error) {
        setCloseError(`Failed to close ${symbol}: ${data.error}`);
      } else {
        // Optimistically remove position from UI
        setPositions(prev => prev.filter(p => !(p.symbol === symbol && p.account_id === accountId)));
      }
      fetchData();
    } catch (err) {
      console.error('Failed to close position:', err);
      setCloseError(`Failed to close ${symbol}: ${err.message}`);
    } finally {
      setClosingPosition(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Wallet className="w-6 h-6 text-amber-500" />
          <h2 className="text-xl font-bold text-white">Paper Trading Dashboard</h2>
        </div>
        <div className="flex items-center gap-3">
          {/* Auto-reload status indicator */}
          <div className="flex items-center gap-2 text-xs px-3 py-1.5 bg-green-500/10 border border-green-500/20 rounded-lg">
            <RefreshCw className="w-3 h-3 text-green-400" />
            <span className="text-green-400">Auto-reload active</span>
          </div>
          <Button 
            variant="outline" 
            size="sm" 
            onClick={handleRefresh}
            disabled={refreshing}
            className="border-zinc-700 hover:bg-zinc-800"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Close position error banner */}
      {closeError && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-red-400 flex-shrink-0" />
            <span className="text-sm text-red-300">{closeError}</span>
          </div>
          <button onClick={() => setCloseError(null)} className="text-red-400 hover:text-red-200">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Health Status Banner - show if any account is low */}
      {healthStatus && healthStatus.low_balance && healthStatus.low_balance.length > 0 && (
        <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-lg flex items-center gap-3">
          <AlertTriangle className="w-5 h-5 text-amber-400" />
          <div>
            <p className="text-sm text-amber-300 font-medium">Low Balance Warning</p>
            <p className="text-xs text-amber-400/70">
              {healthStatus.low_balance.map(a => `${a.account_id}: ${a.pct_remaining}% remaining`).join(' | ')}
              {' - Will auto-reload at 5%'}
            </p>
          </div>
        </div>
      )}

      {/* Recent Events - auto-reloads */}
      {events && events.length > 0 && events.some(e => e.type === 'auto_reload') && (
        <div className="p-3 bg-blue-500/10 border border-blue-500/30 rounded-lg">
          <p className="text-sm text-blue-300 font-medium mb-2">Recent Auto-Reloads</p>
          <div className="space-y-1">
            {events.filter(e => e.type === 'auto_reload').slice(0, 3).map((event, idx) => (
              <p key={idx} className="text-xs text-blue-400/70">
                {event.account_id}: ${formatPrice(event.old_balance)} → ${formatPrice(event.new_balance)}
                {event.timestamp && ` (${new Date(event.timestamp).toLocaleTimeString()})`}
              </p>
            ))}
          </div>
        </div>
      )}

      {/* Account Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {accounts.map((account) => {
          // Calculate health percentage
          const healthPct = account.starting_balance ? (account.balance / account.starting_balance) * 100 : 0;
          const isLow = healthPct < 20;
          const isCritical = healthPct < 5;
          
          return (
          <Card key={account.account_id} className={`bg-zinc-900/50 border-zinc-800 ${isCritical ? 'border-red-500/50' : isLow ? 'border-amber-500/30' : ''}`}>
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  {account.account_id === 'PRO' ? (
                    <Crown className="w-5 h-5 text-amber-500" />
                  ) : (
                    <Leaf className="w-5 h-5 text-green-500" />
                  )}
                  <CardTitle className="text-lg">{account.name}</CardTitle>
                  {/* Health badge */}
                  {isCritical && (
                    <Badge className="bg-red-500/20 text-red-300 border-red-500/30 text-xs">
                      Auto-reloading...
                    </Badge>
                  )}
                  {isLow && !isCritical && (
                    <Badge className="bg-amber-500/20 text-amber-300 border-amber-500/30 text-xs">
                      Low Balance
                    </Badge>
                  )}
                </div>
                <Button 
                  variant="ghost" 
                  size="sm"
                  onClick={() => handleResetAccount(account.account_id)}
                  className="text-zinc-400 hover:text-red-400 hover:bg-red-500/10"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Balance health bar */}
              <div className="mb-4">
                <div className="flex justify-between text-xs mb-1">
                  <span className="text-zinc-500">Account Health</span>
                  <span className={healthPct > 50 ? 'text-green-400' : healthPct > 20 ? 'text-amber-400' : 'text-red-400'}>
                    {healthPct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
                  <div 
                    className={`h-full transition-all duration-500 ${
                      healthPct > 50 ? 'bg-green-500' : healthPct > 20 ? 'bg-amber-500' : 'bg-red-500'
                    }`}
                    style={{ width: `${Math.min(100, healthPct)}%` }}
                  />
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <p className="text-xs text-zinc-500">Balance</p>
                  <p className="text-xl font-bold text-white">${formatPrice(account.balance)}</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Total PnL</p>
                  <p className={`text-xl font-bold ${account.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {account.total_pnl >= 0 ? '+' : ''}${formatPrice(account.total_pnl)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Open Positions</p>
                  <p className="text-lg font-semibold text-white">{account.open_positions}</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Win Rate</p>
                  <p className={`text-lg font-semibold ${account.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
                    {account.win_rate}%
                  </p>
                </div>
                <div>
                  <p className="text-xs text-zinc-500">Total Trades</p>
                  <p className="text-sm text-zinc-300">{account.total_trades}</p>
                </div>
                <div>
                  <p className="text-xs text-zinc-500">W/L</p>
                  <p className="text-sm text-zinc-300">
                    <span className="text-green-400">{account.wins}</span>
                    <span className="text-zinc-500"> / </span>
                    <span className="text-red-400">{account.losses}</span>
                  </p>
                </div>
              </div>
              
              {/* Unrealized PnL */}
              {account.unrealized_pnl !== 0 && (
                <div className="mt-3 p-2 bg-zinc-800/50 rounded-lg">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-zinc-500">Unrealized PnL</span>
                    <span className={`text-sm font-semibold ${account.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {account.unrealized_pnl >= 0 ? '+' : ''}${formatPrice(account.unrealized_pnl)}
                    </span>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        );
        })}
      </div>

      {/* Strategy Performance */}
      {performance && performance.strategies && performance.strategies.length > 0 && (
        <Card className="bg-zinc-900/50 border-zinc-800">
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-amber-500" />
              <CardTitle>Strategy Performance</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {performance.strategies.map((strategy) => (
                <div 
                  key={strategy.name}
                  className="p-4 bg-zinc-800/50 rounded-lg border border-zinc-700/50"
                >
                  <div className="flex items-center justify-between mb-3">
                    <Badge className={getStrategyColor(strategy.name)}>
                      {strategy.name}
                    </Badge>
                    <span className="text-xs text-zinc-500">{strategy.total_trades} trades</span>
                  </div>
                  
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <p className="text-xs text-zinc-500">Win Rate</p>
                      <p className={`font-semibold ${strategy.win_rate >= 50 ? 'text-green-400' : 'text-amber-400'}`}>
                        {strategy.win_rate}%
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Avg Leverage</p>
                      <p className="font-semibold text-white">{strategy.avg_leverage}x</p>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Total PnL</p>
                      <p className={`font-semibold ${strategy.total_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        ${formatPrice(strategy.total_pnl)}
                      </p>
                    </div>
                    <div>
                      <p className="text-xs text-zinc-500">Open</p>
                      <p className="font-semibold text-cyan-400">{strategy.open_trades}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Positions Monitor */}
      <Card className="bg-zinc-900/50 border-zinc-800">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Activity className="w-5 h-5 text-green-500" />
              <CardTitle>Live Positions ({positions.length})</CardTitle>
            </div>
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              Auto-refreshing
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {positions.length === 0 ? (
            <div className="text-center py-8 text-zinc-500">
              <Target className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>No open positions</p>
              <p className="text-xs mt-1">Positions will appear here when engines open trades</p>
            </div>
          ) : (
            <ScrollArea className="h-[400px]">
              <div className="space-y-3">
                {positions.map((pos, idx) => (
                  <div 
                    key={pos.id || idx}
                    className="p-4 bg-zinc-800/50 rounded-lg border border-zinc-700/50 hover:border-zinc-600/50 transition-colors"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <span className="text-lg">{pos.account_emoji}</span>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-white">{pos.symbol}</span>
                            <Badge className={pos.direction === 'LONG' ? 
                              'bg-green-500/20 text-green-300 border-green-500/30' : 
                              'bg-red-500/20 text-red-300 border-red-500/30'
                            }>
                              {pos.direction}
                            </Badge>
                            <span className="text-xs text-amber-400">{pos.leverage}x</span>
                          </div>
                          <Badge className={`mt-1 ${getStrategyColor(pos.strategy)}`}>
                            {pos.strategy}
                          </Badge>
                        </div>
                      </div>
                      
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleClosePosition(pos.account_id, pos.symbol)}
                        disabled={closingPosition === `${pos.account_id}-${pos.symbol}`}
                        className="text-zinc-400 hover:text-red-400 hover:bg-red-500/10 disabled:opacity-50"
                        title="Close position"
                      >
                        {closingPosition === `${pos.account_id}-${pos.symbol}`
                          ? <RefreshCw className="w-4 h-4 animate-spin" />
                          : <X className="w-4 h-4" />
                        }
                      </Button>
                    </div>
                    
                    <div className="grid grid-cols-3 md:grid-cols-5 gap-3 text-sm">
                      <div>
                        <p className="text-xs text-zinc-500">Entry</p>
                        <p className="text-white">${formatPrice(pos.entry_price)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">Margin</p>
                        <p className="text-white">${formatPrice(pos.margin)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">Liq Price</p>
                        <p className="text-red-400">${formatPrice(pos.liquidation_price)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">SL</p>
                        <p className="text-orange-400">${formatPrice(pos.stop_loss)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-zinc-500">TP</p>
                        <p className="text-green-400">${formatPrice(pos.take_profit)}</p>
                      </div>
                    </div>
                    
                    {/* PnL Bar */}
                    <div className="mt-3 p-2 bg-zinc-900/50 rounded-lg">
                      <div className="flex justify-between items-center">
                        <span className="text-xs text-zinc-500">Unrealized PnL</span>
                        <div className="flex items-center gap-2">
                          {pos.unrealized_pnl >= 0 ? (
                            <TrendingUp className="w-4 h-4 text-green-400" />
                          ) : (
                            <TrendingDown className="w-4 h-4 text-red-400" />
                          )}
                          <span className={`font-bold ${pos.unrealized_pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {pos.unrealized_pnl >= 0 ? '+' : ''}${formatPrice(pos.unrealized_pnl)}
                            <span className="text-xs ml-1">({pos.unrealized_pnl_pct >= 0 ? '+' : ''}{pos.unrealized_pnl_pct?.toFixed(1)}%)</span>
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
