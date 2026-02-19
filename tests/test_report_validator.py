import pytest
from src.output.report_validator import ReportValidator

VALID_DATA = {
    "overall_viability_score": 0.72,
    "overall_rating": "Strong",
    "financial_score": 0.75,
    "market_score": 0.80,
    "competitive_score": 0.60,
    "aggregated_risks": [],
    "final_recommendations": ["Proceed."],
    "executive_summary": "Strong outlook.",
    "decision": "Proceed"
}

def test_valid_data_passes():
    validator = ReportValidator()
    validator.validate(VALID_DATA)  # should not raise


def test_missing_field_raises():
    validator = ReportValidator()
    bad_data = {k: v for k, v in VALID_DATA.items() if k != "decision"}
    with pytest.raises(ValueError, match="Missing required field"):
        validator.validate(bad_data)


def test_score_out_of_range_raises():
    validator = ReportValidator()
    bad_data = {**VALID_DATA, "overall_viability_score": 1.5}
    with pytest.raises(ValueError, match="must be between 0 and 1"):
        validator.validate(bad_data)


def test_wrong_type_raises():
    validator = ReportValidator()
    bad_data = {**VALID_DATA, "overall_rating": 99}
    with pytest.raises(ValueError, match="must be of type str"):
        validator.validate(bad_data)