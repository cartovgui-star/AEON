# The Data Pipeline

Everything AEON knows starts here: live market data, ingested continuously, normalized, stored, and scored.

## What gets ingested

### Level 2 order books
The backbone. Live order-book snapshots stream from multiple major venues on a fixed cadence (every ~10 seconds) and are normalized into a unified snapshot log. Each snapshot captures the shape of the book — where the bids stack, where the offers sit, how deep the liquidity runs.

From the raw book, the pipeline derives:
- **Order-book imbalance** — the relative weight of bids vs. asks near the touch. Persistent imbalance is pressure; it doesn't guarantee direction, but it tells you where the urgency is.
- **Liquidity walls** — large resting orders that act as magnets or barriers. Walls appear, get eaten, get pulled — each behavior means something different.
- **Support and resistance** — levels derived from where the book has historically clustered, where breaks have happened, and where price has reacted. These are computed, not drawn.

### Derivatives
Funding rates, open interest, and positioning proxies. The derivatives market often moves first — liquidations cascade, funding extremes mark crowded trades, and open interest divergences warn when spot and leverage disagree.

### News, macro, and on-chain
Structured event feeds, economic calendar awareness, and network-level signals. These don't generate signals on their own; they provide the *context* in which the order-book data is interpreted. A wall breaking into a news vacuum means something different from a wall breaking into a headline.

## Market-structure scoring

On a fixed cadence, the scoring engine turns the snapshot log into a readable market state per instrument:

- **Bias label** — bullish, bearish, or neutral, derived from a ruleset over imbalance, level position, and momentum. Labels flip when the evidence flips, and every flip is logged with its reasons.
- **Nearest levels** — the closest support below and resistance above, with distances.
- **Notable events** — level breaks, bias flips, new walls, imbalance swings. These are the pipeline's way of tapping you on the shoulder.

The bias labels are descriptive, not prescriptive. They say "this is what the book looks like right now," not "you should buy." The distinction matters — the pipeline's job is to see clearly, not to have opinions.

## Why multiple venues

No single exchange is the market. Liquidity fragments across venues, walls appear on one and not another, and venue-specific behavior (a large seller on one book, spoofing patterns, fee-driven flow) only becomes visible in comparison. The pipeline normalizes across venues so the scoring engine sees the whole picture, not one slice of it.

## Storage and history

Nothing is consumed ephemerally. Every snapshot, every score, every bias flip is stored with a timestamp. That history is what makes the weekly scorecards possible — and what lets the research lab train on reality instead of memory.

## What isn't shared

Venue credentials, exact ingestion cadence tuning, the scoring ruleset weights, and the raw historical data are private. What's public is the design: multi-venue L2 ingestion, normalized snapshot log, rules-based structure scoring, event-driven alerts, and full historical retention.
