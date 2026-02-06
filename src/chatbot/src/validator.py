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
