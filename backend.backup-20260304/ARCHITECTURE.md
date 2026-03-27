# Aeon Backend Architecture

## File Structure

```
/app/backend/
├── server.py                 # Main FastAPI app, core endpoints only
├── routes/                   # Modular route handlers (preferred location)
│   ├── trading.py           # All /trading/* and /trades/* endpoints  
│   ├── market.py            # Market data endpoints
│   ├── alerts.py            # Alert management
│   ├── analysis.py          # Analysis endpoints
│   ├── derivatives.py       # Derivatives data
│   ├── intelligence.py      # Intelligence features
│   ├── smc.py               # Smart Money Concepts
│   ├── memory.py            # Memory system
│   ├── strategies.py        # Trading strategies
│   └── freewill.py          # Free will trading engine
├── services/                # Business logic
└── telegram/                # Telegram bot handlers
```

## Routing Rules

### ✅ DO
1. **Add NEW endpoints to `routes/*.py` files** - keeps code modular
2. **Use appropriate prefixes** in APIRouter definition
3. **Include routers in server.py** with `app.include_router()`
4. **Follow REST conventions** for endpoint naming

### ❌ DON'T  
1. **NEVER create duplicate endpoints** in both server.py and routes/*.py
2. **Don't add business logic to server.py** - keep it in services/
3. **Don't modify server.py for new features** - use routes/

## Route Registration Order

```python
# In server.py:
app.include_router(api_router)         # Core endpoints (server.py)
app.include_router(alerts_router, prefix="/api")
app.include_router(market_router)      # Already has /api prefix
app.include_router(trading_router)     # Already has /api prefix
# ... other routers
```

**Last registered routes take precedence** - modular routes override server.py duplicates.

## Endpoint Migration Checklist

When moving endpoints from server.py to routes/*.py:

- [ ] Copy endpoint function to appropriate routes/*.py file
- [ ] Update imports in routes/*.py if needed
- [ ] Test endpoint works via routes/*.py
- [ ] Remove old endpoint from server.py
- [ ] Add comment in server.py noting where endpoint moved
- [ ] Verify no functionality broken
- [ ] Update documentation

## Current Status

### ✅ Fully Migrated
- **Trading endpoints** (`/trading/*`, `/trades/*`) → `routes/trading.py`

### ⚠️ Partial Duplicates (To be cleaned up)
- Market endpoints (both in server.py and routes/market.py)
- Alerts endpoints (both in server.py and routes/alerts.py) 
- Derivatives endpoints
- Strategy endpoints

**Note**: Duplicates currently work because modular routes are registered last and take precedence. However, they cause confusion and should be removed.

## Migration Priority

1. ✅ **DONE**: Trading endpoints (completed 2026-02-18)
2. 🔜 **Next**: Market, Alerts, Derivatives
3. 🔜 **Future**: Strategies, Intelligence, other remaining duplicates

---

**Last Updated**: 2026-02-18  
**Refactored By**: E1 Agent (Fork Job)
