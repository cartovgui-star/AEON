# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- **Dual Trading Engine** - Day Trader (aggressive) + Long Term (smart) running simultaneously
- Autonomous paper trading with live MEXC data
- No contradicting signals (direction lock prevents flip-flopping)
- Smart alerts that are only the best setups
- User profiling (Aeon learns your preferences)
- Moltbot-inspired features (sentiment, arbitrage, self-improving strategies)
- Self-healing system that auto-detects and recovers from errors

---

## Latest Session (Feb 19, 2026) - UI Enhancements

### Position "Calling Card" Modal (P0) - DONE
- Fixed critical JSX structure error in Trading.jsx (modal body was outside container)
- Modal opens when clicking any open position
- Shows all position details: Symbol, Direction, PnL%, PnL USD, Entry/Current Price
- **Margin Used** highlighted in cyan styling
- Exit Strategy with Take Profit and Stop Loss
- Trade Confirmations list
- Close Position and Back buttons
- Modal closes via X button or clicking outside

### Settings Page Redesign (P1) - DONE
- Complete UI overhaul with collapsible accordion sections
- 4 tabs: Trading Engines, Alert System, Profile, Voice
- Paper Trading Mode notice at top
- Autonomous Trader v2 with toggle and confidence slider
- Day Trader (yellow styling) and Long Term (blue styling) side by side
- Elite Alerts with stats dashboard (Today's Alerts, Total Sent, Blocked, Pairs)
- Recent Signal Directions display with direction lock
- Data Sources grid with live indicators

### SMC Analysis Trade Reasoning (P2) - DONE
- New "Why This Signal?" section with detailed explanations
- Dynamic reasoning generation based on SMC data
- Color-coded bullish (green) and bearish (red) factors
- Market Structure reasoning (trend, HH/HL, LH/LL, BOS)
- Premium/Discount zone explanations
- Order Blocks and FVG reasoning
- Confluence Factors with checkmarks/alerts and scores
- "Why This Trade?" reasoning for trade setups

---

## Previous Session (Feb 15, 2026) - Alert Overhaul + Self-Healing

### Alert System Overhaul v2 (P0) - DONE
- RSI alerts batched into single grouped message per scan (was individual per coin)
- Breakout alerts now require 0.8% threshold (was 0.5%) + volume confirmation tag
- Breakout cooldown increased to 30min per symbol (was 5min)
- Funding rate alerts grouped into single message (was individual per symbol, 2h cooldown)
- All alert messages made lean/concise (dual engine, free will v2)
- General alert cooldown increased to 10min (was 5min)

### CSV Export (P1) - DONE
- Backend endpoint `/api/trades/export` returns CSV with headers: Date, Symbol, Direction, Entry, Exit, PnL%, Exit Reason, Style
- Frontend TradeAnalytics export button now uses backend endpoint (was client-side generation)
- Added `/api/trades/closed` alias for frontend TradeAnalytics page

### Self-Healing System (P0) - DONE
- `self_healer.py` monitors all 5 background services
- Auto-detects dead/crashed tasks and restarts them
- Tracks error rates per hour, throttles restart if too many errors (20/hr)
- Stale heartbeat detection (5min threshold)
- Healing log with audit trail
- `/api/system/health` API endpoint for status

### System Health UI Page - DONE
- New "Health" page in navigation
- Shows overall status (HEALTHY/DEGRADED/CRITICAL)
- Service cards with heartbeat, errors/hr, restart count
- Auto-Heal log showing recovery actions
- Auto-refresh every 15s

### Bug Fix: free_will_v2.py `scan` variable - DONE
- Fixed `NameError: name 'scan' is not defined` in `analyze_setup_full()`
- Now properly fetches market structure from `market_intel.get_full_market_scan()`

---

## Previous Sessions Summary

### Feb 14 - Moltbot + Intelligence Features
- Sentiment Analysis, Arbitrage Detection (5 exchanges), Strategy Health
- New Intelligence page, updated Telegram commands
- Market structure filter to prevent contradictory alerts
- Permanent Telegram webhook auto-setup fix

### Feb 14 (Earlier) - Alert Validation + Settings UI
- Alert price validation (2% threshold for dual, 1.5% for elite)
- Unified trading configuration in Settings
- Voice integration, Trade Analytics Dashboard
- One-click Coin Scan, Notification preferences

### Feb 12 - Memory Fix + Commands Reference
- Memory leak fix with cleanup routines
- Commands Reference page with 40+ commands

### Earlier - Dual Engine + Core Features
- Dual Trading Engine v3 (Day Trader + Long Term)
- Anti-contradiction system, User profiling
- Conversational AI v4, Additional free APIs

---

## Key Files

### Modified (Feb 19, 2026)
- `/app/frontend/src/components/Trading.jsx` - Fixed modal structure, position calling card
- `/app/frontend/src/components/SettingsPanel.jsx` - Complete redesign with collapsible sections
- `/app/frontend/src/components/SMCAnalysis.jsx` - Added "Why This Signal?" reasoning section

### New (Feb 15, 2026)
- `/app/backend/self_healer.py` - Self-healing system
- `/app/frontend/src/components/SystemHealth.jsx` - Health monitoring UI

### Modified (This Session)
- `/app/backend/price_alerts.py` - Rewritten v2 with RSI batching
- `/app/backend/server.py` - Added /trades/closed, /trades/export, /system/health endpoints + self-healer integration
- `/app/backend/dual_trading_engine.py` - Leaner alert format
- `/app/backend/free_will_v2.py` - Fixed scan bug, leaner alert format
- `/app/frontend/src/components/TradeAnalytics.jsx` - Backend CSV export
- `/app/frontend/src/App.js` - Added Health nav + SystemHealth route

---

## API Endpoints Summary

### New Endpoints (This Session)
| Endpoint | Method | Description |
|----------|--------|-------------|
| /api/system/health | GET | Self-healer status (5 services) |
| /api/trades/closed | GET | Closed trades list for TradeAnalytics |
| /api/trades/export | GET | CSV download of all closed trades |

### Existing Endpoints
- Alerts: /api/alerts/add, /api/alerts/custom, /api/alerts/{id}, /api/alerts/stats, /api/alerts/dashboard
- Backtest: /api/backtest/compare/{sym}, /api/backtest/rsi/{sym}, /api/backtest/bb/{sym}, /api/backtest/ema/{sym}
- Dual Engine: /api/dual/stats, /api/dual/toggle, /api/dual/day-trader/*, /api/dual/long-term/*
- Trading: /api/trading/v2/stats, /api/trading/toggle, /api/trading/summary
- Market: /api/mexc/live, /api/market/scan/{symbol}
- Sentiment: /api/sentiment/composite, /api/sentiment/news, /api/sentiment/fear-greed
- Arbitrage: /api/arbitrage/scan, /api/arbitrage/scan/{symbol}, /api/arbitrage/recent
- Strategy Health: /api/strategy-health/status, /api/strategy-health/ranking

---

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Day Trader | ACTIVE | 75% conf, 15m/1h/4h |
| Long Term | ACTIVE | 88% conf, 4h/1d |
| Free Will v2 | ACTIVE | 80% conf, scan bug fixed |
| Paper Trading | ACTIVE | 9 closed, ~9 open trades |
| Price Alerts v2 | ACTIVE | Batched RSI, vol-confirmed breakouts |
| Self-Healer | ACTIVE | 5 services monitored |
| Sentiment | ACTIVE | News + Fear/Greed |
| Arbitrage | ACTIVE | 5 exchanges |
| Strategy Health | ACTIVE | Auto-bench enabled |
| Telegram Chat | ACTIVE | Auto-webhook on startup |
| Memory Mgmt | ACTIVE | Cleanup routines |

---

## Backlog

### P1 (Next)
- Mobile Optimization - full review of all pages for mobile-friendliness
- Trade Journal improvements - allow notes on individual trades
- server.py refactoring - extract more responsibilities into modules

### P2 (When Ready)
- Real-money trading (user deferred)
- Moltbot deeper integration - sentiment-based trade signals

### P3 (Future)
- More exchange integrations
- Advanced backtesting with multiple timeframes
- Portfolio tracking
- Discord/Slack integration

---

## Deployment
- Preview: https://aeon-trading-1.preview.emergentagent.com
- Backend: Port 8001
- Frontend: Port 3000
