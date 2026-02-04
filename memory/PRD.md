# Aeon Telegram Chatbot PRD

## Original Problem Statement
Build a Telegram chatbot "Aeon" that integrates with OpenAI - a business partner and second brain character with crypto/alchemy personality traits.

## User Personas
- **Primary User**: Crypto traders/enthusiasts seeking an AI partner for analysis and philosophical discussions
- **Bot Character**: Aeon - blunt, direct business partner forged in alchemy and crypto mastery

## Core Requirements
- Telegram bot webhook integration
- OpenAI GPT-4o-mini integration (via Emergent LLM key)
- Conversation memory within sessions
- Monitoring dashboard for bot activity

## What's Been Implemented (Jan 2026)
- [x] Backend Telegram webhook endpoint (`/api/webhook`)
- [x] OpenAI integration via Emergent integrations library
- [x] Conversation history stored in MongoDB
- [x] Context-aware responses (maintains recent conversation history)
- [x] Bot statistics API (`/api/bot/stats`)
- [x] Message history API (`/api/bot/messages`)
- [x] LLM health check API (`/api/bot/test`)
- [x] Webhook info/set APIs
- [x] React dashboard with real-time stats
- [x] Recent conversations display
- [x] Telegram link button

## MEXC Integration (Feb 2026)
- [x] Live MEXC crypto data via ccxt library
- [x] Real-time BTC/USDT, ETH/USDT, SOL/USDT prices
- [x] `/api/mexc/live` endpoint for market data
- [x] `/price` command for quick market snapshot
- [x] MEXC data injected into every Aeon response
- [x] Dashboard shows live prices with trend indicators
- [x] MEXC Live badge in status bar

## Aeon Quartet Upgrade (Feb 2026)
- [x] Full orderbook analysis (bid/ask depth, imbalance %)
- [x] Dual mode detection (Trading vs Alchemy keywords)
- [x] 30 alchemical interview questions bank
- [x] Scheduled rituals (6AM crypto, 8:45AM stocks CST)
- [x] Background ritual runner with asyncio
- [x] Obsidian vault integration (webhook ready)
- [x] New commands: /probe, /ritual
- [x] Conversation context tracking (trading/alchemy/ritual)
- [x] Frontend filter tabs by conversation type
- [x] Orderbook imbalance visualization bars

## Technical Architecture
- **Backend**: FastAPI + MongoDB + Emergent integrations
- **Frontend**: React + TailwindCSS + shadcn/ui
- **LLM**: OpenAI gpt-4o-mini via Emergent Universal Key
- **Bot**: Telegram Bot API with webhook mode

## Credentials Used
- Telegram Bot Token: `8586106246:AAHZTWfSHMuLwyGxeOn9DelRaesZF2Joans`
- Bot URL: https://t.me/ObsidianCabalbot
- Webhook URL: https://aeon-chatbot.preview.emergentagent.com/api/webhook

## Prioritized Backlog
### P0 (Completed)
- Core bot functionality
- Dashboard monitoring

### P1 (Next Phase)
- Enhanced conversation memory (cross-session persistence)
- Rate limiting per user
- Admin commands (/stats, /users)
- Message search functionality

### P2 (Future)
- User analytics charts
- Export conversation history
- Multiple personality modes
- Crypto price integration

## Next Tasks
1. Add persistent conversation memory across sessions
2. Implement admin commands for bot management
3. Add rate limiting to prevent abuse
4. Create user engagement analytics
