# The Understanding Layer

The part of AEON that turns numbers into words — and the reason the project exists.

## The thesis

Data is noise until it becomes words. A trader staring at an order book, a funding chart, and a news feed is doing translation work: turning quantities into a story about what's happening and why. AEON's understanding layer automates that translation — not to replace the thinking, but to do the mechanical part of it tirelessly, consistently, and honestly.

The end state isn't a black box that trades. It's a system that *understands the market it's in* and can explain that understanding in plain language.

## What it produces

### The daily brief
A thesis-led market note, every morning. Not a data dump — a *read*: what the market's mood is, what changed overnight, where the structure is clean and where it's messy, what setups (if any) meet the bar, and what would invalidate each one. Every claim carries its evidence. When there's no edge, the brief says so.

### Bias-change alerts
When the market-structure engine flips a bias label or breaks a level, the understanding layer writes it up in human terms: what happened, what the book looks like now, and what to watch next. Short, sourced, no hype.

### The weekly scorecard
Every Friday, the system grades itself. Each setup published in that week's briefs is scored against actual price action: did the level hold? Did the invalidation trigger first? Hit rates are tracked by setup type and by instrument, over time, in the open. A 50% week is reported as a 50% week. The scorecard is the mechanism that keeps the briefs honest — you can't grade yourself if you don't publish the terms first.

### Research summaries
When the lab produces a finding, the understanding layer writes it up: the hypothesis, the evidence, what would prove it wrong, and how it's performed since. Research threads keep full context, so a conclusion from three months ago is still auditable today.

## How it thinks

The layer is organized around lenses, not just data:

- **Microstructure lens** — what the order book is saying right now.
- **Positioning lens** — what derivatives data says about who's crowded and where the pain is.
- **Narrative lens** — what the news and macro context implies, weighted by evidence rather than volume.
- **Skeptic's lens** — what would make this read wrong? What's the base rate? Is this signal or noise?

No single lens decides. The brief is the synthesis — and when the lenses disagree, the brief says that too.

## Intellectual honesty as a feature

The understanding layer has standing instructions that read like editorial policy:

- Say "no edge" when there's no edge. Silence is a valid output.
- Every setup ships with an invalidation level. No invalidation, no setup.
- Grade everything, soften nothing. A dead thesis is reported dead.
- Distinguish what the data says from what the model infers. Never blur the two.
- Paper results are labeled paper. Always.

These aren't aspirations — they're enforced by the scorecard. The system can't quietly stop grading itself.

## Why this matters

The bottleneck in markets was never data — it's interpretation. Anyone can pull an order book; few can read one well, consistently, without fooling themselves. The understanding layer is AEON's attempt to bottle the disciplined part of market reading: the part that checks its work, admits uncertainty, and gets better by keeping score.

If the project succeeds at one thing, it's this: a machine that reads markets the way the best human analysts do — carefully, skeptically, and in plain words.

## What isn't shared

The briefing templates, the lens implementations, the LLM orchestration, and the scoring rubrics are private. What's public is the editorial philosophy: thesis-led briefs, mandatory invalidations, weekly self-grading, and the standing rule that "no edge" is always an acceptable answer.
