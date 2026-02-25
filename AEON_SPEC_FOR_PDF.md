# AEON Trading Bot
## Complete System Documentation

---

**Live URL**: https://aeon-trading-2.preview.emergentagent.com

---

## 1. Executive Summary

AEON is an autonomous cryptocurrency paper trading bot that operates 24/7, analyzing markets and executing trades based on technical analysis, smart money concepts, and derivatives data.

| Property | Value |
|----------|-------|
| Bot Type | Autonomous Paper Trading Bot |
| Markets | Crypto Futures (25 pairs) |
| Exchanges | MEXC, Binance (data feeds) |
| Trading Mode | Paper Trading (simulated) |
| Operation | 24/7 Autonomous |
| AI Powered | Yes - GPT-4o for conversation |

### Current Statistics
- **Total Trades**: 103+
- **Win Rate**: 19%
- **Active Positions**: 2-3
- **Trading Pairs**: 25
- **Active Users**: 38+

---

## 2. System Architecture

### Technology Stack

**Backend:**
- Framework: FastAPI (Python 3.11)
- Database: MongoDB with Motor (async driver)
- Task Scheduling: APScheduler
- Async Runtime: asyncio
- Process Manager: Supervisor
- Web Server: Uvicorn

**Frontend:**
- Framework: React 18
- Build Tool: Create React App + Craco
- UI Components: Shadcn/UI
- Styling: Tailwind CSS
- Charts: Recharts
- Icons: Lucide React

**Infrastructure:**
- Hosting: Emergent Platform (Kubernetes)
- Container: Docker
- Proxy: Nginx
- SSL: Cloudflare
- Backend Port: 8001
- Frontend Port: 3000

---

## 3. AI & API Integrations

### AI Services

#### OpenAI GPT-4o (Conversation AI)
- **Purpose**: Powers "Talk to Aeon" voice/text chat
- **Model**: gpt-4o-mini
- **Integration**: Emergent LLM Key (Universal Key)
- **Features**:
  - Natural language trading questions
  - Market analysis explanations
  - Personalized responses
  - Context-aware conversation

#### OpenAI Whisper (Speech-to-Text)
- **Purpose**: Transcribe user voice input
- **Integration**: Emergent LLM Key
- **Endpoint**: `/api/voice/transcribe`

#### Edge TTS (Text-to-Speech)
- **Purpose**: Generate Aeon's voice responses
- **Voices**: Multiple options (male, female)
- **Output**: MP3 audio

### Market Data APIs

| API | Purpose | Rate Limit |
|-----|---------|------------|
| MEXC Exchange | Primary price data & orderbook | 1200/min |
| Binance | Technical indicators, funding rates | 1200/min |
| CoinGecko | Market cap, global data | 10-30/min |
| CoinGlass | Derivatives data, liquidations | 30/min |
| CryptoCompare | News aggregation | - |
| CryptoPanic | Crypto news feed | - |

### Telegram Bot API
- **Token**: TELEGRAM_TOKEN (in .env)
- **Webhook**: Auto-configured on startup
- **Endpoint**: `/webhook` (receives updates)
- **Features**: Inline keyboards, Markdown formatting, Real-time alerts

---

## 4. Trading Engine Specifications

### Confluence Scoring System (Weighted)

| Category | Weight | Indicators |
|----------|--------|------------|
| Core Technicals | 60% | RSI, MACD, Bollinger Bands, EMAs (9/21/50), Stochastic |
| Market Structure/SMC | 20% | HH/HL, LL/LH, BOS, CHoCH, FVG, Order Blocks |
| Derivatives/Order Flow | 20% | Funding Rate, Open Interest, L/S Ratio, CVD |

### Entry Requirements
- Minimum 4/5 confluences agreeing
- Minimum 80% confidence score
- R:R ratio minimum 2:1
- ATR < 2x average (no choppy markets)
- Pair not blacklisted or on cooldown

### Trade Styles (Dynamically Assigned)

| Style | Timeframes | Leverage | ATR Trigger |
|-------|------------|----------|-------------|
| SCALP | 5m, 15m | 50-200x | ATR > 2% (high vol) |
| DAY | 1h, 4h | 20-75x | ATR 1-2% (medium) |
| SWING | 4h, 1d | 10-25x | ATR < 1% (low vol) |

### Position Sizing

**Kelly Criterion Formula**: `f = (p × b - q) / b`

| Parameter | Value |
|-----------|-------|
| Minimum Position | $500 |
| Maximum Position | $2,500 |
| Base Position | $1,000 |
| Risk Per Trade | 1% max |

**Position Scaling (50/50 Entry)**:
- Initial Entry: 50% of calculated size
- Scale-In: Remaining 50% when price moves 0.3-1.5% in favor

### Risk Management

| Feature | Description |
|---------|-------------|
| Auto-Blacklist | Pairs with <30% win rate after 10 trades |
| Cooldown Period | 4 hours after losing trade on same pair |
| Volatility Filter | Skip if ATR > 2x 20-period average |
| Max Open Trades | 15 positions maximum |
| Min Confidence | 80% threshold for trade entry |
| Trailing Stop | Moves to breakeven at +1% profit |
| Momentum Exit | Early exit if RSI diverges while in profit |

### Supported Trading Pairs (25)

```
BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT,
DOGE/USDT, ADA/USDT, AVAX/USDT, LINK/USDT, DOT/USDT,
ATOM/USDT, UNI/USDT, LTC/USDT, ARB/USDT, OP/USDT,
INJ/USDT, NEAR/USDT, APT/USDT, FIL/USDT, TRX/USDT,
POL/USDT, SHIB/USDT, BCH/USDT, ETC/USDT, XLM/USDT
```

---

## 5. Technical Indicators

### Core Technicals
| Indicator | Configuration | Usage |
|-----------|---------------|-------|
| RSI | Period: 14 | <30 = oversold (long), >70 = overbought (short) |
| MACD | 12,26,9 | Crossovers + histogram expansion |
| Bollinger Bands | 20,2 | Band touches + squeeze detection |
| EMAs | 9/21/50 | Stack alignment, pullback entries |
| Stochastic | 14,3,3 | Overbought/oversold crossovers |
| ATR | Period: 14 | Stop loss calculation, volatility filtering |

### Smart Money Concepts (SMC)
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Fair Value Gaps (FVG)
- Order Blocks
- Liquidity Sweeps
- Premium/Discount Zones

### Derivatives Data
- Funding Rate (from Binance/MEXC)
- Open Interest changes
- Long/Short Ratio
- Cumulative Volume Delta (CVD)

---

## 6. Frontend Dashboard

### Navigation Menu
| Page | Description |
|------|-------------|
| Dashboard | Main stats, positions, market data |
| Trading | Position management, trade details |
| History | Closed trades history |
| Alerts | Price alerts management |
| Backtest | Strategy backtesting |
| Intel | Market intelligence |
| Analytics | Performance charts |
| SMC | Smart Money analysis |
| Journal | Trade journaling |
| Commands | Telegram command reference |
| Health | System health monitoring |
| Settings | Configuration |

### Dashboard Components
1. **Stats Bar** - Status, Win Rate, PnL, Open Trades, Leverage, Users
2. **Daily Goal Progress** - Visual progress toward daily target
3. **Live Positions** - Real-time position display with PnL
4. **Performance Stats** - Best/Worst pairs, Risk Management
5. **Live Market Data** - BTC, ETH, SOL prices with buy/sell imbalance

### Position Modal Features
- PnL (percentage and USD)
- ROI Badge
- Risk Assessment
- Margin Ratio
- Entry/Current/Target/Stop prices
- Quick Close buttons (25%, 50%, 75%, 100%)
- Trailing Stop setter
- Trade confirmations list

---

## 7. Telegram Bot Commands (50+)

### Trading Commands
```
/trade [COIN]   - Quick trade analysis
/scan [COIN]    - Full market scan with SMC
/positions      - View all open positions
/close [COIN]   - Close specific position
/closeall       - Emergency close all positions
/pnl            - Today's PnL summary
```

### Analysis Commands
```
/ta [COIN]        - Technical analysis (RSI, MACD, BB)
/smc [COIN]       - Smart Money Concepts analysis
/structure [COIN] - Market structure (HH/HL, BOS)
/divergence [COIN]- RSI divergence detection
/funding          - Funding rates
/fear             - Fear & Greed index
```

### Stats Commands
```
/stats        - Trading statistics
/accuracy     - Alert accuracy stats
/leaderboard  - Coin performance ranking
/riskcheck    - Risk assessment
```

---

## 8. API Endpoints (70+)

### Trading Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/trading/v2/stats | Full trading statistics |
| GET | /api/trading/v2/live-positions | Live positions with PnL |
| GET | /api/trading/v2/closed | Closed trades history |
| POST | /api/trading/v2/close/{symbol} | Close position |
| POST | /api/trading/v2/trail/{symbol} | Set trailing stop |
| POST | /api/trading/v2/toggle-scaling | Toggle position scaling |

### Dashboard & Stats
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/stats/dashboard | Best/worst pairs, blacklist, cooldowns |
| GET | /api/accuracy/leaderboard | Coin performance leaderboard |
| GET | /api/system/health | Service health status |

### Analysis
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/analysis/{symbol} | Technical analysis |
| GET | /api/smc/{symbol} | Smart Money Concepts |
| GET | /api/derivatives/{symbol} | Derivatives data |
| GET | /api/sentiment/composite | Composite sentiment |

### Voice
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/voice/respond | Voice conversation (TTS) |
| POST | /api/voice/transcribe | Transcribe audio (STT) |

---

## 9. Database Schema (MongoDB)

### Collections

**v2_open_trades**
```json
{
  "_id": "trade_103",
  "symbol": "BCH/USDT",
  "direction": "LONG",
  "entry_price": 495.30,
  "stop_price": 482.09,
  "target_price": 528.33,
  "position_size": 1200,
  "leverage": 25,
  "confidence": 70.0,
  "trade_type": "SWING",
  "pending_scale_in": true
}
```

**v2_closed_trades**
```json
{
  "_id": "trade_99",
  "symbol": "ETH/USDT",
  "pnl_pct": 1.54,
  "exit_reason": "TARGET"
}
```

**trader_settings**
```json
{
  "_id": "v2_settings",
  "active": true,
  "min_confidence": 80,
  "position_scaling_enabled": true
}
```

---

## 10. Background Tasks

| Task | Interval | Description |
|------|----------|-------------|
| autonomous_trading_v2 | 60s | Scan markets, execute trades |
| free_will_v2 | 90s | Elite signal generation |
| dual_engine | 120s | Day trader + Long term scans |
| price_alerts | 30s | Check price alert triggers |
| trade_evaluation | 30s | Evaluate trades, trail stops |
| self_healer | 60s | Monitor service health |

---

## 11. Environment Variables

### Backend (.env)
| Variable | Purpose |
|----------|---------|
| MONGO_URL | MongoDB connection string |
| DB_NAME | Database name (aeon_trading) |
| TELEGRAM_TOKEN | Telegram bot token |
| MEXC_API_KEY | MEXC exchange API key |
| EMERGENT_KEY | Emergent LLM universal key |

### Frontend (.env)
| Variable | Value |
|----------|-------|
| REACT_APP_BACKEND_URL | https://aeon-trading-2.preview.emergentagent.com |

---

## Summary

AEON is a comprehensive autonomous trading system featuring:

- ✅ 24/7 autonomous paper trading
- ✅ 25 crypto pairs coverage
- ✅ Weighted confluence scoring (Tech 60%, SMC 20%, Derivatives 20%)
- ✅ Dynamic trade styles (SCALP/DAY/SWING) based on volatility
- ✅ Position scaling (50/50 entry system)
- ✅ Risk management (auto-blacklist, cooldowns, trailing stops)
- ✅ AI-powered voice/text chat (GPT-4o)
- ✅ Full web dashboard with real-time data
- ✅ Telegram bot with 50+ commands
- ✅ Comprehensive API (70+ endpoints)
- ✅ MongoDB persistence
- ✅ Self-healing system monitoring

---

**Document Version**: 2.0  
**Last Updated**: February 24, 2026  
**Live URL**: https://aeon-trading-2.preview.emergentagent.com
