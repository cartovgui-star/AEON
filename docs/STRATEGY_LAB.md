# The Strategy Lab

How AEON researches trading strategies: not by hand-designing systems and hoping, but by encoding the *space* of possible strategies and letting evolution search it.

## The core idea

A trading strategy is a specification, not a script. Each strategy is described as:

- **Component primitives** — the building blocks: momentum, mean-reversion, breakout, volatility filters, and others. Each primitive has parameters and a weight.
- **Combine rules** — how the primitives' outputs merge into a single decision: voting, weighted consensus, veto logic.
- **Global genes** — portfolio-level settings like aggressiveness and confirmation thresholds.

This encoding turns "design a strategy" into "search a space" — and search is something you can automate, measure, and improve.

## How evolution works

The lab maintains a population of strategy specifications and improves it through:

1. **Structural mutation** — adding or removing primitives, changing the architecture of the strategy itself.
2. **Per-component mutation** — tuning the parameters and weights of individual primitives.
3. **Global mutation** — adjusting the combine rules and portfolio-level genes.
4. **Crossover** — breeding elite parent strategies, mixing their components the way genetics mixes traits.

Selection is driven by performance against live market data — not backtests alone. The fitness function rewards what actually matters: risk-adjusted edge, consistency across regimes, and behavior that survives contact with real market friction.

## The gauntlet

Evolving a good backtest is easy. The lab is designed around the fact that backtests lie:

1. **Evolution** — candidates compete on historical and live-forward data.
2. **Paper sandbox** — winners are deployed against *live* market data in a simulated environment. They experience real spreads, real latency, real regime shifts. Most candidates die here, and that's the point.
3. **Champion selection** — survivors are compared not just on returns but on *behavior*: does the strategy do what its specification claims? Is its edge explainable or a statistical accident?
4. **The deploy bar** — a single, explicit standard decides what is allowed near capital. It covers sample size, per-instrument breadth, forward-test performance, and whether the live edge holds up as a fraction of the backtested edge. Anything below the bar stays in the lab.
5. **Continuous re-validation** — deployment isn't a finish line. Strategies are re-scored as new data arrives, and the bar doesn't move down for anyone.

## Why this instead of hand-designed strategies

Hand-designed strategies carry the designer's biases: the regimes they've seen, the patterns they believe in, the parameters that "feel right." Evolution has no feelings. It finds combinations a human wouldn't try — and, just as importantly, it kills beloved ideas quickly when the data says no.

The lab keeps full lineage: every strategy knows its parents, its mutations, and its performance at every stage. When something works, you can see *why* it works. When it stops, you can see *when* it stopped.

## What isn't shared

The primitive library, the exact encoding, the fitness function weights, the deploy-bar thresholds, and the evolved strategies themselves are private. What's public is the methodology: encode the space, evolve honestly, validate against live data, gate deployment behind explicit standards, and keep score on everything.
