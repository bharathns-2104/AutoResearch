"""
dialog_state.py

Manages the state of slot-filling dialog for AutoResearch.
This module does NOT replace the global system StateManager.
It only tracks intake-level conversational progress.
"""

from typing import Dict, Any, List
from copy import deepcopy

from .slot_schema import (
    SLOTS,
    get_required_slots,
    validate_slot_value,
)


class DialogState:
    """
    Tracks dialog progress during slot filling.
    """

    def __init__(self):
        # Stores validated slot values
        self.filled_slots: Dict[str, Any] = {}

        # Keeps history of updates (optional but useful)
        self.history: List[Dict[str, Any]] = []

        self.status: str = "collecting"  # collecting | complete

    # ==========================================================
    # Core Slot Operations
    # ==========================================================

    def update_slot(self, slot_name: str, value: Any) -> bool:
        """
        Attempts to update a slot with validation.
        Returns True if successful, False otherwise.
        """

        if slot_name not in SLOTS:
            return False

        if not validate_slot_value(slot_name, value):
            return False

        self.filled_slots[slot_name] = value
        self._record_history(slot_name, value)
        self._check_completion()

        return True

    def bulk_update(self, extracted_data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Update multiple slots at once (for NLP multi-entity extraction).
        Returns dict of slot_name -> success status.
        """

        results = {}

        for slot_name, value in extracted_data.items():
            results[slot_name] = self.update_slot(slot_name, value)

        return results

    def get_filled_slots(self) -> Dict[str, Any]:
        return deepcopy(self.filled_slots)

    def get_unfilled_required_slots(self) -> List[str]:
        required = get_required_slots()
        return [slot for slot in required if slot not in self.filled_slots]

    def is_complete(self) -> bool:
        return self.status == "complete"

    # ==========================================================
    # Slot Correction / Override
    # ==========================================================

    def overwrite_slot(self, slot_name: str, value: Any) -> bool:
        """
        Allows user to change previously filled slot.
        """

        if slot_name not in SLOTS:
            return False

        if not validate_slot_value(slot_name, value):
            return False

        self.filled_slots[slot_name] = value
        self._record_history(slot_name, value)
        self._check_completion()

        return True

    # ==========================================================
    # Prompting Logic Support
    # ==========================================================

    def get_next_required_slot(self) -> str:
        """
        Returns the next required slot that is not filled.
        """
        unfilled = self.get_unfilled_required_slots()
        return unfilled[0] if unfilled else ""

    def get_progress_summary(self) -> Dict[str, Any]:
        """
        Returns lightweight progress status for UI.
        """
        return {
            "filled": list(self.filled_slots.keys()),
            "remaining_required": self.get_unfilled_required_slots(),
            "status": self.status,
        }

    # ==========================================================
    # Internal Helpers
    # ==========================================================

    def _check_completion(self):
        if not self.get_unfilled_required_slots():
            self.status = "complete"
        else:
            self.status = "collecting"

    def _record_history(self, slot_name: str, value: Any):
        self.history.append({
            "slot": slot_name,
            "value": value
        })