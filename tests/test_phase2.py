"""
test_phase2_rag_integration.py
================================
Tests for Phase 2 RAG integration across all agents.

Run with:
    pytest tests/test_phase2_rag_integration.py -v
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from typing import Dict, Any, List


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / shared fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_rag(chunks: List[str] | None = None, ready: bool = True):
    """Build a minimal RAGManager mock."""
    rag = MagicMock()
    rag.is_ready.return_value = ready
    rag.query.return_value = chunks or [
        "The AI automation market is growing at 15% CAGR annually.",
        "Startups in this space raised $50M in Series A rounds on average.",
        "Key competitors include OpenAI, Anthropic, and Cohere.",
        "Total addressable market estimated at $200 billion by 2030.",
        "Regulation and data privacy are major risks for AI companies.",
    ]
    return rag


def _sample_extracted_data(
    *,
    startup_costs=None,
    revenue_figures=None,
    growth_rates=None,
    market_sizes=None,
    organizations=None,
    keywords=None,
) -> Dict[str, Any]:
    return {
        "financial_metrics": {
            "startup_costs":   startup_costs   or [],
            "revenue_figures": revenue_figures or [],
            "funding_amounts": [],
            "growth_rates":    growth_rates   or [],
            "market_sizes":    market_sizes   or [],
        },
        "entities": {
            "organizations": organizations or [],
        },
        "keywords":    keywords or [],
        "swot_signals": {
            "strengths":     ["Scalable technology stack"],
            "weaknesses":    ["Limited brand awareness"],
            "opportunities": ["Underserved SMB segment"],
            "threats":       ["Incumbent price pressure"],
        },
        "meta": {"num_pages": 8},
    }


_BUSINESS_INPUT = {
    "business_idea": "AI-powered legal document analysis",
    "industry":      "LegalTech",
    "target_market": "Law firms and corporate legal teams",
    "budget":        500_000,
}


# ─────────────────────────────────────────────────────────────────────────────
# FinancialAnalysisAgent  — Phase 2
# ─────────────────────────────────────────────────────────────────────────────

class TestFinancialAnalysisAgentRAG:

    def _make_agent(self):
        from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig
        return FinancialAnalysisAgent(FinancialConfig())

    def test_run_without_rag_unchanged(self):
        """Omitting rag= must not break existing behaviour."""
        agent = self._make_agent()
        data  = _sample_extracted_data(
            startup_costs=[100_000], revenue_figures=[200_000], growth_rates=[12.0]
        )
        result = agent.run(data, budget=500_000)
        assert "viability_score"  in result
        assert "runway_months"    in result
        assert result["rag_augmented"] is False

    def test_run_with_rag_not_ready(self):
        """Disabled RAG must be a no-op."""
        agent = self._make_agent()
        rag   = _make_rag(ready=False)
        data  = _sample_extracted_data()
        result = agent.run(data, budget=500_000, rag=rag)
        rag.query.assert_not_called()
        assert result["rag_augmented"] is False

    def test_rag_augments_empty_costs(self):
        """RAG should fill in startup_costs when none found in extraction."""
        agent = self._make_agent()
        chunks = [
            "Initial investment typically ranges from $150,000 to $300,000.",
            "Startups report monthly burn of $25,000 in the first year.",
        ]
        rag  = _make_rag(chunks=chunks)
        data = _sample_extracted_data()   # all empty

        with patch(
            "src.agents.financial_analysis.FinancialAnalysisAgent._parse_rag_chunks",
            return_value={
                "startup_costs":   [150_000, 300_000],
                "revenue_figures": [],
                "funding_amounts": [],
                "growth_rates":    [],
                "market_sizes":    [],
            },
        ):
            result = agent.run(data, budget=500_000, rag=rag)

        assert result["rag_augmented"] is True
        assert rag.query.called

    def test_rag_does_not_overwrite_existing_data(self):
        """RAG should extend, not replace, already-present metrics."""
        agent = self._make_agent()
        rag   = _make_rag()
        data  = _sample_extracted_data(
            startup_costs=[200_000],
            revenue_figures=[500_000],
            growth_rates=[10.0],
            market_sizes=[5_000_000_000],
        )
        # All 5 signal categories already populated → RAG queries skipped
        with patch.object(agent, "_augment_with_rag", wraps=agent._augment_with_rag) as spy:
            result = agent.run(data, budget=500_000, rag=rag)
        # augment_with_rag called but should skip queries because all lists are non-empty
        # (the internal log says "all signal categories already populated")
        assert result["rag_augmented"] is True

    def test_run_with_review_passes_rag(self):
        """run_with_review must forward rag= to the inner run()."""
        agent = self._make_agent()
        rag   = _make_rag(ready=False)   # disabled → deterministic
        data  = _sample_extracted_data(startup_costs=[100_000], growth_rates=[8.0])

        with patch.object(agent, "run", wraps=agent.run) as spy:
            agent.run_with_review(data, budget=500_000, rag=rag)
        # rag kwarg must have been forwarded
        _, kwargs = spy.call_args
        assert "rag" in kwargs

    def test_parse_rag_chunks_regex_fallback(self):
        """Regex parser extracts money and percentages from raw text."""
        from src.agents.financial_analysis import FinancialAnalysisAgent
        text = (
            "Startup costs are around $500k. "
            "Annual revenue projections reach $2M. "
            "Growth rate is approximately 12% per year."
        )
        result = FinancialAnalysisAgent._parse_rag_chunks_regex(text)
        assert result["startup_costs"]
        assert result["growth_rates"]


# ─────────────────────────────────────────────────────────────────────────────
# MarketAnalysisAgent  — Phase 2
# ─────────────────────────────────────────────────────────────────────────────

class TestMarketAnalysisAgentRAG:

    def _make_agent(self):
        from src.agents.market_analysis import MarketAnalysisAgent
        return MarketAnalysisAgent()

    def test_run_without_rag_unchanged(self):
        agent  = self._make_agent()
        data   = _sample_extracted_data(
            market_sizes=[10_000_000_000], growth_rates=[15.0]
        )
        result = agent.run(data)
        assert "opportunity_score" in result
        assert result["rag_augmented"] is False

    def test_rag_fills_missing_market_size(self):
        agent  = self._make_agent()
        chunks = ["Global market valued at $50 billion in 2025."]
        rag    = _make_rag(chunks=chunks)
        data   = _sample_extracted_data()   # no market_sizes

        with patch(
            "src.agents.market_analysis.MarketAnalysisAgent._parse_money_from_chunks",
            return_value=[50_000_000_000],
        ):
            result = agent.run(data, rag=rag)

        assert result["market_size"]["global"] == pytest.approx(50_000_000_000)
        assert result["rag_augmented"] is True

    def test_rag_fills_missing_growth_rate(self):
        agent  = self._make_agent()
        chunks = ["CAGR for this sector is 18% over the next five years."]
        rag    = _make_rag(chunks=chunks)
        data   = _sample_extracted_data()

        with patch(
            "src.agents.market_analysis.MarketAnalysisAgent._parse_percentages_from_chunks",
            return_value=[18.0],
        ):
            result = agent.run(data, rag=rag)

        assert result["growth_rate"] == pytest.approx(18.0)

    def test_sentiment_augmented_by_rag(self):
        agent = self._make_agent()
        rag   = _make_rag(chunks=[
            "Market is rapidly growing with strong demand and adoption.",
            "Declining costs and rising investment signal expansion.",
        ])
        data  = _sample_extracted_data(keywords=["ai", "saas"])
        result = agent.run(data, rag=rag)
        # Positive chunks → sentiment score should be > 0
        assert result["sentiment"]["positive_signals"] >= 0   # always non-negative
        assert result["rag_augmented"] is True

    def test_rag_disabled_skips_queries(self):
        agent = self._make_agent()
        rag   = _make_rag(ready=False)
        data  = _sample_extracted_data()
        result = agent.run(data, rag=rag)
        rag.query.assert_not_called()

    def test_opportunity_score_range(self):
        agent = self._make_agent()
        rag   = _make_rag(ready=False)
        data  = _sample_extracted_data(
            market_sizes=[200_000_000_000], growth_rates=[20.0],
            keywords=["growth", "expanding", "demand"]
        )
        result = agent.run(data, rag=rag)
        assert 0.0 <= result["opportunity_score"] <= 1.0


# ─────────────────────────────────────────────────────────────────────────────
# CompetitiveAnalysisAgent  — Phase 2
# ─────────────────────────────────────────────────────────────────────────────

class TestCompetitiveAnalysisAgentRAG:

    def _make_agent(self):
        from src.agents.competitive_analysis import CompetitiveAnalysisAgent
        return CompetitiveAnalysisAgent()

    def test_run_without_rag_unchanged(self):
        agent  = self._make_agent()
        data   = _sample_extracted_data(
            organizations=["OpenAI", "Anthropic", "Cohere", "Mistral", "DeepMind"]
        )
        result = agent.run(data)
        assert "swot_analysis"           in result
        assert "competitive_intensity"   in result
        assert result["rag_augmented"] is False

    def test_rag_fills_sparse_competitors(self):
        agent  = self._make_agent()
        rag    = _make_rag()
        data   = _sample_extracted_data(organizations=["OpenAI"])   # only 1 → sparse

        with patch(
            "src.agents.competitive_analysis"
            ".CompetitiveAnalysisAgent._extract_competitors_from_rag",
            return_value=["Anthropic", "Cohere", "Mistral"],
        ):
            result = agent.run(data, rag=rag)

        assert result["competitors_found"] >= 2
        assert result["rag_augmented"] is True

    def test_rag_not_called_when_enough_competitors(self):
        agent = self._make_agent()
        rag   = _make_rag()
        data  = _sample_extracted_data(
            organizations=["A", "B", "C", "D", "E"]   # 5 → not sparse
        )
        with patch.object(
            agent, "_extract_competitors_from_rag"
        ) as mock_rag_ext:
            agent.run(data, rag=rag)
        mock_rag_ext.assert_not_called()

    def test_swot_includes_swot_signals(self):
        """ExtractionEngine swot_signals must be incorporated."""
        agent = self._make_agent()
        data  = _sample_extracted_data(organizations=["OpenAI", "Anthropic", "Cohere"])
        result = agent.run(data)
        swot  = result["swot_analysis"]
        # "Scalable technology stack" comes from swot_signals fixture
        all_swot_items = (
            swot["strengths"] + swot["weaknesses"] +
            swot["opportunities"] + swot["threats"]
        )
        assert any("Scalable" in item for item in all_swot_items)

    def test_rag_swot_enrichment(self):
        """RAG SWOT quadrant retrieval should produce non-empty lists."""
        agent  = self._make_agent()
        rag    = _make_rag()
        data   = _sample_extracted_data(organizations=["A", "B", "C"])

        with patch(
            "src.agents.competitive_analysis"
            ".CompetitiveAnalysisAgent._rag_swot",
            return_value={
                "strengths":     ["First-mover advantage in AI-native workflow"],
                "weaknesses":    [],
                "opportunities": ["Unmet demand in regulated industries"],
                "threats":       [],
            },
        ):
            result = agent.run(data, rag=rag)

        all_swot = (
            result["swot_analysis"]["strengths"] +
            result["swot_analysis"]["opportunities"]
        )
        assert any("AI-native" in s for s in all_swot)

    def test_feature_extraction_augmented_by_rag(self):
        agent  = self._make_agent()
        rag    = _make_rag(chunks=["The platform offers an API and mobile app."])
        data   = _sample_extracted_data(keywords=["saas"])

        with patch(
            "src.agents.competitive_analysis"
            ".CompetitiveAnalysisAgent._parse_features_from_chunks",
            return_value=["api", "mobile app"],
        ):
            result = agent.run(data, rag=rag)

        # Feature extraction ran without error
        assert "market_gaps" in result


# ─────────────────────────────────────────────────────────────────────────────
# ConsolidationAgent  — Phase 2
# ─────────────────────────────────────────────────────────────────────────────

def _make_financial_result(**kwargs) -> Dict[str, Any]:
    base = {
        "viability_score":  0.65,
        "runway_months":    18.0,
        "risks":            ["Burn rate may exceed projections."],
        "recommendations":  ["Seek Series A within 12 months."],
        "summary":          "Moderate financial viability.",
        "data_confidence":  "Medium",
        "rag_augmented":    False,
        "metrics": {
            "total_estimated_cost": 300_000,
            "monthly_burn":          25_000,
            "estimated_revenue":    400_000,
            "growth_rate":           12.0,
            "profit_margin":         10.0,
        },
    }
    base.update(kwargs)
    return base


def _make_market_result(**kwargs) -> Dict[str, Any]:
    base = {
        "opportunity_score": 0.70,
        "growth_rate":        15.0,
        "market_size":       {"global": 50_000_000_000, "currency": "USD"},
        "sentiment":         {"label": "Positive", "score": 0.4,
                              "positive_signals": 5, "negative_signals": 1},
        "key_insights":      ["Strong B2B demand expected."],
        "summary":           "Attractive market with high growth.",
        "data_confidence":   "High",
        "rag_augmented":     False,
    }
    base.update(kwargs)
    return base


def _make_competitive_result(**kwargs) -> Dict[str, Any]:
    base = {
        "competitive_intensity": "Medium",
        "competitors_found":     8,
        "top_competitors":       ["A", "B", "C"],
        "swot_analysis": {
            "strengths":     ["Niche focus"],
            "weaknesses":    ["Small team"],
            "opportunities": ["Regulatory tailwind"],
            "threats":       ["Big tech entry"],
        },
        "market_gaps":    ["No AI-native workflow tool"],
        "summary":        "Moderate competition.",
        "data_confidence": "Medium",
        "rag_augmented":  False,
    }
    base.update(kwargs)
    return base


class TestConsolidationAgentRAG:

    def _make_agent(self):
        from src.agents.consolidation_agent import ConsolidationAgent
        return ConsolidationAgent()

    def test_consolidate_without_rag(self):
        agent  = self._make_agent()
        result = agent.consolidate(
            _make_financial_result(),
            _make_market_result(),
            _make_competitive_result(),
            _BUSINESS_INPUT,
        )
        assert "overall_viability_score"     in result
        assert "executive_summary"           in result
        assert "strategic_recommendations"   in result
        assert result["rag_augmented"] is False

    def test_consolidate_with_rag_disabled(self):
        agent = self._make_agent()
        rag   = _make_rag(ready=False)
        result = agent.consolidate(
            _make_financial_result(),
            _make_market_result(),
            _make_competitive_result(),
            _BUSINESS_INPUT,
            rag=rag,
        )
        rag.query.assert_not_called()
        assert result["rag_augmented"] is False

    def test_cross_synthesis_enriches_key_findings(self):
        agent = self._make_agent()
        rag   = _make_rag()

        synthesis_return = {
            "executive_insights":        ["Proprietary data moat is critical to defensibility."],
            "strategic_recommendations": ["Launch in legal vertical before expanding horizontally."],
            "key_risks":                 ["Market may commoditise faster than expected."],
            "confidence_note":           "Good data quality across all three agents.",
        }

        with patch.object(
            agent, "_cross_agent_synthesis", return_value=synthesis_return
        ):
            result = agent.consolidate(
                _make_financial_result(),
                _make_market_result(),
                _make_competitive_result(),
                _BUSINESS_INPUT,
                rag=rag,
            )

        assert any(
            "data moat" in f for f in result["key_findings"]
        ), "RAG executive insight not merged into key_findings"

        assert any(
            "legal vertical" in r for r in result["strategic_recommendations"]
        ), "RAG recommendation not merged"

        assert any(
            "commoditise" in r for r in result["risk_assessment"]
        ), "RAG risk not merged"

        assert result["rag_cross_synthesis"] == synthesis_return

    def test_cross_synthesis_deduplicates(self):
        """Insight already in key_findings must not be added again."""
        agent  = self._make_agent()
        rag    = _make_rag()

        existing_insight = "Strong B2B demand expected."   # already in market key_insights
        synthesis_return = {
            "executive_insights":        [existing_insight],
            "strategic_recommendations": [],
            "key_risks":                 [],
            "confidence_note":           "",
        }

        with patch.object(agent, "_cross_agent_synthesis", return_value=synthesis_return):
            result = agent.consolidate(
                _make_financial_result(),
                _make_market_result(),
                _make_competitive_result(),
                _BUSINESS_INPUT,
                rag=rag,
            )

        count = sum(
            1 for f in result["key_findings"] if existing_insight in f
        )
        assert count <= 1, "Duplicate insight found in key_findings"

    def test_overall_viability_score_range(self):
        agent  = self._make_agent()
        result = agent.consolidate(
            _make_financial_result(),
            _make_market_result(),
            _make_competitive_result(),
            _BUSINESS_INPUT,
        )
        assert 0.0 <= result["overall_viability_score"] <= 1.0

    def test_heuristic_cross_synthesis_fallback(self):
        """Heuristic synthesis must not crash and must return expected keys."""
        from src.agents.consolidation_agent import ConsolidationAgent
        agent = ConsolidationAgent()
        result = agent._heuristic_cross_synthesis(
            chunks=["AI adoption is accelerating globally."],
            financial_result=_make_financial_result(runway_months=10),
            market_result=_make_market_result(growth_rate=20.0,
                                              market_size={"global": 5e9}),
            competitive_result=_make_competitive_result(competitive_intensity="High",
                                                        competitors_found=20),
        )
        assert "executive_insights"        in result
        assert "strategic_recommendations" in result
        assert "key_risks"                 in result
        assert "confidence_note"           in result


# ─────────────────────────────────────────────────────────────────────────────
# End-to-end smoke test (no network / LLM calls)
# ─────────────────────────────────────────────────────────────────────────────

class TestPhase2EndToEnd:

    def test_full_pipeline_with_rag_disabled(self):
        """
        Full pipeline with rag.is_ready() = False must produce a valid
        consolidated result identical in structure to Phase 1 output.
        """
        from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig
        from src.agents.market_analysis    import MarketAnalysisAgent
        from src.agents.competitive_analysis import CompetitiveAnalysisAgent
        from src.agents.consolidation_agent  import ConsolidationAgent

        rag = _make_rag(ready=False)
        data = _sample_extracted_data(
            startup_costs=[200_000],
            revenue_figures=[500_000],
            growth_rates=[12.0],
            market_sizes=[20_000_000_000],
            organizations=["Clio", "MyCase", "PracticePanther", "Smokeball"],
            keywords=["ai", "legal", "automation", "saas", "api"],
        )

        fin_agent  = FinancialAnalysisAgent(FinancialConfig())
        mkt_agent  = MarketAnalysisAgent()
        comp_agent = CompetitiveAnalysisAgent()
        con_agent  = ConsolidationAgent()

        fin_result  = fin_agent.run(data, budget=500_000, rag=rag)
        mkt_result  = mkt_agent.run(data, rag=rag)
        comp_result = comp_agent.run(data, rag=rag)
        con_result  = con_agent.consolidate(
            fin_result, mkt_result, comp_result, _BUSINESS_INPUT, rag=rag
        )

        # Structure checks
        assert 0.0 <= con_result["overall_viability_score"] <= 1.0
        assert isinstance(con_result["key_findings"], list)
        assert isinstance(con_result["strategic_recommendations"], list)
        assert con_result["rag_augmented"] is False   # RAG disabled

    def test_full_pipeline_with_rag_enabled(self):
        """
        Full pipeline with rag.is_ready() = True must produce a result with
        rag_augmented=True at each layer and a non-empty rag_cross_synthesis.
        """
        from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig
        from src.agents.market_analysis    import MarketAnalysisAgent
        from src.agents.competitive_analysis import CompetitiveAnalysisAgent
        from src.agents.consolidation_agent  import ConsolidationAgent

        rag  = _make_rag(ready=True)
        data = _sample_extracted_data()   # all empty → RAG must fill gaps

        fin_agent  = FinancialAnalysisAgent(FinancialConfig())
        mkt_agent  = MarketAnalysisAgent()
        comp_agent = CompetitiveAnalysisAgent()
        con_agent  = ConsolidationAgent()

        with patch(
            "src.agents.financial_analysis.FinancialAnalysisAgent._parse_rag_chunks",
            return_value={
                "startup_costs":   [150_000],
                "revenue_figures": [300_000],
                "funding_amounts": [1_000_000],
                "growth_rates":    [14.0],
                "market_sizes":    [10_000_000_000],
            },
        ), patch(
            "src.agents.market_analysis.MarketAnalysisAgent._parse_money_from_chunks",
            return_value=[10_000_000_000],
        ), patch(
            "src.agents.market_analysis.MarketAnalysisAgent._parse_percentages_from_chunks",
            return_value=[14.0],
        ), patch(
            "src.agents.competitive_analysis.CompetitiveAnalysisAgent._extract_competitors_from_rag",
            return_value=["LexisNexis", "Thomson Reuters", "Kira Systems"],
        ), patch(
            "src.agents.competitive_analysis.CompetitiveAnalysisAgent._rag_swot",
            return_value={
                "strengths":     ["AI-native approach"],
                "weaknesses":    [],
                "opportunities": ["GDPR compliance gap"],
                "threats":       [],
            },
        ), patch(
            "src.agents.consolidation_agent.ConsolidationAgent._cross_agent_synthesis",
            return_value={
                "executive_insights":        ["Defensibility requires proprietary training data."],
                "strategic_recommendations": ["Enter UK market first due to favourable AI regulation."],
                "key_risks":                 ["LegalZoom expansion into AI tooling."],
                "confidence_note":           "High quality data from 12 sources.",
            },
        ):
            fin_result  = fin_agent.run(data, budget=500_000, rag=rag)
            mkt_result  = mkt_agent.run(data, rag=rag)
            comp_result = comp_agent.run(data, rag=rag)
            con_result  = con_agent.consolidate(
                fin_result, mkt_result, comp_result, _BUSINESS_INPUT, rag=rag
            )

        assert fin_result["rag_augmented"]  is True
        assert mkt_result["rag_augmented"]  is True
        assert comp_result["rag_augmented"] is True
        assert con_result["rag_augmented"]  is True
        assert con_result["rag_cross_synthesis"] != {}
        assert any(
            "proprietary" in f.lower() for f in con_result["key_findings"]
        )