from orchestration.workflow_controller import WorkflowController
from orchestration.state_manager import StateManager, SystemState


def test_workflow_completion():
    # Ensure a fresh StateManager for this test
    StateManager._instance = None

    controller = WorkflowController()
    controller.run()

    state = StateManager()
    assert state.current_state == SystemState.COMPLETED
