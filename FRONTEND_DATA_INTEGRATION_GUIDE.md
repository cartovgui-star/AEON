# Frontend Live Data Integration Guide

**Current Status:** ✅ Backend APIs 100% operational | 🔄 Frontend partially integrated

---

## 🎯 Quick Reference: All Available Data Endpoints

### Dashboard / Home Page

```javascript
// Price tickers (top 15 coins, OKX orderbook data)
GET /api/mexc/live
→ { symbols: [ {symbol, price, change_24h, volume_24h, bid_depth, ask_depth} ] }

// Fear & Greed sentiment
GET /api/intel/fear-greed
→ { value: 33, classification: "Fear" }

// Global market data
GET /api/intel/global
→ { total_market_cap, btc_dominance, eth_dominance, 24h_volume, market_cap_change_24h }

// Top 100 coins (for Intelligence.jsx or Markets page)
GET /api/intel/top100
→ [ {symbol, name, current_price, market_cap, volume, change_24h, change_7d} ]
```

### Market Analysis

```javascript
// Full technical scan for a symbol
GET /api/market/scan/{symbol}
→ {
    symbol, price, change_24h, 
    technical: {rsi, macd, bb_upper/lower, ema_9/20/50/200, atr, stoch, adx, trend},
    market_structure: {bias, pattern, last_swing_high/low},
    signals: [[indicator, rating, direction]],
    orderbook: {bid_depth, ask_depth, imbalance}
  }

// Technical analysis (RSI, MACD, etc.)
GET /api/market/ta/{symbol}?interval=1h
→ { rsi, macd, macd_signal, bb_upper/middle/lower, ema_9/20/50/200, atr, stoch, adx }
```

### Derivatives Intelligence

```javascript
// Funding rates (aggregate across OKX, Bitget, KuCoin, Gate.io)
GET /api/derivatives/funding/{symbol}
→ {
    symbol, average_funding_rate, average_funding_pct, interpretation,
    exchanges: [ {exchange, funding_rate, funding_rate_pct, next_funding_time} ]
  }

// Long/Short ratio (trader positioning)
GET /api/derivatives/ls/{symbol}
→ { symbol, long_short_ratio, interpretation, exchanges: [{...}] }

// Open interest
GET /api/derivatives/oi/{symbol}
→ { symbol, open_interest, oi_change_24h, top_contracts }

// Full derivatives report
GET /api/derivatives/full/{symbol}
→ { funding_rates, long_short_ratio, open_interest, liquidations, summary }
```

### Position & Trading Data

```javascript
// Open positions across all accounts
GET /api/trading/v2/open
→ {
    total_open: 5,
    positions: [
      {
        symbol, direction, entry_price, current_price, pnl, pnl_pct,
        size, leverage, stop_loss, take_profit, account_id, opened_at
      }
    ]
  }

// Trading summary
GET /api/trading/summary
→ {
    total_balance, total_pnl, total_pnl_pct, win_rate,
    total_trades, winning_trades, losing_trades,
    largest_win, largest_loss, avg_trade_duration
  }

// Account-specific data
GET /api/trading/v2/account/{account_id}
→ { balance, positions, pnl, heat, last_trade }
```

### System & Operations

```javascript
// System health (feed status, engine status, error rates)
GET /api/system/health
→ {
    overall: "healthy",
    services: {
      OKX: {status, last_heartbeat, error_count},
      Coinbase: {status, last_heartbeat},
      CoinGecko: {status},
      trading_v2: {status, errors_this_hour},
      free_will: {status, error_count}
    }
  }

// Engine governance state
GET /api/engine/governance
→ {
    states: [
      {
        engine, current_recommendation, current_tier, current_score,
        n_clean_last_week, last_update_timestamp
      }
    ]
  }

// Portfolio summary (accounts, positions, heat)
GET /api/portfolio/summary
→ {
    accounts_list: [{account_id, balance, portfolio_heat, open_positions}],
    total_balance, total_open_positions, aggregate_portfolio_heat
  }

// Free Will V2 report (performance, health tier)
GET /api/engine/fw_v2/report
→ {
    status, health_7d: {tier, score, n_cohorts},
    malformed_rejects_30d, win_rate_7d, avg_confidence
  }
```

---

## 🏗️ Frontend Components & Their Data Needs

### Dashboard.jsx (Home Page)
**Current:** Shows stats, recent trades  
**Should Add:**
```javascript
// Top section: Market sentiment + fear gauge
const { value, classification } = await api.get('/api/intel/fear-greed');

// Ticker tape: Live prices + 24h changes
const { symbols } = await api.get('/api/mexc/live');

// Global market cap + BTC dominance
const globalMarket = await api.get('/api/intel/global');
```

### Intelligence.jsx (Market Info Page)
**Current:** Partially populated  
**Should Add:**
```javascript
// Top 100 coins table
const topCoins = await api.get('/api/intel/top100');

// Per-coin quick analysis
for (const coin of topCoins.slice(0, 20)) {
  const scan = await api.get(`/api/market/scan/${coin.symbol}`);
  // Display: price, RSI, MACD, trend, orderbook imbalance
}
```

### TradingHub.jsx (Trading Control Room)
**Current:** Shows positions, accounts, heat  
**Should Add:**
```javascript
// Real-time position updates (currently fetches once)
// Suggestion: WebSocket subscription to position changes
// Or: Polling every 5 seconds instead of 30 seconds

const positions = await api.get('/api/trading/v2/open');
// Show: entry→current price change, P&L, stop-loss/take-profit levels
```

### AnalyticsPage.jsx (Performance Analysis)
**Current:** Charts missing  
**Should Add:**
```javascript
// Equity curve (cumulative PnL over time)
GET /api/analytics/equity-curve?account_id=PRO&days=30
→ [{timestamp, equity, cumulative_pnl}]

// Win rate by engine
GET /api/analytics/engine-performance
→ [{engine_name, win_rate, avg_trade_size, avg_duration}]

// Drawdown analysis
GET /api/analytics/drawdown-metrics
→ {max_drawdown, current_drawdown, recovery_time}
```

### SystemHealth.jsx (Status & Monitoring)
**Current:** Shows feed pills  
**Should Add:**
```javascript
// Real-time health updates (currently fetches once at load)
// Suggestion: WebSocket or polling every 30s

const health = await api.get('/api/system/health');
// Already displays feed status — good!
// Could add: Engine error rates, recent critical errors
```

### OperatorHome.jsx (Operator Command Center) — NEW
**Current:** Skeleton in place  
**Data Flow:**
```javascript
useEffect(() => {
  Promise.allSettled([
    api.get('/api/system/health'),
    api.get('/api/portfolio/summary'),
    api.get('/api/engine/governance'),
    api.get('/api/engine/health?days=7'),
    api.get('/api/engine/fw_v2/report'),
    api.get('/api/quantum/state'),
  ]);
}, []);

// Displays: System health, Portfolio heat, Governance pressures, FW V2 status
// Already integrated ✅
```

---

## 📡 WebSocket Real-Time Updates (Wishlist)

**Current:** None (all polling)  
**Proposed for Future:**

```javascript
// In App.js
const ws = new WebSocket(`${WS_URL}/prices`);

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // { symbol: "BTC/USDT", price: 77379.9, change: -0.4, timestamp }
  
  // Real-time update to:
  // - Dashboard ticker
  // - TradingHub positions (current P&L)
  // - Chart overlays
};

// Subscribe to specific symbols
ws.send(JSON.stringify({
  type: 'subscribe',
  symbols: ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
}));
```

**Note:** Backend already has `/ws` endpoint in FastAPI, just needs symbol streaming.

---

## 🔄 Recommended Data Refresh Intervals

| Component | Endpoint | Interval | Reason |
|-----------|----------|----------|--------|
| Dashboard tickers | `/api/mexc/live` | 5s | Show live price movement |
| Market scanner | `/api/market/scan/{sym}` | 5-10s | Tech update + signals |
| Positions | `/api/trading/v2/open` | 5s | P&L updates, SL/TP checks |
| Funding rates | `/api/derivatives/funding/{sym}` | 60s | Hourly-updated data |
| Fear & Greed | `/api/intel/fear-greed` | 3600s (1h) | Daily-updated data |
| System health | `/api/system/health` | 30s | Feed degradation detection |
| Portfolio heat | `/api/portfolio/summary` | 10s | Risk monitoring |
| Governance | `/api/engine/governance` | 60s | Engine state changes |

---

## 🎨 Visual Mockup: Enhanced Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│  AEON Quantum Trading System                    🟢 All Feeds Online
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Market Sentiment              Portfolio Status                 │
│  ┌─────────────────┐          ┌──────────────────┐             │
│  │ Fear & Greed    │          │ Total Balance    │             │
│  │      ◉          │          │    $51,520       │             │
│  │      33         │          │                  │             │
│  │      Fear       │          │ Open Positions   │             │
│  │   ↓ Selling     │          │        6         │             │
│  └─────────────────┘          │                  │             │
│                               │ Portfolio Heat   │             │
│  Live Prices (OKX)            │      38.2%       │             │
│  ┌─────────────────┐          │  ⚠️ Elevated     │             │
│  │ BTC  $77,379    │          └──────────────────┘             │
│  │  ↓ -0.40% 24h   │                                           │
│  │                 │          System Health                    │
│  │ ETH  $2,309     │          ┌──────────────────┐             │
│  │  ↓ -0.40% 24h   │          │ OKX    ✅ Healthy             │
│  │                 │          │ Coinbase ✅ Live              │
│  │ SOL  $85.93     │          │ LCW    ✅ Healthy             │
│  │  ↓ -0.65% 24h   │          │ CoinGecko ✅ OK               │
│  └─────────────────┘          └──────────────────┘             │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│  Open Positions                                                  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ BTC/USDT LONG  @77,400    [Current: $77,379]  ↓ -$21 (-0.03%)││
│  │ Entry  77,400 | SL 77,100 | TP 78,452 | Size 0.01 BTC      ││
│  │ Opened 2h ago by autonomous_trader_v2                       ││
│  │                                                              ││
│  │ ETH/USDT SHORT @2,320     [Current: $2,309]   ↑ +$11 (+0.47%)││
│  │ Entry 2,320 | SL 2,350 | TP 2,272 | Size 5.0 ETH           ││
│  │ Opened 1h ago by elite_strategy_v3                          ││
│  └─────────────────────────────────────────────────────────────┘│
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Implementation Checklist

### Phase 1: Display Enhancement (ASAP)
- [ ] Dashboard: Add live ticker (5s refresh)
- [ ] Dashboard: Add Fear & Greed index gauge
- [ ] Intelligence: Add top 100 coins table with sorting
- [ ] TradingHub: Add 5s position refresh (was 30s)
- [ ] SystemHealth: Add error log feed

### Phase 2: Data Integration (This Week)
- [ ] Analytics: Implement equity curve chart
- [ ] Analytics: Add win rate by engine
- [ ] Markets: Add technical scan popup on symbol click
- [ ] Markets: Add derivatives (funding, L/S) panels
- [ ] Portfolio: Real-time heat gauge updates

### Phase 3: Advanced Features (Future)
- [ ] WebSocket real-time prices (eliminate polling)
- [ ] Live order book visualization
- [ ] Heatmap: Trade frequency by hour/symbol
- [ ] Correlation matrix: Multi-asset movements
- [ ] Engine performance dashboard (Sharpe, Sortino, etc.)

---

## 💾 Backend Endpoints Ready Today

**All working. Test with:**

```bash
API_KEY=$(grep DASHBOARD_API_KEY /root/aeon-finale-formv1.2.3.6/backend/.env | cut -d= -f2)

# Test market data
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/mexc/live | python3 -m json.tool

# Test system health
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/system/health | python3 -m json.tool

# Test top 100
curl -H "X-API-Key: $API_KEY" http://127.0.0.1:8000/api/intel/top100 | python3 -m json.tool | head -40
```

---

## 🎯 Next Steps

1. **Update refresh intervals** in existing components (5s instead of 30s for prices/positions)
2. **Add top 100 coins** to Intelligence.jsx
3. **Wire up Fear & Greed** gauge to Dashboard
4. **Enhance analytics** with equity curve + engine breakdown
5. **Monitor backend** logs for any data quality issues

**All data is live. Frontend just needs to display it more frequently.** ✅
