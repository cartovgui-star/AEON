# Aeon Trading Bot PRD

## Original Problem Statement
Build a sophisticated trading bot named "Aeon" with:
- **Dual Trading Engine** - Day Trader (aggressive) + Long Term (smart) running simultaneously
- Autonomous paper trading with live MEXC data
- No contradicting signals (direction lock prevents flip-flopping)
- Smart alerts that are only the best setups
- User profiling (Aeon learns your preferences)

---

## Latest Session (Feb 12, 2026) - Dual Trading Engine

### Dual Trading Engine v3 ✅
**User Request**: Day trader style (scalps/swings - aggressive) + Long term (smart/cautious) running at the same time

**Implementation**:

**Day Trader (AGGRESSIVE)**:
- Timeframes: 15m, 1h, 4h
- Min Confidence: 75%
- Direction Lock: 1 hour
- Max Daily Alerts: 20
- Cooldown: 15 min per symbol
- R:R: 1.5:2.5 (tighter stops)

**Long Term (SMART)**:
- Timeframes: 4h, 1d
- Min Confidence: 88%
- Direction Lock: 4 hours
- Max Daily Alerts: 6
- Cooldown: 2 hours per symbol
- R:R: 2.0:5.0 (wider stops, bigger moves)

**API Endpoints**:
- `GET /api/dual/stats` - Get both engines' statistics
- `POST /api/dual/toggle` - Toggle entire system
- `POST /api/dual/day-trader/toggle` - Toggle day trader
- `POST /api/dual/long-term/toggle` - Toggle long term
- `POST /api/dual/day-trader/confidence` - Set day trader confidence
- `POST /api/dual/long-term/confidence` - Set long term confidence

**UI**: Settings > Alerts tab now shows:
- Day Trader card (yellow) with toggle, confidence slider, stats
- Long Term card (blue) with toggle, confidence slider, stats
- Legacy Free Will alerts
- Alert System Status with recent signal directions

---

## Previous Sessions Summary

### Anti-Contradiction System ✅
- Direction lock prevents flip-flopping (no LONG → SHORT within lock period)
- Contradictions blocked count tracked

### User Profiling System ✅
- Tracks favorite coins from conversations
- Detects trading style (scalper/swing/hodler)
- Detects risk tolerance (low/medium/high)
- Personalizes Aeon's responses

### Additional Free APIs ✅
- Blockchain.com (BTC on-chain)
- mempool.space (BTC fees)
- ETH gas prices
- DefiLlama (DeFi TVL)
- CryptoCompare (social stats)

### Conversational AI v4 ✅
- Unified personality (no mode switching)
- Asks follow-up questions
- Response length matches input
- Never repetitive

---

## Key Files

### Dual Trading Engine
- `/app/backend/dual_trading_engine.py` - DualTradingEngine class
- `/app/backend/server.py` - Background task `dual_trading_scanner()`

### Settings UI
- `/app/frontend/src/components/SettingsPanel.jsx` - 4-tab settings with dual engine

### Other Key Files
- `/app/backend/free_will_v2.py` - Legacy alert engine
- `/app/backend/user_profiler.py` - User learning system
- `/app/backend/aeon_personality.py` - Conversational AI
- `/app/backend/autonomous_trader_v2.py` - Paper trading

---

## API Endpoints Summary

### Dual Trading Engine
- `GET /api/dual/stats`
- `POST /api/dual/toggle`
- `POST /api/dual/day-trader/toggle`
- `POST /api/dual/day-trader/confidence`
- `POST /api/dual/long-term/toggle`
- `POST /api/dual/long-term/confidence`

### Legacy Free Will
- `GET /api/freewill/stats`
- `POST /api/freewill/toggle`

### User Profile
- `GET /api/user/profile`
- `GET /api/user/profile/{chat_id}`

### Additional Data
- `GET /api/data/btc/onchain`
- `GET /api/data/btc/fees`
- `GET /api/data/eth/gas`
- `GET /api/data/defi/tvl`

---

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| Day Trader | ✅ ACTIVE | 75% conf, 15m/1h/4h |
| Long Term | ✅ ACTIVE | 88% conf, 4h/1d |
| Free Will v2 | ✅ ACTIVE | 80% conf, legacy |
| Paper Trading | ✅ ACTIVE | 10 open trades |
| User Profiling | ✅ ACTIVE | Learning preferences |
| Telegram Chat | ✅ ACTIVE | Responding |
| All Alerts | ✅ RUNNING | No contradictions |

---

## Backlog

### P1 (When Ready)
- Enable real-money trading

### P2 (Future)
- Trade logging form UI
- More exchange integrations
- Advanced backtesting

---

## Deployment
- Preview: https://aeon-chat-refine.preview.emergentagent.com
- Backend: Port 8001
- Frontend: Port 3000
