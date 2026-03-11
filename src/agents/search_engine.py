"""
search_engine.py  —  Phase 1c update: Intelligent Search Routing

New: IntentRouter class
  Classifies each query into one of five intents and maps it to the
  optimal DuckDuckGo search configuration:

    Intent          | timelimit | backend | site-restrict examples
    ──────────────────────────────────────────────────────────────
    MARKET_SIZE     | y (year)  | text    | statista, grandviewresearch
    CURRENT_EVENTS  | w (week)  | news    | reuters, bloomberg, techcrunch
    COMPETITOR      | m (month) | text    | crunchbase, pitchbook
    FUNDING         | m         | text    | crunchbase, techcrunch
    GENERAL         | None      | text    | (no restriction)

The router uses the LLM when available; falls back to keyword matching
rules when the LLM is unreachable.  Either way, search() itself is
unchanged at the call-site — it simply gets smarter queries internally.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any

from ddgs import DDGS

from src.config.settings import LLM_SETTINGS
from src.orchestration.logger import setup_logger
from src.orchestration.state_manager import StateManager, SystemState

logger = setup_logger()


# ═══════════════════════════════════════════════════════════════════════════
# Intent taxonomy
# ═══════════════════════════════════════════════════════════════════════════

class QueryIntent(str, Enum):
    MARKET_SIZE    = "MARKET_SIZE"     # TAM, market valuation, industry size
    CURRENT_EVENTS = "CURRENT_EVENTS"  # news, quarterly earnings, recent launches
    COMPETITOR     = "COMPETITOR"      # company profiles, comparisons, landscape
    FUNDING        = "FUNDING"         # investment rounds, VCs, fundraising
    GENERAL        = "GENERAL"         # catch-all / informational


@dataclass
class SearchConfig:
    """Parameters passed to each DuckDuckGo call."""
    query:      str
    intent:     QueryIntent             = QueryIntent.GENERAL
    timelimit:  str | None              = None   # "d", "w", "m", "y"
    backend:    str                     = "text" # "text" | "news"
    site_hints: List[str]               = field(default_factory=list)
    max_results: int                    = 5


# ── LLM classification prompt ─────────────────────────────────────────────

_INTENT_SYSTEM = """You are a search-query intent classifier.
Given a search query, return ONLY a JSON object with:
{
  "intent": one of "MARKET_SIZE" | "CURRENT_EVENTS" | "COMPETITOR" | "FUNDING" | "GENERAL",
  "rationale": "one short sentence"
}

Intent definitions:
  MARKET_SIZE    — queries about industry/market size, TAM, CAGR, valuations
  CURRENT_EVENTS — queries about recent news, earnings, product launches, quarterly reports
  COMPETITOR     — queries about specific companies, competitor comparisons, market landscape
  FUNDING        — queries about fundraising rounds, venture capital, investors
  GENERAL        — everything else
"""

_INTENT_USER = "Classify this search query: {query}"


# ── Keyword-based fallback classifier ─────────────────────────────────────

_INTENT_KEYWORDS: Dict[QueryIntent, List[str]] = {
    QueryIntent.MARKET_SIZE: [
        "market size", "market cap", "tam", "cagr", "valuation",
        "industry size", "addressable market", "market share",
        "growth rate", "forecast", "billion", "trillion",
    ],
    QueryIntent.CURRENT_EVENTS: [
        "latest", "recent", "news", "today", "quarterly", "earnings",
        "launch", "announce", "2025", "2026", "this week", "just",
    ],
    QueryIntent.COMPETITOR: [
        "competitor", "vs ", "alternative", "landscape", "players",
        "top companies", "startup", "companies in", "market leader",
        "crunchbase", "pitchbook",
    ],
    QueryIntent.FUNDING: [
        "funding", "series a", "series b", "seed", "raised", "investor",
        "venture", "vc", "round", "investment",
    ],
}

# ── Source-routing table ───────────────────────────────────────────────────

_INTENT_CONFIG: Dict[QueryIntent, Dict[str, Any]] = {
    QueryIntent.MARKET_SIZE: {
        "timelimit":  "y",
        "backend":    "text",
        "site_hints": [
            "site:statista.com",
            "site:grandviewresearch.com",
            "site:mordorintelligence.com",
            "site:marketsandmarkets.com",
        ],
    },
    QueryIntent.CURRENT_EVENTS: {
        "timelimit":  "w",
        "backend":    "news",
        "site_hints": [
            "site:reuters.com",
            "site:bloomberg.com",
            "site:techcrunch.com",
            "site:businesswire.com",
        ],
    },
    QueryIntent.COMPETITOR: {
        "timelimit":  "m",
        "backend":    "text",
        "site_hints": [
            "site:crunchbase.com",
            "site:pitchbook.com",
            "site:g2.com",
        ],
    },
    QueryIntent.FUNDING: {
        "timelimit":  "m",
        "backend":    "text",
        "site_hints": [
            "site:crunchbase.com",
            "site:techcrunch.com",
            "site:venturebeat.com",
        ],
    },
    QueryIntent.GENERAL: {
        "timelimit":  None,
        "backend":    "text",
        "site_hints": [],
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# IntentRouter
# ═══════════════════════════════════════════════════════════════════════════

class IntentRouter:
    """
    Classifies a query into a QueryIntent and returns a SearchConfig that
    optimises the DuckDuckGo call for that intent.
    """

    def __init__(self, max_results: int = 5):
        self._max_results  = max_results
        self._use_llm      = LLM_SETTINGS.get("enable_smart_routing", True)

    def build_config(self, query: str) -> SearchConfig:
        """Classify query and return the optimised SearchConfig."""
        intent = self._classify(query)
        cfg    = _INTENT_CONFIG[intent]
        return SearchConfig(
            query       = query,
            intent      = intent,
            timelimit   = cfg["timelimit"],
            backend     = cfg["backend"],
            site_hints  = cfg["site_hints"],
            max_results = self._max_results,
        )

    # ── classification ────────────────────────────────────────────────────

    def _classify(self, query: str) -> QueryIntent:
        if self._use_llm:
            try:
                return self._classify_llm(query)
            except Exception as exc:
                logger.warning(
                    f"IntentRouter LLM classification failed: {exc}. "
                    "Using keyword fallback."
                )
        return self._classify_keywords(query)

    def _classify_llm(self, query: str) -> QueryIntent:
        from src.orchestration.llm_client import call_llm_json
        result = call_llm_json(
            _INTENT_SYSTEM,
            _INTENT_USER.format(query=query),
        )
        raw_intent = result.get("intent", "GENERAL").strip().upper()
        try:
            intent = QueryIntent(raw_intent)
            logger.info(
                f"IntentRouter: '{query[:60]}' → {intent.value} "
                f"[{result.get('rationale', '')}]"
            )
            return intent
        except ValueError:
            logger.warning(f"Unknown intent '{raw_intent}' — defaulting to GENERAL")
            return QueryIntent.GENERAL

    def _classify_keywords(self, query: str) -> QueryIntent:
        q_lower = query.lower()
        scores  = {intent: 0 for intent in QueryIntent}
        for intent, keywords in _INTENT_KEYWORDS.items():
            for kw in keywords:
                if kw in q_lower:
                    scores[intent] += 1
        best_intent = max(scores, key=scores.__getitem__)
        if scores[best_intent] == 0:
            return QueryIntent.GENERAL
        logger.info(
            f"IntentRouter (keyword): '{query[:60]}' → {best_intent.value} "
            f"(score={scores[best_intent]})"
        )
        return best_intent


# ═══════════════════════════════════════════════════════════════════════════
# SearchEngine  (Phase 1c update)
# ═══════════════════════════════════════════════════════════════════════════

class SearchEngine:

    def __init__(self, max_results_per_query: int = 5):
        self.state        = StateManager()
        self.max_results  = max_results_per_query
        self.router       = IntentRouter(max_results=max_results_per_query)
        logger.info("SearchEngine initialized with IntentRouter")

    # ── single query ─────────────────────────────────────────────────────

    def search_query(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute a single query, automatically routing to the best source.
        """
        cfg     = self.router.build_config(query)
        results = self._execute(cfg)
        ranked  = self.rank_results(results, query)
        logger.info(
            f"search_query: '{query[:60]}' "
            f"intent={cfg.intent.value} "
            f"backend={cfg.backend} "
            f"timelimit={cfg.timelimit} "
            f"→ {len(ranked)} results"
        )
        return ranked

    def _execute(self, cfg: SearchConfig) -> List[Dict[str, Any]]:
        """
        Run the actual DuckDuckGo call with intent-specific parameters.

        Site hints are tried one at a time (appended to query); if a
        site-restricted call returns no results we fall back to the
        open query so we never return nothing.
        """
        results: List[Dict[str, Any]] = []

        # Try the most specific site hint first
        if cfg.site_hints:
            primary_site = cfg.site_hints[0]
            routed_query = f"{cfg.query} {primary_site}"
            results = self._ddgs_call(
                routed_query,
                cfg.backend,
                cfg.timelimit,
                cfg.max_results,
            )
            if results:
                return results
            logger.info(
                f"Site-restricted call ({primary_site}) returned 0 results "
                "— falling back to open search"
            )

        # Fall back to open search (no site restriction, original query)
        return self._ddgs_call(
            cfg.query,
            cfg.backend,
            cfg.timelimit,
            cfg.max_results,
        )

    def _ddgs_call(
        self,
        query:      str,
        backend:    str,
        timelimit:  str | None,
        max_results: int,
    ) -> List[Dict[str, Any]]:
        """
        Thin wrapper around DDGS so the rest of the class never touches it directly.
        backend="news" uses ddgs.news(); backend="text" uses ddgs.text().
        """
        results: List[Dict[str, Any]] = []
        try:
            with DDGS() as ddgs:
                if backend == "news":
                    raw = ddgs.news(
                        query,
                        region     = "wt-wt",
                        safesearch = "moderate",
                        timelimit  = timelimit,
                        max_results = max_results,
                    )
                    for r in raw:
                        results.append({
                            "query":   query,
                            "title":   r.get("title"),
                            "url":     r.get("url"),
                            "snippet": r.get("body") or r.get("excerpt"),
                        })
                else:
                    ddgs_kwargs: Dict[str, Any] = {
                        "region":      "wt-wt",
                        "safesearch":  "moderate",
                        "max_results": max_results,
                    }
                    if timelimit:
                        ddgs_kwargs["timelimit"] = timelimit
                    raw = ddgs.text(query, **ddgs_kwargs)
                    for r in raw:
                        results.append({
                            "query":   query,
                            "title":   r.get("title"),
                            "url":     r.get("href"),
                            "snippet": r.get("body"),
                        })
        except Exception as exc:
            logger.error(f"DDGS call failed for '{query}': {exc}")
            self.state.add_error(f"Search error: {exc}")
        return results

    # ── ranking (unchanged logic) ─────────────────────────────────────────

    def rank_results(
        self,
        results: List[Dict[str, Any]],
        query:   str,
    ) -> List[Dict[str, Any]]:
        query_terms = set(query.lower().split())
        for item in results:
            text  = (item.get("title") or "") + " " + (item.get("snippet") or "")
            terms = set(text.lower().split())
            overlap     = query_terms.intersection(terms)
            item["score"] = round(len(overlap) / (len(query_terms) + 1), 3)
        return sorted(results, key=lambda x: x["score"], reverse=True)

    # ── full search (entry point for WorkflowController) ─────────────────

    def search(self, structured_input: Dict[str, Any]) -> List[Dict[str, Any]]:
        logger.info("SearchEngine.search() started")
        self.state.update_state(SystemState.SEARCHING)
        self.state.update_progress(30)

        all_results: List[Dict[str, Any]] = []
        for query in structured_input.get("search_queries", []):
            all_results.extend(self.search_query(query))

        logger.info(f"Total URLs collected: {len(all_results)}")
        self.state.add_data("search_results", all_results)
        return all_results