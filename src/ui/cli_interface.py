# src/ui/cli_interface.py

from ..orchestration.logger import setup_logger
from ..orchestration.state_manager import StateManager, SystemState

logger = setup_logger()


def collect_user_input():
    """
    Collect Business Idea Research inputs from user.
    Returns validated structured dictionary.
    """

    state = StateManager()

    print("\n=== Business Idea Research Input ===\n")

    # -------------------------------
    # Business Idea Description
    # -------------------------------
    while True:
        idea = input("Describe your business idea: ").strip()
        if idea:
            break
        print("Business idea description cannot be empty.")

    # -------------------------------
    # Industry (optional)
    # -------------------------------
    industry = input("Industry (optional, press Enter to auto-detect): ").strip()
    if not industry:
        industry = "Unknown"

    # -------------------------------
    # Budget Validation (> 1000)
    # -------------------------------
    while True:
        try:
            budget = float(input("Enter available budget (USD): "))
            if budget > 1000:
                break
            print("Budget must be greater than $1,000.")
        except ValueError:
            print("Please enter a valid number.")

    # -------------------------------
    # Timeline (1–60 months)
    # -------------------------------
    while True:
        try:
            timeline = int(input("Enter timeline (in months): "))
            if 1 <= timeline <= 60:
                break
            print("Timeline must be between 1 and 60 months.")
        except ValueError:
            print("Please enter a valid integer.")

    # -------------------------------
    # Target Market
    # -------------------------------
    while True:
        target_market = input("Target market (e.g., US small businesses): ").strip()
        if target_market:
            break
        print("Target market cannot be empty.")

    # -------------------------------
    # Team Size
    # -------------------------------
    while True:
        try:
            team_size = int(input("Team size: "))
            if team_size > 0:
                break
            print("Team size must be positive.")
        except ValueError:
            print("Please enter a valid integer.")

    raw_input = {
        "business_idea": idea,
        "industry": industry,
        "budget": budget,
        "timeline_months": timeline,
        "target_market": target_market,
        "team_size": team_size
    }

    state.add_data("raw_input", raw_input)
    state.update_state(SystemState.INPUT_RECEIVED)

    logger.info("Business idea input collected successfully")

    return raw_input
