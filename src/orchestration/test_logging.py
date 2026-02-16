from .logger import setup_logger

logger = setup_logger()

logger.info("AutoResearch system initialized")
logger.debug("Debug mode active")
logger.error("Sample error Message")