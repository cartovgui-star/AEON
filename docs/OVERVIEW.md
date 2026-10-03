# Research Overview

## Philosophy

Data is noise until it becomes words. AEON's end goal is market understanding — translating numbers into plain, understandable explanations of why things are happening.

Most market tools optimize for the trade: entry, exit, size. AEON optimizes for the explanation: *why did that level break? What is the order book actually saying? Which narrative has evidence behind it and which is just loud?* A system that can explain itself honestly — including "there's no edge here right now" — is worth more than a system that always has an opinion.

## What gets researched

- **Market microstructure** — how order books behave: where liquidity sits, how it shifts between venues, what imbalance tells you about near-term pressure, and how walls form and dissolve around key levels.
- **Systematic strategy design** — building strategies from composable primitives and letting evolution, not intuition, decide which combinations survive. See [STRATEGY_LAB.md](STRATEGY_LAB.md).
- **Multi-source fusion** — no single data source tells the truth. Order flow, derivatives positioning, news, macro, and on-chain each see part of the picture; the research question is how they combine — and when they disagree, which one to trust.
- **Validation rigor** — paper sandbox first, always. A strategy earns the right to be considered for capital only after surviving live-data validation, an independent execution gate, and ongoing re-validation. Past performance is a hypothesis, not a credential.

## How findings are treated

Every research conclusion carries its evidence with it: what data it was based on, what would prove it wrong, and how it performed after publication. The weekly scorecard grades every published setup against actual price action — by setup type, by instrument, over time. Findings that stop working are retired, not rationalized.

## What this repo is

A public window into the project's shape: what it does, how it's organized, how it thinks, and what it's for. The working implementation, strategy code, parameters, thresholds, and infrastructure details are private — not because secrecy is the goal, but because the value is in the years of iteration, not in any single file.
