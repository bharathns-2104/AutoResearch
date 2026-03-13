"""
search_engine.py  —  Phase 1c update: intent-routed search with Wikipedia API

Changes vs original:
  - intent_router() classifies each query into one of four intents:
      COMPETITOR  → DuckDuckGo News (freshest company/product mentions)
      MARKET_SIZE → Wikipedia API   (encyclopaedic market size / CAGR data)
      FINANCIAL   → DuckDuckGo general search
      GENERAL     → DuckDuckGo general search (fallback)
  - search() delegates to the correct backend based on the routed intent.
  - wikipedia_search() hits the Wikipedia REST API (zero cost, no key needed).
  - Results are capped at 5-7 URLs per query and deduplicated by domain.
  - All original DuckDuckGo behaviour is preserved as the default fallback.
  - Requires `wikipedia-api` in requirements.txt:
      wikipedia-api>=0.6.0
"""

from __future__ import annotations

import re
import time
import random
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse, quote_plus
from dataclasses import dataclass, field

import requests

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────

MAX_RESULTS_PER_QUERY  = 7
MIN_RESULTS_PER_QUERY  = 3
DOMAIN_DEDUP           = True          # one URL per root domain
WIKIPEDIA_API_URL      = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_REST_URL     = "https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
DDGS_NEWS_MAX_RESULTS  = 7
DDGS_GENERAL_MAX       = 7
REQUEST_TIMEOUT        = 10            # seconds
RATE_LIMIT_DELAY       = (0.5, 1.5)   # random sleep range between requests

# ── Intent taxonomy ────────────────────────────────────────────────────────

INTENT_COMPETITOR  = "COMPETITOR"
INTENT_MARKET_SIZE = "MARKET_SIZE"
INTENT_FINANCIAL   = "FINANCIAL"
INTENT_GENERAL     = "GENERAL"

_COMPETITOR_SIGNALS = [
    "competitor", "competition", "rival", "alternative", "vs ", "versus",
    "company", "startup", "player", "vendor", "provider", "landscape",
    "market leader", "incumbent",
]
_MARKET_SIGNALS = [
    "market size", "tam ", "total addressable", "cagr", "growth rate",
    "market share", "industry size", "market value", "addressable market",
    "forecast", "projection", "billion", "trillion", "market report",
]
_FINANCIAL_SIGNALS = [
    "funding", "revenue", "investment", "valuation", "cost", "budget",
    "burn rate", "runway", "series a", "series b", "seed round", "ipo",
    "profit", "margin", "earnings", "startup cost", "operating cost",
]


@dataclass
class SearchResult:
    url:     str
    title:   str
    snippet: str
    source:  str   # "duckduckgo_news" | "duckduckgo_general" | "wikipedia"
    intent:  str   # routed intent


@dataclass
class SearchEngineConfig:
    max_results:      int  = MAX_RESULTS_PER_QUERY
    domain_dedup:     bool = DOMAIN_DEDUP
    rate_limit_delay: tuple = field(default_factory=lambda: RATE_LIMIT_DELAY)
    wikipedia_lang:   str  = "en"
    ddgs_region:      str  = "wt-wt"
    enable_news:      bool = True
    enable_wikipedia: bool = True


class SearchEngine:
    """
    Intent-routed search engine.

    Usage:
        engine  = SearchEngine()
        results = engine.search("AI automation market size CAGR")
        urls    = [r.url for r in results]
    """

    def __init__(self, config: SearchEngineConfig | None = None):
        self.config = config or SearchEngineConfig()

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC API
    # ═══════════════════════════════════════════════════════════════════════

    def search(
        self,
        query:  str,
        intent: str | None = None,
        *,
        max_results: int | None = None,
    ) -> List[SearchResult]:
        """
        Route a query to the appropriate backend and return deduplicated results.

        Args:
            query:       Free-text search query.
            intent:      Override auto-detected intent (optional).
            max_results: Override config.max_results (optional).

        Returns:
            List of SearchResult objects, capped and deduplicated by domain.
        """
        cap     = max_results or self.config.max_results
        routed  = intent or self.intent_router(query)
        logger.info(f"SearchEngine: query='{query[:60]}' intent={routed}")

        if routed == INTENT_MARKET_SIZE and self.config.enable_wikipedia:
            results = self._wikipedia_search(query, cap)
            # Supplement sparse Wikipedia results with DuckDuckGo
            if len(results) < MIN_RESULTS_PER_QUERY:
                ddg = self._ddg_general_search(query, cap - len(results))
                results.extend(ddg)
        elif routed == INTENT_COMPETITOR and self.config.enable_news:
            results = self._ddg_news_search(query, cap)
            if len(results) < MIN_RESULTS_PER_QUERY:
                ddg = self._ddg_general_search(query, cap - len(results))
                results.extend(ddg)
        else:
            results = self._ddg_general_search(query, cap)

        if self.config.domain_dedup:
            results = self._dedup_by_domain(results)

        return results[:cap]

    def search_batch(
        self,
        queries: List[str],
        *,
        max_results_each: int | None = None,
    ) -> Dict[str, List[SearchResult]]:
        """
        Search multiple queries sequentially with rate limiting.
        Returns a dict mapping query → results.
        """
        output: Dict[str, List[SearchResult]] = {}
        for i, query in enumerate(queries):
            if i > 0:
                time.sleep(random.uniform(*self.config.rate_limit_delay))
            output[query] = self.search(query, max_results=max_results_each)
        return output

    # ═══════════════════════════════════════════════════════════════════════
    # INTENT ROUTER
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def intent_router(query: str) -> str:
        """
        Classify a search query into one of four intents.

        Priority order:
          1. MARKET_SIZE  — TAM / CAGR / market forecast queries
          2. COMPETITOR   — company / competitor / landscape queries
          3. FINANCIAL    — funding / cost / revenue queries
          4. GENERAL      — catch-all fallback

        This is intentionally kept as a lightweight keyword heuristic
        (no LLM call) to avoid latency on every search.
        """
        q = query.lower()

        market_score     = sum(1 for kw in _MARKET_SIGNALS     if kw in q)
        competitor_score = sum(1 for kw in _COMPETITOR_SIGNALS if kw in q)
        financial_score  = sum(1 for kw in _FINANCIAL_SIGNALS  if kw in q)

        scores = {
            INTENT_MARKET_SIZE: market_score,
            INTENT_COMPETITOR:  competitor_score,
            INTENT_FINANCIAL:   financial_score,
        }
        best_intent = max(scores, key=scores.get)
        if scores[best_intent] == 0:
            return INTENT_GENERAL
        return best_intent

    # ═══════════════════════════════════════════════════════════════════════
    # WIKIPEDIA API BACKEND
    # ═══════════════════════════════════════════════════════════════════════

    def _wikipedia_search(
        self,
        query:       str,
        max_results: int,
    ) -> List[SearchResult]:
        """
        Query the Wikipedia Search API, then fetch page summaries.

        Steps:
          1. Use the `opensearch` action to find matching page titles.
          2. Fetch the REST summary for each title (intro paragraph + URL).
          3. Return structured SearchResult objects.

        No API key required — rate limits are handled by RATE_LIMIT_DELAY.
        """
        titles = self._wiki_opensearch(query, max_results)
        results: List[SearchResult] = []

        for title in titles:
            summary = self._wiki_page_summary(title)
            if summary:
                results.append(SearchResult(
                    url     = summary["url"],
                    title   = summary["title"],
                    snippet = summary["extract"][:300],
                    source  = "wikipedia",
                    intent  = INTENT_MARKET_SIZE,
                ))
            if len(results) >= max_results:
                break

        logger.info(f"Wikipedia search '{query[:50]}' → {len(results)} results")
        return results

    def _wiki_opensearch(self, query: str, limit: int) -> List[str]:
        """
        Call Wikipedia's OpenSearch API to get matching page titles.
        Returns a list of title strings.
        """
        params = {
            "action":   "opensearch",
            "search":   query,
            "limit":    min(limit, 10),
            "namespace": 0,
            "format":   "json",
        }
        try:
            resp = requests.get(
                WIKIPEDIA_API_URL,
                params  = params,
                timeout = REQUEST_TIMEOUT,
                headers = {"User-Agent": "AutoResearch/2.0 (educational research tool)"},
            )
            resp.raise_for_status()
            data = resp.json()
            # OpenSearch returns [query, [titles], [descriptions], [urls]]
            return data[1] if len(data) > 1 else []
        except Exception as exc:
            logger.warning(f"Wikipedia OpenSearch failed for '{query}': {exc}")
            return []

    def _wiki_page_summary(self, title: str) -> Optional[Dict[str, str]]:
        """
        Fetch a Wikipedia page summary via the REST summary endpoint.
        Returns dict with 'title', 'extract', 'url' or None on failure.
        """
        encoded = quote_plus(title.replace(" ", "_"))
        url     = WIKIPEDIA_REST_URL.format(title=encoded)
        try:
            resp = requests.get(
                url,
                timeout = REQUEST_TIMEOUT,
                headers = {"User-Agent": "AutoResearch/2.0 (educational research tool)"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "title":   data.get("title",         title),
                "extract": data.get("extract",       ""),
                "url":     data.get("content_urls",  {})
                               .get("desktop",       {})
                               .get("page",          f"https://en.wikipedia.org/wiki/{encoded}"),
            }
        except Exception as exc:
            logger.warning(f"Wikipedia REST summary failed for '{title}': {exc}")
            return None

    def wikipedia_search(
        self,
        query:       str,
        max_results: int = 5,
    ) -> List[SearchResult]:
        """
        Public alias for _wikipedia_search() — callable directly from agents
        that want Wikipedia results regardless of auto-routed intent.
        """
        return self._wikipedia_search(query, max_results)

    # ═══════════════════════════════════════════════════════════════════════
    # DUCKDUCKGO BACKENDS
    # ═══════════════════════════════════════════════════════════════════════

    def _ddg_news_search(
        self,
        query:       str,
        max_results: int,
    ) -> List[SearchResult]:
        """
        DuckDuckGo News search — best for fresh competitor/company mentions.
        Falls back to general search if duckduckgo_search not installed.
        """
        try:
            from duckduckgo_search import DDGS
            results: List[SearchResult] = []
            with DDGS() as ddgs:
                for item in ddgs.news(
                    query,
                    region   = self.config.ddgs_region,
                    max_results = min(max_results, DDGS_NEWS_MAX_RESULTS),
                ):
                    results.append(SearchResult(
                        url     = item.get("url",  ""),
                        title   = item.get("title",  ""),
                        snippet = item.get("body",   "")[:300],
                        source  = "duckduckgo_news",
                        intent  = INTENT_COMPETITOR,
                    ))
            logger.info(f"DDG News '{query[:50]}' → {len(results)} results")
            return results
        except Exception as exc:
            logger.warning(f"DDG News search failed: {exc} — falling back to general")
            return self._ddg_general_search(query, max_results)

    def _ddg_general_search(
        self,
        query:       str,
        max_results: int,
    ) -> List[SearchResult]:
        """
        DuckDuckGo general web search — existing behaviour, unchanged.
        """
        try:
            from duckduckgo_search import DDGS
            results: List[SearchResult] = []
            with DDGS() as ddgs:
                for item in ddgs.text(
                    query,
                    region      = self.config.ddgs_region,
                    max_results = min(max_results, DDGS_GENERAL_MAX),
                ):
                    results.append(SearchResult(
                        url     = item.get("href",  ""),
                        title   = item.get("title", ""),
                        snippet = item.get("body",  "")[:300],
                        source  = "duckduckgo_general",
                        intent  = INTENT_GENERAL,
                    ))
            logger.info(f"DDG General '{query[:50]}' → {len(results)} results")
            return results
        except Exception as exc:
            logger.warning(f"DDG General search failed: {exc}")
            return []

    # ═══════════════════════════════════════════════════════════════════════
    # DEDUPLICATION
    # ═══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _dedup_by_domain(results: List[SearchResult]) -> List[SearchResult]:
        """
        Keep only the first result per root domain.
        e.g.  news.bbc.com  and  bbc.com/sport  → only the first is kept.
        """
        seen_domains: set = set()
        deduped: List[SearchResult] = []
        for r in results:
            try:
                domain = ".".join(urlparse(r.url).netloc.split(".")[-2:])
            except Exception:
                domain = r.url
            if domain not in seen_domains:
                seen_domains.add(domain)
                deduped.append(r)
        return deduped

    # ═══════════════════════════════════════════════════════════════════════
    # CONVENIENCE: URLs only (drop-in for original interface)
    # ═══════════════════════════════════════════════════════════════════════

    def get_urls(
        self,
        query:       str,
        max_results: int | None = None,
    ) -> List[str]:
        """
        Backwards-compatible method that returns a plain list of URLs.
        Existing callers using search_engine.get_urls() need no changes.
        """
        results = self.search(query, max_results=max_results)
        return [r.url for r in results if r.url]