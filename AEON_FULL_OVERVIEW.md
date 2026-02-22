# AEON Trading Bot - Complete Overview

## What is AEON?
AEON is an autonomous AI-powered crypto trading bot with a sophisticated personality. It performs **paper trading** using real market data from MEXC exchange, provides market intelligence via Telegram and web UI, and has conversational AI capabilities.

---

## CORE FEATURES

### 1. Autonomous Paper Trading
- **Scans 44 crypto pairs** every 5 minutes
- **Dynamic entry/exit decisions** based on technical + sentiment analysis
- **Trade styles**: SCALP (50-200x), DAY (20-75x), SWING (10-25x)
- **Dynamic position sizing**: $500-$2500 based on confidence
- **Dynamic leverage**: Varies with randomness for each trade
- **Auto trailing stops**: Locks in profits as price moves favorably
- **Partial profit taking**: Closes 50% at first target

### 2. Market Intelligence
- **Technical Analysis**: RSI, MACD, Bollinger Bands, EMA, Stochastic
- **Smart Money Concepts (SMC)**: Order blocks, Fair Value Gaps, Break of Structure
- **Multi-Timeframe Analysis**: 1h, 4h, 1d confluence
- **Derivatives Data**: Funding rates, Open Interest, Long/Short ratios
- **On-Chain Data**: Whale movements, exchange flows
- **Sentiment**: Fear & Greed Index, social stats, news

### 3. AI Personality (Conversational)
- **Text chat**: Natural conversations about trading, life, markets
- **Voice chat**: Talk to Aeon via web UI (TTS + STT)
- **Alchemy Mode**: Mystical/philosophical responses
- **Casual Mode**: Direct trading focus
- **Proactive check-ins**: Never repeats same question

### 4. Alert System
- **Elite Free Will Alerts**: 80%+ confidence, 3+ confirmations
- **Price Alerts**: Set custom above/below triggers
- **Trade Signals**: Entry, SL, TP with detailed explanations
- **Performance Tracking**: Accuracy stats per coin

---

## TELEGRAM COMMANDS (50+)

### Quick Start
| Command | Description |
|---------|-------------|
| `/scan [coin]` | Full SMC analysis with entry/SL/TP |
| `/ta [coin] [tf]` | Technical indicators (RSI, MACD, BB) |
| `/auto` | Paper trading status |
| `/fw` | Free Will elite alerts status |

### Analysis
| Command | Description |
|---------|-------------|
| `/scan [coin]` | Full SMC analysis |
| `/ta [coin] [tf]` | Technical indicators |
| `/mtf [coin]` | Multi-timeframe view |
| `/structure [coin]` | HH/HL/LH/LL market structure |
| `/smc [coin]` | Order blocks & FVG |
| `/divergence [coin]` | RSI/MACD divergence scan |
| `/advanced [coin]` | Full advanced analysis |

### Market Data
| Command | Description |
|---------|-------------|
| `/market` | Global market summary |
| `/fear` | Fear & Greed Index |
| `/top100` | Top 10 by market cap |
| `/movers` | 24h gainers/losers |
| `/trending` | Most searched coins |
| `/news` | Latest crypto news |
| `/whales` | Whale activity |
| `/onchain` | BTC on-chain stats |

### Derivatives
| Command | Description |
|---------|-------------|
| `/funding [coin]` | Funding rates across exchanges |
| `/deriv [coin]` | Full derivatives data |
| `/positions [coin]` | Long/Short ratio |
| `/cg [coin]` | Coinglass data |
| `/options [btc/eth]` | Options analysis |
| `/cvd [coin]` | Order flow / CVD |

### Trading
| Command | Description |
|---------|-------------|
| `/auto on/off` | Toggle paper trading |
| `/opps` | Current opportunities |
| `/open` | Open positions |
| `/close [coin]` | Close position |
| `/trail [coin] [%]` | Set trailing stop |

### Performance
| Command | Description |
|---------|-------------|
| `/accuracy` | Alert accuracy stats |
| `/leaderboard` | Coin win rates ranking |
| `/stats` | Learning system stats |
| `/journal` | Trading journal |

### Alerts
| Command | Description |
|---------|-------------|
| `/alerts` | View active alerts |
| `/alert add [coin] above/below [price]` | Create price alert |
| `/fw` | Free Will status |
| `/fwconf [80-95]` | Set confidence threshold |

### Advanced
| Command | Description |
|---------|-------------|
| `/intel` | Full market intelligence |
| `/arbi` | Multi-exchange arbitrage |
| `/health` | Strategy health check |
| `/probe` | Quantum consciousness probe |

### Modes
- Say **"alchemy mode"** for mystical responses
- Say **"casual mode"** for trading focus

---

## WEB UI FEATURES

### Dashboard
- Live MEXC data banner
- Status cards: Active, Win Rate, PnL, Open Trades, Leverage, Users
- Daily Goal Progress bar
- Live Positions preview
- Live Market Data (BTC, ETH, SOL)
- AI Engine Status
- Recent Activity feed

### Trading Page
- Performance chart
- Market Regime / BTC Bias / Fear & Greed / Session indicators
- Min Confidence slider (60-95%)
- Tabs: Positions, Opportunities, History
- Position cards with full details

### Position Card Modal (Professional Exchange Style)
- Symbol with LONG/SHORT badge, leverage, trade type
- LIVE indicator with pulse
- Unrealized PnL (% and USD) with glow effect
- ROI badge
- Progress bar (SL → Current → TP)
- Key stats: Entry, Mark, Size, Margin
- Risk Assessment (HIGH/MEDIUM/LOW)
- Margin Ratio bar
- Distance to Stop
- Signal Confidence bar
- Price Levels visualization
- Signal Confirmations chips
- Quick Close buttons (25%, 50%, 75%, 100%)
- Set Trailing Stop input
- Close Position / Back buttons

### Other Pages
- **History**: Past trades with filters
- **Alerts**: Active price alerts
- **Backtest**: Strategy backtesting
- **Intel**: Market intelligence dashboard
- **Analytics**: Performance analytics
- **SMC**: Smart Money Concepts view
- **Journal**: Trading journal
- **Health**: Strategy health monitoring
- **Settings**: Bot configuration
- **Live**: Real-time feed
- **Commands**: Full command reference

### Voice Conversation
- Talk to Aeon button (top right)
- Voice selector (Confident American, British, etc.)
- Start Talking button with mic visualization
- Text input fallback ("Prefer typing?")
- Conversation history
- TTS audio playback

---

## TECHNICAL ARCHITECTURE

### Backend (FastAPI + Python)
```
/app/backend/
├── server.py              # Main server, Telegram webhook, core logic
├── autonomous_trader_v2.py # Paper trading engine
├── free_will_engine.py    # Elite signal filtering
├── market_intel.py        # Technical analysis
├── enhanced_intel.py      # Extended market data
├── derivatives_intel.py   # Funding, OI, L/S ratios
├── smc_analysis.py        # Smart Money Concepts
├── advanced_strategies.py # VWAP, Divergence, Structure
├── aeon_personality.py    # AI personality & responses
├── learning_system.py     # ML prediction tracking
├── trade_outcome_tracker.py # Accuracy tracking
├── additional_data.py     # News, on-chain, social
├── voice_tts.py           # Text-to-speech (Edge TTS)
├── routes/                # 29 modular API route files
│   ├── trading.py
│   ├── analysis.py
│   ├── accuracy.py
│   ├── voice.py
│   └── ... (26 more)
└── tests/                 # Unit tests
```

### Frontend (React + Tailwind)
```
/app/frontend/src/
├── App.js                 # Main app, routing, state
├── components/
│   ├── Trading.jsx        # Trading page + PositionCardModal
│   ├── VoiceConversation.jsx # Voice chat UI
│   ├── Dashboard.jsx
│   ├── Alerts.jsx
│   └── ... (12 more)
└── components/ui/         # Shadcn components
```

### Database (MongoDB)
Collections:
- `chat_messages` - Telegram conversations
- `user_settings` - Per-user preferences
- `trades` - Trade history
- `open_trades` - Current positions
- `price_alerts` - User price alerts
- `predictions` - ML predictions
- `trade_outcomes` - Accuracy tracking
- `journal_entries` - Trading journal
- `trader_settings` - Bot configuration

---

## INTEGRATIONS

| Service | Purpose |
|---------|---------|
| **MEXC Exchange** | Primary market data source |
| **Binance** | Technical analysis data |
| **CoinGecko** | Global market data, trending |
| **CoinGlass** | Derivatives data |
| **OpenAI GPT-4o** | Conversational AI (via Emergent) |
| **Edge TTS** | Text-to-speech voices |
| **OpenAI Whisper** | Speech-to-text |
| **Telegram Bot API** | Primary interaction interface |
| **CryptoCompare** | News, social stats |
| **CryptoPanic** | News aggregation |
| **DefiLlama** | DeFi TVL data |
| **Blockchain.com** | BTC on-chain data |

---

## CURRENT STATS

```
Status: ACTIVE
Total Trades: 105
Open Trades: 5
Win Rate: 19%
Total PnL: -22.29%
Best Trade: +12.14%
Worst Trade: -11.11%
Market Regime: VOLATILE
Fear & Greed: 9 (Extreme Fear)
Min Confidence: 70%
Min Confirmations: 3
```

---

## KEY DIFFERENTIATORS

1. **FREE WILL**: Aeon chooses its own trades - not just rule-based
2. **Dynamic Everything**: Leverage, position size, trade style all vary
3. **No Repeated Questions**: Tracks conversation history per user
4. **Multi-Source Intelligence**: 10+ data sources combined
5. **Professional UI**: Exchange-style position management
6. **Voice Interaction**: Talk to your bot naturally
7. **Detailed Explanations**: Every signal explains WHY and what could go wrong

---

## FILES SUMMARY

- **34 Backend Python files**
- **29 Route modules**
- **15 Frontend components**
- **50+ Telegram commands**
- **26 API endpoint groups**
- **9 Test cases**

---

*AEON - Your Autonomous Trading Intelligence*
