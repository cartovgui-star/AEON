# AEON API Surface

Generated from the current backend router set in `backend/server.py` and `backend/routes/*.py`.

## Notes

- Most modular routers are mounted under `/api` in `backend/server.py`.
- Some routers already include `/api/...` in their route paths and are mounted without an extra prefix.
- The backend enforces `X-API-Key` on `/api/*` unless the path is explicitly exempt.

## Core Access

- `GET /ws`
- `GET /api/system/health`
- `GET /api/system/ws/stats`
- `GET /api/system/pairs`
- `GET /api/system/news`
- `POST /api/system/kill-switch`

## Bot And Messaging

- `GET /api/bot/stats`
- `GET /api/bot/messages`
- `GET /api/bot/test`
- `POST /api/voice/respond`
- `POST /api/voice/transcribe`
- `GET /api/voice/info`

## Trading And Paper

- `POST /api/trading/toggle`
- `GET /api/trading/summary`
- `GET /api/trading/opportunities`
- `GET /api/trading/strategy`
- `GET /api/trading/analyze/{symbol}`
- `GET /api/trading/v2/stats`
- `GET /api/trading/v2/open`
- `GET /api/trading/v2/closed`
- `GET /api/trading/v2/live-positions`
- `GET /api/trading/v2/pnl-history`
- `POST /api/trading/v2/confidence`
- `POST /api/trading/v2/close/{symbol}`
- `GET /api/paper/accounts`
- `GET /api/paper/positions`
- `GET /api/paper/performance`
- `GET /api/paper/equity-curves`
- `GET /api/paper/weekly-summary`
- `POST /api/paper/close/{account_id}/{symbol}`
- `POST /api/paper/reset/{account_id}`
- `GET /api/positions`
- `POST /api/positions/close`
- `GET /api/trades/open`
- `GET /api/trades/open/{engine_name}`
- `GET /api/trades/closed`

## Engines

- `GET /api/engines/status`
- `GET /api/engines/status/{engine_name}`
- `GET /api/engines/stats/global`
- `GET /api/engines/stats/{engine_name}`
- `POST /api/engines/signal`
- `POST /api/engines/close-trade`
- `GET /api/engines/compare`
- `GET /api/engines/snapshots`
- `GET /api/engines/confirmations`
- `GET /api/engines/outcomes`
- `GET /api/engine/health`
- `GET /api/engine/health/{engine_name}`
- `GET /api/engine/governance`
- `POST /api/engine/governance/refresh`
- `GET /api/engine/governance/log`
- `GET /api/engine/overlap`
- `GET /api/portfolio/summary`
- `GET /api/portfolio/regime-fit`
- `GET /api/portfolio/account-fit`
- `GET /api/engine/fw_v2/report`

## Strategy Engines

- `GET /api/freewill/stats`
- `GET /api/freewill/scan/{symbol}`
- `POST /api/freewill/toggle`
- `POST /api/freewill/confidence`
- `POST /api/freewill/feedback`
- `GET /api/dual/stats`
- `POST /api/dual/toggle`
- `POST /api/dual/day-trader/toggle`
- `POST /api/dual/long-term/toggle`
- `POST /api/dual/day-trader/confidence`
- `POST /api/dual/long-term/confidence`
- `GET /api/elite/status`
- `GET /api/elite/scan`
- `GET /api/elite/analyze/{symbol}`
- `POST /api/elite/toggle`
- `POST /api/elite/settings`
- `POST /api/elite/relaxed`
- `GET /api/scalper/status`
- `GET /api/scalper/scan`
- `GET /api/scalper/scan/all`
- `GET /api/scalper/opportunities`
- `GET /api/scalper/signals/{symbol}`
- `GET /api/scalper/backtest/{symbol}`
- `GET /api/scalper/backtest/all/{timeframe}`
- `GET /api/scalper/settings`
- `POST /api/scalper/settings`
- `POST /api/scalper/toggle`
- `GET /api/scalper/learning/status`
- `POST /api/scalper/learning/optimize`
- `GET /api/scalper/learning/performance`
- `POST /api/scalper/learning/toggle`
- `GET /api/scalper/v2/status`
- `GET /api/scalper/v2/queued`
- `POST /api/scalper/v2/toggle`
- `GET /api/scalper/mtf/confluence/{symbol}`
- `GET /api/scalper/mtf/scan`
- `GET /api/scalper/mtf/report`
- `GET /api/scalper/mtf/best`
- `GET /api/vwap-scalper/stats`
- `GET /api/vwap-scalper/scan`
- `GET /api/vwap-scalper/analyze/{symbol}`
- `GET /api/institutional-scalper/stats`

## Market Data And Intelligence

- `GET /api/market/scan/{symbol}`
- `GET /api/market/ta/{symbol}`
- `GET /api/market/funding/{symbol}`
- `GET /api/market/positions/{symbol}`
- `GET /api/mexc/live`
- `GET /api/mexc/ohlcv/{symbol}`
- `GET /api/news/latest`
- `GET /api/news/sentiment`
- `GET /api/intel/top100`
- `GET /api/intel/fear-greed`
- `GET /api/intel/global`
- `GET /api/intel/trending`
- `GET /api/sentiment/composite`
- `GET /api/sentiment/news`
- `GET /api/sentiment/fear-greed`
- `GET /api/sentiment/history`
- `GET /api/derivatives/funding/{symbol}`
- `GET /api/derivatives/oi/{symbol}`
- `GET /api/derivatives/ls/{symbol}`
- `GET /api/derivatives/full/{symbol}`
- `GET /api/coinglass/funding/{symbol}`
- `GET /api/coinglass/oi/{symbol}`
- `GET /api/coinglass/ls/{symbol}`
- `GET /api/coinglass/liquidations/{symbol}`
- `GET /api/coinglass/full/{symbol}`
- `GET /api/data/social/{symbol}`
- `GET /api/data/btc/onchain`
- `GET /api/data/btc/fees`
- `GET /api/data/eth/gas`
- `GET /api/data/defi/tvl`
- `GET /api/data/all/{symbol}`

## Analysis

- `GET /api/smc/analysis/{symbol}`
- `GET /api/smc/structure/{symbol}`
- `GET /api/smc/orderblocks/{symbol}`
- `GET /api/smc/fvg/{symbol}`
- `GET /api/smc/liquidity/{symbol}`
- `GET /api/smc/zones/{symbol}`
- `GET /api/confluence/{symbol}`
- `GET /api/mtf/{symbol}`
- `GET /api/mtf/align/{symbol}`
- `GET /api/orderflow/cvd/{symbol}`
- `GET /api/orderflow/divergence/{symbol}`
- `GET /api/orderflow/absorption/{symbol}`
- `GET /api/orderflow/full/{symbol}`
- `GET /api/advanced/divergence/{symbol}`
- `GET /api/advanced/structure/{symbol}`
- `GET /api/advanced/vwap/{symbol}`
- `GET /api/advanced/full/{symbol}`
- `GET /api/options/maxpain/{currency}`
- `GET /api/options/pcr/{currency}`
- `GET /api/options/oi/{currency}`
- `GET /api/options/full/{currency}`
- `GET /api/vp/profile/{symbol}`
- `GET /api/vp/liquidations/{symbol}`
- `GET /api/vp/orderbook/{symbol}`
- `GET /api/vp/full/{symbol}`
- `GET /api/vp/scan`
- `GET /api/vp/stats`
- `GET /api/quant/status`
- `GET /api/quant/scan`
- `GET /api/quant/analyze`
- `GET /api/quant/analyze/{symbol}`
- `GET /api/quant/debug/{symbol}`

## Backtesting And Calculators

- `GET /api/calc/pnl`
- `GET /api/calc/position`
- `GET /api/calc/scenarios`
- `GET /api/backtest/rsi/{symbol}`
- `GET /api/backtest/bb/{symbol}`
- `GET /api/backtest/ema/{symbol}`
- `GET /api/backtest/compare/{symbol}`
- `POST /api/backtest/v21/run`
- `GET /api/backtest/v21/status`
- `GET /api/backtest/v21/result`
- `GET /api/backtest/v21/quick/{symbol}`
- `GET /api/backtest/v21/settings`
- `GET /api/backtest/v21/compare`
- `POST /api/backtest/v21/multi-confidence`
- `POST /api/backtest/v21/multi-timeframe`
- `POST /api/backtest/v21/comprehensive`
- `GET /api/backtest/v21/confidence-range`
- `GET /api/backtest/v21/timeframe-comparison`

## Alerts, Reporting, And Learning

- `GET /api/alerts/stats`
- `GET /api/alerts/dashboard`
- `POST /api/alerts/mark-read/{dashboard_id}`
- `POST /api/alerts/clear`
- `POST /api/alerts/add`
- `DELETE /api/alerts/{alert_id}`
- `GET /api/alerts/custom`
- `POST /api/alerts/threshold`
- `GET /api/briefing/status`
- `POST /api/briefing/test`
- `GET /api/briefing/preview`
- `POST /api/briefing/toggle`
- `GET /api/briefing/movers`
- `GET /api/briefing/structure`
- `GET /api/briefing/setups`
- `GET /api/report/status`
- `POST /api/report/test`
- `GET /api/report/preview`
- `POST /api/report/toggle`
- `GET /api/report/strategy-stats`
- `GET /api/report/coin-performance`
- `GET /api/learning/status`
- `GET /api/learning/recommendations`
- `GET /api/learning/insights`
- `GET /api/learning/patterns`
- `GET /api/learning/coins`
- `GET /api/learning/sessions`
- `POST /api/learning/force-cycle`
- `GET /api/learning/summary/preview`
- `POST /api/learning/summary/send`

## Memory, User, And Accuracy

- `GET /api/memory/stats`
- `GET /api/memory/journal/stats`
- `GET /api/memory/journal/trades`
- `POST /api/memory/journal/log`
- `GET /api/memory/journal/patterns`
- `GET /api/memory/insights`
- `POST /api/memory/insights/generate`
- `GET /api/memory/context/{chat_id}`
- `POST /api/memory/preference`
- `GET /api/memory/preference/{chat_id}/{key}`
- `GET /api/memory/conversation/{chat_id}`
- `GET /api/user/profile`
- `GET /api/user/profile/{chat_id}`
- `POST /api/user/profile/{chat_id}/fact`
- `GET /api/accuracy`
- `GET /api/accuracy/pending`
- `GET /api/accuracy/leaderboard`
- `GET /api/accuracy/dashboard`
- `POST /api/accuracy/record`
- `GET /api/signals/recent`
- `GET /api/signals/accuracy`
- `GET /api/signals/performance`
- `GET /api/signals/stats`
- `POST /api/signals/record`
- `POST /api/signals/outcome`

## Oracle, Quantum, And Nexus

- `GET /api/oracle/status`
- `GET /api/oracle/bias/{symbol}`
- `GET /api/oracle/report`
- `GET /api/oracle/top`
- `GET /api/oracle/opportunities`
- `GET /api/oracle/scan/full`
- `GET /api/oracle/scan/status`
- `GET /api/oracle/scan/results`
- `GET /api/quantum/state`
- `GET /api/quantum/identity`
- `GET /api/quantum/identity/gate`
- `GET /api/quantum/history`
- `GET /api/quantum/memory/summary`
- `GET /api/quantum/memory/retrieve`
- `GET /api/quantum/memory/count`
- `GET /api/quantum/omega/history`
- `GET /api/quantum/omega/status`
- `GET /api/quantum/web/lphi`
- `GET /api/quantum/web/sentiment`
- `GET /api/quantum/web/status`
- `GET /api/nexus/awareness`
- `GET /api/nexus/config`
- `GET /api/nexus/heals`
- `GET /api/nexus/adaptations`
- `GET /api/nexus/alerts`
- `GET /api/nexus/heartbeat`
- `GET /api/nexus/suspended-engines`
- `GET /api/nexus/awareness-feed`

## Additional Direct `/api` Groups

- `GET /api/analytics/report`
- `GET /api/analytics/equity-curve`
- `GET /api/analytics/win-rates`
- `GET /api/analytics/top-performers`
- `GET /api/analytics/drawdown`
- `GET /api/analytics/recent`
- `GET /api/analytics/performance`
- `GET /api/analytics/hourly-heatmap`
- `GET /api/regime`
- `GET /api/regime/stats`
- `GET /api/regime/global`
- `GET /api/regime/macro`
- `GET /api/regime/{symbol}`
- `GET /api/risk/summary`
- `GET /api/risk/candidates`
