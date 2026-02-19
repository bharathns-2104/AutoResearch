from src.orchestration.workflow_controller import WorkflowController
from src.orchestration.state_manager import StateManager, SystemState


def test_workflow_completion():
    StateManager.reset()

    controller = WorkflowController()

    # Inject mock input
    controller.state_manager.add_data("test_input", {
        "business_idea": "Test EV Startup",
        "industry": "Automotive",
        "budget": 500000,
        "timeline_months": 12,
        "target_market": "India",
        "team_size": 10,
        "search_queries": [
            "EV startup cost",
            "EV competitors",
            "EV market size"
        ]
    })

    controller.run()

    state = StateManager()
    assert state.current_state == SystemState.COMPLETED