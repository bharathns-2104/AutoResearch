"""
slot_extractor.py

Extracts slot values from user message using
regex + spaCy NER + keyword mapping.

This module does NOT update DialogState directly.
It only returns extracted slot-value pairs.
"""

import re
from typing import Dict, Any

import spacy

from .slot_schema import SLOTS

# Load spaCy model once
nlp = spacy.load("en_core_web_sm")


# ==========================================================
# Industry Keyword Mapping
# ==========================================================

INDUSTRY_KEYWORDS = {
    "SaaS": ["software", "saas", "platform", "cloud"],
    "FinTech": ["finance", "fintech", "payments", "banking"],
    "HealthTech": ["health", "medical", "hospital", "clinic"],
    "EdTech": ["education", "learning", "school", "course"],
    "E-commerce": ["ecommerce", "store", "marketplace", "retail"],
}


# ==========================================================
# Main Extraction Function
# ==========================================================

def extract_slots_from_text(text: str) -> Dict[str, Any]:
    """
    Extract possible slot values from user input.
    Returns dictionary: {slot_name: value}
    """

    extracted = {}

    doc = nlp(text.lower())

    # ------------------------------------------------------
    # 1. Extract Budget (Currency)
    # ------------------------------------------------------

    budget = extract_budget(text)
    if budget:
        extracted["budget"] = budget

    # ------------------------------------------------------
    # 2. Extract Timeline
    # ------------------------------------------------------

    timeline = extract_timeline(text)
    if timeline:
        extracted["timeline_months"] = timeline

    # ------------------------------------------------------
    # 3. Extract Team Size
    # ------------------------------------------------------

    team_size = extract_team_size(text)
    if team_size:
        extracted["team_size"] = team_size

    # ------------------------------------------------------
    # 4. Extract Target Market (GPE / Location)
    # ------------------------------------------------------

    target_market = extract_target_market(doc)
    if target_market:
        extracted["target_market"] = target_market

    # ------------------------------------------------------
    # 5. Infer Industry
    # ------------------------------------------------------

    industry = infer_industry(text)
    if industry:
        extracted["industry"] = industry

    # ------------------------------------------------------
    # 6. Extract Business Idea (Fallback)
    # ------------------------------------------------------

    if "business_idea" not in extracted:
        extracted["business_idea"] = extract_business_idea(text)

    return extracted


# ==========================================================
# Budget Extraction
# ==========================================================

def extract_budget(text: str):

    currency_pattern = r"(\$|usd|dollars)?\s?(\d+(?:,\d{3})*(?:\.\d+)?)(\s?(k|m|million|billion))?"

    match = re.search(currency_pattern, text.lower())

    if not match:
        return None

    amount = match.group(2).replace(",", "")
    multiplier = match.group(4)

    try:
        amount = float(amount)
    except:
        return None

    if multiplier:
        if multiplier in ["k"]:
            amount *= 1_000
        elif multiplier in ["m", "million"]:
            amount *= 1_000_000
        elif multiplier in ["billion"]:
            amount *= 1_000_000_000

    return {
        "amount": amount,
        "currency": "USD"
    }


# ==========================================================
# Timeline Extraction
# ==========================================================

def extract_timeline(text: str):

    timeline_pattern = r"(\d+)\s?(months|month|years|year)"

    match = re.search(timeline_pattern, text.lower())

    if not match:
        return None

    value = int(match.group(1))
    unit = match.group(2)

    if "year" in unit:
        value *= 12

    return value


# ==========================================================
# Team Size Extraction
# ==========================================================

def extract_team_size(text: str):

    team_pattern = r"(team of|we are|we have)\s?(\d+)"

    match = re.search(team_pattern, text.lower())

    if not match:
        return None

    return int(match.group(2))


# ==========================================================
# Target Market Extraction
# ==========================================================

def extract_target_market(doc):

    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC"]:
            return ent.text

    return None


# ==========================================================
# Industry Inference
# ==========================================================

def infer_industry(text: str):

    text = text.lower()

    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text:
                return industry

    return None


# ==========================================================
# Business Idea Extraction
# ==========================================================

def extract_business_idea(text: str):
    """
    Basic fallback: return full text.
    Later can refine to remove detected entities.
    """
    return text.strip()