# AEON Architecture

High-level view of the system. Implementation details live in the private repository.

## Components

### 1. Data pipeline
Ingests live Level 2 order-book snapshots from multiple venues on a fixed cadence and normalizes them into a unified snapshot log that downstream analysis consumes.

### 2. Market-structure engine
Scores instruments on support/resistance levels, liquidity walls, and order-book imbalance. Emits bias labels and notable events (level breaks, bias flips, wall changes) on a fixed cadence.

### 3. Strategy lab (evolutionary engine)
Strategies are encoded as specifications: component primitives (momentum, mean-reversion, breakout, and others), each with parameters and a weight, plus global combine rules. The engine evolves a population through structural, per-component, and global mutation, plus crossover between elite parents. Winners graduate to a paper sandbox against live market data.

### 4. Execution gate
A separate evaluation gate decides whether the desk may auto-execute. No strategy touches capital without passing sandbox validation and the gate.

### 5. Paper trading station
Manual paper-trading UI: chart with plotted positions, live ticker watchlist, order ticket, account dock. Client-side simulated accounts; engine accounts are view-only.

### 6. Briefing layer
Turns pipeline output into human-readable market notes: daily thesis-led briefs, bias-change alerts, and weekly performance scorecards grading published setups against actual price action.

## Data flow

```
venues → L2 pipeline → snapshot log → market-structure engine → briefs / alerts
                                                    ↘ strategy lab → paper sandbox → execution gate
```
