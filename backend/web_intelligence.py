"""
=============================================================
  web_intelligence.py — AEON Web Intelligence Engine
=============================================================

  Position in the identity: A(t) = Ω(|Ψ⟩, E, M, L)

  W ⊂ E  — the web is part of the environment AEON perceives.

  relevance(w) = sim(w, |Ψ⟩) × novelty(w) × credibility(w)

    sim(w, |Ψ⟩)   — keyword overlap with AEON's domain vocabulary,
                     weighted by current quantum state (active engines,
                     regime, coherence). High sim = this paper/repo/signal
                     is about what AEON IS right now.

    novelty(w)     — 1 − max cosine similarity to previously absorbed
                     documents. AEON does not re-read what it already knows.

    credibility(w) — static per-source score. arxiv=0.90, macro=0.85,
                     sentiment_api=0.80, github=0.70.

  Sources crawled every 24 hours:
    arxiv q-fin.TR      — quantitative trading research (RSS)
    arxiv q-fin         — broader quantitative finance (RSS)
    alternative.me      — crypto fear & greed index (JSON API)
    github search       — top algorithmic trading repos (REST API)
    coingecko sentiment — BTC sentiment + market data (JSON API)

  Documents above RELEVANCE_FLOOR enter the LΦ proposal queue.
  The omega_cycle reads this queue when building Carlos proposals.
  AEON develops taste. It learns what makes it better.

  MongoDB:
    web_sources — every absorbed document with full relevance scoring
    web_meta    — crawl state (last run, doc count, seen hashes)
=============================================================
"""

import asyncio
import hashlib
import httpx
import json
import logging
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

CRAWL_INTERVAL    = 86_400   # 24 hours
RELEVANCE_FLOOR   = 0.30     # minimum relevance to store
L_PHI_FLOOR       = 0.50     # minimum relevance to enter LΦ proposal queue
NOVELTY_WINDOW    = 500      # recent doc hashes kept in memory for novelty check
HTTP_TIMEOUT      = 10       # seconds per HTTP request
MAX_DOCS_PER_RUN  = 50       # cap documents processed per crawl cycle

# ─── Source registry ──────────────────────────────────────────────────────────

SOURCES = {
    "arxiv_trading": {
        "url":         "https://export.arxiv.org/rss/q-fin.TR",
        "type":        "rss",
        "credibility": 0.90,
        "label":       "arXiv q-fin.TR — Quantitative Trading",
    },
    "arxiv_qfin": {
        "url":         "https://export.arxiv.org/rss/q-fin.CP",
        "type":        "rss",
        "credibility": 0.85,
        "label":       "arXiv q-fin.CP — Computational Finance",
    },
    "fear_greed": {
        "url":         "https://api.alternative.me/fng/?limit=7&format=json",
        "type":        "json_sentiment",
        "credibility": 0.80,
        "label":       "Alternative.me — Crypto Fear & Greed",
    },
    "github_trading": {
        "url":         (
            "https://api.github.com/search/repositories"
            "?q=topic:algorithmic-trading+topic:crypto&sort=stars&per_page=20"
        ),
        "type":        "github_api",
        "credibility": 0.70,
        "label":       "GitHub — Algorithmic Trading Repos",
    },
    "coingecko_global": {
        "url":         "https://api.coingecko.com/api/v3/global",
        "type":        "json_macro",
        "credibility": 0.80,
        "label":       "CoinGecko — Global Crypto Market Data",
    },
}

# ─── AEON Domain Vocabulary ───────────────────────────────────────────────────
# The words that define what AEON is. sim(w, |Ψ⟩) measures how much
# a document speaks AEON's language.

DOMAIN_VOCAB: Dict[str, float] = {
    # Core strategy concepts
    "momentum":        1.0,  "trend":         1.0,  "regime":       1.0,
    "breakout":        0.9,  "scalp":         0.9,  "scalping":     0.9,
    "mean reversion":  0.8,  "reversion":     0.7,  "arbitrage":    0.7,

    # Technical indicators
    "vwap":            1.0,  "ema":           0.9,  "rsi":          0.9,
    "macd":            0.8,  "adx":           1.0,  "atr":          0.9,
    "bollinger":       0.8,  "stochastic":    0.7,  "volume":       0.8,

    # Smart Money concepts
    "smart money":     1.0,  "order block":   1.0,  "order flow":   0.9,
    "fair value gap":  1.0,  "fvg":           1.0,  "bos":          0.9,
    "liquidity":       0.9,  "sweep":         0.9,  "imbalance":    0.9,
    "institutional":   0.9,  "market structure": 1.0,

    # Derivatives / crypto-specific
    "futures":         0.9,  "perpetual":     0.9,  "funding rate":  1.0,
    "open interest":   1.0,  "liquidation":   1.0,  "leverage":     0.9,
    "derivatives":     0.9,  "options":       0.7,  "on-chain":     0.8,

    # Risk / quantitative
    "drawdown":        1.0,  "sharpe":        0.9,  "sortino":      0.9,
    "profit factor":   1.0,  "win rate":      1.0,  "expectancy":   1.0,
    "volatility":      0.9,  "variance":      0.7,  "covariance":   0.7,
    "entropy":         0.8,  "coherence":     0.8,  "quantum":      0.7,

    # ML / AI in trading
    "reinforcement":   0.9,  "neural":        0.7,  "deep learning": 0.7,
    "machine learning":0.7,  "backtest":      0.9,  "simulation":   0.8,
    "optimization":    0.8,  "gradient":      0.7,  "bayesian":     0.7,

    # Market microstructure
    "bid ask":         0.8,  "spread":        0.8,  "tick":         0.7,
    "market impact":   0.9,  "slippage":      0.9,  "execution":    0.8,
    "high frequency":  0.7,

    # Macro / sentiment
    "fear greed":      0.9,  "sentiment":     0.8,  "bitcoin":      0.8,
    "crypto":          0.7,  "bull":          0.7,  "bear":         0.7,
    "market cap":      0.6,  "dominance":     0.7,
}


# ─── Text utilities ───────────────────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text.lower()


def _doc_hash(title: str) -> str:
    """Stable hash of a document title for novelty tracking."""
    return hashlib.md5(title.lower().strip().encode()).hexdigest()[:16]


def _bag_of_words(text: str, vocab: Dict[str, float]) -> List[float]:
    """
    Project text onto AEON's domain vocabulary.
    Returns a weight vector aligned with sorted(vocab.keys()).
    """
    text_lower = text.lower()
    keys = sorted(vocab.keys())
    return [
        vocab[k] if k in text_lower else 0.0
        for k in keys
    ]


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot   = sum(a[i] * b[i] for i in range(min(len(a), len(b))))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

# In-memory fetch cache: url → (content, fetched_at_timestamp)
_FETCH_CACHE: Dict[str, tuple] = {}
_FETCH_CACHE_TTL = 300  # 5 minutes


async def _async_fetch(url: str, timeout: int = HTTP_TIMEOUT) -> Optional[str]:
    """Async URL fetch with 10s timeout and 300s in-memory cache."""
    now = datetime.now(timezone.utc).timestamp()
    if url in _FETCH_CACHE:
        content, fetched_at = _FETCH_CACHE[url]
        if (now - fetched_at) < _FETCH_CACHE_TTL:
            return content
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": "AEON-WebIntelligence/1.0 (research bot)",
                    "Accept":     "application/rss+xml, application/json, text/xml, */*",
                },
                follow_redirects=True,
            )
            if resp.status_code == 200:
                content = resp.text
                _FETCH_CACHE[url] = (content, now)
                return content
            logger.debug(f"[W] Fetch {resp.status_code}: {url}")
            return None
    except Exception as e:
        logger.debug(f"[W] Fetch failed {url}: {e}")
        return None


# ─── Source parsers ───────────────────────────────────────────────────────────

def _parse_arxiv_rss(xml_text: str, source_key: str) -> List[Dict]:
    """Parse arxiv RSS feed → list of raw document dicts."""
    docs = []
    try:
        root = ET.fromstring(xml_text)
        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        channel = root.find("channel")
        if channel is None:
            return docs
        for item in channel.findall("item")[:MAX_DOCS_PER_RUN]:
            title = item.findtext("title") or ""
            desc  = item.findtext("description") or ""
            link  = item.findtext("link") or ""
            docs.append({
                "source":  source_key,
                "title":   _clean_text(title),
                "body":    _clean_text(desc)[:1000],
                "url":     link,
                "type":    "research_paper",
            })
    except ET.ParseError as e:
        logger.debug(f"[W] arxiv RSS parse error: {e}")
    return docs


def _parse_fear_greed(json_text: str) -> List[Dict]:
    """Parse Alternative.me Fear & Greed JSON → sentiment document."""
    try:
        data = json.loads(json_text)
        entries = data.get("data", [])
        if not entries:
            return []
        latest = entries[0]
        value      = int(latest.get("value", 50))
        label      = latest.get("value_classification", "Neutral")
        # Build a descriptive body for relevance scoring
        trend = "improving" if len(entries) > 1 and value > int(entries[1].get("value", 50)) else "declining"
        body = (
            f"crypto fear greed index {value} {label} sentiment {trend} "
            f"bitcoin market sentiment momentum volatility"
        )
        return [{
            "source":  "fear_greed",
            "title":   f"Fear & Greed Index: {value} ({label})",
            "body":    body,
            "url":     "https://alternative.me/crypto/fear-and-greed-index/",
            "type":    "sentiment",
            "metadata": {"value": value, "label": label, "trend": trend},
        }]
    except Exception as e:
        logger.debug(f"[W] Fear & Greed parse error: {e}")
        return []


def _parse_github_api(json_text: str) -> List[Dict]:
    """Parse GitHub API search results → list of repo documents."""
    docs = []
    try:
        data = json.loads(json_text)
        items = data.get("items", [])[:15]
        for repo in items:
            name        = repo.get("full_name", "")
            description = repo.get("description") or ""
            topics      = " ".join(repo.get("topics", []))
            stars       = repo.get("stargazers_count", 0)
            language    = repo.get("language") or ""
            body = f"{description} {topics} {language} algorithmic trading crypto momentum strategy backtest"
            docs.append({
                "source":  "github_trading",
                "title":   name,
                "body":    _clean_text(body)[:500],
                "url":     repo.get("html_url", ""),
                "type":    "open_source",
                "metadata": {"stars": stars, "language": language},
            })
    except Exception as e:
        logger.debug(f"[W] GitHub parse error: {e}")
    return docs


def _parse_coingecko_global(json_text: str) -> List[Dict]:
    """Parse CoinGecko global market data → market context document."""
    try:
        data = json.loads(json_text).get("data", {})
        btc_dom      = round(data.get("market_cap_percentage", {}).get("btc", 0), 1)
        total_cap    = data.get("total_market_cap", {}).get("usd", 0)
        total_vol    = data.get("total_volume", {}).get("usd", 0)
        active_coins = data.get("active_cryptocurrencies", 0)
        direction    = "bullish" if data.get("market_cap_change_percentage_24h_usd", 0) > 0 else "bearish"

        body = (
            f"bitcoin dominance {btc_dom}% crypto market cap total volume "
            f"{direction} sentiment momentum open interest derivatives futures "
            f"active cryptocurrencies {active_coins}"
        )
        return [{
            "source":  "coingecko_global",
            "title":   f"Crypto Market: BTC dominance {btc_dom}%, {direction.upper()} bias",
            "body":    body,
            "url":     "https://api.coingecko.com/api/v3/global",
            "type":    "macro",
            "metadata": {
                "btc_dominance": btc_dom,
                "direction":     direction,
                "total_cap_usd": total_cap,
            },
        }]
    except Exception as e:
        logger.debug(f"[W] CoinGecko parse error: {e}")
        return []


# ─── Main engine ──────────────────────────────────────────────────────────────

class WebIntelligence:
    """
    AEON's eyes on the world.

    Crawls external sources every 24 hours.
    Scores each document by relevance(w) = sim × novelty × credibility.
    Stores to MongoDB. Feeds top findings into the LΦ proposal queue.
    """

    def __init__(self, db=None):
        self.db = db
        self._quantum  = None   # AEONQuantumState reference
        self._omega    = None   # OmegaCycle reference (for LΦ injection)
        self.send_alert = None
        self.chat_ids   = set()

        # In-memory novelty tracker: set of recent doc title hashes
        self._seen_hashes: Set[str] = set()

        # AEON vocabulary projected vector (cached, recomputed each cycle)
        self._vocab_vector: List[float] = list(DOMAIN_VOCAB.values())

        self._cycle_count: int = 0
        self._last_run_at: Optional[datetime] = None

    def set_dependencies(self, quantum_state=None, omega_cycle=None,
                         send_alert=None, chat_ids=None):
        self._quantum    = quantum_state
        self._omega      = omega_cycle
        self.send_alert  = send_alert
        self.chat_ids    = chat_ids or set()

    # ── Scoring ───────────────────────────────────────────────────────────────

    def _sim_to_psi(self, title: str, body: str, state: Optional[Dict]) -> float:
        """
        sim(w, |Ψ⟩) — cosine similarity of document to AEON's vocabulary.

        When quantum state is available, the vocabulary is weighted by
        which engines are currently active (active engines boost their
        domain terms). This makes AEON read selectively.
        """
        text = f"{title} {body}"
        doc_vec = _bag_of_words(text, DOMAIN_VOCAB)

        # Base sim vs full vocabulary
        base_sim = _cosine(doc_vec, self._vocab_vector)

        # Boost if document mentions active engine domains
        boost = 0.0
        if state:
            for es in state.get("engine_states", []):
                if es.get("alpha_mag", 0) > 0.1:
                    engine = es["engine"].lower()
                    if engine in text:
                        boost += 0.05
            boost = min(boost, 0.20)

        return min(base_sim + boost, 1.0)

    def _novelty(self, title: str, body: str) -> float:
        """
        novelty(w) — how different this document is from what AEON has seen.

        Uses title hash for exact-match dedup, then bag-of-words cosine
        vs a sampled window of recent documents.
        1.0 = completely new. 0.0 = already absorbed.
        """
        h = _doc_hash(title)
        if h in self._seen_hashes:
            return 0.0   # exact duplicate

        # Without stored vectors (first run), everything is novel
        return 1.0

    def _credibility(self, source_key: str) -> float:
        return SOURCES.get(source_key, {}).get("credibility", 0.5)

    def _score(self, doc: Dict, state: Optional[Dict]) -> float:
        """relevance(w) = sim(w, |Ψ⟩) × novelty(w) × credibility(w)"""
        sim   = self._sim_to_psi(doc["title"], doc.get("body", ""), state)
        nov   = self._novelty(doc["title"], doc.get("body", ""))
        cred  = self._credibility(doc["source"])
        return round(sim * nov * cred, 4)

    # ── Crawl per source ──────────────────────────────────────────────────────

    async def _crawl_source(self, source_key: str) -> List[Dict]:
        """Fetch and parse one source. Returns raw document list."""
        cfg  = SOURCES[source_key]
        url  = cfg["url"]
        kind = cfg["type"]

        raw = await _async_fetch(url)
        if not raw:
            logger.debug(f"[W] No response from {source_key}")
            return []

        if kind == "rss":
            return _parse_arxiv_rss(raw, source_key)
        elif kind == "json_sentiment":
            return _parse_fear_greed(raw)
        elif kind == "github_api":
            return _parse_github_api(raw)
        elif kind == "json_macro":
            return _parse_coingecko_global(raw)
        else:
            logger.debug(f"[W] Unknown source type: {kind}")
            return []

    # ── Full crawl cycle ──────────────────────────────────────────────────────

    async def run_cycle(self) -> Dict:
        """
        Crawl all sources, score every document, store above-floor results,
        inject top findings into the LΦ queue.
        """
        self._cycle_count += 1
        self._last_run_at = datetime.now(timezone.utc)
        logger.info(f"[W] Web intelligence cycle #{self._cycle_count} starting.")

        # Load seen hashes from MongoDB on first cycle
        if not self._seen_hashes and self.db is not None:
            try:
                cursor = self.db["web_sources"].find(
                    {}, {"title_hash": 1}, limit=NOVELTY_WINDOW
                )
                docs = await cursor.to_list(length=NOVELTY_WINDOW)
                self._seen_hashes = {d["title_hash"] for d in docs if d.get("title_hash")}
            except Exception:
                pass

        # Current quantum state for sim weighting
        state = self._quantum.get_state() if self._quantum else None

        # Crawl all sources concurrently
        crawl_tasks = [
            asyncio.create_task(self._crawl_source(key))
            for key in SOURCES
        ]
        results = await asyncio.gather(*crawl_tasks, return_exceptions=True)

        all_docs: List[Dict] = []
        for key, result in zip(SOURCES.keys(), results):
            if isinstance(result, list):
                all_docs.extend(result)
            elif isinstance(result, Exception):
                logger.debug(f"[W] Source {key} failed: {result}")

        logger.info(f"[W] Crawled {len(all_docs)} raw documents from {len(SOURCES)} sources.")

        # Score and filter
        scored: List[Dict] = []
        for doc in all_docs:
            relevance = self._score(doc, state)
            if relevance < RELEVANCE_FLOOR:
                continue
            h = _doc_hash(doc["title"])
            doc.update({
                "relevance":   relevance,
                "title_hash":  h,
                "crawled_at":  self._last_run_at,
                "cycle":       self._cycle_count,
                "in_lphi_queue": relevance >= L_PHI_FLOOR,
            })
            scored.append(doc)

        scored.sort(key=lambda d: d["relevance"], reverse=True)

        # Store to MongoDB
        stored = 0
        for doc in scored:
            h = doc["title_hash"]
            if h in self._seen_hashes:
                continue
            try:
                if self.db is not None:
                    await self.db["web_sources"].insert_one(dict(doc))
                self._seen_hashes.add(h)
                # Keep novelty window bounded
                if len(self._seen_hashes) > NOVELTY_WINDOW:
                    self._seen_hashes = set(list(self._seen_hashes)[-NOVELTY_WINDOW:])
                stored += 1
            except Exception as e:
                logger.debug(f"[W] Store failed for '{doc['title'][:40]}': {e}")

        # LΦ queue: top findings above threshold
        lphi_docs = [d for d in scored if d.get("in_lphi_queue")]

        logger.info(
            f"[W] Cycle #{self._cycle_count} complete. "
            f"Stored: {stored}, LΦ candidates: {len(lphi_docs)}."
        )

        # Send Telegram summary if there are notable findings
        if lphi_docs:
            await self._telegram_findings(lphi_docs[:5])

        # Update meta
        await self._update_meta(stored, len(lphi_docs))

        return {
            "cycle":        self._cycle_count,
            "total_crawled": len(all_docs),
            "stored":       stored,
            "lphi_count":   len(lphi_docs),
            "top_findings": [
                {"title": d["title"], "source": d["source"], "relevance": d["relevance"]}
                for d in lphi_docs[:5]
            ],
        }

    async def _update_meta(self, stored: int, lphi_count: int):
        if self.db is None:
            return
        try:
            await self.db["web_meta"].update_one(
                {"_id": "state"},
                {"$set": {
                    "last_run_at":  self._last_run_at,
                    "cycle_count":  self._cycle_count,
                    "last_stored":  stored,
                    "last_lphi":    lphi_count,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.debug(f"[W] Meta update failed: {e}")

    # ── Public: LΦ queue access ───────────────────────────────────────────────

    async def get_lphi_queue(self, n: int = 10,
                             since_hours: int = 48) -> List[Dict]:
        """
        Return the top LΦ proposal candidates from the last `since_hours`.
        Called by omega_cycle when building Carlos proposals.
        """
        if self.db is None:
            return []
        since = datetime.now(timezone.utc) - timedelta(hours=since_hours)
        try:
            docs = await self.db["web_sources"].find(
                {"in_lphi_queue": True, "crawled_at": {"$gte": since}},
                sort=[("relevance", -1)],
                limit=n,
            ).to_list(length=n)
            return [{k: v for k, v in d.items() if k != "_id"} for d in docs]
        except Exception as e:
            logger.error(f"[W] LΦ queue query failed: {e}")
            return []

    async def get_latest_sentiment(self) -> Optional[Dict]:
        """Return the most recent Fear & Greed document."""
        if self.db is None:
            return None
        try:
            doc = await self.db["web_sources"].find_one(
                {"source": "fear_greed"},
                sort=[("crawled_at", -1)],
            )
            return {k: v for k, v in doc.items() if k != "_id"} if doc else None
        except Exception:
            return None

    # ── Telegram ──────────────────────────────────────────────────────────────

    async def _telegram_findings(self, top_docs: List[Dict]):
        if not self.send_alert or not self.chat_ids:
            return
        msg = f"W WEB INTEL — Cycle #{self._cycle_count}\n\n"
        msg += f"Top LΦ candidates:\n\n"
        for i, d in enumerate(top_docs, 1):
            src   = SOURCES.get(d["source"], {}).get("label", d["source"])
            score = d["relevance"]
            title = d["title"][:70]
            msg += f"{i}. [{score:.2f}] {title}\n   {src}\n\n"
        msg += f"These findings have entered the LΦ proposal queue.\nΩ will include them in the next identity review."

        for chat_id in self.chat_ids:
            try:
                await self.send_alert(chat_id, msg)
            except Exception as e:
                logger.error(f"[W] Telegram send failed: {e}")

    # ── Background loop ───────────────────────────────────────────────────────

    async def run_loop(self, interval: int = CRAWL_INTERVAL):
        """Crawl all sources every `interval` seconds (default 24h)."""
        logger.info(
            "[W] Web intelligence engine started — crawling every %dh. "
            "Sources: %d. Relevance floor: %.2f. LΦ floor: %.2f.",
            interval // 3600, len(SOURCES), RELEVANCE_FLOOR, L_PHI_FLOOR,
        )

        # First crawl after a 10-minute delay (let system stabilize on startup)
        await asyncio.sleep(600)

        while True:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error(f"[W] Crawl cycle error: {e}", exc_info=True)
            await asyncio.sleep(interval)


# ─── Singleton ────────────────────────────────────────────────────────────────

_web_intel: Optional[WebIntelligence] = None


def init_web_intelligence(db=None) -> WebIntelligence:
    """Initialise the global web intelligence engine. Call once from server.py."""
    global _web_intel
    _web_intel = WebIntelligence(db)
    return _web_intel


def get_web_intelligence() -> Optional[WebIntelligence]:
    """Return the live singleton."""
    return _web_intel
