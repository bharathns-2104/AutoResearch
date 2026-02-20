"""
dialog_engine.py

Controls the conversational slot-filling process.

FIXES APPLIED:
- Passes current_slot context to extract_slots_from_text() so extraction
  is targeted per-slot, eliminating cross-contamination (e.g. industry
  answer being stored as business_idea).
- Added get_opening_message() for web_app.py to display on first load.
- Handles the case where extraction returns nothing for the current slot
  with a clearer re-prompt (instead of a generic "couldn't detect" message).
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
    # Opening Message (call once on app load)
    # ==========================================================

    def get_opening_message(self) -> str:
        return (
            "Hi! I'm AutoResearch. I'll help you analyse your business idea. "
            "Let's start — could you briefly describe your business idea?"
        )

    # ==========================================================
    # Public Interface
    # ==========================================================

    def process_message(self, user_message: str) -> Dict[str, Any]:

        # Determine which slot we're currently collecting BEFORE extraction,
        # so we can pass it as context to the extractor.
        current_slot = self.state.get_next_required_slot()

        # 1. Extract slot values — targeted to the current slot
        extracted = extract_slots_from_text(user_message, current_slot=current_slot)

        # 2. If nothing was extracted at all → re-prompt for current slot
        if not extracted:
            return {
                "status": "collecting",
                "response": (
                    f"I didn't quite catch that. "
                    f"{self._generate_prompt_for_slot(current_slot)}"
                ),
                "data": None
            }

        # 3. Attempt to update slots
        update_results = self.state.bulk_update(extracted)

        # 4. Detect failed validations
        failed_slots = [
            slot for slot, success in update_results.items()
            if not success
        ]

        # If the current slot specifically failed validation, show its error
        if current_slot in failed_slots:
            return {
                "status": "collecting",
                "response": self._generate_validation_error(current_slot),
                "data": None
            }

        # If other slots failed but current slot is now filled, continue
        if failed_slots:
            # Log but don't block — the important slot was filled
            pass

        # 5. Check completion
        if self.state.is_complete():
            final_data = convert_to_pipeline_format(
                self.state.get_filled_slots()
            )
            return {
                "status": "complete",
                "response": "Perfect! I have everything I need. Starting analysis...",
                "data": final_data
            }

        # 6. Continue dialog — ask for next unfilled slot
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
            "business_idea": (
                "Could you describe your business idea?"
            ),
            "industry": (
                "What industry does your idea belong to? "
                "(e.g. SaaS, FinTech, HealthTech, E-commerce, Logistics, "
                "Manufacturing, EdTech, or any other)"
            ),
            "budget": (
                "What is your available budget? "
                "(e.g. $50,000 or $2 million)"
            ),
            "timeline_months": (
                "What is your expected timeline? "
                "(e.g. '12 months' or '2 years')"
            ),
            "target_market": (
                "Who is your target market? "
                "(e.g. 'US small businesses' or 'India')"
            ),
            "team_size": (
                "How many team members do you have? "
                "(optional — press Enter to skip)"
            ),
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
            "budget": (
                "The budget amount seems outside the expected range ($1,000 – $100M). "
                "Please provide a value like '$50,000' or '$2 million'."
            ),
            "timeline_months": (
                "The timeline must be between 1 and 60 months. "
                "Please re-enter — e.g. '12 months' or '1 year'."
            ),
            "team_size": (
                "Team size must be between 1 and 100 members. "
                "Please enter a number like '5'."
            ),
            "industry": (
                "I couldn't classify the industry. Could you clarify? "
                "(e.g. SaaS, FinTech, HealthTech, E-commerce, Logistics)"
            ),
            "target_market": (
                "Please specify a clear market — e.g. 'US small businesses', "
                "'India', or 'European consumers'."
            ),
        }

        return error_templates.get(
            slot_name,
            f"The value provided for '{slot_name}' is invalid. Please try again."
        )