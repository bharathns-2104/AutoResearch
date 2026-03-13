"""
test_search_engine_phase1c.py
==============================
Tests for Phase 1c search_engine.py: intent router and Wikipedia API.

Run with:
    pytest tests/test_search_engine_phase1c.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch, call
from typing import List

from src.core.search_engine import (
    SearchEngine,
    SearchEngineConfig,
    SearchResult,
    INTENT_COMPETITOR,
    INTENT_MARKET_SIZE,
    INTENT_FINANCIAL,
    INTENT_GENERAL,
)


# ─────────────────────────────────────────────────────────────────────────────
# Intent Router
# ─────────────────────────────────────────────────────────────────────────────

class TestIntentRouter:

    @pytest.mark.parametrize("query,expected", [
        # Market signals
        ("AI automation market size CAGR 2026",         INTENT_MARKET_SIZE),
        ("legal tech total addressable market forecast", INTENT_MARKET_SIZE),
        ("SaaS market share billion dollar industry",    INTENT_MARKET_SIZE),
        ("TAM SAM SOM projection 2025",                 INTENT_MARKET_SIZE),
        # Competitor signals
        ("OpenAI competitors alternative LLM providers", INTENT_COMPETITOR),
        ("LegalTech startup landscape rival companies",  INTENT_COMPETITOR),
        ("who are the key players in AI document review",INTENT_COMPETITOR),
        # Financial signals
        ("Series A funding round AI startup 2025",       INTENT_FINANCIAL),
        ("startup cost budget burn rate runway",         INTENT_FINANCIAL),
        ("revenue model SaaS profit margin",             INTENT_FINANCIAL),
        # General fallback
        ("how does transformer attention work",          INTENT_GENERAL),
        ("python async best practices",                 INTENT_GENERAL),
    ])
    def test_intent_classification(self, query: str, expected: str):
        assert SearchEngine.intent_router(query) == expected

    def test_market_beats_general_on_tie(self):
        # "market" keyword → should not fall through to GENERAL
        result = SearchEngine.intent_router("industry market trends")
        assert result != INTENT_GENERAL

    def test_empty_query_returns_general(self):
        assert SearchEngine.intent_router("") == INTENT_GENERAL

    def test_single_word_returns_general(self):
        assert SearchEngine.intent_router("innovation") == INTENT_GENERAL


# ─────────────────────────────────────────────────────────────────────────────
# Wikipedia API backend
# ─────────────────────────────────────────────────────────────────────────────

_MOCK_OPENSEARCH = [
    "Artificial intelligence market",
    "Machine learning industry",
]

_MOCK_SUMMARY = {
    "title":   "Artificial intelligence market",
    "extract": "The global AI market was valued at $150 billion in 2023 and is projected to grow at a CAGR of 37% through 2030.",
    "content_urls": {
        "desktop": {
            "page": "https://en.wikipedia.org/wiki/Artificial_intelligence_market"
        }
    },
}


class TestWikipediaBackend:

    def _make_engine(self):
        return SearchEngine(SearchEngineConfig(enable_wikipedia=True))

    def test_wikipedia_search_returns_results(self):
        engine = self._make_engine()
        with patch.object(engine, "_wiki_opensearch", return_value=_MOCK_OPENSEARCH), \
             patch.object(engine, "_wiki_page_summary", return_value=_MOCK_SUMMARY):
            results = engine._wikipedia_search("AI market size", max_results=5)

        assert len(results) == len(_MOCK_OPENSEARCH)
        assert results[0].source == "wikipedia"
        assert results[0].intent == INTENT_MARKET_SIZE
        assert "150 billion" in results[0].snippet

    def test_wikipedia_public_alias(self):
        engine = self._make_engine()
        with patch.object(engine, "_wiki_opensearch", return_value=["AI market"]), \
             patch.object(engine, "_wiki_page_summary", return_value=_MOCK_SUMMARY):
            results = engine.wikipedia_search("AI market", max_results=3)
        assert isinstance(results, list)

    def test_opensearch_failure_returns_empty(self):
        engine = self._make_engine()
        with patch("requests.get", side_effect=ConnectionError("timeout")):
            titles = engine._wiki_opensearch("anything", limit=5)
        assert titles == []

    def test_page_summary_failure_returns_none(self):
        engine = self._make_engine()
        with patch("requests.get", side_effect=ConnectionError("timeout")):
            result = engine._wiki_page_summary("Some Title")
        assert result is None

    def test_wikipedia_falls_back_to_ddg_when_sparse(self):
        """If Wikipedia returns < MIN_RESULTS, DDG general is called."""
        engine = self._make_engine()
        ddg_result = SearchResult(
            url="https://example.com", title="Test", snippet="snippet",
            source="duckduckgo_general", intent=INTENT_GENERAL,
        )
        with patch.object(engine, "_wiki_opensearch", return_value=[]), \
             patch.object(engine, "_wiki_page_summary", return_value=None), \
             patch.object(engine, "_ddg_general_search", return_value=[ddg_result]) as mock_ddg:
            results = engine._wikipedia_search("AI market", max_results=5)
            # _wikipedia_search itself doesn't call DDG; search() does the fallback
        # Verify the parent search() triggers DDG fallback
        with patch.object(engine, "_wikipedia_search", return_value=[]), \
             patch.object(engine, "_ddg_general_search", return_value=[ddg_result]) as mock_ddg2:
            results = engine.search("AI market size total addressable", intent=INTENT_MARKET_SIZE)
        mock_ddg2.assert_called_once()

    def test_wikipedia_disabled_uses_ddg(self):
        engine = SearchEngine(SearchEngineConfig(enable_wikipedia=False))
        ddg_result = SearchResult(
            url="https://example.com", title="Test", snippet="snippet",
            source="duckduckgo_general", intent=INTENT_GENERAL,
        )
        with patch.object(engine, "_ddg_general_search", return_value=[ddg_result]) as mock_ddg, \
             patch.object(engine, "_wikipedia_search") as mock_wiki:
            engine.search("market size CAGR forecast", intent=INTENT_MARKET_SIZE)
        mock_wiki.assert_not_called()
        mock_ddg.assert_called()

    def test_wikipedia_caps_snippet_to_300_chars(self):
        engine = self._make_engine()
        long_summary = dict(_MOCK_SUMMARY)
        long_summary["extract"] = "A" * 1000
        with patch.object(engine, "_wiki_opensearch", return_value=["Title"]), \
             patch.object(engine, "_wiki_page_summary", return_value=long_summary):
            results = engine._wikipedia_search("long text", max_results=1)
        assert len(results[0].snippet) <= 300


# ─────────────────────────────────────────────────────────────────────────────
# DuckDuckGo News backend
# ─────────────────────────────────────────────────────────────────────────────

class TestDDGNewsBackend:

    def _make_engine(self):
        return SearchEngine(SearchEngineConfig(enable_news=True))

    def test_news_search_returns_results(self):
        engine = self._make_engine()
        mock_item = {
            "url":   "https://techcrunch.com/ai-startup",
            "title": "New AI startup raises $50M",
            "body":  "A new competitor in the AI space...",
        }
        mock_ddgs = MagicMock()
        mock_ddgs.__enter__ = MagicMock(return_value=mock_ddgs)
        mock_ddgs.__exit__ = MagicMock(return_value=False)
        mock_ddgs.news.return_value = [mock_item]

        with patch("src.core.search_engine.DDGS", return_value=mock_ddgs):
            results = engine._ddg_news_search("AI competitor startup", max_results=5)

        assert len(results) == 1
        assert results[0].source == "duckduckgo_news"

    def test_news_falls_back_to_general_on_failure(self):
        engine = self._make_engine()
        ddg_gen_result = SearchResult(
            url="https://example.com", title="Test", snippet="",
            source="duckduckgo_general", intent=INTENT_GENERAL,
        )
        with patch("src.core.search_engine.DDGS", side_effect=ImportError("not installed")), \
             patch.object(engine, "_ddg_general_search", return_value=[ddg_gen_result]) as mock_gen:
            results = engine._ddg_news_search("AI competitors", max_results=3)
        mock_gen.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Domain deduplication
# ─────────────────────────────────────────────────────────────────────────────

class TestDomainDedup:

    def _make_result(self, url: str) -> SearchResult:
        return SearchResult(url=url, title="T", snippet="S",
                            source="duckduckgo_general", intent=INTENT_GENERAL)

    def test_dedup_removes_same_domain(self):
        results = [
            self._make_result("https://techcrunch.com/article/1"),
            self._make_result("https://techcrunch.com/article/2"),
            self._make_result("https://forbes.com/story"),
        ]
        deduped = SearchEngine._dedup_by_domain(results)
        assert len(deduped) == 2
        domains = [r.url for r in deduped]
        assert "https://forbes.com/story" in domains

    def test_dedup_preserves_different_domains(self):
        results = [
            self._make_result("https://a.com/1"),
            self._make_result("https://b.com/1"),
            self._make_result("https://c.com/1"),
        ]
        deduped = SearchEngine._dedup_by_domain(results)
        assert len(deduped) == 3

    def test_dedup_handles_subdomains(self):
        results = [
            self._make_result("https://news.ycombinator.com/item?id=1"),
            self._make_result("https://news.ycombinator.com/item?id=2"),
        ]
        deduped = SearchEngine._dedup_by_domain(results)
        assert len(deduped) == 1

    def test_dedup_handles_malformed_urls(self):
        results = [
            self._make_result("not-a-url"),
            self._make_result("https://valid.com/page"),
        ]
        # Should not raise
        deduped = SearchEngine._dedup_by_domain(results)
        assert len(deduped) == 2


# ─────────────────────────────────────────────────────────────────────────────
# search() routing integration
# ─────────────────────────────────────────────────────────────────────────────

class TestSearchRouting:

    def _wiki_result(self) -> SearchResult:
        return SearchResult(
            url="https://en.wikipedia.org/wiki/AI",
            title="AI market", snippet="...",
            source="wikipedia", intent=INTENT_MARKET_SIZE,
        )

    def _ddg_result(self) -> SearchResult:
        return SearchResult(
            url="https://example.com", title="Test", snippet="",
            source="duckduckgo_general", intent=INTENT_GENERAL,
        )

    def test_market_query_calls_wikipedia(self):
        engine = SearchEngine()
        with patch.object(engine, "_wikipedia_search",
                          return_value=[self._wiki_result()] * 4) as mock_wiki, \
             patch.object(engine, "_ddg_general_search", return_value=[]):
            engine.search("market size CAGR total addressable market")
        mock_wiki.assert_called_once()

    def test_competitor_query_calls_news(self):
        engine = SearchEngine()
        with patch.object(engine, "_ddg_news_search",
                          return_value=[self._ddg_result()] * 4) as mock_news, \
             patch.object(engine, "_ddg_general_search", return_value=[]):
            engine.search("startup competitor landscape alternative")
        mock_news.assert_called_once()

    def test_financial_query_calls_general(self):
        engine = SearchEngine()
        with patch.object(engine, "_ddg_general_search",
                          return_value=[self._ddg_result()] * 4) as mock_gen, \
             patch.object(engine, "_wikipedia_search", return_value=[]), \
             patch.object(engine, "_ddg_news_search", return_value=[]):
            engine.search("Series A funding startup cost budget burn rate")
        mock_gen.assert_called_once()

    def test_intent_override(self):
        """Explicit intent= must override the auto-router."""
        engine = SearchEngine()
        with patch.object(engine, "_wikipedia_search",
                          return_value=[self._wiki_result()]) as mock_wiki:
            engine.search("cost budget funding", intent=INTENT_MARKET_SIZE)
        mock_wiki.assert_called_once()

    def test_result_capped_at_max(self):
        engine = SearchEngine(SearchEngineConfig(max_results=3))
        many = [self._ddg_result() for _ in range(10)]
        with patch.object(engine, "_ddg_general_search", return_value=many):
            results = engine.search("anything", intent=INTENT_GENERAL)
        assert len(results) <= 3

    def test_get_urls_returns_strings(self):
        engine = SearchEngine()
        with patch.object(engine, "_ddg_general_search",
                          return_value=[self._ddg_result()]):
            urls = engine.get_urls("some query", max_results=5)
        assert isinstance(urls, list)
        assert all(isinstance(u, str) for u in urls)


# ─────────────────────────────────────────────────────────────────────────────
# Batch search
# ─────────────────────────────────────────────────────────────────────────────

class TestBatchSearch:

    def test_batch_returns_dict_keyed_by_query(self):
        engine = SearchEngine()
        queries = ["AI market size", "AI startup competitor", "AI funding"]
        mock_result = SearchResult(
            url="https://ex.com", title="T", snippet="S",
            source="duckduckgo_general", intent=INTENT_GENERAL,
        )
        with patch.object(engine, "search", return_value=[mock_result]):
            results = engine.search_batch(queries)
        assert set(results.keys()) == set(queries)

    def test_batch_applies_rate_limiting(self):
        engine = SearchEngine(SearchEngineConfig(rate_limit_delay=(0.0, 0.0)))
        with patch.object(engine, "search", return_value=[]), \
             patch("src.core.search_engine.time.sleep") as mock_sleep:
            engine.search_batch(["q1", "q2", "q3"])
        # sleep called N-1 times (not before first query)
        assert mock_sleep.call_count == 2