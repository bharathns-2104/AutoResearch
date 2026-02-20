"""
slot_schema.py

Defines the formal slot schema for the AutoResearch
slot-filling conversational intake system.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ==========================================================
# Slot Model
# ==========================================================

@dataclass
class Slot:
    name: str
    required: bool
    data_type: str
    description: str
    constraints: Dict[str, Any] = field(default_factory=dict)


# ==========================================================
# Slot Definitions
# ==========================================================

SLOTS: Dict[str, Slot] = {

    "business_idea": Slot(
        name="business_idea",
        required=True,
        data_type="text",
        description="Core concept of the business idea"
    ),

    "industry": Slot(
        name="industry",
        required=True,
        data_type="inferred_category",
        description="Industry extracted from user input"
    ),

    "budget": Slot(
        name="budget",
        required=True,
        data_type="currency_object",
        description="Initial available budget",
        constraints={
            "min_value": 1000,
            "max_value": 100_000_000,
            "supported_currencies": ["USD"],
            "default_currency": "USD"
        }
    ),

    "timeline_months": Slot(
        name="timeline_months",
        required=True,
        data_type="integer",
        description="Project timeline in months",
        constraints={
            "min_value": 1,
            "max_value": 60
        }
    ),

    "target_market": Slot(
        name="target_market",
        required=True,
        data_type="text",
        description="Target geographic or demographic market"
    ),

    "team_size": Slot(
        name="team_size",
        required=False,                  # optional — user may skip
        data_type="integer",
        description="Number of team members",
        constraints={
            "min_value": 1,
            "max_value": 100
        }
    )
}


# ==========================================================
# Slot Access Utilities
# ==========================================================

def get_required_slots() -> List[str]:
    return [slot.name for slot in SLOTS.values() if slot.required]


def get_optional_slots() -> List[str]:
    return [slot.name for slot in SLOTS.values() if not slot.required]


def get_all_slots() -> List[str]:
    return list(SLOTS.keys())


def get_slot(name: str) -> Optional[Slot]:
    return SLOTS.get(name)


# ==========================================================
# Validation Utilities
# ==========================================================

def validate_numeric(value: float, slot: Slot) -> bool:
    min_val = slot.constraints.get("min_value")
    max_val = slot.constraints.get("max_value")
    if min_val is not None and value < min_val:
        return False
    if max_val is not None and value > max_val:
        return False
    return True


def validate_currency_object(value: Dict[str, Any], slot: Slot) -> bool:
    if not isinstance(value, dict):
        return False
    amount = value.get("amount")
    currency = value.get("currency")
    if amount is None or currency is None:
        return False
    if not isinstance(amount, (int, float)):
        return False
    if currency not in slot.constraints.get("supported_currencies", []):
        return False
    return validate_numeric(amount, slot)


def validate_slot_value(slot_name: str, value: Any) -> bool:
    slot = get_slot(slot_name)
    if not slot:
        return False

    if slot.data_type == "integer":
        if not isinstance(value, int):
            return False
        return validate_numeric(value, slot)

    if slot.data_type == "currency_object":
        return validate_currency_object(value, slot)

    if slot.data_type in ["text", "inferred_category"]:
        if value is None:
            return False
        if not isinstance(value, str):
            value = str(value)
        return len(value.strip()) > 0

    # FIX: unknown data_type should fail, not silently pass
    return False


# ==========================================================
# Output Compatibility Helper
# ==========================================================

def convert_to_pipeline_format(filled_slots: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts dialog slot data into the original Intake Agent JSON format.
    Ensures backward compatibility with all downstream agents.

    FIX: Always includes all fields with safe defaults so IntakeAgent
    never hits a KeyError on optional slots like team_size.
    """
    output = filled_slots.copy()

    # Convert currency_object → numeric budget value
    if "budget" in output and isinstance(output["budget"], dict):
        output["budget"] = output["budget"].get("amount", 0)

    # Guarantee all fields exist with defaults — prevents KeyError in IntakeAgent
    output.setdefault("industry", "Unknown")
    output.setdefault("team_size", 1)          # FIX: optional slot default
    output.setdefault("target_market", "General")
    output.setdefault("timeline_months", 12)
    output.setdefault("budget", 0)

    return output