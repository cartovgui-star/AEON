# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- Autonomous trading engine (v2)
- Multi-strategy analysis
- Real-time price alerts
- Smart Money Concepts (SMC) analysis
- Trade journaling and memory system
- Dashboard with analytics
- Telegram bot integration
- Voice conversation capability

## User Personas
- **Crypto Traders**: Need real-time market analysis, alerts, and trading signals
- **Telegram Users**: Want to interact with Aeon via chat commands
- **Dashboard Users**: Need visual analytics and strategy insights

---

## What's Been Implemented

### Feb 10, 2026 (Session 2) - SMC, Memory, & Refactoring

**New Features:**
- ✅ **Smart Money Concepts (SMC) Analyzer**
  - Market Structure Analysis (HH/HL/LH/LL)
  - Break of Structure (BOS) & Change of Character (CHoCH)
  - Order Blocks (bullish/bearish)
  - Fair Value Gaps (FVG)
  - Liquidity Zones (buy-side/sell-side)
  - Premium/Discount Zones with Fibonacci levels

- ✅ **Memory & Journaling System**
  - Trade Journal with performance tracking
  - Pattern Memory (best setups, win rates)
  - AI-generated Trading Insights
  - Conversation Context storage
  - Performance analytics (30-day stats)

- ✅ **Code Refactoring**
  - Created modular route files:
    - `/routes/smc.py` - SMC endpoints
    - `/routes/memory.py` - Journal/memory endpoints
    - `/routes/strategies.py` - Strategy endpoints
    - `/routes/alerts.py` - Alert endpoints
  - Cleaner server.py with route imports

- ✅ **Telegram Commands Added**
  - `/smc btc` - Full SMC analysis
  - `/journal` - Trading performance stats
  - `/insights` - AI trading insights

### Feb 10, 2026 (Session 1) - Multi-Strategy & Alerts
- ✅ **Multi-Strategy Engine** (6 strategies)
- ✅ **Real-Time Price Alert System**
- ✅ **Analytics Page**
- ✅ **Telegram Strategy/Alert Commands**

### Previous Work (Feb 2026)
- ✅ Autonomous Trader v2 integration
- ✅ Multi-page dashboard with navigation
- ✅ Voice conversation with Aeon
- ✅ Trade History page
- ✅ Settings page
- ✅ Telegram bot with 40+ commands

---

## Technical Architecture

### Backend Modules
```
/app/backend/
├── server.py              # Main server (refactored, imports routes)
├── routes/
│   ├── smc.py            # SMC API endpoints
│   ├── memory.py         # Journal/memory endpoints
│   ├── strategies.py     # Strategy endpoints
│   ├── alerts.py         # Alert endpoints
│   ├── derivatives.py    # Existing derivatives routes
│   └── freewill.py       # Free will routes
├── smc_analyzer.py        # NEW: SMC analysis engine
├── memory_system.py       # NEW: Journal & memory system
├── strategy_engine.py     # Multi-strategy engine
├── price_alerts.py        # Alert system
├── autonomous_trader_v2.py
├── free_will_v2.py
└── ...
```

### Frontend
```
/app/frontend/src/
├── App.js                # Main app with navigation
├── components/
│   ├── Analytics.jsx     # Alerts + Strategies tabs
│   ├── TradeHistory.jsx
│   ├── SettingsPanel.jsx
│   └── VoiceConversation.jsx
```

---

## API Endpoints

### SMC Analysis
- `GET /api/smc/analysis/{symbol}` - Full SMC analysis
- `GET /api/smc/structure/{symbol}` - Market structure
- `GET /api/smc/orderblocks/{symbol}` - Order blocks
- `GET /api/smc/fvg/{symbol}` - Fair value gaps
- `GET /api/smc/liquidity/{symbol}` - Liquidity zones
- `GET /api/smc/zones/{symbol}` - Premium/discount zones

### Memory & Journal
- `GET /api/memory/stats` - System statistics
- `GET /api/memory/journal/stats` - Performance stats
- `GET /api/memory/journal/trades` - Recent trades
- `POST /api/memory/journal/log` - Log a trade
- `GET /api/memory/journal/patterns` - Best patterns
- `GET /api/memory/insights` - AI insights
- `POST /api/memory/insights/generate` - Generate insights

### Strategies
- `GET /api/strategies/all/{symbol}` - All strategies
- `GET /api/strategies/ma/{symbol}` - MA Crossover
- `GET /api/strategies/rsi/{symbol}` - RSI Momentum
- `GET /api/strategies/breakout/{symbol}` - Breakout
- `GET /api/strategies/bb/{symbol}` - Bollinger Squeeze
- `GET /api/strategies/macd/{symbol}` - MACD Reversal
- `GET /api/strategies/pullback/{symbol}` - Trend Pullback

### Alerts
- `GET /api/alerts/stats` - Alert stats
- `GET /api/alerts/dashboard` - Dashboard alerts
- `POST /api/alerts/add` - Add custom alert
- `DELETE /api/alerts/{id}` - Remove alert

---

## Telegram Commands Reference

### Analysis
- `/scan btc` - Full analysis
- `/mtf btc` - Multi-timeframe
- `/deriv btc` - Derivatives data

### Strategies
- `/strat btc` - Multi-strategy scan
- `/smc btc` - Smart Money analysis

### Alerts
- `/alerts` - View status
- `/alert add btc above 70000`
- `/alert remove [id]`

### Journal
- `/journal` - Performance stats
- `/insights` - AI insights

### Auto-Trading
- `/auto` - Status
- `/opps` - Trading opportunities
- `/open` - Open positions

---

## Prioritized Backlog

### P0 - Completed ✅
- [x] Multi-strategy engine
- [x] Real-time price alerts
- [x] Analytics page
- [x] SMC analyzer
- [x] Memory/journal system
- [x] Route refactoring

### P1 - Future Improvements
- [ ] SMC page in frontend dashboard
- [ ] Journal page in frontend dashboard
- [ ] Coinglass API (requires paid key)
- [ ] Further server.py refactoring

### P2 - Backlog
- [ ] Advanced charting with SMC levels
- [ ] Backtesting visualization
- [ ] Portfolio management
- [ ] More detailed trade analysis

---

## Known Issues
1. **Coinglass API** - Blocked on paid API key
2. **MATIC Symbol** - Deprecated on MEXC (non-critical)

---

## Final Recommendations

### Performance Enhancements
1. **Add WebSocket for real-time alerts** - Currently polling-based
2. **Cache SMC calculations** - Expensive calculations could be cached
3. **Add notification sounds** - Browser audio for alerts

### Trading Improvements
1. **SMC + Strategy Confluence** - Combine SMC levels with strategy signals
2. **Auto-journal trades** - Automatically log trades from autonomous trader
3. **Pattern backtesting** - Test SMC patterns historically

### User Experience
1. **Mobile-responsive design** - Current dashboard is desktop-focused
2. **Custom alert sounds** - Different sounds for different alert types
3. **Dark/light theme toggle** - Currently only dark mode

---

## Deployment
- Preview: https://autonomous-trader-9.preview.emergentagent.com
- Backend: Port 8001 (supervisor managed)
- Frontend: Port 3000 (hot reload)
