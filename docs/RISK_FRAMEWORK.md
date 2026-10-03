# The Risk Framework

How AEON thinks about not losing money — which, in this design, is a bigger job than making it.

## The governing insight

Every autonomous system eventually meets a market it wasn't designed for. The question isn't whether that happens — it's what the system does in the first minute after. AEON's risk framework is built for that minute.

## Layers of defense

### 1. Engine governance
Every autonomous engine is individually governed: its behavior is tracked, its decisions are logged, and its permissions can be restricted or revoked without affecting anything else. An engine that starts behaving oddly — unusual frequency, unexpected instruments, degrading performance — gets throttled or paused by governance, not by hope.

### 2. The gate ledger
Every autonomous decision is recorded with its reasoning: what the engine saw, what it decided, and why. This isn't just an audit trail — it's the raw material for the post-mortem process. When something goes wrong, the first question is answerable: *what exactly did the system think was happening?*

### 3. The execution gate
Wanting to trade and being allowed to trade are separate things, handled by separate components. An independent evaluation gate stands between any autonomous intent and any real execution. The gate doesn't care how confident the engine is — it cares whether the preconditions for safe execution are met.

### 4. Portfolio heat
Aggregate exposure is monitored as a first-class concern. Individual positions can each look reasonable while the portfolio as a whole is overextended. Heat monitoring watches the sum, not just the parts.

### 5. Kill switches
Multiple levels of stop: per-engine, per-strategy, and system-wide. Designed to be reached for — a kill switch you hesitate to pull is decoration.

## Position sizing philosophy

Size is where most systems die. AEON treats sizing as a risk decision, not an optimization problem: the question isn't "how much can we make?" but "how much can we lose without impairing the next decision?" Different account types use different sizing models (flat-dollar-risk for some, volatility-adaptive for others), and every model has hard ceilings that no signal can override.

## The paper rule

No strategy, engine, or parameter change touches real capital without first surviving the paper sandbox against live data. This isn't a one-time certification — it's a standing requirement. The moment a component's live behavior diverges from its validated behavior, it's back to paper until it re-earns trust.

## What "risk management" means here

Not a stop-loss formula. A culture, encoded in software: separation of powers between research and execution, explicit gates with explicit criteria, full decision logging, and the standing assumption that any component can fail. The system is designed to be *survivable* — to take a bad day, a bad week, or a bad regime and still be standing, still learning, still honest about what happened.

## What isn't shared

Exact limits, thresholds, sizing parameters, gate criteria, and the governance rule implementations are private. What's public is the architecture of caution: governed engines, decision ledgers, independent execution gates, portfolio-level monitoring, and a paper-first rule with no exceptions.
