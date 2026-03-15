from enum import Enum
from threading import Lock
import json
from pathlib import Path
from dataclasses import asdict, fields
import dataclasses

from .logger import setup_logger

logger = setup_logger()


class SystemState(Enum):
    INITIALIZED = "initialized"
    INPUT_RECEIVED = "input_received"
    SEARCHING = "searching"
    SCRAPING = "scraping"
    RAG_INDEXING = "rag_indexing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    CONSOLIDATING = "consolidating"
    GENERATING_REPORT = "generating_report"
    COMPLETED = "completed"
    ERROR = "error"


def _safe_serializer(obj):
    """
    JSON serializer for objects not serializable by default json encoder.
    Handles dataclasses (SearchResult, etc.), Enums, and unknown objects.
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return dataclasses.asdict(obj)
    if isinstance(obj, Enum):
        return obj.value
    # Fallback: convert to string so dump never crashes
    return str(obj)


def _make_serializable(obj):
    """
    Recursively convert an object tree into JSON-safe primitives.
    Handles dicts, lists, dataclasses, Enums, and unknown objects.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k.name: _make_serializable(getattr(obj, k.name))
                for k in dataclasses.fields(obj)}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_make_serializable(i) for i in obj]
    # Unknown type: convert to string to avoid crash
    return str(obj)


class StateManager:
    _instance = None
    _lock = Lock()
    # Class-level annotations let Pyre2 recognise instance attributes that are
    # assigned inside _initialize() (called from __new__, invisible to the checker).
    current_state: SystemState
    progress: int
    data: dict
    errors: list

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(StateManager, cls).__new__(cls)
                cls._instance._initialize()
        return cls._instance

    def __init__(self):
        # __init__ is called every time StateManager() is called, but
        # _initialize only ran once (in __new__). We must NOT re-initialize
        # here; this stub just lets type-checkers see the instance attributes.
        if not hasattr(self, "current_state"):
            self._initialize()

    @classmethod
    def reset(cls):
        """Reset singleton instance for testing purposes."""
        with cls._lock:
            cls._instance = None

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
            "state":    self.current_state.value,
            "progress": self.progress,
            # FIX: strip non-serializable objects (SearchResult, RAGManager, etc.)
            # before building the snapshot so dump_to_file never crashes.
            "data":     _make_serializable(self._safe_data_snapshot()),
            "errors":   self.errors,
        }

    def _safe_data_snapshot(self) -> dict:
        """
        Return a copy of self.data with keys that are never JSON-serializable
        (RAGManager instances, threading objects, etc.) replaced by a
        human-readable placeholder string.
        """
        snapshot = {}
        _skip_types_by_key = {"rag", "workflow_thread", "controller"}
        for k, v in self.data.items():
            if k in _skip_types_by_key:
                snapshot[k] = f"<{type(v).__name__} instance — omitted from snapshot>"
            else:
                snapshot[k] = v
        return snapshot

    def dump_to_file(self, path="logs/state_snapshot.json"):
        snapshot = self.get_snapshot()
        Path("logs").mkdir(exist_ok=True)
        with open(path, "w") as f:
            # Use default=_safe_serializer as a final safety net
            json.dump(snapshot, f, indent=4, default=_safe_serializer)
        logger.info("State snapshot dumped to file")