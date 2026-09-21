> **SUPERSEDED 2026-07-16:** folded into `CLAUDE.md` (repo root) after a fresh verification pass — read that instead. Kept for history only.

# AEON System Snapshot — 2026-07-16

Ground-truth reference of what's live on `personalaeonai` (162.243.184.249, aeontrading.xyz) as of this date.
**Purpose:** so no future session — human or agent — accidentally regresses what's currently working. If you're about to change something, check here first for whether it's load-bearing.

---

## 1. What this system is

AEON is an autonomous AI crypto **paper-trading** system (no real money moves — verify this hasn't changed before assuming otherwise). It combines:

- 9 signal-generating trading engines
- A multi-stage risk gate pipeline
- 5 paper accounts of varying size
- A research/intelligence layer (290-pair Oracle scanner, sentiment, derivatives, on-chain, macro)
- A conversational persona layer (Telegram bot, "free will" engine, memory system)
- A "team"/specialist layer (`team_engine`) and a separate `nexus_core.py` subsystem
- Two frontend UI modes toggled from one app: **AeonHub** (default dashboard) and **ArenaShell** (gamified alternate view — quests, achievements, level-ups)

## 2. DO NOT BREAK — current live UI

Live at **https://aeontrading.xyz** — this look/layout is considered correct and must be preserved unless explicitly asked to change it.

- Entry point: `frontend/src/App.js` (in `/var/www/aeon-finale-formv1.2.3.6.5/frontend/src/`)
- Renders **`AeonHub`** (`components/hub/AeonHub.jsx`) by default — tabs/screens: hub, engines, exposure, oracle, control, researcher
- Toggles to **`ArenaShell`** (`components/arena/ArenaShell.jsx`) via `onEnterArena` — a separate gamified view (HeroDeck, EngineRoster, TeamPage, QuestPanel, AchievementShelf, TradeFireworks, MindPage, OracleDeck, LiveFeed)
- Both are real, both are wired, both are current (build is up to date with source as of 2026-07-15)
- **Do not** re-wire in `components/aeon-hub/AeonHubShell.jsx` or any `App.js.pre-pass*` variant — those are dead/abandoned (see §5)

## 3. Two trees — know which one you're editing

| Tree | Path | Role |
|---|---|---|
| Staging | `/root/aeon-finale-formv1.2.3.6` | Has git history (`dev` branch checked out). Preferred edit location. |
| Live | `/var/www/aeon-finale-formv1.2.3.6.5` | **This is what PM2 actually runs and nginx serves.** |
| Sync | `/root/aeon-sync.sh` | Rsyncs root → www + restarts PM2 (no `--delete`) |

The two trees have drifted (see backend/CLAUDE.md's own "reality check" note — written April, itself partially stale now). When in doubt, check which tree actually has the current version of a file before editing.

## 4. Runtime — what's actually running (verified 2026-07-16 via `/api/system/health`)

All of the following reported `healthy` with heartbeats in the last minute at time of this snapshot:
rituals, trading_v2, free_will, dual_engine, price_alerts, morning_briefing, weekly_report, continuous_learning, vp_engine, vwap_scalper, yolo_engine, institutional_scalper, tcn_neural, elite_strategy, oracle.

Process supervision:
- Live backend (`uvicorn server:app`, port 8000) runs as Linux user **`aeon`**, supervised by **`pm2-aeon.service`** (a *separate* PM2 daemon under the `aeon` user — `pm2 list` as root will NOT show it; that's expected, not broken)
- `nexus/nexus_core.py` — separate standalone process, root, long-running
- `terminal-app` (node) — tracked in root's own PM2
- Research/lab timers: `aeon-lab-arxiv`, `aeon-lab-defillama`, `aeon-lab-onchain` (systemd `.service` + `.timer` pairs)
- `futures-intel` — separate FastAPI app on port 8011 (root's own venv)

## 5. Built but NOT wired in (looks done, isn't)

**`quantum_identity.py` / the H-gate — the important one.** `backend/CLAUDE.md` documents this as an active safety gate ("blocks if H < 1.0"). It is fully implemented (~690 lines, singleton, has a live read API at `routes/quantum.py`), but **nothing in the codebase calls `init_quantum_identity()` or attaches it to the engine manager.** It is not gating any trade right now — pure read-only API surface. There's also an in-file comment: *"Hard block disabled 2026-06-15 (Carlos): the H-gate now only scales position"* — so even its intended behavior has already changed once without the docs catching up.

**Abandoned frontend redesign.** `frontend/src/components/aeon-hub/AeonHubShell.jsx` plus its own fully-built `CommandCenter.jsx`, `OperatorHome.jsx`, `NexusPanel.jsx`, `QuantumStatePanel.jsx`, `CrisisModeOverlay.jsx` — none imported by the live `App.js`. Alongside it, 9 dead snapshot files: `App.js.pre-pass3` through `pre-pass9`, `pre-dashboard-pass2`, `pre-old-shell-upgrade` (all dated 2026-04-21). This was an earlier hub redesign attempt, superseded by what's live now (§2). Safe to delete once confirmed unneeded, but not touched in this pass.

**Unfinished Coinbase integration.** `coinbase_feed.py`, `coinbase_trader.py`, `market_data_fetcher.py` — untracked in the root repo, not imported by either tree. Exploratory work that stalled.

## 6. Wired-in and confirmed working (verified via import/call-site grep)

- `team_engine` — real `asyncio.create_task` at startup (server.py:1571), registered with `self_healer`
- `hurst_gate`, `ensemble_voter`, `oracle_entropy_gate`, `von_neumann_gate`, `strategy_backtest` — imported and used in `routes/researcher.py`
- `qubo_sizer` — feeds position sizing in `aeon_engine_system.py`
- `engine_governance`, `engine_health` — live in `routes/dashboard.py`
- Nexus — both a standalone process (`nexus_core.py`) and an API router (`routes/nexus.py`, registered in `server.py`)

## 7. Git / backup state (as of 2026-07-16)

- Root repo on branch `dev`. Last commit `4e0babc` ("Redesign frontend as AEON Hub") — **~3 months old**.
- ~55 modified tracked files + ~70 untracked new files, **uncommitted**, representing ~3 months of continuous work (team layer, gates, governance, Coinbase experiments, frontend redesign).
- `dev` has **never been pushed to `origin`** (`https://github.com/cartovgui-star/aeon-finale-formv1.2.3.6.git`, only `main` exists remotely). No credential helper configured — pushing will need a PAT.
- Daily `/root/backups/YYYYMMDD/` — **MongoDB dumps only** (trade history, state, memory), not code.
- One code tarball, `aeon-live-code-2026-06-30.tar.gz` — stale as of this snapshot.
- A fresh code tarball of both trees was pulled to the local machine on 2026-07-16 as a stopgap (see local `aeon-backups/` folder) — this is not a substitute for real git history; recommend committing + pushing `dev` when ready.

## 7b. Superseded documentation — do not trust

`/var/www/aeon-finale-formv1.2.3.6.5/AEON_FULL_DOCUMENTATION.txt` and `AEON_COMPLETE_SPECIFICATION.pdf` (dated 2026-03-04) are leftovers from the original import and are badly stale — they reference MEXC/Binance (replaced by OKX in April), 25 trading pairs (Oracle now scans 290), and a preview URL that isn't `aeontrading.xyz`. This document (`AEON_SNAPSHOT_2026-07-16.md`) supersedes them. Consider deleting or archiving the old ones once this is confirmed useful.

## 8. Rules carried over from backend/CLAUDE.md (still apply)

- Never remove safety gates — only make them smarter
- Never edit `/var/www/.../backend` directly for files that also exist in root — edit root, sync via `aeon-sync.sh`
- Never `git push` without explicit user confirmation (PAT required)
- Frontend build: `NODE_OPTIONS="--max-old-space-size=768"` (1GB server — OOM risk otherwise)
- MEXC was replaced by OKX in Apr 2026 — do not re-add MEXC
