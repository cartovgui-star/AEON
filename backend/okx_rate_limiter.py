"""
Global OKX rate-limit guard.

OKX public candle/ticker endpoints allow 40 requests per 2 seconds.
All sync (thread-executor) OKX calls across AEON must acquire OKX_SEM before
firing. The asyncio counterpart in MarketIntelligence._okx_sem guards async
paths.  Together they prevent hitting OKX's per-IP rate limit across all
engines running concurrently.
"""

import threading

# 4 concurrent sync OKX calls max.  At ~300 ms avg RTT that is ≈13 req/s
# worst-case — well under the 40 req/2 s (20 req/s) public limit.
OKX_SEM: threading.Semaphore = threading.Semaphore(4)
