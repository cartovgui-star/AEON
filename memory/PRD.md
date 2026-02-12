# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- Autonomous trading engine (v2) - PAPER TRADING MODE
- Multi-strategy analysis
- Real-time price alerts with NO CONTRADICTING SIGNALS
- Smart Money Concepts (SMC) analysis
- Trade journaling and memory system
- Dashboard with analytics
- Telegram bot integration
- Voice conversation capability
- User profiling system (Aeon learns your preferences)

---

## Latest Session (Feb 12, 2026) - Major Feature Additions

### 1. Anti-Contradiction Alert System ✅
**User Request**: No flip-flopping signals - if LONG sent, won't send SHORT within hours

**Implementation**:
- Added `direction_lock_time = 7200` (2 hours) to Free Will v2
- `last_direction` dict tracks last signal direction per symbol
- `_can_alert()` checks if opposite direction within lock time → blocks it
- `contradictions_blocked` stat tracks how many flip-flops were prevented
- Logs show: "Blocked contradicting signal: DOGE/USDT was SHORT, now LONG"

### 2. Enhanced Settings UI ✅
**Implementation**: Added 4-tab Settings page

**Trading Tab**:
- Enable Auto Trading toggle
- Min Confidence slider (70-95%)
- Trading Stats card (Open Trades, Mode: Paper)

**Alerts Tab**:
- Enable Alerts toggle
- Alert Confidence slider (65-95%)
- Alert System Status (Today/Max, Total, Blocked)
- Direction lock info (2h no flip-flop)
- Recent Signal Directions (e.g., XRP: SHORT, DOGE: SHORT)
- Data Sources list (8 sources)

**Your Profile Tab**:
- Trading Style (scalper/swing/hodler or "Learning...")
- Risk Tolerance (low/medium/high)
- Favorite Coins
- Messages Analyzed count
- Aeon's Understanding section

**Voice Tab**:
- 4 voice options (Guy, Davis, Ryan, William)

### 3. User Profiling System ✅
**File**: `/app/backend/user_profiler.py`

**Features**:
- Tracks coin mentions → builds `favorite_coins` list
- Detects trading style from keywords (scalp/swing/hodl)
- Detects risk tolerance from language (yolo/degen vs cautious/dca)
- Stores key facts about user
- Injects user context into LLM prompts for personalization

**API Endpoints**:
- `GET /api/user/profile` - Get user profile summary
- `GET /api/user/profile/{chat_id}` - Get specific user's profile
- `POST /api/user/profile/{chat_id}/fact` - Add key fact

### 4. Additional Free Data Sources ✅
**File**: `/app/backend/additional_data.py`

**New APIs integrated**:
- **Blockchain.com** - BTC on-chain: hash rate, difficulty, mempool
- **mempool.space** - BTC fee estimates (fastest/economy)
- **gasprice.io/blocknative** - ETH gas prices
- **DefiLlama** - DeFi TVL data
- **CryptoCompare** - Social stats (Reddit, Twitter, GitHub)

**API Endpoints**:
- `GET /api/data/btc/onchain` - BTC on-chain stats
- `GET /api/data/btc/fees` - Mempool fee estimates
- `GET /api/data/eth/gas` - ETH gas prices
- `GET /api/data/defi/tvl` - DeFi TVL
- `GET /api/data/social/{symbol}` - Social stats
- `GET /api/data/all/{symbol}` - All combined

### 5. Conversational AI v4 ✅
**Previous session improvement**:
- Unified personality (no mode switching)
- Follow-up questions in 70%+ of responses
- Response length matches user input
- Anti-repetition system
- Natural proactive messages

**Test Results**: 21/21 tests passed (iteration_17.json)

---

## What's Been Implemented - Complete List

### Session 5 (Feb 12, 2026) - This Session
- ✅ Anti-contradiction alert system (2hr direction lock)
- ✅ Enhanced Settings UI (4 tabs)
- ✅ User profiling system
- ✅ Additional free APIs (5 new sources)

### Session 4 (Feb 12, 2026)
- ✅ Conversational AI v4 (unified personality)
- ✅ Telegram webhook fix

### Session 3 (Feb 12, 2026)
- ✅ Autonomous trading bug fix
- ✅ Live MEXC data integration
- ✅ Trading dashboard enhancements

### Session 2 (Feb 10, 2026)
- ✅ WebSocket real-time alerts
- ✅ Browser push notifications
- ✅ SMC Dashboard page
- ✅ Journal Dashboard page
- ✅ Mobile responsiveness
- ✅ SMC + Strategy confluence

### Session 1 Features
- ✅ Multi-Strategy Engine (6 strategies)
- ✅ Real-Time Price Alert System
- ✅ Analytics Page
- ✅ SMC Analyzer module
- ✅ Memory/Journal system

### Original Features
- ✅ Autonomous Trader v2
- ✅ Multi-page dashboard
- ✅ Voice conversation with Aeon
- ✅ Trade History page
- ✅ Telegram bot with 40+ commands

---

## Key Files

### New This Session
- `/app/backend/user_profiler.py` - User profiling system
- `/app/backend/additional_data.py` - Additional data sources
- `/app/frontend/src/components/SettingsPanel.jsx` - Enhanced settings UI

### Core Files
- `/app/backend/free_will_v2.py` - Alert engine with anti-contradiction
- `/app/backend/aeon_personality.py` - Conversational AI v4
- `/app/backend/autonomous_trader_v2.py` - Paper trading engine
- `/app/backend/server.py` - Main FastAPI server

---

## API Endpoints Summary

### Settings & Configuration
- `GET /api/trading/v2/stats` - Trading engine stats
- `POST /api/trading/toggle` - Toggle auto trading
- `POST /api/trading/v2/confidence` - Set confidence
- `GET /api/freewill/stats` - Alert system stats
- `POST /api/freewill/toggle` - Toggle alerts

### User Profiling
- `GET /api/user/profile` - Get user profile
- `GET /api/user/profile/{chat_id}` - Get specific profile
- `POST /api/user/profile/{chat_id}/fact` - Add fact

### Additional Data
- `GET /api/data/btc/onchain` - BTC on-chain
- `GET /api/data/btc/fees` - Mempool fees
- `GET /api/data/eth/gas` - ETH gas
- `GET /api/data/defi/tvl` - DeFi TVL
- `GET /api/data/social/{symbol}` - Social stats

### Trading
- `GET /api/trading/v2/live-positions` - Open trades
- `GET /api/trading/v2/pnl-history` - Closed trades
- `POST /api/webhook` - Telegram webhook

---

## Feature Status

| Feature | Status | Notes |
|---------|--------|-------|
| Dashboard | ✅ | Main page with stats |
| Trading | ✅ | Live paper trading |
| Settings | ✅ | 4-tab configuration |
| Alerts | ✅ | No contradicting signals |
| User Profiling | ✅ | Learns preferences |
| Conversational AI | ✅ | v4 unified personality |
| Analytics | ✅ | Alerts + Strategies |
| SMC Analysis | ✅ | Market structure |
| Journal | ✅ | Performance tracking |
| Voice Chat | ✅ | Talk to Aeon |
| Telegram Bot | ✅ | 40+ commands |

---

## Backlog / Future Tasks

### P1 (High Priority)
- Enable real-money trading when user is ready

### P2 (Medium Priority)
- Enhanced trade logging form UI
- More exchange integrations

### P3 (Low Priority)
- Coinglass premium integration
- Advanced backtesting

---

## Deployment
- Preview: https://aeon-chat-refine.preview.emergentagent.com
- Backend: Port 8001
- Frontend: Port 3000
