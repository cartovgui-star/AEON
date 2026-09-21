# AEON Trading System — Canonical Agent Reference

Rebuilt 2026-07-16 by full verification against live code and the running system (every claim below was checked against an import/call site, a running process, or a live API response — not copied from older docs). Supersedes `AEON_SNAPSHOT_2026-07-16.md` and the previous CLAUDE.md. **Ignore `AEON_FULL_DOCUMENTATION.txt` and `AEON_COMPLETE_SPECIFICATION.pdf`** — leftovers from the original 2026-03 import (MEXC-era, 25 pairs, wrong URLs).

AEON is an autonomous AI crypto **paper-trading** system (no real money moves). Backend: FastAPI, Python 3.12. Frontend: React 18. DB: MongoDB `aeon` @ 127.0.0.1:27017 (creds in `backend/.env`). Live at https://aeontrading.xyz.

---

## ⚠️ THE ONE THING TO GET RIGHT: two trees, and WWW IS CANONICAL

| Tree | Path | State (verified by full `diff -rq` + mtimes, 2026-07-16) |
|---|---|---|
| **LIVE / canonical** | `/var/www/aeon-finale-formv1.2.3.6.5` | What PM2 runs and nginx serves. **Strictly ahead of root**: ~50 shared files newer here (e.g. `server.py` Jul 15 vs root Jun 12) plus ~35 modules that exist ONLY here (`gate_ledger.py`, `research_desk.py`, `research_threads.py`, `head_of_research.py`, `team_council.py`, `oracle_deep.py`, `desk_actions.py`, `lab_*.py`, `routes/miniapp.py`, `telegram/command_registry.py`, …). |
| Staging (STALE) | `/root/aeon-finale-formv1.2.3.6` | Old git-history tree. Has NOTHING unique except `.bak` files. Its "uncommitted work" is itself weeks–months behind live. |

The old CLAUDE.md rule "edit root, then aeon-sync.sh" is **inverted from reality** — all work since ~June happens directly in www. `aeon-sync.sh` is now non-destructive (rsync `-u`, never overwrites newer destination files, prints a divergence report), so it can't clobber live code anymore, but syncing from stale root is mostly a no-op. **Edit www directly.**

**Git (verified):** BOTH trees are git repos, both on `dev`.
- www repo → `git@github.com:cartovgui-star/aeon-finale-formv1.2.3.6.5.git`, `dev` pushed 2026-06-24 ("capture running backend/frontend" commits). Since then: ~48 modified + ~14 untracked, uncommitted (all July work: gate ledger, research cognition, Oracle Search, security hardening, LLM routing fixes).
- root repo → `…/aeon-finale-formv1.2.3.6.git` (last commit `4e0babc` "Redesign frontend as AEON Hub", ~mid-April; 56 M + 92 ?? on top — historical interest only).

---

## Deploy workflow (what actually works)

```bash
# 1. Edit files in /var/www/aeon-finale-formv1.2.3.6.5/backend/
# 2. CRITICAL — root edits flip ownership and crash-loop the backend:
chown aeon:aeon <every file you touched>
# 3. Restart:
sudo -u aeon pm2 restart aeon-backend      # or: systemctl restart pm2-aeon
# 4. Logs:
sudo -u aeon pm2 logs aeon-backend --lines 30 --nostream
# 5. Health:
curl -s -H "X-API-Key: $(grep DASHBOARD_API_KEY /var/www/aeon-finale-formv1.2.3.6.5/backend/.env | cut -d= -f2)" \
  http://127.0.0.1:8000/api/system/health | python3 -m json.tool | head -20
# Port stuck: fuser -k 8000/tcp && sleep 1 && sudo -u aeon pm2 restart aeon-backend
```

Frontend: edit `/var/www/…/frontend/src/`, then
`cd /var/www/aeon-finale-formv1.2.3.6.5/frontend && export NODE_OPTIONS="--max-old-space-size=768" && yarn build`
(1GB server — if OOM, stop the backend during build). Current live bundle: `main.6d00ecde.js` (2026-07-15).

Auth: all `/api/*` need `X-API-Key` (`DASHBOARD_API_KEY` in backend/.env; frontend uses `REACT_APP_API_KEY`). Since the 2026-07-13 hardening, nginx restricts non-GET `/api` writes to Tailscale.

### Hard rules (NEVER)
- Never remove or bypass safety gates — make them smarter.
- Never `git push` without explicit user (Carlos) confirmation.
- Never leave edited /var/www files owned by root — always `chown aeon:aeon`.
- Never install heavy npm packages or build without the 768MB NODE_OPTIONS cap.
- Never change paper balances to simulate real money.
- Never restart the backend mid council/research-thread/head-of-research run if avoidable.
- Never trust root-tree file contents as current — check www first.
- Do not re-add MEXC (replaced by OKX, Apr 2026).

---

## What we use (all verified: call site, process, or API response)

### Process map (verified via systemctl / pm2 / ss)
| What | How it runs | Notes |
|---|---|---|
| `aeon-backend` (uvicorn `server:app`, 127.0.0.1:8000) | PM2 under Linux user **`aeon`**, supervised by `pm2-aeon.service` | `pm2 ls` as root will NOT show it — use `sudo -u aeon pm2 ls`. |
| NEXUS (`backend/nexus/nexus_core.py`) | `nexus.service`, **root**, binds **0.0.0.0:8001** | Separate "nervous system" process; writes `nexus_config` to Mongo every 60s; the backend's NEXUS gate enforces it. ⚠️ open bind = known security TODO. |
| futures-intel (separate product, `/root/futures-intel/`) | `futures-intel-api.service`, 127.0.0.1:8011 | Not part of AEON proper. |
| ttyd web terminal | `ttyd.service`, :7681, SSL + credential | plus 2 procs in root's own PM2 (terminal-app etc.). |
| Lab ingest | systemd timers `aeon-lab-arxiv`, `aeon-lab-defillama`, `aeon-lab-onchain` | feed `lab_research_papers`, `lab_macro_snapshots`, on-chain collections. |
| Ollama | local snap (small models only) + **remote Ollama at 100.79.50.80:11434 (Carlos's PC via Tailscale — `OLLAMA_BASE_URL` in .env)** | local LLM work depends on that PC being up. |

### The 9 trading engines (all started in `server.py` startup, all `healthy` in `/api/system/health` at verification time)
| Engine | Started at (www server.py) | Cadence |
|---|---|---|
| autonomous_trader_v2 | :1197 | 5-min scan loop |
| free_will_v2 | :1198 | 45s scanner |
| dual_engine (day_trader + long_term) | :1199 | continuous |
| vwap_scalper | :1264 | 5 min |
| volume_profile (vp_engine) | :1275 | 5 min |
| yolo_engine | :1295 | 3 min |
| institutional_scalper | :1304 | hourly |
| tcn_neural (Engine 9, PyTorch, BTC 1h) | :1314 | hourly inference |
| elite_strategy_v3 | :1325 | 30 min |

Plus non-engine loops (health-confirmed): oracle scanner (:1335, ~290 pairs), rituals, price_alerts, briefings/reports, continuous_learning, memory_engine, omega_cycle, web_intelligence, quantum_state, oria_stress, paper maintenance loops (health/price/tick/auto-deposit), engine_data_collector, strategy_lab (+HF sandbox+watchdog), research_desk, research_threads, head_of_research, team_council auto-runs, team_engine loop (:1571, 90-min interval), self_healer, alert monitors, chart_monitor.

### Paper accounts (verified via `/api/paper/accounts`)
**REAL_LIFE, TIER_5K, TIER_1K, TIER_500, PERSONAL, RESEARCH** (6 active). PRO/STARTER/THE_PROOF/BENCHMARK are retired/archived — old docs listing them are stale.

### Gate pipeline, in execution order (verified by reading www `aeon_engine_system.py`)
Entry point `submit_signal_gated` (:771) wraps everything in the **gate-ledger counterfactual recorder** (every REJECT logged to `gate_ledger` collection and marked to market). Then `_submit_signal_gated_inner` (:797) runs:

1. **NEXUS config gate** (:821) — crisis/pause hard block, per-engine allowlist (Morpheus), position modifier
2. **Reversing-regime gate** (:874) — trend REVERSING → LONGs need 85%+ confidence
3. **H-gate** (:899) — **size-scaler ONLY** (hard block removed 2026-06-15 by Carlos after a 3-day trade freeze deadlock); scales position by H, floor 0.25×. Backed by `aeon_quantum_state.py` via `app_state.quantum_state` — **NOT** `quantum_identity.py` (see dead list)
4. **Team gate, early/proactive** (:927) — specialist CAUTION/approved recs
5. **Gate 15: MTF confluence** (:952) — EMA20/50 alignment across 5m/15m/1h/4h; >55 long / <45 short
6. **Fear & Greed gate** (:979) — extreme fear blocks longs / extreme greed blocks shorts unless 90%+ conf
7. **Macro directional gate + directional governor** (:999) — BEARISH: counter-trend longs blocked below `COUNTERTREND_LONG_ESCAPE_CONF` (default 95); BULLISH: shorts need 72%+; NEUTRAL chop: 80%+ conviction AND size ×0.35
8. **Entropy gate** (:1050) — `oracle_entropy_gate`, H_norm > 0.65 (ranging/noise) → reject
9. **Gate 16: Hurst regime gate** (:1093) — `hurst_gate.py` (Anis–Lloyd corrected)
10. **Gate 17: Von Neumann entropy gate** (:1121) — market-wide correlation regime; block or half-size
11. **TCN ensemble direction gate** (~:1151) — BTC/USDT only; blocks when neural vote disagrees confidently
12. **Quant Gatekeeper V2** (:1204) — `quant_analyzer_v2.get_quant_gatekeeper_v2`, injected at server.py:1143; regime-aware score threshold + position multiplier; blocked engines may adapt and resubmit once
13. **Gate 12: ORIA edge filter** (:1250) — Kelly edge vs cost+uncertainty
14. **Team gate, approved recommendations** (:1337)

…then the synchronous `submit_signal` path: macro re-check (:1544), **ORIA layer** stress sizing + convergence bonus (:1557–1673), QUBO position sizer, and a combined size-multiplier floor of 0.35 (:16). Free-will longs: `FW_LONGS_MODE=shadow`; quant gate on FW shorts advisory (`FW_QUANT_GATE_MODE=short_advisory`).

### Data sources (verified in `feed_health.py` probes + import sites)
- **OKX** — primary: prices, candles, OI, L/S, funding, tick WS; ccxt wrapper in `market_intelligence.py` (+`ccxt_patch.py`); dynamic universe `get_full_universe()` ($1M floor, ~74 pairs)
- **LiveCoinWatch** — top-coin prices (`LIVECOINWATCH_API_KEY`)
- **CoinGecko** — sentiment/meta; **Coinbase** — cross-check + `routes/orderbook.py`
- Lab timers: arXiv q-fin, DefiLlama, keyless mempool/blockchain.info
- LLM: role-routed local Ollama (`llm_client.py` `LOCAL_MODELS_BY_ROLE` — general qwen3:14b, coding qwen2.5-coder:14b, reasoning deepseek-r1:14b, fast r1:8b; env-overridable) with `FAILOVER_CHAIN = ["gemini", "claude", "deepseek"]` (llm_client.py:122). Claude currently dead (no API credits, Jul 15 audit).

### Frontend (verified in www `App.js`)
`App.js` renders **AeonHub** (`components/hub/AeonHub.jsx`, tabs: Hub / Engines / Exposure / Oracle / Control / Lab) by default, toggling to **ArenaShell** (`components/arena/ArenaShell.jsx` — gamified: HeroDeck, OracleDeck, MindPage, quests/achievements). Both current. **This look at aeontrading.xyz is the one to preserve.** There is also a Telegram Mini App (`routes/miniapp.py`, HMAC initData auth) on ObsidianCabalbot.

---

## What we don't use anymore (each verified by grepping for call sites, not just definitions)

- **`quantum_identity.py` — fully dead.** ~690 lines, but `init_quantum_identity()` has **zero callers** anywhere (grep across www backend). Even `routes/quantum.py` — whose endpoint is confusingly named `get_quantum_identity` — reads `aeon_quantum_state.py`, not this file. The live H-gate is backed by `aeon_quantum_state`. Any doc saying "quantum_identity.py = the H-gate" is wrong.
- **MEXC** — replaced by OKX Apr 2026. `server.py:148-149` keeps env vars marked "legacy, unused"; `mexc_utils.py` etc. are vestigial.
- **`quant_analyzer_engine.get_quant_gatekeeper` (V1 gatekeeper)** — superseded by V2. (The module itself is still live for `CoinAnalyzer`/`get_quant_engine` used by V2 and `routes/quant_analyzer.py` — don't delete it.)
- **Abandoned Apr-2026 hub redesign** — `frontend/src/components/aeon-hub/AeonHubShell.jsx` (+its CommandCenter/OperatorHome/NexusPanel/etc.) not imported by App.js; 9 dead `App.js.pre-*-20260421` snapshots. Never wire these back in.
- **`coinbase_feed.py`, `coinbase_trader.py`** — zero importers; stalled experiment. (**`market_data_fetcher.py` is NOT dead** — used by `oracle_entropy_gate.py:202` — a correction to the earlier snapshot.)
- **Old docs** — `AEON_FULL_DOCUMENTATION.txt`, `AEON_COMPLETE_SPECIFICATION.pdf`, and now also `AEON_SNAPSHOT_2026-07-16.md` (folded into this file).
- **Oracle conviction score as a signal** — proven on 262k calls (2026-07-14) to have NO predictive edge; deliberately NOT wired into engines (`get_oracle_bias()` intentionally uncalled). Oracle = context dashboard + advisory only.
- **The root staging tree** as an edit target (see top).

## What's been worked on

**Committed (root repo, Mar→mid-Apr):** import of original system → NEXUS + InstitutionalScalper + Mongo auth → OKX migration off MEXC → engines package/MTF confluence → canonical trade schema, risk policy, leverage caps → AEON Hub frontend redesign (`4e0babc`).
**Committed (www repo, Jun 24):** "capture running backend/frontend/llm-routing" — snapshot of the live state into git.
**Uncommitted on www since Jun 24 (the real recent history), by feature area:** agentic research org (desk ACT mode, threads, head_of_research, council with settled-ledger, base-rate theory scoring, Jul-14 "cognition verbs" + self-model/reflections); gate & execution overhauls (gate-ledger counterfactuals, directional governor, R-based trailing, liq-rounding fix, sizer audit); Oracle tab + Oracle Search (`oracle_deep.py`, Jul 15); Telegram mini-app + command registry; LLM routing (role-based Ollama, failover chain, deepseek timeout fix); lab ingest timers; security hardening (Tailscale-only writes, terminal lockdown, Jul 13); OKX AI-marketplace agent (#4907, separate `/root/okx-ai/`).

## How everything is supposed to work (end to end)

1. An engine's scan loop finds a setup and calls `engine_manager.submit_signal_gated(signal, engine_type)`.
2. The signal runs the 14-stage async gauntlet above; every rejection is ledgered with counterfactual tracking; survivors get a size multiplier composed of NEXUS modifier × H-scale × governor/VN/ORIA/quant multipliers (floor 0.35).
3. `paper_trading.py` opens the trade on the target paper account (leverage caps, SL-guard rejects across-entry clamps, liq at 8dp) and manages exits: TP1 → breakeven, R-trailing arms at 1R / trails 1.25R; tick engine + price loops mark to market; open uPnL is mirrored live (never read open PnL from history).
4. Frontend: AeonHub tabs read the authed REST API (trades, engines, exposure, oracle, control, lab); ArenaShell gamifies the same data; Telegram bot (persona = AEON itself via `aeon_live_context.py`) + Mini App mirror it.
5. Research org: oracle/lab/desk/threads/council/HOR generate theories → AST-sandboxed strategies → tournament → canary promotion (`qr_lab_promotions`); desk governor caps book-verbs at 10/day (cognition verbs bypass); kill-switch `qr_desk_state.enabled`.
6. NEXUS independently classifies regime and can pause/suspend engines via `nexus_config`, which gate #1 enforces.

## Findings from this verification pass (2026-07-16)

- **Tree drift is total and one-directional** — root has no unique live code; treat www as the only source of truth. `RECONCILE_LIVE_TO_ROOT.md` in this repo describes the plan, largely not executed.
- **`routes/quantum.py:56`** defines endpoint `get_quantum_identity()` that has nothing to do with `quantum_identity.py` — naming trap.
- **NEXUS binds 0.0.0.0:8001 as root** — open item from Jul 13 hardening (with master-key rotation and CUPS).
- **`OLLAMA_BASE_URL=http://100.79.50.80:11434/v1`** — "local" LLM = Carlos's PC over Tailscale; if it's off, local roles fail over per chain.
- www carries dozens of `.bak.*` files alongside live modules (e.g. `aeon_engine_system.py.bak.ledger.20260705_203706`) — never edit a `.bak`; sync excludes them.
- ~62 total uncommitted files on www `dev` = the only copy of a month of work. Recommend committing/pushing (with Carlos's confirmation) as the top housekeeping priority.
