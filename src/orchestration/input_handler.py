import json
from pathlib import Path
from .logger import setup_logger

logger = setup_logger()

CACHE_PATH = Path("data/cache/last_input.json")


def save_structured_input(data):
    """
    Saves structured intake data to cache for inspection and reuse.
    """

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CACHE_PATH, "w") as f:
        json.dump(data, f, indent=4)

    logger.info("Structured input saved to cache")
