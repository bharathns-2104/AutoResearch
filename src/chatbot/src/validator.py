# chatbot/validator.py

import re

MIN_WORDS = 10
REQUIRED_KEYWORDS = [
    "app", "platform", "service", "product", "software",
    "marketplace", "tool", "system"
]

BAD_PATTERNS = [
    r"^[a-zA-Z]{1,3}$",     # very short words
    r"^[^a-zA-Z]+$",       # only symbols
    r"(asdf|qwerty|zxcv)"  # gibberish
]

def validate_idea(text):
    text = text.strip().lower()

    # Length check
    if len(text.split()) < MIN_WORDS:
        return False, "too_short"

    # Gibberish / nonsense check
    for pattern in BAD_PATTERNS:
        if re.search(pattern, text):
            return False, "nonsense"

    # Keyword check
    if not any(keyword in text for keyword in REQUIRED_KEYWORDS):
        return False, "missing_keywords"

    return True, "valid"
