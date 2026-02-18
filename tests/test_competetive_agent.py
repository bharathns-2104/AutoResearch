from src.agents.competitive_analysis import CompetitiveAnalysisAgent


def test_competitive_intensity_medium():

    extracted_data = {
        "entities": [
            {"text": "CompanyA", "label": "ORG"},
            {"text": "CompanyB", "label": "ORG"},
            {"text": "CompanyC", "label": "ORG"},
            {"text": "CompanyD", "label": "ORG"},
            {"text": "CompanyE", "label": "ORG"},
        ],
        "keywords": ["AI automation", "mobile app", "API integration"]
    }

    agent = CompetitiveAnalysisAgent()
    result = agent.run(extracted_data)

    assert result["competitive_intensity"] == "Medium"
    assert result["competitors_found"] == 5
