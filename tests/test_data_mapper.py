def test_mapping_structure():
    mapper = ReportDataMapper()
    result = mapper.map(sample_json)
    assert "executive_summary" in result
    assert "score_overview" in result
