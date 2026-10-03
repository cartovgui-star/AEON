# AEON

AEON is a market research and trading infrastructure project — a personal lab for understanding markets through data: live order-book pipelines, systematic strategy research, and paper-trading validation.

## What it does

- **Market data pipeline** — streams live Level 2 order-book data across major crypto venues, powering real-time market-structure analysis (order-book imbalance, liquidity walls, support/resistance).
- **Strategy research lab** — an evolutionary engine that encodes trading strategies as composable specifications, mutates and crosses over elite candidates, and validates winners in a paper sandbox against live market data before they can touch capital.
- **Paper trading station** — a TradingView-style manual paper-trading interface with live watchlists and position tracking.
- **Automated market briefs** — thesis-led daily market notes generated from the data pipeline: bias changes, notable events, and weekly performance scorecards.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the high-level system design.

## Tech stack

Python, React, WebSockets, REST APIs.

## Status

Active research project. This repository is a public overview — the full implementation lives in a private repository.

## Disclaimer

Research and educational purposes only. Nothing here is financial advice.
