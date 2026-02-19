from src.output.data_mapper import ReportDataMapper

sample_json = {
    "overall_viability_score": 0.72,
    "overall_rating": "Strong",
    "financial_score": 0.75,
    "market_score": 0.80,
    "competitive_score": 0.60,
    "aggregated_risks": [
        {"category": "Financial", "severity": "Low", "message": "Runway is adequate."}
    ],
    "final_recommendations": ["Proceed with expansion."],
    "executive_summary": "Strong viability across all domains.",
    "decision": "Proceed"
}
def test_mapping_structure():
    mapper = ReportDataMapper()
    result = mapper.map(sample_json)
    assert "executive_summary" in result
    assert "score_overview" in result
