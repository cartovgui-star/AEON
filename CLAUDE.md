# AEON Trading System — Coding Agent Reference

Read this before touching anything.

## What This Project Is
AEON is a paper-trading AI system. All trading is simulated — no real money moves.
Backend: FastAPI (Python 3.12). Frontend: React 18. Database: MongoDB (`aeon` db).
Live process: PM2 manages `aeon-backend`, nginx serves the built React frontend.

---

## Canonical Paths

| What | Path | Notes |
|------|------|-------|
| **Backend (PM2 runs here)** | `/root/aeon-finale-formv1.2.3.6/backend` | **Edit here. This is the source of truth.** |
| **Frontend source** | `/var/www/aeon-finale-formv1.2.3.6.5/frontend/src` | Edit here for UI changes |
| **Frontend build** | `/var/www/aeon-finale-formv1.2.3.6.5/frontend/build` | Rebuilt by yarn, served by nginx |
| **www backend (mirror)** | `/var/www/aeon-finale-formv1.2.3.6.5/backend` | Synced from root — do NOT edit here directly |
| **Sync script** | `/root/aeon-sync.sh` | Run after backend edits to deploy |
| **MongoDB** | `127.0.0.1:27017`, db=`aeon` | Credentials in backend/.env |

**The www backend is a deployment mirror. Always edit `/root/.../backend`, then run `/root/aeon-sync.sh`.**

---

## Deploy Workflow (ALWAYS follow this)

```bash
# 1. Edit files in /root/aeon-finale-formv1.2.3.6/backend/
# 2. Deploy:
/root/aeon-sync.sh              # syncs backend + restarts PM2
/root/aeon-sync.sh --full       # also rebuilds React frontend
/root/aeon-sync.sh --dry-run    # preview what would change

# 3. Check logs:
pm2 logs aeon-backend --lines 30 --nostream

# 4. Verify:
curl -s -H "X-API-Key: $(grep DASHBOARD_API_KEY /root/aeon-finale-formv1.2.3.6/backend/.env | cut -d= -f2)" \
  http://127.0.0.1:8000/api/system/health | python3 -m json.tool
```

## If Port 8000 Is Stuck (EADDRINUSE)
```bash
fuser -k 8000/tcp && sleep 1 && pm2 restart aeon-backend
```

---

## Auth

All `/api/*` routes require header: `X-API-Key: <key>`

Key is in `backend/.env` as `DASHBOARD_API_KEY`.
Frontend reads it from `frontend/.env` as `REACT_APP_API_KEY`.

---

## Active Engines (paper trading only)

- `autonomous_trader_v2` — 5min scan loop
- `free_will_v2` — 45s scan loop  
- `dual_engine` (day_trader + long_term) — continuous
- `vwap_scalper` — 5min loop
- `yolo_engine` — 3min loop
- `elite_strategy_v3` — 30min loop
- `institutional_scalper` — wired
- `tcn_neural` — hourly inference
- `quant_analyzer` — 30min loop

All signals go to paper accounts: PRO ($50K), STARTER ($1.5K), REAL_LIFE ($700), THE_PROOF ($40), BENCHMARK ($50K).

---

## Gate Pipeline (submit_signal_gated)

Every engine signal passes these gates before a paper trade is placed:

1–11: Quant gates in `aeon_engine_system.py`  
12: ORIA Edge Filter (`oria_layer.py`)  
13: ORIA Stress Sizing  
14: ORIA Convergence Bonus  
15: MTF Confluence (score > 55)  
H-gate: Quantum identity gate (`quantum_identity.py`) — blocks if H < 1.0

**Never remove or bypass gates. Make them smarter instead.**

---

## Data Sources

| Source | Used For | Auth |
|--------|----------|------|
| OKX public API | Prices, candles, OI, L/S ratios, funding rates | None |
| LiveCoinWatch | Top 100 coin prices | `LIVECOINWATCH_API_KEY` in .env |
| CoinGecko | Fear & Greed index, sentiment | None |
| Coinbase | Price cross-check | None |

MEXC was replaced with OKX in Apr 2026. Do not re-add MEXC dependencies.

---

## Key Files

| File | What It Does |
|------|-------------|
| `server.py` | FastAPI app, all route registrations, startup lifecycle |
| `app_state.py` | Global singletons (db, engines, paper_trading, etc.) |
| `aeon_engine_system.py` | Engine registry, gate pipeline, `submit_signal_gated()` |
| `paper_trading.py` | Paper account management, trade execution, TP/SL monitoring |
| `market_intelligence.py` | OKX CCXT wrapper, candles, tickers, L/S ratios |
| `oracle_engine.py` | 290-pair multi-timeframe scanner, scores all pairs |
| `quantum_identity.py` | H-gate, AEON quantum state |
| `oria_layer.py` | Stress monitor, edge filter, position sizing |
| `feed_health.py` | Feed health monitor, graceful degradation |
| `routes/` | FastAPI routers (analytics, quant_analyzer, quantum, etc.) |
| `engines/` | TCN Neural engine (Engine 9) |

---

## NEVER

- Remove safety gates (only make them smarter)
- Edit files in `/var/www/.../backend` directly — always edit root, then sync
- Run `git push` without confirming with the user (PAT required)
- Install heavy npm packages (1GB RAM — risk OOM during build)
- Change paper account balances to simulate real money
- Skip the sync script and expect changes to take effect

---

## Frontend Build

```bash
cd /var/www/aeon-finale-formv1.2.3.6.5/frontend
export NODE_OPTIONS="--max-old-space-size=768"  # Required — 1GB server
yarn build
```

If OOM: `pm2 stop aeon-backend` → build → `pm2 start aeon-backend`

---

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Stable, deployed state |
| `dev` | Active architecture work — merge to main when tested |

Always work on `dev` for new features. Only merge to `main` when PM2 shows no errors for 10+ minutes.

---

## Before Any Edit

1. Read the file first
2. Check what imports it: `grep -rn "import.*<module>" backend/ --include="*.py"`
3. Make the edit
4. Run `/root/aeon-sync.sh`
5. Check `pm2 logs aeon-backend --lines 20 --nostream`
