from src.agents.market_analysis import MarketAnalysisAgent


def test_market_opportunity_positive():

    extracted_data = {
        "currencies": [
            {"value": 20000000000, "context": "global market size"}
        ],
        "percentages": [
            {"value": 12, "context": "CAGR growth"}
        ],
        "keywords": [
            "rapid growth",
            "market expansion",
            "strong demand"
        ]
    }

    agent = MarketAnalysisAgent()
    result = agent.run(extracted_data)

    assert result["opportunity_score"] >= 0.5
    assert result["sentiment"]["label"] == "Positive"
