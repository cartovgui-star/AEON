# Aeon Telegram Chatbot PRD

## Original Problem Statement
Build a Telegram chatbot "Aeon" that serves as an AI business partner, crypto trading buddy, and "second brain." The bot should have:
- Switchable persona: casual trading buddy (default) vs philosophical "Alchemy" mode
- Integration with free real-time data APIs for market awareness
- Autonomous trading with paper trading capabilities
- Proactive "Free Will" mode for 24/7 market monitoring

## What's Been Implemented

### Core Features (All Complete)
- [x] Telegram bot webhook with full command system
- [x] OpenAI GPT-4o-mini integration (via Emergent LLM key)
- [x] Dual mode persona (Casual + Alchemy)
- [x] React dashboard for monitoring
- [x] MongoDB for conversation/trade history

### Market Intelligence (All Complete)
- [x] Live prices from MEXC via ccxt
- [x] Technical Analysis (RSI, MACD, BB, EMA, Stoch, ATR)
- [x] Real funding rates from OKX, Bitget, KuCoin, Gate.io
- [x] Real Open Interest from multiple exchanges
- [x] Real Long/Short Ratio from OKX Public API
- [x] Fear & Greed Index from Alternative.me
- [x] Options data (Max Pain, PCR) from Deribit
- [x] Order Flow / CVD analysis
- [x] News & sentiment analysis
- [x] Whale tracking
- [x] BTC on-chain data

### Advanced Analysis (All Complete)
- [x] Divergence Detection (RSI/MACD)
- [x] Market Structure (HH/HL/LH/LL, BOS)
- [x] VWAP calculations with bands
- [x] Multi-timeframe confluence analysis
- [x] Backtesting framework (RSI, BB, EMA strategies)

### Autonomous Trading v2 (JUST COMPLETED - Feb 2026)
- [x] **AutonomousTraderV2** - Elite trading engine
- [x] Uses ALL 8 data sources for signal generation
- [x] 85% minimum confidence threshold
- [x] 4+ confirmation requirement from different sources
- [x] Smart entry timing (pullbacks to key levels)
- [x] Market regime detection (TRENDING/RANGING/VOLATILE)
- [x] BTC correlation filter for alts
- [x] Session awareness (Asia/London/NY overlap)
- [x] Dynamic position sizing by confidence
- [x] Trail stops and partial profit taking
- [x] "Unlimited" signals (quality-filtered)

### Free Will v2 (Complete)
- [x] Ultra-selective alerting (80%+ confidence)
- [x] 3+ source confirmations required
- [x] 30-minute cooldown per symbol
- [x] Max 10 alerts per day
- [x] All 8 data sources integrated

### Coinglass Integration (NEW - Feb 2026)
- [x] API module created (`coinglass_intel.py`)
- [x] API routes added (`/api/coinglass/*`)
- [x] Telegram command `/coinglass btc` or `/cg btc`
- [x] Requires API key (free tier available at coinglass.com/api)
- [x] Supports: funding, OI, L/S ratio, liquidation heatmaps

## Data Sources
| Data | Source | Status |
|------|--------|--------|
| Fear & Greed Index | Alternative.me | ✅ REAL |
| Global Market | CoinGecko | ✅ REAL |
| Prices | MEXC (ccxt) | ✅ REAL |
| Technical Analysis | MEXC (ccxt) | ✅ REAL |
| Funding Rate | OKX, Bitget, KuCoin, Gate.io | ✅ REAL |
| Open Interest | OKX, Bitget | ✅ REAL |
| L/S Ratio | OKX Public API | ✅ REAL |
| Order Flow / CVD | MEXC Trades | ✅ REAL |
| Options (Max Pain/PCR) | Deribit | ✅ REAL |
| News | RSS feeds | ✅ REAL |
| Whale Activity | Whale Alert | ✅ REAL |
| On-Chain | mempool.space | ✅ REAL |
| Coinglass Data | Coinglass API | ⚠️ Requires API key |

## Key Files
```
/app/backend/
├── server.py                 # Main FastAPI app (~2200 lines)
├── autonomous_trader_v2.py   # NEW Elite trading engine
├── autonomous_trader.py      # Legacy (kept for backward compat)
├── free_will_v2.py           # Ultra-selective alerts
├── advanced_strategies.py    # Divergence, Structure, VWAP
├── order_flow.py             # CVD analysis
├── options_data.py           # Max Pain, PCR from Deribit
├── coinglass_intel.py        # NEW Coinglass API module
├── derivatives_intel.py      # Funding, OI, L/S from exchanges
├── market_intelligence.py    # Core TA and market data
├── backtesting.py            # Strategy backtesting
└── routes/, telegram/, tasks/ # Modular structure (partial)
```

## API Endpoints

### Trading v2 APIs (NEW)
- `GET /api/trading/summary` - v2 stats with market context
- `GET /api/trading/opportunities` - Elite signals (85%+ conf)
- `GET /api/trading/v2/stats` - Comprehensive v2 statistics
- `GET /api/trading/v2/open` - Open trades
- `GET /api/trading/v2/closed` - Closed trades (last 20)
- `POST /api/trading/toggle` - Toggle v2 engine
- `POST /api/trading/v2/confidence` - Set min confidence

### Coinglass APIs (NEW)
- `GET /api/coinglass/funding/{symbol}` - Funding rates
- `GET /api/coinglass/oi/{symbol}` - Open interest
- `GET /api/coinglass/ls/{symbol}` - Long/short ratio
- `GET /api/coinglass/liquidations/{symbol}` - Liquidation heatmap (paid)
- `GET /api/coinglass/full/{symbol}` - Combined report

### Free Will v2 APIs
- `GET /api/freewill/stats` - Engine statistics
- `GET /api/freewill/scan/{symbol}` - Manual scan
- `POST /api/freewill/toggle` - Toggle engine
- `POST /api/freewill/confidence` - Set threshold

## Telegram Commands

### Trading v2
- `/auto` - v2 trading status & elite stats
- `/auto on/off` - Toggle v2 engine
- `/opps` - View top elite signals
- `/open` - View open positions

### Analysis
- `/scan btc` - Full AI analysis
- `/ta btc 4h` - Technical indicators
- `/deriv btc` - Derivatives report
- `/coinglass btc` or `/cg btc` - Coinglass data (NEW)

### Advanced
- `/divergence btc` - RSI/MACD divergence
- `/structure btc` - Market structure (HH/HL)
- `/vwap btc` - VWAP with bands
- `/cvd btc` - Order flow analysis
- `/options btc` - Max pain & PCR
- `/adv btc` - Combined advanced analysis

### Market Intel
- `/market` - Global summary
- `/fear` - Fear & Greed Index
- `/news` - Crypto news
- `/whales` - Whale activity
- `/onchain` - BTC on-chain

### Tools
- `/calc entry exit size lev dir` - PnL calculator
- `/calcsize bal risk% entry stop lev` - Position size
- `/backtest btc` or `/bt btc` - Strategy backtest

## Current Performance (Feb 2026)
- **Auto Trader v2**: ACTIVE (85% min conf, 4+ confirmations)
- **Free Will v2**: ACTIVE (80% min conf, 3+ confirmations)
- **Market Regime**: VOLATILE (Fear & Greed: 7 - Extreme Fear)
- **Pairs Monitored**: 25 (top liquidity)
- **Timeframes**: 4h, 1h, 1d
- **Test Success Rate**: 97%+ (29/30 tests passing)

## Prioritized Backlog

### P0 (COMPLETED)
- [x] Autonomous Trader v2 implementation
- [x] v2 integration into server.py
- [x] All trading endpoints updated

### P1 (Next)
- [ ] Complete server.py refactoring (move webhook logic to telegram/handlers.py)
- [ ] Enhance Coinglass integration when API key added

### P2 (Future)
- [ ] Smart Money Concepts (Order Blocks, FVG)
- [ ] Wyckoff Analysis
- [ ] Session-based strategies (Asia/London/NY)

### P3 (Backlog)
- [ ] Cross-session conversation memory
- [ ] ML-based strategy optimization
- [ ] Real trading execution (beyond paper trading)

## How to Get Coinglass API Key
1. Visit https://www.coinglass.com/api
2. Sign up for an account
3. Navigate to API section
4. Generate your API key
5. Add `COINGLASS_API_KEY=your_key` to `/app/backend/.env`
6. Restart backend: `sudo supervisorctl restart backend`

Pricing: Free tier available (limited calls), paid plans ~$30-50/month

## Credentials
- Telegram Bot: https://t.me/ObsidianCabalbot
- Webhook: https://aeon-signals.preview.emergentagent.com/api/webhook
- Dashboard: https://aeon-signals.preview.emergentagent.com

## Test Reports
- `/app/test_reports/iteration_11.json` - Latest test results
