"""
dialog_engine.py

Controls the conversational slot-filling process.

This module:
- Uses SlotExtractor
- Updates DialogState
- Determines next question
- Returns final structured data when complete
"""

from typing import Dict, Any

from .dialog_state import DialogState
from .slot_extractor import extract_slots_from_text
from .slot_schema import (
    get_required_slots,
    convert_to_pipeline_format
)


class DialogEngine:

    def __init__(self):
        self.state = DialogState()

    # ==========================================================
    # Public Interface
    # ==========================================================

    def process_message(self, user_message: str) -> Dict[str, Any]:

        # 1. Extract possible slot values
        extracted = extract_slots_from_text(user_message)

        # 2. If nothing extracted → clarify
        if not extracted:
            next_slot = self.state.get_next_required_slot()
            return {
                "status": "collecting",
                "response": f"I couldn't detect relevant information. {self._generate_prompt_for_slot(next_slot)}",
                "data": None
            }

        # 3. Attempt to update slots
        update_results = self.state.bulk_update(extracted)

        # 4. Detect failed validations
        failed_slots = [
            slot for slot, success in update_results.items()
            if not success
        ]

        if failed_slots:
            slot = failed_slots[0]
            return {
                "status": "collecting",
                "response": self._generate_validation_error(slot),
                "data": None
            }

        # 5. Check completion
        if self.state.is_complete():
            final_data = convert_to_pipeline_format(
                self.state.get_filled_slots()
            )

            return {
                "status": "complete",
                "response": "All required information collected. Starting analysis...",
                "data": final_data
            }

        # 6. Continue dialog
        next_slot = self.state.get_next_required_slot()

        return {
            "status": "collecting",
            "response": self._generate_prompt_for_slot(next_slot),
            "data": None
        }
    # ==========================================================
    # Prompt Logic
    # ==========================================================

    def _generate_prompt_for_slot(self, slot_name: str) -> str:
        """
        Generates user-friendly prompt for missing slot.
        """

        prompt_templates = {
            "business_idea": "Could you describe your business idea?",
            "industry": "What industry does your idea belong to?",
            "budget": "What is your available budget?",
            "timeline_months": "What is your expected timeline (in months)?",
            "target_market": "Who is your target market?",
            "team_size": "How many team members do you have?"
        }

        return prompt_templates.get(
            slot_name,
            f"Please provide information for: {slot_name}"
        )

    # ==========================================================
    # Utility
    # ==========================================================

    def get_progress(self):
        """
        Returns progress summary for UI.
        """
        return self.state.get_progress_summary()

    def _generate_validation_error(self, slot_name: str) -> str:

        error_templates = {
            "budget": "The budget amount seems unrealistic. Please provide a value between $1,000 and $100 million.",
            "timeline_months": "The timeline must be between 1 and 60 months. Please re-enter a valid duration.",
            "team_size": "Team size must be between 1 and 100 members.",
            "industry": "I couldn't confidently classify the industry. Could you clarify the domain?",
            "target_market": "Please specify a clear geographic or customer market."
        }

        return error_templates.get(
            slot_name,
            f"The value provided for {slot_name} is invalid. Please try again."
    )