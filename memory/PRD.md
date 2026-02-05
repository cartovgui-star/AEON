# Aeon Telegram Chatbot PRD

## Original Problem Statement
Build a Telegram chatbot "Aeon" that integrates with OpenAI - a business partner and second brain character with crypto/alchemy personality traits. The bot should have autonomous trading capabilities, learning from market data to generate trading signals.

## User Personas
- **Primary User**: Crypto traders/enthusiasts seeking an AI partner for analysis and philosophical discussions
- **Bot Character**: Aeon - blunt, direct business partner forged in alchemy and crypto mastery

## Core Requirements
- Telegram bot webhook integration
- OpenAI GPT-4o-mini integration (via Emergent LLM key)
- Conversation memory within sessions
- Monitoring dashboard for bot activity
- **Autonomous trading with learning feedback loop**

## What's Been Implemented

### Phase 1: Core Bot (Completed)
- [x] Backend Telegram webhook endpoint (`/api/webhook`)
- [x] OpenAI integration via Emergent integrations library
- [x] Conversation history stored in MongoDB
- [x] Context-aware responses (maintains recent conversation history)
- [x] Bot statistics API (`/api/bot/stats`)
- [x] Message history API (`/api/bot/messages`)
- [x] React dashboard with real-time stats

### Phase 2: MEXC Integration (Completed)
- [x] Live MEXC crypto data via ccxt library
- [x] Real-time BTC/USDT, ETH/USDT, SOL/USDT prices
- [x] `/api/mexc/live` endpoint for market data
- [x] `/price` command for quick market snapshot
- [x] MEXC data injected into every Aeon response
- [x] Dashboard shows live prices with trend indicators

### Phase 3: Aeon Quartet Upgrade (Completed)
- [x] Full orderbook analysis (bid/ask depth, imbalance %)
- [x] Dual mode detection (Trading vs Alchemy keywords)
- [x] 30 alchemical interview questions bank
- [x] Scheduled rituals (6AM crypto, 8:45AM stocks CST)
- [x] Background ritual runner with asyncio
- [x] Obsidian vault integration (webhook ready)
- [x] New commands: /probe, /ritual
- [x] Conversation context tracking (trading/alchemy/ritual)

### Phase 4: Market Intelligence (Completed)
- [x] Real-time technical analysis via MEXC/ccxt
- [x] Indicators: RSI, MACD, Bollinger Bands, EMA (9/21/50), ATR, Stochastic
- [x] Trading signal detection with bias scoring
- [x] Trade setup analyzer with entry/target/stop levels
- [x] Learning system to track predictions
- [x] Commands: /scan, /ta, /positions, /funding
- [x] Automatic high-probability setup alerts (Free Will)

### Phase 5: Quantum Mason & Free Will (Completed)
- [x] Quantum Mason persona for /probe command
- [x] Free Will mode - proactive user engagement
- [x] Intensity levels: INITIATE → APPRENTICE → FELLOWCRAFT → MASTER
- [x] Deep/ordeal probe modes for shadow work

### Phase 6: Autonomous Trading System (Completed - Feb 2026)
- [x] **AutonomousTrader class** - scans markets every 5 minutes
- [x] **Paper trading** - records predictions without executing real trades
- [x] **Learning feedback loop** - adjusts strategy weights based on outcomes
- [x] **Strategy persistence** - saves weights to MongoDB
- [x] **New commands**: /auto, /auto on/off, /opps, /open, /strategy
- [x] **Dashboard integration** - shows trading stats, win rate, PnL
- [x] **Telegram alerts** - notifies users of high-confidence setups and closed trades

## Technical Architecture
- **Backend**: FastAPI + MongoDB + Emergent integrations
- **Frontend**: React + TailwindCSS + shadcn/ui
- **LLM**: OpenAI gpt-4o-mini via Emergent Universal Key
- **Bot**: Telegram Bot API with webhook mode
- **Market Data**: MEXC + Bybit via ccxt library

## Key Files
- `/app/backend/server.py` - Main FastAPI app, webhook, commands
- `/app/backend/autonomous_trader.py` - Autonomous trading engine
- `/app/backend/market_intelligence.py` - Market data & technical analysis
- `/app/backend/learning_system.py` - Prediction tracking & learning
- `/app/frontend/src/App.js` - Dashboard with trading stats

## API Endpoints

### Trading APIs
- `GET /api/trading/summary` - Comprehensive trading summary
- `GET /api/trading/opportunities` - Current market opportunities
- `GET /api/trading/analyze/{symbol}` - Detailed symbol analysis
- `GET /api/trading/strategy` - Strategy weights and performance
- `POST /api/trading/toggle` - Enable/disable autonomous trading

### Market APIs
- `GET /api/market/scan/{symbol}` - Full market scan
- `GET /api/market/ta/{symbol}` - Technical analysis
- `GET /api/market/funding/{symbol}` - Funding rate data
- `GET /api/market/positions/{symbol}` - Long/short ratio data

### Learning APIs
- `GET /api/learning/stats` - Prediction statistics
- `GET /api/learning/open` - Open predictions

## Telegram Commands

### Analysis
- `/scan btc` - Full market analysis
- `/ta btc` - Technical indicators
- `/positions btc` - Long/short data
- `/funding btc` - Funding rates
- `/price` - MEXC orderbook

### Autonomous Trading
- `/auto` - Trading status & stats
- `/auto on/off` - Toggle auto-trading
- `/opps` - Current opportunities
- `/open` - Open positions
- `/strategy` - Strategy performance

### Quantum Mason
- `/probe` - Standard question
- `/probe deep` - Multi-layer spiral
- `/probe ordeal` - Shadow work mode
- `free on/off` - Toggle proactive AI
- `/stats` - Full performance

## Database Collections
- `chat_messages` - Conversation history
- `user_settings` - User preferences (free_will, etc.)
- `probe_states` - Quantum Mason progress
- `user_insights` - Learned user insights
- `predictions` - Trade predictions and outcomes
- `strategy_weights` - Current strategy weights

## Credentials (Pre-configured)
- Telegram Bot Token: `8586106246:AAHZTWfSHMuLwyGxeOn9DelRaesZF2Joans`
- Bot URL: https://t.me/ObsidianCabalbot
- Webhook URL: https://quantum-mason.preview.emergentagent.com/api/webhook

## Current Performance
- Total Trades: 2
- Win Rate: 100%
- Total PnL: +26.72%
- Status: ACTIVE
- Tracked Symbols: BTC, ETH, SOL, DOGE, XRP, AVAX

## Recent Enhancements (Feb 2026)
- [x] Added 3 more trading pairs: DOGE, XRP, AVAX
- [x] Implemented funding rate alerts (triggers on >0.08%)
- [x] Implemented liquidation alerts (triggers on >$8M)
- [x] Enhanced trade close notifications with running stats
- [x] Added `/liqs` command for liquidation data
- [x] All 6 coins now scanned every 5 minutes

## Alerts System
Aeon automatically alerts users (with Free Will ON) when:
- **High-confidence trade signals** (≥75% confidence)
- **Trade closes** (win or loss, with running stats)
- **Extreme funding rates** (>0.08% - squeeze potential)
- **Large liquidations** (>$8M - market stress)

## Prioritized Backlog

### P1 (Next)
- [ ] Add more trading pairs (DOGE, XRP, AVAX)
- [ ] Implement funding rate & liquidation alerts
- [ ] Cross-session conversation memory

### P2 (Future)
- [ ] Order flow analysis tools
- [ ] ML-based strategy optimization
- [ ] Backtesting framework
- [ ] Portfolio position sizing

### P3 (Backlog)
- [ ] Refactor server.py into smaller modules
- [ ] User analytics dashboard
- [ ] Export conversation history
- [ ] Multi-exchange support

## Mocked APIs Note
Long/short ratio, funding rate, and liquidation data are **MOCKED** with random values as MEXC doesn't provide this data via public API. This is documented for awareness.

## Next Steps
1. User to verify autonomous trading system in Telegram
2. Monitor paper trading performance over time
3. Consider adding more trading pairs based on user preference
4. Evaluate if real trading integration is desired
