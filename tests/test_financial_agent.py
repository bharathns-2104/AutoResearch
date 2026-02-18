from src.agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig


def test_financial_viability_high():

    extracted_data = {
        "currencies": [
            {"value": 50000, "context": "development cost"},
            {"value": 200000, "context": "annual revenue"},
        ],
        "percentages": [
            {"value": 15, "context": "annual growth"},
            {"value": 20, "context": "profit margin"}
        ]
    }

    budget = 150000

    agent = FinancialAnalysisAgent(FinancialConfig())
    result = agent.run(extracted_data, budget)

    assert result["viability_score"] >= 0.5
    assert result["runway_months"] > 0
    assert "metrics" in result
