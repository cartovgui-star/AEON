"""
MEXC Symbol Formatter
=====================
Single source of truth for converting any trading symbol variant into the
format expected by CCXT's MEXC driver (BTC/USDT slash format).

MEXC Futures native format : BTC_USDT
CCXT abstraction format    : BTC/USDT  ← what ccxt.mexc() expects

Accepted input forms:
    BTCUSDT          bare concat
    BTC_USDT         underscore (MEXC native)
    BTC/USDT         CCXT spot slash (already correct)
    BTC-USDT         hyphen
    btcusdt          lowercase
    BTC/USDT:USDT    CCXT perpetual swap notation (settle suffix stripped)

All MarketIntelligence public methods call format_mexc_symbol() at entry,
so callers may pass any variant and will always get correct CCXT output.
"""


def format_mexc_symbol(symbol: str) -> str:
    """
    Normalize any symbol variant to CCXT slash format for MEXC: ``BTC/USDT``.

    Returns:
        ``BTC/USDT`` (CCXT standard — ccxt.mexc() converts to BTC_USDT internally)
    """
    s = symbol.upper().strip()

    # Strip CCXT perpetual/swap settle suffix  e.g. "BTC/USDT:USDT" → "BTC/USDT"
    if ":" in s:
        s = s.split(":")[0]

    # Strip all remaining separators → "BTCUSDT"
    s = s.replace("_", "").replace("-", "").replace("/", "")

    # Split on known quote currencies (longest match first)
    for quote in ("USDT", "BUSD", "USDC", "USD", "BTC", "ETH", "BNB"):
        if s.endswith(quote) and len(s) > len(quote):
            base = s[: -len(quote)]
            return f"{base}/{quote}"

    # Unknown quote — return uppercased as-is (safe fallback)
    return symbol.upper().strip()
