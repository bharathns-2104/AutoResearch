import json
from src.orchestration.logger import setup_logger

logger = setup_logger()


def load_config(path="config/config.json"):
    try:
        with open(path, "r") as f:
            config = json.load(f)
            logger.info("Configuration loaded successfully")
            return config

    except FileNotFoundError:
        logger.error(f"Config file not found at {path}")
        return {}

    except json.JSONDecodeError:
        logger.error("Config file is not valid JSON")
        return {}

    except Exception as e:
        logger.error(f"Unexpected error while loading config: {str(e)}")
        return {}
