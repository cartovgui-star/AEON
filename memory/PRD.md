# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- Autonomous trading engine (v2)
- Multi-strategy analysis
- Real-time price alerts
- Dashboard with analytics
- Telegram bot integration
- Voice conversation capability

## User Personas
- **Crypto Traders**: Need real-time market analysis, alerts, and trading signals
- **Telegram Users**: Want to interact with Aeon via chat commands
- **Dashboard Users**: Need visual analytics and strategy insights

## Core Requirements
1. Multi-strategy trading engine
2. Real-time price alerts (Telegram + Dashboard)
3. Voice conversation with Aeon
4. Multi-page dashboard (Dashboard, Trades, Analytics, Settings)
5. Telegram bot with comprehensive commands

---

## What's Been Implemented

### Feb 10, 2026 - Multi-Strategy & Price Alerts
**New Features:**
- ✅ **Multi-Strategy Engine** (6 strategies)
  - MA Crossover (EMA 9/21)
  - RSI Momentum (oversold/overbought)
  - Breakout Detection (support/resistance)
  - Bollinger Band Squeeze
  - MACD Histogram Reversal
  - Trend Pullback (EMA 21/50)
  
- ✅ **Real-Time Price Alert System**
  - Auto-alerts for 10 symbols (BTC, ETH, SOL, etc.)
  - 5-minute price change alerts (2%+ moves)
  - 1-hour price change alerts (5%+ moves)
  - RSI extreme alerts (oversold <25, overbought >75)
  - Volume spike alerts (3x+ normal volume)
  - Breakout alerts (support/resistance breaks)
  - Custom price target alerts (above/below)
  
- ✅ **Analytics Page**
  - Alerts tab with real-time alerts
  - Strategies tab with multi-strategy analysis
  - Symbol selector (BTC, ETH, SOL, etc.)
  - Overall signal display
  - Best strategy recommendation
  - Entry/Stop/Target for each strategy

- ✅ **Telegram Commands**
  - `/strat [symbol] [timeframe]` - Multi-strategy scan
  - `/alerts` - View alert status
  - `/alert add [symbol] above/below [price]` - Add custom alert
  - `/alert remove [id]` - Remove alert

### Previous Work (Feb 2026)
- ✅ Autonomous Trader v2 integration
- ✅ Multi-page dashboard with navigation
- ✅ Voice conversation with Aeon (continuous mode)
- ✅ Trade History page
- ✅ Settings page
- ✅ Telegram bot with 30+ commands

---

## Prioritized Backlog

### P0 - Completed
- [x] Multi-strategy engine
- [x] Real-time price alerts
- [x] Analytics page
- [x] Telegram alert commands

### P1 - Next Up
- [ ] Fix Coinglass API (requires paid API key from user)
- [ ] Implement Smart Money Concepts (SMC) from `smc_v1.py`
- [ ] Implement Memory/Journaling from `memory_v1.py`

### P2 - Future
- [ ] Refactor `server.py` (~2600 lines) into modular components
- [ ] Add more advanced charting to Analytics
- [ ] Implement trading journal with performance tracking
- [ ] Add portfolio management features
- [ ] Implement backtesting visualization

---

## Technical Architecture

### Backend (FastAPI)
```
/app/backend/
├── server.py          # Main server (2600+ lines) - needs refactoring
├── strategy_engine.py # Multi-strategy analysis engine
├── price_alerts.py    # Real-time price alert system
├── autonomous_trader_v2.py # Elite trading engine
├── free_will_v2.py    # Free will alert engine
├── market_intelligence.py # Market data aggregation
├── advanced_strategies.py # Technical analysis
└── coinglass_intel.py # Coinglass API (blocked on paid key)
```

### Frontend (React)
```
/app/frontend/src/
├── App.js            # Main app with navigation
├── components/
│   ├── Analytics.jsx # NEW: Alerts + Strategies tabs
│   ├── TradeHistory.jsx
│   ├── SettingsPanel.jsx
│   └── VoiceConversation.jsx
└── components/ui/    # Shadcn components
```

---

## API Endpoints

### Price Alerts
- `GET /api/alerts/stats` - Alert system statistics
- `GET /api/alerts/dashboard` - Dashboard alerts list
- `POST /api/alerts/add` - Add custom price alert
- `DELETE /api/alerts/{id}` - Remove custom alert
- `GET /api/alerts/custom` - List custom alerts

### Multi-Strategy
- `GET /api/strategies/all/{symbol}` - Run all 6 strategies
- `GET /api/strategies/ma/{symbol}` - MA Crossover
- `GET /api/strategies/rsi/{symbol}` - RSI Momentum
- `GET /api/strategies/breakout/{symbol}` - Breakout
- `GET /api/strategies/bb/{symbol}` - Bollinger Squeeze
- `GET /api/strategies/macd/{symbol}` - MACD Reversal
- `GET /api/strategies/pullback/{symbol}` - Trend Pullback

### Existing Endpoints
- `/api/v2/stats` - Autonomous trader stats
- `/api/v2/opportunities` - Trading signals
- `/api/voice_chat` - Voice conversation
- `/api/trades` - Trade history
- `/api/settings` - User settings

---

## Test Reports
- `/app/test_reports/iteration_11.json` - All tests passed (24/24 backend, 100% frontend)

---

## Known Issues
1. **Coinglass API** - Blocked on paid API key (user's free key doesn't work)
2. **MATIC Symbol** - Deprecated on MEXC, shows error in logs (non-critical)
3. **server.py Size** - 2600+ lines, needs refactoring for maintainability

---

## Deployment
- Preview: https://autonomous-trader-9.preview.emergentagent.com
- Backend: Port 8001 (supervisor managed)
- Frontend: Port 3000 (hot reload)
