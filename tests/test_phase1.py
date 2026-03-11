#!/usr/bin/env python
"""
test_phase1.py  —  Phase 1 Intelligence Layer Test Suite

Tests cover:
  - LLM client module structure & fallback behaviour
  - ExtractionEngine: LLM path, regex fallback, schema validation
  - SelfCorrectionAgent: confidence scoring, correction merging
  - RoutingAgent: rule-based routing, edge cases
  - WorkflowController: routing config plumbing
  - Settings: LLM_SETTINGS presence

Run with:
    python test_phase1.py
"""

import sys
import json
import types
from unittest.mock import patch, MagicMock

import os
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src'))
sys.path.insert(0, src_path)
print('sys.path:', sys.path)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "✓"
FAIL = "✗"
_results: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    _results.append((name, condition, detail))
    icon = PASS if condition else FAIL
    print(f"  {icon}  {name}" + (f" — {detail}" if detail else ""))


def section(title: str) -> None:
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")


# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

SAMPLE_EXTRACTION = {
    "entities": {
        "organizations": ["TeslaAuto", "RivianEV", "NioInc"],
        "people":        ["Elon Musk"],
        "locations":     ["California", "Texas"],
    },
    "financial_metrics": {
        "startup_costs":   [5_000_000, 2_000_000],
        "revenue_figures": [10_000_000],
        "funding_amounts": [50_000_000],
        "market_sizes":    [400_000_000_000],
        "growth_rates":    [18.5, 12.0],
    },
    "keywords": [
        "electric vehicle", "battery", "charging network",
        "autonomous driving", "software platform",
    ],
    "swot_signals": {
        "strengths":     ["strong brand recognition", "advanced technology"],
        "weaknesses":    ["high manufacturing cost"],
        "opportunities": ["growing EV adoption"],
        "threats":       ["legacy automaker competition"],
    },
    "meta": {
        "num_pages": 8,
        "avg_page_quality": 0.72,
        "pages_with_any_financial_signals": 5,
        "pages_with_any_market_signals":    4,
        "pages_with_any_growth_signals":    3,
        "extraction_method": "llm",
    },
    "sources": [{"url": "https://example.com/ev", "title": "EV Market 2026"}],
}

SAMPLE_STRUCTURED_INPUT = {
    "business_idea":    "EV charging network for apartment buildings",
    "industry":         "Automotive",
    "budget":           500_000,
    "timeline_months":  18,
    "target_market":    "United States",
    "team_size":        5,
}

SAMPLE_SCRAPED = [
    {
        "url": "https://ev-market.example.com",
        "title": "EV Market Overview",
        "text": (
            "Tesla raised $5M in funding. The EV market size is valued at $400B. "
            "Market growth rate is 18.5% CAGR. Startup costs are $2M. "
            "Key competitors include Rivian, NIO, and Lucid Motors."
        ),
        "quality_score": 0.75,
    }
]


# ---------------------------------------------------------------------------
# Test 1 — Settings
# ---------------------------------------------------------------------------

def test_settings():
    section("1. Settings — LLM_SETTINGS present and structured")
    from config.settings import LLM_SETTINGS

    check("LLM_SETTINGS dict exists",      isinstance(LLM_SETTINGS, dict))
    check("model key present",             "model"              in LLM_SETTINGS)
    check("api_base key present",          "api_base"           in LLM_SETTINGS)
    check("use_llm_extraction key",        "use_llm_extraction" in LLM_SETTINGS)
    check("enable_self_correction key",    "enable_self_correction" in LLM_SETTINGS)
    check("enable_smart_routing key",      "enable_smart_routing"   in LLM_SETTINGS)
    check("self_correction_max_iterations", LLM_SETTINGS.get("self_correction_max_iterations", 0) > 0)
    check("confidence_threshold is float",
          isinstance(LLM_SETTINGS.get("self_correction_confidence_threshold"), float))


# ---------------------------------------------------------------------------
# Test 2 — LLM Client
# ---------------------------------------------------------------------------

def test_llm_client():
    section("2. LLM Client — module structure & helpers")
    from orchestration import llm_client

    check("call_llm function exists",      hasattr(llm_client, "call_llm"))
    check("call_llm_json function exists", hasattr(llm_client, "call_llm_json"))
    check("_extract_json helper exists",   hasattr(llm_client, "_extract_json"))

    # _extract_json — basic parsing
    from orchestration.llm_client import _extract_json

    plain_json = '{"key": "value", "num": 42}'
    check("Parses clean JSON",    _extract_json(plain_json) == plain_json)

    fenced = '```json\n{"key": "value"}\n```'
    parsed = _extract_json(fenced)
    check("Strips markdown fences", '"key"' in parsed)

    prefixed = 'Here is the result:\n{"key": "ok"}'
    parsed2  = _extract_json(prefixed)
    check("Extracts JSON from prose prefix", '"key"' in parsed2)


# ---------------------------------------------------------------------------
# Test 3 — ExtractionEngine: schema & regex fallback
# ---------------------------------------------------------------------------

def test_extraction_engine():
    section("3. ExtractionEngine — schema validation & regex fallback")

    # Force regex-only mode (no LLM needed for CI)
    with patch.dict("src.config.settings.LLM_SETTINGS", {"use_llm_extraction": False}):
        from src.agents.extraction_engine import ExtractionEngine
        engine = ExtractionEngine()

    check("ExtractionEngine instantiates",  engine is not None)
    check("normalize_currency $2.5M",       engine.normalize_currency("$2.5M") == 2_500_000)
    check("normalize_currency $50k",        engine.normalize_currency("$50k")  == 50_000)
    check("normalize_currency $1B",         engine.normalize_currency("$1B")   == 1_000_000_000)

    # Keyword threshold
    check("threshold small (5 pages)  → 1", engine._get_keyword_threshold(5)  == 1)
    check("threshold medium (20 pages) → 2", engine._get_keyword_threshold(20) == 2)
    check("threshold large (50 pages)  → 3", engine._get_keyword_threshold(50) == 3)

    # Regex fallback page extraction
    page_data = engine._extract_page_regex(SAMPLE_SCRAPED[0]["text"])
    check("_extract_page_regex returns dict",         isinstance(page_data, dict))
    check("has 'organizations' key",                  "organizations" in page_data)
    check("has 'startup_costs' key",                  "startup_costs"  in page_data)
    check("has 'keywords' key",                       "keywords"       in page_data)
    check("has 'swot' key (empty in regex mode)",     "swot"           in page_data)

    # Full process() with mock scraped pages
    result = engine.process(SAMPLE_SCRAPED)
    check("process() returns dict",                   isinstance(result, dict))
    check("result has 'entities'",                    "entities"         in result)
    check("result has 'financial_metrics'",           "financial_metrics" in result)
    check("result has 'keywords'",                    "keywords"         in result)
    check("result has 'swot_signals'",                "swot_signals"     in result)
    check("result has 'meta'",                        "meta"             in result)
    check("result has 'sources'",                     "sources"          in result)
    check("meta.extraction_method == 'regex'",
          result["meta"].get("extraction_method") == "regex")


# ---------------------------------------------------------------------------
# Test 4 — ExtractionEngine: LLM path with mock
# ---------------------------------------------------------------------------

def test_extraction_engine_llm_mock():
    section("4. ExtractionEngine — LLM extraction path (mocked)")

    mock_llm_response = {
        "organizations": ["TeslaAuto", "RivianEV"],
        "people":        ["Elon Musk"],
        "locations":     ["California"],
        "startup_costs":   [2_000_000],
        "revenue_figures": [],
        "funding_amounts": [50_000_000],
        "market_sizes":    [400_000_000_000],
        "growth_rates":    [18.5],
        "keywords":        ["electric vehicle", "charging", "battery"],
        "swot": {
            "strengths":     ["strong tech"],
            "weaknesses":    ["high cost"],
            "opportunities": ["growing market"],
            "threats":       ["competition"],
        },
    }

    with patch("src.orchestration.llm_client.call_llm_json",
               return_value=mock_llm_response), \
         patch.dict("src.config.settings.LLM_SETTINGS", {"use_llm_extraction": True}):

        from src.agents.extraction_engine import ExtractionEngine
        engine = ExtractionEngine()
        engine._use_llm = True

        page_data = engine._extract_page_llm(
            SAMPLE_SCRAPED[0]["text"],
            SAMPLE_SCRAPED[0]["url"],
            SAMPLE_SCRAPED[0]["title"],
        )

    check("LLM path returns dict",               isinstance(page_data, dict))
    check("organizations extracted",             "TeslaAuto" in page_data.get("organizations", []))
    check("growth_rates extracted",              18.5 in page_data.get("growth_rates", []))
    check("SWOT strengths populated",
          len(page_data.get("swot", {}).get("strengths", [])) > 0)


# ---------------------------------------------------------------------------
# Test 5 — SelfCorrectionAgent
# ---------------------------------------------------------------------------

def test_self_correction_agent():
    section("5. SelfCorrectionAgent — confidence scoring & correction")
    from src.agents.self_correction_agent import SelfCorrectionAgent

    agent = SelfCorrectionAgent()
    check("SelfCorrectionAgent instantiates", agent is not None)

    # Score the rich sample — should be high confidence
    score, issues = agent._score_confidence(SAMPLE_EXTRACTION)
    check(f"Confidence score is float ({score:.2f})",     isinstance(score, float))
    check("Confidence in [0, 1]",                         0.0 <= score <= 1.0)
    check("Rich data → confidence ≥ 0.6",                 score >= 0.6,
          f"got {score:.2f}")

    # Score a sparse extraction — should flag issues
    sparse = {
        "entities":         {"organizations": [], "people": [], "locations": []},
        "financial_metrics": {k: [] for k in
                              ["startup_costs", "revenue_figures", "funding_amounts",
                               "market_sizes", "growth_rates"]},
        "keywords":         [],
        "swot_signals":     {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "meta":             {"num_pages": 1},
    }
    sparse_score, sparse_issues = agent._score_confidence(sparse)
    check("Sparse data → lower confidence",   sparse_score < score)
    check("Sparse data → has issues",         len(sparse_issues) > 0,
          f"issues: {sparse_issues}")

    # run() with LLM disabled: should return unchanged
    with patch.dict("src.config.settings.LLM_SETTINGS",
                    {"enable_self_correction": False}):
        agent_off = SelfCorrectionAgent()
        result    = agent_off.run(SAMPLE_EXTRACTION, SAMPLE_SCRAPED)
    check("run() with correction disabled returns input unchanged",
          result is SAMPLE_EXTRACTION)

    # run() with high-confidence input: no correction triggered
    with patch.dict("src.config.settings.LLM_SETTINGS",
                    {"enable_self_correction": True,
                     "self_correction_max_iterations": 2,
                     "self_correction_confidence_threshold": 0.5}):
        agent_on = SelfCorrectionAgent()
        result2  = agent_on.run(SAMPLE_EXTRACTION, SAMPLE_SCRAPED)
    check("run() with sufficient confidence skips correction",
          not result2.get("meta", {}).get("self_correction_applied", True))


# ---------------------------------------------------------------------------
# Test 6 — RoutingAgent
# ---------------------------------------------------------------------------

def test_routing_agent():
    section("6. RoutingAgent — rule-based routing & output schema")
    from src.agents.routing_agent import RoutingAgent

    agent = RoutingAgent()
    check("RoutingAgent instantiates", agent is not None)

    # Rich data → all agents should run, high confidence
    routing = agent._route_rules(SAMPLE_EXTRACTION)
    check("routing is dict",                         isinstance(routing, dict))
    check("run_financial (rich data)",               routing["run_financial"]   is True)
    check("run_competitive (rich data)",             routing["run_competitive"] is True)
    check("run_market (rich data)",                  routing["run_market"]      is True)
    check("confidence_tier is string",               isinstance(routing["confidence_tier"], str))
    check("rationale is string",                     isinstance(routing["rationale"], str))
    check("additional_queries is list",              isinstance(routing["additional_queries"], list))
    check("rich data → high confidence tier",        routing["confidence_tier"] == "high",
          f"got '{routing['confidence_tier']}'")

    # Empty data → some agents might be skipped
    empty_ext = {
        "entities":         {"organizations": [], "people": [], "locations": []},
        "financial_metrics": {k: [] for k in
                              ["startup_costs", "revenue_figures", "funding_amounts",
                               "market_sizes", "growth_rates"]},
        "keywords":         [],
        "swot_signals":     {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "meta":             {"num_pages": 1, "avg_page_quality": 0.1},
    }
    routing_empty = agent._route_rules(empty_ext)
    check("empty data → at least one agent runs",
          any([routing_empty["run_financial"],
               routing_empty["run_competitive"],
               routing_empty["run_market"]]))
    check("empty data → low confidence tier",
          routing_empty["confidence_tier"] == "low",
          f"got '{routing_empty['confidence_tier']}'")

    # LLM routing path with mock
    mock_routing = {
        "run_financial": True, "run_competitive": False, "run_market": True,
        "additional_queries": ["EV market size 2026"],
        "confidence_tier": "medium",
        "rationale": "No competitor data found.",
    }
    with patch("src.orchestration.llm_client.call_llm_json",
               return_value=mock_routing), \
         patch.dict("src.config.settings.LLM_SETTINGS",
                    {"enable_smart_routing": True}):
        agent_llm = RoutingAgent()
        agent_llm._enabled = True
        llm_routing = agent_llm._route_llm(SAMPLE_EXTRACTION, SAMPLE_STRUCTURED_INPUT)

    check("LLM routing: run_financial=True",       llm_routing["run_financial"] is True)
    check("LLM routing: run_competitive=False",    llm_routing["run_competitive"] is False)
    check("LLM routing: additional_queries list",
          isinstance(llm_routing["additional_queries"], list))


# ---------------------------------------------------------------------------
# Test 7 — WorkflowController plumbing
# ---------------------------------------------------------------------------

def test_workflow_controller_plumbing():
    section("7. WorkflowController — routing config wiring")
    from src.orchestration.workflow_controller import (
        _empty_extraction, _default_routing,
        _merge_entities, _merge_financials, _merge_keywords,
    )

    empty = _empty_extraction()
    check("_empty_extraction has entities",         "entities"         in empty)
    check("_empty_extraction has financial_metrics","financial_metrics" in empty)
    check("_empty_extraction has swot_signals",     "swot_signals"     in empty)

    routing = _default_routing()
    check("_default_routing: run_financial=True",   routing["run_financial"] is True)
    check("_default_routing: confidence_tier",      routing["confidence_tier"] == "medium")

    # Entity merge
    base  = {"entities": {"organizations": ["CompA"], "people": [], "locations": []}}
    extra = {"entities": {"organizations": ["CompB"], "people": [], "locations": []}}
    _merge_entities(base, extra)
    check("_merge_entities: both orgs present",
          "CompA" in base["entities"]["organizations"] and
          "CompB" in base["entities"]["organizations"])
    check("_merge_entities: no duplicates",
          len(base["entities"]["organizations"]) == 2)

    # Keyword merge
    base2 = {"keywords": ["saas", "cloud"]}
    extra2 = {"keywords": ["cloud", "api"]}
    _merge_keywords(base2, extra2)
    check("_merge_keywords: deduplicated union",
          set(base2["keywords"]) == {"saas", "cloud", "api"})


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    print("\n" + "=" * 60)
    print("  PHASE 1 INTELLIGENCE LAYER — TEST SUITE")
    print("=" * 60)

    test_settings()
    test_llm_client()
    test_extraction_engine()
    test_extraction_engine_llm_mock()
    test_self_correction_agent()
    test_routing_agent()
    test_workflow_controller_plumbing()

    passed = sum(1 for _, ok, _ in _results if ok)
    total  = len(_results)
    failed = total - passed

    print("\n" + "=" * 60)
    if failed == 0:
        print(f"  {PASS} ALL {total} TESTS PASSED")
    else:
        print(f"  {FAIL} {failed} / {total} TESTS FAILED")
        print("\n  FAILURES:")
        for name, ok, detail in _results:
            if not ok:
                print(f"    {FAIL}  {name}" + (f" — {detail}" if detail else ""))

    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())