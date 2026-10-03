# AEON

**Market understanding infrastructure** — a personal research lab for turning raw market data into plain-language explanations of what's happening, why, and what to watch next.

Most trading tools answer *"what should I buy?"* AEON answers a harder question: *"what is actually going on?"* It ingests live order-book data across major crypto venues, scores market structure in real time, evolves trading strategies through an evolutionary research engine, and translates all of it into human-readable briefs — thesis-led, graded against reality every week.

## What it does

- **Live market-structure scoring** — streams Level 2 order-book data on a fixed cadence, scoring instruments on support/resistance, liquidity walls, and order-book imbalance. Emits bias labels and notable events (level breaks, bias flips, wall shifts) as they happen.
- **Evolutionary strategy lab** — strategies are encoded as composable specifications and evolved through mutation and crossover. Winners graduate to a paper sandbox against live market data. Nothing touches capital without surviving validation and an independent execution gate.
- **Multi-source intelligence** — order flow, news, macro, derivatives (funding, open interest), and on-chain signals fused into a single research surface.
- **Paper trading station** — a TradingView-style manual paper-trading interface: chart with plotted positions, live ticker watchlist, floating order ticket, account dock.
- **Understanding layer** — an AI-driven briefing system that turns pipeline output into thesis-led daily market notes, bias-change alerts, and weekly performance scorecards that grade every published setup against actual price action.
- **Risk governance** — engine-level governance, a gate ledger for every autonomous decision, portfolio heat monitoring, and kill switches. The system is designed so that no single component can act alone.

## How it's organized

Ten subsystems, each with a single responsibility:

| Subsystem | Role |
|---|---|
| `core` | API server, application state, request routing |
| `engines` | Autonomous trading engines (each with its own logic and lifecycle) |
| `strategies` | Strategy primitives, backtesting, ensemble voting |
| `intel` | Market data ingestion, news, macro, derivatives, on-chain |
| `research` | Research desk, lab pipeline, champion selection |
| `risk` | Governance, execution gates, portfolio heat |
| `alerts` | Telegram and Discord notification routing |
| `trading` | Paper trading, journals, signal scorecards |
| `ai` | LLM layer, continuous learning, system personality |
| `reports` | Briefings, desk actions, performance reports |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full breakdown, and `docs/` for deep dives into the strategy lab, data pipeline, risk framework, and understanding layer.

## Philosophy

Data is noise until it becomes words. The end goal isn't a black box that trades — it's a system that *understands*: why a level broke, what the order book is saying, which narratives have teeth and which don't, and the discipline to say "no edge here" when there's no edge.

Every published setup is graded the following week against actual price action. The system keeps score on itself.

## Tech stack

Python (FastAPI, asyncio), React, WebSockets, REST APIs, MongoDB, multi-exchange market-data feeds.

## Status

Active research project, in continuous development. This repository is a public overview of the project's shape and thinking — the working implementation, strategy code, parameters, and infrastructure details live in a private repository.

## Disclaimer

Research and educational purposes only. Nothing here is financial advice, and nothing here is a recommendation to trade.
