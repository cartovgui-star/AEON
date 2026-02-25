# AEON - Autonomous Crypto Trading Bot
## Complete Technical Specification

**Live Preview**: https://aeon-trading-2.preview.emergentagent.com

---

## 1. OVERVIEW

AEON is a sophisticated autonomous paper trading bot that trades crypto futures using pure technical analysis. It runs 24/7, analyzing 25 trading pairs across multiple timeframes, and executes trades based on a weighted confluence scoring system.

### Core Philosophy
- **Technicals Only Mode**: No sentiment, no Fear & Greed, just pure price action
- **Data-Driven Decisions**: Every trade backed by 4-5 technical confirmations
- **Risk First**: Dynamic position sizing, ATR-based stops, auto-blacklisting bad pairs
- **Free Will**: Bot autonomously chooses leverage, style, and sizing based on market conditions

---

## 2. TRADING ENGINE SPECIFICATIONS

### 2.1 Confluence Scoring System (Weighted)

| Category | Weight | Indicators |
|----------|--------|------------|
| Core Technicals | 60% | RSI, MACD, Bollinger Bands, EMAs (9/21/50), Stochastic |
| Market Structure/SMC | 20% | HH/HL, LL/LH, BOS, CHoCH, FVG, Order Blocks |
| Derivatives/Order Flow | 20% | Funding Rate, Open Interest, L/S Ratio, CVD |

### 2.2 Entry Requirements
- Minimum 4/5 confluences agreeing
- Minimum 80% confidence score
- R:R ratio minimum 2:1
- ATR < 2x average (no choppy markets)
- Pair not blacklisted or on cooldown

### 2.3 Trade Styles (Dynamically Assigned)

| Style | Timeframes | Leverage Range | ATR Trigger |
|-------|------------|----------------|-------------|
| SCALP | 5m, 15m | 50-200x | ATR > 2% (high vol) |
| DAY | 1h, 4h | 20-75x | ATR 1-2% (medium) |
| SWING | 4h, 1d | 10-25x | ATR < 1% (low vol) |

### 2.4 Position Sizing

**Kelly Criterion Formula**: `f = (p*b - q) / b`
- Position range: $500 (min) - $2,500 (max)
- Scales with confidence: Higher confidence = larger position
- 1% max risk per trade

**Position Scaling (50/50 Entry)**:
- Initial entry: 50% of calculated position
- Scale-in: Remaining 50% when price moves 0.3-1.5% in favor

### 2.5 Risk Management

| Feature | Description |
|---------|-------------|
| Auto-Blacklist | Pairs with <30% win rate after 10 trades |
| Cooldown Period | 4 hours after losing trade on same pair |
| Trailing Stop | Moves to breakeven at +1% profit |
| Momentum Exit | Closes early if RSI diverges while in profit |
| Max Open Trades | 15 positions maximum |

---

## 3. TECHNICAL INDICATORS USED

### 3.1 Core Technicals
- **RSI (14)**: <30 = oversold (long bias), >70 = overbought (short bias)
- **MACD (12,26,9)**: Crossovers + histogram expansion
- **Bollinger Bands (20,2)**: Band touches + squeeze detection
- **EMAs**: 9/21/50 stack alignment, pullback entries
- **Stochastic**: Overbought/oversold crossovers
- **ATR**: Stop loss calculation, volatility filtering

### 3.2 Smart Money Concepts (SMC)
- Break of Structure (BOS)
- Change of Character (CHoCH)
- Fair Value Gaps (FVG)
- Order Blocks
- Liquidity Sweeps
- Premium/Discount Zones

### 3.3 Derivatives Data
- Funding Rate (from Binance/MEXC)
- Open Interest changes
- Long/Short Ratio
- Cumulative Volume Delta (CVD)

---

## 4. SUPPORTED TRADING PAIRS

```
BTC/USDT, ETH/USDT, SOL/USDT, BNB/USDT, XRP/USDT,
DOGE/USDT, ADA/USDT, AVAX/USDT, LINK/USDT, DOT/USDT,
ATOM/USDT, UNI/USDT, LTC/USDT, ARB/USDT, OP/USDT,
INJ/USDT, NEAR/USDT, APT/USDT, FIL/USDT, TRX/USDT,
POL/USDT, SHIB/USDT, BCH/USDT, ETC/USDT, XLM/USDT
```

---

## 5. API ENDPOINTS

### 5.1 Trading APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trading/v2/stats` | GET | Full trading statistics |
| `/api/trading/v2/live-positions` | GET | Current open positions |
| `/api/trading/v2/closed` | GET | Closed trade history |
| `/api/trading/v2/close/{symbol}` | POST | Close specific position |
| `/api/trading/v2/trail/{symbol}` | POST | Set trailing stop |
| `/api/trading/v2/toggle-scaling` | POST | Enable/disable position scaling |
| `/api/trading/toggle` | POST | Pause/resume trading |
| `/api/trading/analyze/{symbol}` | GET | Analyze specific symbol |

### 5.2 Dashboard & Stats APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/stats/dashboard` | GET | Best/worst pairs, blacklist, cooldowns |
| `/api/bot/stats` | GET | User/message statistics |
| `/api/accuracy/leaderboard` | GET | Coin win rate leaderboard |
| `/api/system/health` | GET | Service health status |

### 5.3 Analysis APIs
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/market/scan/{symbol}` | GET | Full market scan |
| `/api/smc/{symbol}` | GET | Smart Money analysis |
| `/api/derivatives/{symbol}` | GET | Derivatives data |
| `/api/sentiment/composite` | GET | Market sentiment |

---

## 6. DASHBOARD UI FEATURES

### 6.1 Main Dashboard
- **Status Cards**: Active/Paused, Win Rate, Total PnL, Open Trades, Leverage, Users
- **Daily Goal Progress**: Visual progress bar toward daily PnL target
- **Live Positions**: Real-time display with trade style badges (SCALP/DAY/SWING)
- **Performance Stats**: Best pairs, worst pairs, blacklisted pairs
- **Risk Management Panel**: Cooldowns, auto-blacklist status, position scaling toggle
- **Market Data Grid**: Live prices for BTC, ETH, SOL with click-to-analyze

### 6.2 Trading Page
- **Position Cards**: Click to open detailed modal
- **Position Modal Features**:
  - PnL (% and USD)
  - ROI Badge
  - Risk Assessment
  - Margin Ratio
  - Entry/Current/Target/Stop prices
  - Quick Close buttons (25%, 50%, 75%, 100%)
  - Trailing Stop setter
  - Trade confirmations list

### 6.3 Additional Pages
- **History**: All closed trades with filtering
- **Alerts**: Price alerts and notifications
- **Backtest**: Strategy backtesting on historical data
- **Intel**: Market intelligence and sentiment
- **Analytics**: Performance charts and metrics
- **SMC**: Smart Money Concepts analysis
- **Journal**: Trade notes and journaling
- **Commands**: Telegram command reference
- **Health**: System service monitoring
- **Settings**: Trading configuration

---

## 7. TELEGRAM BOT COMMANDS

### Trading Commands
```
/trade [COIN] - Quick trade analysis
/scan [COIN] - Full market scan
/positions - View open positions
/close [COIN] - Close position
/pnl - Today's PnL summary
```

### Analysis Commands
```
/ta [COIN] - Technical analysis
/smc [COIN] - Smart Money analysis
/structure [COIN] - Market structure
/divergence [COIN] - Divergence detection
/funding - Funding rates
/fear - Fear & Greed index
```

### Stats Commands
```
/stats - Trading statistics
/accuracy - Alert accuracy stats
/leaderboard - Coin performance ranking
/riskcheck - Risk assessment
```

### Settings Commands
```
/start - Initialize bot
/help - Command list
/settings - View/change settings
```

---

## 8. TECHNOLOGY STACK

### Backend
- **Framework**: FastAPI (Python 3.11)
- **Database**: MongoDB
- **Async**: asyncio, motor (async MongoDB driver)
- **Scheduling**: APScheduler

### Frontend
- **Framework**: React 18
- **UI Components**: Shadcn/UI, Tailwind CSS
- **Charts**: Recharts
- **Icons**: Lucide React

### Data Sources
- **Price Data**: MEXC, Binance APIs
- **Market Data**: CoinGecko, CoinGlass
- **News**: CryptoCompare, CryptoPanic
- **Derivatives**: Binance Futures, MEXC Futures

### AI Integration
- **LLM**: OpenAI GPT-4o (via Emergent LLM Key)
- **TTS**: Edge TTS
- **STT**: OpenAI Whisper

---

## 9. PERFORMANCE METRICS

### Current Stats (as of Feb 2026)
- Total Trades: 103
- Win Rate: 19%
- Open Positions: 3
- Best Trade: +12.14%
- Worst Trade: -11.11%
- Profit Factor: 0.71

### Improvement Features Active
- Auto-blacklisting poor performers
- 4-hour cooldown after losses
- 80% minimum confidence threshold
- Position scaling for better entries
- Momentum-based early exits

---

## 10. ARCHITECTURE DIAGRAM

```
┌─────────────────────────────────────────────────────────────┐
│                     AEON TRADING BOT                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │   TELEGRAM   │    │   WEB UI     │    │   REST API   │  │
│  │     BOT      │    │  (React)     │    │  (FastAPI)   │  │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                              │
│                    ┌────────▼────────┐                     │
│                    │  TRADING ENGINE │                     │
│                    │  (autonomous_   │                     │
│                    │   trader_v2)    │                     │
│                    └────────┬────────┘                     │
│                             │                              │
│         ┌───────────────────┼───────────────────┐          │
│         │                   │                   │          │
│  ┌──────▼──────┐    ┌──────▼──────┐    ┌──────▼──────┐   │
│  │  ANALYSIS   │    │   MARKET    │    │ DERIVATIVES │   │
│  │  SERVICE    │    │   INTEL     │    │   INTEL     │   │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘   │
│         │                   │                   │          │
│         └───────────────────┼───────────────────┘          │
│                             │                              │
│                    ┌────────▼────────┐                     │
│                    │    DATA APIS    │                     │
│                    │  MEXC │ Binance │                     │
│                    │ CoinGecko │ etc │                     │
│                    └─────────────────┘                     │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                      MONGODB                          │  │
│  │  trades │ settings │ alerts │ chat_history │ stats   │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. KEY FILES REFERENCE

```
/app
├── backend/
│   ├── server.py                    # Main FastAPI app
│   ├── autonomous_trader_v2.py      # Core trading engine
│   ├── market_intelligence.py       # Technical analysis
│   ├── free_will_v2.py             # Elite signal generation
│   ├── dual_trading_engine.py      # Day/Long term engines
│   ├── routes/                     # 26+ modular route files
│   │   ├── trading.py
│   │   ├── analysis.py
│   │   ├── smc.py
│   │   └── ...
│   └── tests/                      # Pytest test files
│
├── frontend/
│   └── src/
│       ├── App.js                  # Main React app
│       └── components/
│           ├── Dashboard.jsx       # Main dashboard
│           ├── Trading.jsx         # Trading page
│           ├── SettingsPanel.jsx   # Settings
│           └── ...
│
└── memory/
    └── PRD.md                      # Product requirements
```

---

## 12. QUICK START

### Access the Bot
1. **Web Dashboard**: https://aeon-trading-2.preview.emergentagent.com
2. **Telegram**: Search for the bot and send `/start`

### Key Actions
- Click any position card to see detailed trade info
- Use "Quick Trade" button for manual trades
- "Kill Switch" closes all positions immediately
- Click market data cards for instant coin analysis

---

*Built with Emergent Platform | Paper Trading Only | Not Financial Advice*
