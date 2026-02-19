import pytest
from src.agents.consolidation_agent import ConsolidationAgent


def test_basic_weighted_score():
    agent = ConsolidationAgent()

    analysis_results = {
        "financial": {"viability_score": 0.8, "runway_months": 18},
        "competitive": {"competitive_intensity": "Medium"},
        "market": {"opportunity_score": 0.7}
    }

    result = agent.run(analysis_results)

    assert "overall_viability_score" in result
    assert 0 <= result["overall_viability_score"] <= 1


def test_missing_agent_data():
    agent = ConsolidationAgent()

    analysis_results = {
        "financial": None,
        "competitive": None,
        "market": None
    }

    result = agent.run(analysis_results)

    assert result["overall_viability_score"] == 0
    assert result["overall_rating"] == "Weak"


def test_risk_penalty_applied():
    agent = ConsolidationAgent()

    analysis_results = {
        "financial": {"viability_score": 0.8, "runway_months": 4},  # High risk
        "competitive": {"competitive_intensity": "High"},
        "market": {"opportunity_score": 0.8}
    }

    result = agent.run(analysis_results)

    assert result["metadata"]["risk_penalty_applied"] > 0
