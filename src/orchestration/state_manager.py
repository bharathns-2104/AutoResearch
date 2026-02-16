from enum import Enum
from threading import Lock
import json
from pathlib import Path

from .logger import setup_logger

logger = setup_logger()


class SystemState(Enum):
    INITIALIZED = "initialized"
    INPUT_RECEIVED = "input_received"
    SEARCHING = "searching"
    SCRAPING = "scraping"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    CONSOLIDATING = "consolidating"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    ERROR = "error"


class StateManager:
    _instance = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.current_state = SystemState.INITIALIZED
        self.progress = 0
        self.data = {}
        self.errors = []
        logger.info("StateManager initialized")

    def update_state(self, new_state: SystemState):
        self.current_state = new_state
        logger.info(f"State updated to {new_state.value}")

    def update_progress(self, value: int):
        self.progress = value
        logger.info(f"Progress updated to {value}%")

    def add_data(self, key, value):
        self.data[key] = value
        logger.debug(f"Data added under key '{key}'")

    def add_error(self, error_message: str):
        self.errors.append(error_message)
        logger.error(f"Error recorded: {error_message}")
        self.update_state(SystemState.ERROR)

    def get_snapshot(self):
        return {
            "state": self.current_state.value,
            "progress": self.progress,
            "data": self.data,
            "errors": self.errors,
        }

    def dump_to_file(self, path="logs/state_snapshot.json"):
        snapshot = self.get_snapshot()
        Path("logs").mkdir(exist_ok=True)
        with open(path, "w") as f:
            json.dump(snapshot, f, indent=4)
        logger.info("State snapshot dumped to file")
