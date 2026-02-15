# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- **Dual Trading Engine** - Day Trader (aggressive) + Long Term (smart) running simultaneously
- Autonomous paper trading with live MEXC data
- No contradicting signals (direction lock prevents flip-flopping)
- Smart alerts that are only the best setups
- User profiling (Aeon learns your preferences)
- Moltbot-inspired features (sentiment, arbitrage, self-improving strategies)

---

## Latest Session (Feb 14, 2026) - P0 + Moltbot Features

### Custom Price Alerts UI (P0) ✅
- New "Alerts" page with full CRUD for custom price alerts
- Set alerts: symbol, target price, direction (above/below)
- Live price shown when setting alert
- Alert Feed showing real-time auto-alerts (breakouts, RSI extremes, volume spikes)
- Auto-alert threshold display

### Backtesting UI (P0) ✅
- New "Backtest" page with strategy testing against MEXC historical data
- 3 strategies: RSI Mean Reversion, Bollinger Bands, EMA Crossover
- "Compare All" mode ranks strategies by profit factor
- Configurable params: timeframe, period, RSI levels, stop/target, EMA periods
- Equity curve charts, stats cards, recent trades table

### Market Intelligence Page (Moltbot-inspired) ✅
**a) Sentiment Analysis**
- Composite sentiment from news + Fear & Greed Index
- Headlines with bull/bear scoring
- AI recommendation based on market conditions
- Fear & Greed 7-day history bar chart

**b) Arbitrage Detection**
- Cross-exchange price comparison: MEXC, Binance, Bybit, OKX, KuCoin
- Scans 10 symbols for price differences
- Shows spread %, buy/sell exchange, estimated profit

**c) Self-Improving Strategy Health**
- Tracks consecutive wins/losses per strategy
- Auto-benches strategies after 3 consecutive losses (60min cooldown)
- Performance scoring (0-100)
- Manual unbench option

### Navigation & Mobile Optimization (P1) ✅
- 11 nav items with compact desktop layout
- Mobile hamburger menu with 3-column grid
- Responsive across all pages

### CSV Export ✅
- Already functional on Analytics page (client-side CSV generation)

---

## Previous Sessions Summary

### Feb 14 (Earlier) - Alert Validation + Unified Settings UI ✅
- Alert price validation (2% threshold for dual engine, 1.5% for elite)
- Unified trading configuration UI in Settings > Alerts tab
- Voice integration with Edge TTS
- Trade Analytics Dashboard with PnL charts
- One-click Coin Scan modal
- Notification preferences UI

### Feb 12 - Memory Fix + Commands Reference ✅
- Memory leak fix with cleanup routines
- Commands Reference page with 40+ commands

### Earlier - Dual Engine + Core Features ✅
- Dual Trading Engine v3 (Day Trader + Long Term)
- Anti-contradiction system
- User profiling
- Conversational AI v4
- Additional free APIs

---

## Key Files

### New (This Session)
- `/app/frontend/src/components/PriceAlerts.jsx` - Custom price alerts page
- `/app/frontend/src/components/Backtesting.jsx` - Strategy backtesting page
- `/app/frontend/src/components/Intelligence.jsx` - Market intelligence page
- `/app/backend/sentiment_analyzer.py` - Sentiment analysis module
- `/app/backend/arbitrage_detector.py` - Cross-exchange arbitrage
- `/app/backend/strategy_health.py` - Self-improving strategy management

### Existing (Modified)
- `/app/frontend/src/App.js` - Updated nav (11 items), mobile grid, new routes
- `/app/backend/server.py` - Added sentiment, arbitrage, strategy-health endpoints

---

## API Endpoints Summary

### New Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/sentiment/composite | GET | Composite sentiment from all sources |
| /api/sentiment/news | GET | News sentiment analysis |
| /api/sentiment/fear-greed | GET | Fear & Greed with history |
| /api/arbitrage/scan | GET | Full exchange scan (5 exchanges, 10 symbols) |
| /api/arbitrage/scan/{symbol} | GET | Single symbol arbitrage scan |
| /api/arbitrage/recent | GET | Recent arbitrage opportunities |
| /api/strategy-health/status | GET | Strategy health & scores |
| /api/strategy-health/ranking | GET | Strategy ranking by score |
| /api/strategy-health/record | POST | Record trade for health tracking |
| /api/strategy-health/unbench/{id} | POST | Force unbench strategy |

### Existing Endpoints (from previous sessions)
- Alerts: /api/alerts/add, /api/alerts/custom, /api/alerts/{id}, /api/alerts/stats
- Backtest: /api/backtest/compare/{sym}, /api/backtest/rsi/{sym}, /api/backtest/bb/{sym}, /api/backtest/ema/{sym}
- Dual Engine: /api/dual/stats, /api/dual/toggle, /api/dual/day-trader/*, /api/dual/long-term/*
- Trading: /api/trading/v2/stats, /api/trading/toggle, /api/trading/summary
- Market: /api/mexc/live, /api/market/scan/{symbol}

---

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Day Trader | ✅ ACTIVE | 75% conf, 15m/1h/4h |
| Long Term | ✅ ACTIVE | 88% conf, 4h/1d |
| Free Will v2 | ✅ ACTIVE | 80% conf, legacy |
| Paper Trading | ✅ ACTIVE | 10 open trades |
| Price Alerts | ✅ ACTIVE | 10 coins tracked |
| Sentiment | ✅ ACTIVE | News + Fear/Greed |
| Arbitrage | ✅ ACTIVE | 5 exchanges |
| Strategy Health | ✅ ACTIVE | Auto-bench enabled |
| User Profiling | ✅ ACTIVE | Learning preferences |
| Telegram Chat | ⚠️ VERIFY | Webhook was fixed, needs user check |
| Memory Mgmt | ✅ FIXED | Cleanup routines active |

---

## Backlog

### P1 (Next)
- Refactor `server.py` - Extract Telegram handlers to separate module
- Moltbot deeper integration - sentiment-based trade signals
- Trade Journal improvements

### P2 (When Ready)
- Real-money trading (user deferred)
- Discord/Slack integration (user declined)

### P3 (Future)
- More exchange integrations
- Advanced backtesting with multiple timeframes
- Portfolio tracking

---

## Deployment
- Preview: https://aeon-trading.preview.emergentagent.com
- Backend: Port 8001
- Frontend: Port 3000
