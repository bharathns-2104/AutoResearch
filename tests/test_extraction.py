import pytest
from agents.extraction_engine import ExtractionEngine


@pytest.fixture
def engine():
    return ExtractionEngine()


def test_currency_normalization(engine):
    assert engine.normalize_currency("$2.5M") == 2500000
    assert engine.normalize_currency("$50k") == 50000
    assert engine.normalize_currency("$1B") == 1000000000


def test_contextual_financial_extraction(engine):
    text = """
    The startup cost is estimated at $50,000.
    The company raised $5M in seed funding.
    Market size was valued at $15B in 2026.
    Growth rate expected to reach 8.5% CAGR.
    """

    result = engine.extract_contextual_financials(text)

    assert 50000 in result["startup_costs"]
    assert 5000000 in result["funding_amounts"]
    assert 15000000000 in result["market_sizes"]
    assert 8.5 in result["growth_rates"]


def test_entity_normalization(engine):
    org1 = engine.normalize_org_name("Apple Inc.")
    org2 = engine.normalize_org_name("Apple LLC")
    assert org1 == "apple"
    assert org2 == "apple"


def test_keyword_extraction(engine):
    text = "Electric vehicles are transforming the automotive industry."
    keywords = engine.extract_keywords(text)
    assert "electric" in keywords
    assert "vehicles" in keywords
