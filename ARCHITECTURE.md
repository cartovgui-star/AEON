# AEON Architecture

High-level view of the system. This document describes what each part does and why it exists — implementation details, parameters, and strategy code live in the private repository.

## Design principles

1. **No single point of action.** No engine, strategy, or model can move capital on its own. Every path to execution passes through independent gates.
2. **Paper first, always.** Everything is validated against live market data in a sandbox before it earns the right to be considered for real deployment.
3. **The system grades itself.** Every published setup, bias call, and research conclusion is scored against what actually happened. Hit rates are tracked by setup type and instrument, in the open.
4. **Understanding over prediction.** The primary output is explanation, not signals. If the system can't say *why* in plain language, the finding isn't ready.

## Subsystems

### 1. core — API server and application state
The FastAPI application: request routing, shared application state (database handles, configuration), startup/shutdown lifecycle, and background task loops. Everything else plugs into this layer. The API surface is large — several hundred routes covering market data, research, trading, alerts, and system administration.

### 2. engines — autonomous trading engines
A fleet of independent engines, each with its own market logic, scanning cadence, and lifecycle. Examples of engine archetypes: momentum scalpers, institutional-style SMC (smart money concepts) scanners, VWAP-based intraday systems, regime detectors, neural-network inference engines, and volume-profile analyzers. Engines run on their own schedules, emit signals into a shared bus, and are individually governable — any engine can be paused, throttled, or retired without touching the others.

### 3. strategies — strategy primitives and backtesting
The building blocks strategies are made from: composable primitives (momentum, mean-reversion, breakout, volatility filters, and others) that combine into full strategy specifications. Includes a backtesting harness that speaks the same statistical language as the live lab, so a backtest result and a live result are directly comparable. Ensemble voting combines multiple strategy outputs into a single desk view.

### 4. intel — market intelligence
The sensory layer. Ingests and normalizes:
- **Order-book data** — Level 2 snapshots across major venues on a fixed cadence, unified into a single snapshot log.
- **Derivatives** — funding rates, open interest, and positioning proxies across venues.
- **News and macro** — structured event feeds, economic calendar awareness.
- **On-chain** — network-level signals for supported assets.
- **Conversation** — social and community signal, weighted skeptically.

All intel is timestamped, sourced, and stored — nothing is consumed ephemerally. See [DATA_PIPELINE.md](docs/DATA_PIPELINE.md).

### 5. research — the research desk and lab
Where hypotheses become findings. The research pipeline moves ideas through stages — intake, testing, live observation, promotion — with explicit criteria at each gate. A lab researcher runs continuous experiments; a champion-selection process identifies which findings deserve attention; a single deploy bar decides what is allowed near capital. Research threads keep the full context of every investigation, so conclusions are auditable months later.

### 6. risk — governance and execution gates
The immune system. Engine governance tracks every autonomous component's behavior and can restrict it. A gate ledger records every autonomous decision with its reasoning. Portfolio heat monitoring watches aggregate exposure. An independent evaluation gate stands between "the system wants to trade" and "the system may trade" — and the two are never the same component. See [RISK_FRAMEWORK.md](docs/RISK_FRAMEWORK.md).

### 7. alerts — notification routing
Turns system events into human-readable messages across Telegram and Discord: bias flips, level breaks, engine status changes, research milestones. Alert throttling prevents notification spam — the same event doesn't page twice.

### 8. trading — paper trading and journals
Manual paper-trading accounts (client-side simulated, with a TradingView-style chart interface), autonomous engine accounts (view-only), trade journals, outcome tracking, and signal scorecards that grade signal quality over time.

### 9. ai — the understanding layer
LLM-driven analysis, continuous learning from outcomes, a self-healing loop for operational issues, and the system's voice. This is where numbers become words: market briefs, research summaries, and explanations are generated here from the structured output of every other subsystem. See [UNDERSTANDING_LAYER.md](docs/UNDERSTANDING_LAYER.md).

### 10. reports — briefings and desk actions
Scheduled and on-demand reporting: the daily thesis-led market brief, weekly performance scorecards, chart monitoring, and the desk-action log — a record of every significant thing the system did or decided, in plain language.

## Data flow

```
venues ──→ L2 pipeline ──→ snapshot log ──→ market-structure engine ──→ briefs / alerts
         │                                              │
         ├─→ derivatives intel ──┐                       │
         ├─→ news / macro ───────┤                       │
         └─→ on-chain ───────────┴─→ research desk ──→ strategy lab ──→ paper sandbox ──→ execution gate
                                                                                              │
                                                                     risk governance ──────────┘
```

## Why this shape

The architecture mirrors how a professional trading desk is organized: data people, researchers, risk managers, and portfolio managers — except here each role is a subsystem, and the handoffs between them are explicit, logged, and gated. No role can do another role's job. The researcher can't execute. The engine can't override risk. The briefing layer can't invent data.

That separation is the point. It's what makes the system auditable, what makes the scorecards honest, and what keeps a bad day from becoming a catastrophic one.
