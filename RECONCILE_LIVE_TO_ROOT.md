# Reconcile Live `/var/www` Back Into Source `/root`

This checklist exists because the live tree and source tree have diverged.

- Source tree: `/root/aeon-finale-formv1.2.3.6`
- Live tree: `/var/www/aeon-finale-formv1.2.3.6.5`

Do not run a first full deploy until the high-priority live-only code below is reviewed.

## What A First Full Sync Would Do

- It would overwrite shared files in `/var/www` with the `/root` versions.
- It would not physically delete live-only files, because current sync does not use `--delete`.
- It could still break live behavior if overwritten entrypoints stop importing or rendering those live-only files.

## Highest Risk

The highest-risk area is the live frontend shell.

Live `frontend/src/App.js` is substantially different from root and appears to drive a newer operator/cockpit layout. If root is deployed as-is, many live-only UI modules will remain on disk but likely become unreachable.

There is also an important backend contract risk in `backend/routes/dashboard.py`, where live and root differ materially.

## Reconcile Order

1. Frontend shell and routing
2. Backend dashboard contract
3. Live-only backend modules and routes
4. Telegram command modules
5. Small config and naming diffs
6. Only then run `/root/aeon-sync.sh --full`

## Must Review Before Deploy

### Frontend shell

These files are the clearest sign that live `/var/www` is running a different frontend experience and should be reviewed first:

- `frontend/src/App.js`
- `frontend/src/components/Trading.jsx`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/EnginesDashboard.jsx`
- `frontend/src/components/PaperTrading.jsx`
- `frontend/src/components/PerformanceAnalytics.jsx`
- `frontend/src/components/QuantAnalyzer.jsx`
- `frontend/src/components/TradeHistory.jsx`
- `frontend/src/components/BacktestV21.jsx`
- `frontend/src/components/SystemHealth.jsx`
- `frontend/src/components/VoiceConversation.jsx`

### Live-only frontend modules

These exist in live `/var/www` but not in source `/root`. If the operator shell is intended to stay, these likely need to be copied or reimplemented in `/root` before deploy:

- `frontend/src/components/AeonLoader.jsx`
- `frontend/src/components/AnalyticsPage.jsx`
- `frontend/src/components/CommandCenter.jsx`
- `frontend/src/components/CrisisModeOverlay.jsx`
- `frontend/src/components/EngineConfigModal.jsx`
- `frontend/src/components/EnginesPage.jsx`
- `frontend/src/components/FundingRatePanel.jsx`
- `frontend/src/components/HourlyHeatmap.jsx`
- `frontend/src/components/MarketRegime.jsx`
- `frontend/src/components/NexusAwarenessFeed.jsx`
- `frontend/src/components/NexusPanel.jsx`
- `frontend/src/components/OperatorHome.jsx`
- `frontend/src/components/PnLHeatmap.jsx`
- `frontend/src/components/PostMortemPanel.jsx`
- `frontend/src/components/QuantumStatePanel.jsx`
- `frontend/src/components/RegimePerformancePanel.jsx`
- `frontend/src/components/SettingsPage.jsx`
- `frontend/src/components/SlimHeader.jsx`
- `frontend/src/components/SoundAlertSystem.jsx`
- `frontend/src/components/TradesPage.jsx`
- `frontend/src/components/TradingHub.jsx`
- `frontend/src/components/WaveFunctionVisualizer.jsx`
- `frontend/src/services/api.js`

### Source-only frontend modules

These exist in `/root` but not in live `/var/www`. Decide whether they are newer replacements or older branches before merging anything:

- `frontend/src/components/CommandPalette.jsx`
- `frontend/src/components/LearningEngine.jsx`
- `frontend/src/components/MorningBriefing.jsx`
- `frontend/src/components/NewsFeed.jsx`
- `frontend/src/components/OracleDashboard.jsx`
- `frontend/src/components/PositionsCallingCard.jsx`
- `frontend/src/components/QuantumDashboard.jsx`
- `frontend/src/components/VolumeProfile.jsx`
- `frontend/src/components/WeeklyReport.jsx`
- `frontend/src/hooks/useAutoRefresh.js`

## Backend Files To Review Before Deploy

### Material backend drift

These should be manually compared before deploy because they affect live app behavior directly:

- `backend/routes/dashboard.py`
- `backend/telegram/commands/engine_commands.py`
- `backend/institutional_scalper.py`
- `backend/elite_strategy_v3.py`
- `backend/paper_trading.py`
- `backend/autonomous_trader_v2.py`
- `backend/aeon_personality.py`
- `backend/vwap_scalper.py`
- `backend/oria_layer.py`
- `backend/portfolio_heat.py`
- `backend/self_healer.py`
- `backend/aeon_quantum_state.py`
- `backend/tests/test_backtest_v21_quick.py`

### Live-only backend modules

These exist in live `/var/www` but not in source `/root`. Review whether they are active production features or abandoned branches:

- `backend/coinbase_feed.py`
- `backend/coinbase_trader.py`
- `backend/engine_paper_tracker.py`
- `backend/market_data_fetcher.py`
- `backend/oracle_entropy_gate.py`
- `backend/quantum_identity.py`
- `backend/routes/engine_analytics.py`
- `backend/routes/oracle_entropy.py`
- `backend/routes/quant_engine.py`
- `backend/routes/sim.py`
- `backend/telegram/commands/dual_commands.py`
- `backend/telegram/commands/freewill_commands.py`
- `backend/telegram/commands/scalper_commands.py`
- `backend/utils/adx_filter.py`
- `backend/utils/margin_guard.py`

### Live-only backend package tree

This package is present in live `/var/www` and absent in source `/root`:

- `backend/nexus/`
  - `__init__.py`
  - `healer.py`
  - `morpheus.py`
  - `nexus_core.py`
  - `nexus_models.py`
  - `oracle_sense.py`
  - `telegram_commander.py`
  - `warden.py`

If NEXUS is live functionality, this must be reconciled into `/root` before a deploy from source.

## Small But Real Drift

These are small diffs, but they still matter because they change live symbol support:

- `backend/paper_trading.py`
  - live uses `POL/USDT`
  - root still uses `MATIC/USDT`
- `backend/autonomous_trader_v2.py`
  - live uses `POL/USDT`
  - root still uses `MATIC/USDT`
- `frontend/package.json`
  - live build script adds `NODE_OPTIONS=--max_old_space_size=512`

## Recommended Manual Merge Pass

### Pass 1: preserve live frontend shell

Review and merge these from `/var/www` into `/root` first:

- `frontend/src/App.js`
- `frontend/src/components/Trading.jsx`
- `frontend/src/components/Dashboard.jsx`
- `frontend/src/components/EnginesDashboard.jsx`
- `frontend/src/components/PaperTrading.jsx`
- `frontend/src/components/PerformanceAnalytics.jsx`
- `frontend/src/components/QuantAnalyzer.jsx`
- `frontend/src/components/TradeHistory.jsx`
- `frontend/src/components/SystemHealth.jsx`

Then decide whether the live-only operator pages become the canonical UI in `/root`.

### Pass 2: preserve dashboard/backend contract

Review and merge these next:

- `backend/routes/dashboard.py`
- `backend/telegram/commands/engine_commands.py`

This is the contract most likely to break the live operator frontend if overwritten blindly.

### Pass 3: preserve live-only features

Review whether these live-only modules are real production features:

- `backend/nexus/`
- `backend/routes/engine_analytics.py`
- `backend/routes/oracle_entropy.py`
- `backend/routes/quant_engine.py`
- `backend/routes/sim.py`
- `frontend/src/components/NexusPanel.jsx`
- `frontend/src/components/OperatorHome.jsx`
- `frontend/src/components/TradingHub.jsx`
- `frontend/src/components/QuantumStatePanel.jsx`

### Pass 4: clean small diffs

Bring over:

- `POL/USDT` replacements in backend trading files
- frontend build memory option if still needed
- any remaining command or config deltas

## Deploy Gate

Do not run `/root/aeon-sync.sh --full` until:

- the live frontend shell decision is made
- `backend/routes/dashboard.py` is reconciled
- any required live-only modules are either copied into `/root` or intentionally abandoned

## Practical Rule

If a file is only in `/var/www` and still matters to the live UI or API, then `/root` is not yet a valid deploy source.
