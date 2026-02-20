"""
slot_extractor.py

Extracts slot values from user message using
regex + spaCy NER + keyword mapping.

FIXES:
- Two-mode budget extraction: targeted (no currency signal needed) vs generic (strict)
- Handles budget misspellings: dollors, dollers, dollar, bucks
- Expanded INDUSTRY_KEYWORDS (13 categories including Automotive)
- Direct industry name matching (user can type the industry name directly)
- business_idea fallback only fires when NOTHING else was detected
- Targeted extraction returns early, preventing cross-slot contamination
"""

import re
from typing import Dict, Any

import spacy

from .slot_schema import SLOTS

nlp = spacy.load("en_core_web_sm")


# ==========================================================
# Industry Keyword Mapping
# ==========================================================

INDUSTRY_KEYWORDS = {
    "SaaS": [
        "software", "saas", "platform", "cloud", "subscription",
        "b2b software", "crm", "erp", "developer tool", "api",
        "it services", "technology", "tech", "it"
    ],
    "FinTech": [
        "finance", "fintech", "payments", "banking", "financial",
        "insurance", "insurtech", "lending", "investment", "crypto",
        "blockchain", "accounting", "payroll", "wealth management"
    ],
    "HealthTech": [
        "health", "medical", "hospital", "clinic", "healthcare",
        "pharma", "biotech", "telemedicine", "wellness", "fitness",
        "mental health", "diagnostics", "medtech"
    ],
    "EdTech": [
        "education", "learning", "school", "course", "edtech",
        "tutoring", "university", "e-learning", "training", "upskilling",
        "online education", "mooc"
    ],
    "E-commerce": [
        "ecommerce", "e-commerce", "store", "marketplace", "retail",
        "online shop", "d2c", "direct to consumer", "shopping",
        "fashion", "apparel", "consumer goods"
    ],
    "Logistics": [
        "logistics", "supply chain", "shipping", "delivery", "freight",
        "warehousing", "transport", "fleet", "last mile"
    ],
    "Real Estate": [
        "real estate", "proptech", "property", "housing", "rental",
        "mortgage", "construction", "architecture"
    ],
    "Manufacturing": [
        "manufacturing", "factory", "production", "industrial",
        "hardware", "iot", "automation", "robotics", "3d printing"
    ],
    "AgriTech": [
        "agriculture", "farming", "agritech", "agtech", "crop",
        "livestock", "food tech", "foodtech", "food delivery"
    ],
    "Media & Entertainment": [
        "media", "entertainment", "gaming", "game", "streaming",
        "content", "music", "video", "podcast", "social media"
    ],
    "Travel & Hospitality": [
        "travel", "tourism", "hotel", "hospitality", "booking",
        "flights", "vacation", "airbnb"
    ],
    "Legal Tech": [
        "legal", "legaltech", "law", "compliance", "contract"
    ],
    "HR Tech": [
        "hr", "human resources", "recruitment", "hiring", "payroll",
        "hrtech", "workforce"
    ],
    "Automotive": [
        "automotive", "automobile", "car", "vehicle", "ev",
        "electric vehicle", "mobility", "fleet management", "auto"
    ],
}

INDUSTRY_DIRECT_NAMES = {name.lower(): name for name in INDUSTRY_KEYWORDS}


# ==========================================================
# Main Extraction Function
# ==========================================================

def extract_slots_from_text(text: str, current_slot: str = None) -> Dict[str, Any]:
    """
    Extract slot values from user input.

    When current_slot is provided, only that slot's extractor runs
    and we return early — this prevents answers to one question from
    accidentally filling a different slot.
    """
    extracted = {}
    doc = nlp(text.lower())

    # ------ Targeted extraction (one slot at a time) ------

    if current_slot == "industry":
        industry = infer_industry(text)
        if industry:
            extracted["industry"] = industry
        else:
            # Accept whatever the user typed as the industry name
            cleaned = text.strip().strip(".,!?").title()
            if cleaned:
                extracted["industry"] = cleaned
        return extracted

    if current_slot == "budget":
        budget = extract_budget(text, targeted=True)   # no currency signal needed
        if budget:
            extracted["budget"] = budget
        return extracted

    if current_slot == "timeline_months":
        timeline = extract_timeline(text)
        if timeline:
            extracted["timeline_months"] = timeline
        return extracted

    if current_slot == "team_size":
        team_size = extract_team_size(text)
        if team_size:
            extracted["team_size"] = team_size
        return extracted

    if current_slot == "target_market":
        target_market = extract_target_market(doc)
        if target_market:
            extracted["target_market"] = target_market
        else:
            cleaned = text.strip().strip(".,!?")
            if cleaned:
                extracted["target_market"] = cleaned
        return extracted

    if current_slot == "business_idea":
        extracted["business_idea"] = text.strip()
        return extracted

    # ------ Generic extraction (first turn / no context) ------

    budget = extract_budget(text, targeted=False)   # currency signal required
    if budget:
        extracted["budget"] = budget

    timeline = extract_timeline(text)
    if timeline:
        extracted["timeline_months"] = timeline

    team_size = extract_team_size(text)
    if team_size:
        extracted["team_size"] = team_size

    target_market = extract_target_market(doc)
    if target_market:
        extracted["target_market"] = target_market

    industry = infer_industry(text)
    if industry:
        extracted["industry"] = industry

    if not extracted:
        extracted["business_idea"] = text.strip()

    return extracted


# ==========================================================
# Budget Extraction — two-mode
# ==========================================================

def extract_budget(text: str, targeted: bool = False):
    """
    targeted=True  → currency signal optional (user is answering budget question).
    targeted=False → currency signal required (generic pass, avoid false positives).

    Currency signals handled (including common misspellings):
        $  |  usd  |  dollars  |  dollar  |  dollors  |  dollers  |  bucks

    Accepted formats in targeted mode:
        500000          500,000         500k            2 million
        $2m             500000 dollors  USD 500000      my budget is 500000
    """
    text_lower = text.lower().strip()
    sig = r"(?:\$|usd|dollars?|dollors?|dollers?|bucks?)"

    if targeted:
        pattern = (
            r"(?:" + sig + r")?\s?"
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s?"
            r"(?:" + sig + r")?\s?"
            r"(k|m|million|billion)?"
        )
    else:
        pattern = (
            sig + r"\s?"
            r"(\d+(?:,\d{3})*(?:\.\d+)?)\s?"
            r"(k|m|million|billion)?"
        )

    match = re.search(pattern, text_lower)
    if not match:
        return None

    amount_str = match.group(1)
    multiplier = match.group(2)

    if not amount_str:
        return None

    try:
        amount = float(amount_str.replace(",", ""))
    except ValueError:
        return None

    if multiplier:
        m = multiplier.strip().lower()
        if m == "k":
            amount *= 1_000
        elif m in ("m", "million"):
            amount *= 1_000_000
        elif m == "billion":
            amount *= 1_000_000_000

    # Enforce slot constraints
    if amount < 1_000 or amount > 100_000_000:
        return None

    return {"amount": amount, "currency": "USD"}


# ==========================================================
# Timeline Extraction
# ==========================================================

def extract_timeline(text: str):
    match = re.search(r"(\d+)\s?(months|month|years|year)", text.lower())
    if not match:
        return None
    value = int(match.group(1))
    if "year" in match.group(2):
        value *= 12
    return value


# ==========================================================
# Team Size Extraction
# ==========================================================

def extract_team_size(text: str):
    pattern = (
        r"(team of|we are|we have|members?|people)\s?(\d+)"
        r"|(\d+)\s?(members?|people|founders?|co-?founders?)"
    )
    match = re.search(pattern, text.lower())
    if not match:
        bare = re.fullmatch(r"\s*(\d+)\s*", text.strip())
        if bare:
            val = int(bare.group(1))
            if 1 <= val <= 100:
                return val
        return None
    num_str = match.group(2) or match.group(3)
    return int(num_str) if num_str else None


# ==========================================================
# Target Market Extraction
# ==========================================================

def extract_target_market(doc):
    for ent in doc.ents:
        if ent.label_ in ["GPE", "LOC", "NORP"]:
            return ent.text
    return None


# ==========================================================
# Industry Inference
# ==========================================================

def infer_industry(text: str):
    text_lower = text.strip().lower()
    cleaned = text_lower.strip(".,!? ")

    # Direct name match first
    if cleaned in INDUSTRY_DIRECT_NAMES:
        return INDUSTRY_DIRECT_NAMES[cleaned]

    # Keyword substring match
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in text_lower:
                return industry

    return None


# ==========================================================
# Business Idea Extraction
# ==========================================================

def extract_business_idea(text: str):
    return text.strip()