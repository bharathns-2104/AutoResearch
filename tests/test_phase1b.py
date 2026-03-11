import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
#!/usr/bin/env python
"""
test_phase1b.py  —  Phase 1b/1c Test Suite

Covers:
  1. FinancialAnalysisAgent._heuristic_review()  — all 5 signal states
  2. FinancialAnalysisAgent.run_with_review()    — PASS path, NEEDS_MORE_DATA path,
                                                   gap-fill callback invoked
  3. MarketAnalysisAgent._heuristic_review()     — TAM/growth/sentiment combos
  4. MarketAnalysisAgent.run_with_review()       — callback integration
  5. IntentRouter._classify_keywords()           — all 5 intents
  6. IntentRouter._classify_llm()                — mocked LLM response
  7. SearchEngine.search_query()                 — intent propagates to SearchConfig
  8. SearchEngine._ddgs_call()                   — news vs text backend selection
  9. WorkflowController._gap_fill_search()       — stub integration
"""

import sys
from unittest.mock import patch, MagicMock

PASS_ICON = "✓"
FAIL_ICON = "✗"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _results.append((name, condition, detail))
    icon = PASS_ICON if condition else FAIL_ICON
    print(f"  {icon}  {name}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'─' * 62}\n  {title}\n{'─' * 62}")


# ─────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

RICH_EXTRACTED = {
    "entities":          {"organizations": ["TeslaAuto", "Rivian"], "people": [], "locations": []},
    "financial_metrics": {
        "startup_costs":   [2_000_000],
        "revenue_figures": [10_000_000],
        "funding_amounts": [50_000_000],
        "market_sizes":    [400_000_000_000],
        "growth_rates":    [18.5],
    },
    "keywords": ["electric vehicle", "battery", "charging", "cagr", "growth",
                 "demand", "adoption", "expansion", "opportunity", "rising"],
    "swot_signals": {"strengths": ["tech"], "weaknesses": [], "opportunities": ["market"], "threats": []},
    "meta": {"num_pages": 8, "avg_page_quality": 0.72},
    "sources": [],
}

SPARSE_EXTRACTED = {
    "entities":          {"organizations": [], "people": [], "locations": []},
    "financial_metrics": {k: [] for k in ["startup_costs", "revenue_figures",
                                           "funding_amounts", "market_sizes", "growth_rates"]},
    "keywords": [],
    "swot_signals": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
    "meta": {"num_pages": 1},
    "sources": [],
}

STRUCTURED_INPUT = {
    "business_idea":   "EV charging network for apartments",
    "industry":        "Automotive",
    "budget":          500_000,
    "timeline_months": 18,
    "target_market":   "United States",
    "team_size":       5,
}


# ─────────────────────────────────────────────────────────────────────────────
# 1. FinancialAnalysisAgent  — heuristic review
# ─────────────────────────────────────────────────────────────────────────────

def test_financial_heuristic_review():
    section("1. FinancialAnalysisAgent — heuristic_review()")
    from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig

    agent = FinancialAnalysisAgent(FinancialConfig())

    # Full-signal result → PASS
    full_result = {
        "metrics": {
            "total_estimated_cost": 2_000_000,
            "estimated_revenue":    10_000_000,
            "growth_rate":          18.5,
            "profit_margin":        15.0,
        },
        "runway_months": 24.0,
    }
    rev = agent._heuristic_review(full_result)
    check("Full signals → confidence = 1.0",    rev["confidence"] == 1.0,
          f"got {rev['confidence']}")
    check("Full signals → verdict = PASS",      rev["verdict"] == "PASS")
    check("Full signals → no issues",           len(rev["issues"]) == 0)

    # No-signal result → NEEDS_MORE_DATA
    empty_result = {"metrics": {}, "runway_months": 0}
    rev_empty = agent._heuristic_review(empty_result)
    check("Empty result → confidence = 0.0",   rev_empty["confidence"] == 0.0,
          f"got {rev_empty['confidence']}")
    check("Empty result → NEEDS_MORE_DATA",     rev_empty["verdict"] == "NEEDS_MORE_DATA")
    check("Empty result → missing_signals ≥ 4",
          len(rev_empty["missing_signals"]) >= 4,
          f"got {len(rev_empty['missing_signals'])}")

    # Partial (3/5 signals) → borderline
    partial_result = {
        "metrics": {"total_estimated_cost": 1_000_000, "estimated_revenue": 5_000_000,
                    "growth_rate": 10.0, "profit_margin": 0},
        "runway_months": 0,
    }
    rev_partial = agent._heuristic_review(partial_result)
    check("Partial result → 0.0 < confidence < 1.0",
          0.0 < rev_partial["confidence"] < 1.0,
          f"got {rev_partial['confidence']}")


# ─────────────────────────────────────────────────────────────────────────────
# 2. FinancialAnalysisAgent  — run_with_review()
# ─────────────────────────────────────────────────────────────────────────────

def test_financial_run_with_review():
    section("2. FinancialAnalysisAgent — run_with_review()")
    from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig

    agent = FinancialAnalysisAgent(FinancialConfig())

    # ── PASS path: LLM disabled, rich data → heuristic gives PASS ────────
    with patch.dict("src.config.settings.LLM_SETTINGS", {"enable_self_correction": False}):
        result = agent.run_with_review(RICH_EXTRACTED, 500_000, STRUCTURED_INPUT)
    check("result is dict",                    isinstance(result, dict))
    check("review key present",               "review" in result)
    check("review.verdict = SKIPPED (LLM off)",
          result["review"]["verdict"] == "SKIPPED")
    check("viability_score present",          "viability_score" in result)
    check("runway_months present",            "runway_months"   in result)

    # ── NEEDS_MORE_DATA path with callback ────────────────────────────────
    callback_calls: list[list[str]] = []
    callback_extra = {
        "financial_metrics": {
            "startup_costs":   [3_000_000],
            "revenue_figures": [],
            "funding_amounts": [],
            "market_sizes":    [],
            "growth_rates":    [12.0],
        }
    }

    def mock_callback(queries: list[str]):
        callback_calls.append(queries)
        return callback_extra

    # Force heuristic review to return NEEDS_MORE_DATA for sparse data
    with patch.dict("src.config.settings.LLM_SETTINGS",
                    {"enable_self_correction": True,
                     "self_correction_max_iterations": 1,
                     "self_correction_confidence_threshold": 0.99}):  # very high threshold
        result2 = agent.run_with_review(
            SPARSE_EXTRACTED, 500_000, STRUCTURED_INPUT,
            search_callback=mock_callback,
        )

    check("callback was called for sparse data",  len(callback_calls) > 0,
          f"calls: {len(callback_calls)}")
    check("result2 has review key",               "review" in result2)
    check("review confidence is float",
          isinstance(result2["review"].get("confidence"), float))


# ─────────────────────────────────────────────────────────────────────────────
# 3. MarketAnalysisAgent  — heuristic review
# ─────────────────────────────────────────────────────────────────────────────

def test_market_heuristic_review():
    section("3. MarketAnalysisAgent — _heuristic_review()")
    from src.agents.market_analysis import MarketAnalysisAgent

    agent = MarketAnalysisAgent()
    ctx   = STRUCTURED_INPUT

    # Full market data → PASS
    full = {
        "market_size":       {"global": 400_000_000_000},
        "growth_rate":       18.5,
        "sentiment":         {"positive_signals": 5, "negative_signals": 1},
        "opportunity_score": 0.75,
    }
    rev = agent._heuristic_review(full, ctx)
    check("Full market → confidence ≥ 0.65",  rev["confidence"] >= 0.65,
          f"got {rev['confidence']}")
    check("Full market → PASS",               rev["verdict"] == "PASS")
    check("Full market → no issues",          len(rev["issues"]) == 0)

    # No TAM, no growth → NEEDS_MORE_DATA
    empty = {"market_size": {"global": 0}, "growth_rate": 0,
             "sentiment": {"positive_signals": 0, "negative_signals": 0},
             "opportunity_score": 0}
    rev_empty = agent._heuristic_review(empty, ctx)
    check("No TAM/growth → NEEDS_MORE_DATA",  rev_empty["verdict"] == "NEEDS_MORE_DATA")
    check("No TAM → missing_signals present", len(rev_empty["missing_signals"]) > 0)

    # Growth but no TAM → partial confidence
    partial = {"market_size": {"global": 0}, "growth_rate": 15.0,
               "sentiment": {"positive_signals": 3, "negative_signals": 0},
               "opportunity_score": 0.4}
    rev_p = agent._heuristic_review(partial, ctx)
    check("Growth only → 0 < confidence < 1",
          0.0 < rev_p["confidence"] < 1.0, f"got {rev_p['confidence']}")
    check("Missing TAM → TAM query suggested",
          any("market" in q.lower() or "tam" in q.lower()
              for q in rev_p["missing_signals"]))


# ─────────────────────────────────────────────────────────────────────────────
# 4. MarketAnalysisAgent  — run_with_review()
# ─────────────────────────────────────────────────────────────────────────────

def test_market_run_with_review():
    section("4. MarketAnalysisAgent — run_with_review()")
    from src.agents.market_analysis import MarketAnalysisAgent

    agent = MarketAnalysisAgent()

    # LLM disabled → SKIPPED
    with patch.dict("src.config.settings.LLM_SETTINGS", {"enable_self_correction": False}):
        result = agent.run_with_review(RICH_EXTRACTED, STRUCTURED_INPUT)
    check("review.verdict = SKIPPED (LLM off)", result["review"]["verdict"] == "SKIPPED")
    check("opportunity_score present",           "opportunity_score" in result)

    # Callback integration with sparse data (threshold > possible score)
    cb_calls: list = []
    def mock_cb(queries):
        cb_calls.append(queries)
        return {"financial_metrics": {"market_sizes": [500_000_000_000], "growth_rates": [20.0]},
                "keywords": ["growth", "expansion"]}

    with patch.dict("src.config.settings.LLM_SETTINGS",
                    {"enable_self_correction": True,
                     "self_correction_max_iterations": 1,
                     "self_correction_confidence_threshold": 0.99}):
        result2 = agent.run_with_review(
            SPARSE_EXTRACTED, STRUCTURED_INPUT, search_callback=mock_cb
        )
    check("market callback called for sparse data", len(cb_calls) > 0)
    check("result2 review key present",             "review" in result2)


# ─────────────────────────────────────────────────────────────────────────────
# 5. IntentRouter  — keyword classification
# ─────────────────────────────────────────────────────────────────────────────

def test_intent_router_keywords():
    section("5. IntentRouter — keyword classification (all 5 intents)")
    from src.agents.search_engine import IntentRouter, QueryIntent

    router = IntentRouter()
    router._use_llm = False   # force keyword path

    cases = [
        ("EV market size CAGR 2026",            QueryIntent.MARKET_SIZE),
        ("latest Tesla quarterly earnings news", QueryIntent.CURRENT_EVENTS),
        ("Tesla vs Rivian competitor comparison", QueryIntent.COMPETITOR),
        ("Rivian Series C funding round",        QueryIntent.FUNDING),
        ("how electric motors work",             QueryIntent.GENERAL),
    ]
    for query, expected in cases:
        got = router._classify_keywords(query)
        check(f"'{query[:45]}' → {expected.value}", got == expected,
              f"got {got.value}")


# ─────────────────────────────────────────────────────────────────────────────
# 6. IntentRouter  — LLM classification (mocked)
# ─────────────────────────────────────────────────────────────────────────────

def test_intent_router_llm():
    section("6. IntentRouter — LLM classification (mocked)")
    from src.agents.search_engine import IntentRouter, QueryIntent

    router = IntentRouter()
    router._use_llm = True

    cases = [
        ({"intent": "MARKET_SIZE",    "rationale": "size query"}, QueryIntent.MARKET_SIZE),
        ({"intent": "FUNDING",        "rationale": "round"},      QueryIntent.FUNDING),
        ({"intent": "CURRENT_EVENTS", "rationale": "news"},       QueryIntent.CURRENT_EVENTS),
        ({"intent": "BAD_VALUE",      "rationale": "unknown"},    QueryIntent.GENERAL),  # fallback
    ]
    for mock_resp, expected in cases:
        with patch("src.orchestration.llm_client.call_llm_json", return_value=mock_resp):
            got = router._classify_llm("any query")
        check(f"LLM '{mock_resp['intent']}' → {expected.value}", got == expected,
              f"got {got.value}")


# ─────────────────────────────────────────────────────────────────────────────
# 7. SearchEngine  — intent propagates to SearchConfig
# ─────────────────────────────────────────────────────────────────────────────

def test_search_engine_config():
    section("7. SearchEngine — intent propagates to SearchConfig")
    from src.agents.search_engine import SearchEngine, QueryIntent

    se = SearchEngine(max_results_per_query=3)
    se.router._use_llm = False   # keyword router for determinism

    market_cfg = se.router.build_config("EV market size CAGR 2026")
    check("market query → MARKET_SIZE intent",
          market_cfg.intent == QueryIntent.MARKET_SIZE)
    check("market query → timelimit = 'y'",
          market_cfg.timelimit == "y")
    check("market query → backend = 'text'",
          market_cfg.backend == "text")
    check("market query → site_hints not empty",
          len(market_cfg.site_hints) > 0)

    news_cfg = se.router.build_config("latest Tesla quarterly earnings news")
    check("news query → CURRENT_EVENTS intent",
          news_cfg.intent == QueryIntent.CURRENT_EVENTS)
    check("news query → timelimit = 'w'",
          news_cfg.timelimit == "w")
    check("news query → backend = 'news'",
          news_cfg.backend == "news")

    funding_cfg = se.router.build_config("Rivian Series C funding round investors")
    check("funding query → FUNDING intent",
          funding_cfg.intent == QueryIntent.FUNDING)

    general_cfg = se.router.build_config("how does an electric motor work")
    check("general query → GENERAL intent",
          general_cfg.intent == QueryIntent.GENERAL)
    check("general query → timelimit = None",
          general_cfg.timelimit is None)
    check("general query → no site_hints",
          len(general_cfg.site_hints) == 0)


# ─────────────────────────────────────────────────────────────────────────────
# 8. SearchEngine  — news vs text backend selection
# ─────────────────────────────────────────────────────────────────────────────

def test_search_engine_backend():
    section("8. SearchEngine — news vs text backend (DDGS mocked)")
    from src.agents.search_engine import SearchEngine, SearchConfig, QueryIntent

    se    = SearchEngine(max_results_per_query=3)
    calls = {"backend": None, "timelimit": None, "query": None}

    def fake_ddgs_call(query, backend, timelimit, max_results):
        calls["backend"]   = backend
        calls["timelimit"] = timelimit
        calls["query"]     = query
        return [{"query": query, "title": "T", "url": "http://example.com",
                 "snippet": "test"}]

    se._ddgs_call = fake_ddgs_call   # monkey-patch the thin wrapper

    # News backend
    news_cfg = SearchConfig(
        query="latest EV news", intent=QueryIntent.CURRENT_EVENTS,
        timelimit="w", backend="news", site_hints=[], max_results=3,
    )
    se._execute(news_cfg)
    check("news intent → backend='news'",   calls["backend"]   == "news")
    check("news intent → timelimit='w'",    calls["timelimit"] == "w")

    # Text backend with site hint
    mkt_cfg = SearchConfig(
        query="EV TAM 2026", intent=QueryIntent.MARKET_SIZE,
        timelimit="y", backend="text",
        site_hints=["site:statista.com"], max_results=3,
    )
    se._execute(mkt_cfg)
    check("market intent → backend='text'",      calls["backend"] == "text")
    check("market intent → site hint appended",
          "site:statista.com" in (calls["query"] or ""),
          f"query was: {calls['query']}")


# ─────────────────────────────────────────────────────────────────────────────
# 9. WorkflowController._gap_fill_search()
# ─────────────────────────────────────────────────────────────────────────────

def test_gap_fill_search():
    section("9. WorkflowController — _gap_fill_search() stub")
    from src.orchestration.workflow_controller import WorkflowController
    from src.orchestration.state_manager import StateManager

    StateManager.reset()
    ctrl = WorkflowController()

    stub_extracted = {
        "financial_metrics": {"startup_costs": [1_000_000], "revenue_figures": [],
                               "funding_amounts": [], "market_sizes": [],
                               "growth_rates": [10.0]},
        "keywords": ["electric", "vehicle"],
        "entities": {"organizations": [], "people": [], "locations": []},
        "meta": {"num_pages": 1},
        "sources": [],
    }

    # Mock the entire search → scrape → extract chain
    mock_se      = MagicMock()
    mock_scraper = MagicMock()
    mock_engine  = MagicMock()

    mock_se.search_query.return_value = [
        {"url": "https://ev.example.com", "title": "EV data", "snippet": "test", "score": 0.8}
    ]
    mock_scraper.scrape.return_value = [
        {"url": "https://ev.example.com", "text": "EV market is $400B growing at 18.5% CAGR"}
    ]
    mock_engine.process.return_value = stub_extracted

    # Patch at the site where _gap_fill_search imports them (inside workflow_controller)
    with patch("src.orchestration.workflow_controller.SearchEngine",      return_value=mock_se), \
         patch("src.orchestration.workflow_controller.WebScraper",         return_value=mock_scraper), \
         patch("src.agents.extraction_engine.ExtractionEngine",            return_value=mock_engine):
        result = ctrl._gap_fill_search(
            ["{industry} market CAGR growth rate forecast"],
            STRUCTURED_INPUT,
        )

    check("_gap_fill_search returns dict",     isinstance(result, dict))
    check("result has financial_metrics",      "financial_metrics" in result)
    check("SE.search_query was called",        mock_se.search_query.called)
    check("Scraper.scrape was called",         mock_scraper.scrape.called)
    check("ExtractionEngine.process called",   mock_engine.process.called)

    # Placeholder substitution — only check if the mock was actually called
    if mock_se.search_query.call_args is not None:
        call_args = mock_se.search_query.call_args[0][0]
        check("{industry} placeholder filled", "{industry}" not in call_args,
              f"got: {call_args}")
        check("'Automotive' filled in query",  "Automotive" in call_args,
              f"got: {call_args}")
    else:
        check("{industry} placeholder filled", False,
              "mock was not called — patch target may be wrong")
        check("'Automotive' filled in query",  False,
              "mock was not called — patch target may be wrong")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

def main() -> int:
    print("\n" + "=" * 62)
    print("  PHASE 1b/1c — SELF-REVIEW + INTENT ROUTER TEST SUITE")
    print("=" * 62)

    test_financial_heuristic_review()
    test_financial_run_with_review()
    test_market_heuristic_review()
    test_market_run_with_review()
    test_intent_router_keywords()
    test_intent_router_llm()
    test_search_engine_config()
    test_search_engine_backend()
    test_gap_fill_search()

    passed = sum(1 for _, ok, _ in _results if ok)
    total  = len(_results)
    failed = total - passed

    print("\n" + "=" * 62)
    if failed == 0:
        print(f"  {PASS_ICON} ALL {total} TESTS PASSED")
    else:
        print(f"  {FAIL_ICON} {failed}/{total} TESTS FAILED")
        print("\n  FAILURES:")
        for name, ok, detail in _results:
            if not ok:
                print(f"    {FAIL_ICON}  {name}" + (f" — {detail}" if detail else ""))
    print("=" * 62)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())