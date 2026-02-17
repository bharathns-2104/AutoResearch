# src/ui/cli_interface.py

from ..orchestration.logger import setup_logger
from ..orchestration.state_manager import StateManager, SystemState

logger = setup_logger()


def collect_user_input():
    """
    Collect corporate analysis requirements from user via CLI.
    Returns validated structured dictionary.
    """

    state = StateManager()

    logger.info("Starting CLI input collection")

    print("\n=== Corporate Analysis Input ===\n")

    # ---- Business / Company Name ----
    while True:
        company_name = input("Enter Company Name: ").strip()
        if company_name:
            break
        print("Company name cannot be empty.")

    # ---- Industry ----
    industry = input("Enter Industry (e.g., FinTech, SaaS, Healthcare): ").strip()
    if not industry:
        industry = "Other"

    # ---- Analysis Type ----
    allowed_types = ["financial", "market", "competitive", "all"]

    while True:
        analysis_type = input(
            "Select Analysis Type (financial / market / competitive / all): "
        ).strip().lower()

        if analysis_type in allowed_types:
            break

        print("Invalid choice. Please choose from financial, market, competitive, all.")

    # ---- Geographic Focus ----
    geographic_focus = input("Enter Geographic Focus (e.g., US, Global): ").strip()
    if not geographic_focus:
        geographic_focus = "Global"

    # ---- Time Horizon ----
    while True:
        try:
            time_horizon = int(input("Enter Time Horizon (in years): "))
            if time_horizon > 0:
                break
            print("Time horizon must be a positive number.")
        except ValueError:
            print("Please enter a valid integer.")

    # ---- Optional Custom Requirements ----
    custom_req = input("Any specific KPIs or requirements? (Optional): ").strip()

    # ---- Build Structured Dict ----
    structured_input = {
        "company_name": company_name,
        "industry": industry,
        "analysis_type": analysis_type,
        "geographic_focus": geographic_focus,
        "time_horizon_years": time_horizon,
        "custom_requirements": custom_req if custom_req else None,
    }

    # ---- Update State ----
    state.add_data("raw_input", structured_input)
    state.update_state(SystemState.INPUT_RECEIVED)

    logger.info("User input successfully collected and validated")

    return structured_input
