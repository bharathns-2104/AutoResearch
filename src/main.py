from .orchestration.workflow_controller import WorkflowController
from .orchestration.state_manager import StateManager


def run_system():
    controller = WorkflowController()
    controller.run()

    state = StateManager()
    state.dump_to_file()

    return state.get_snapshot()


if __name__ == "__main__":
    snapshot = run_system()
    print("\nFinal Snapshot:")
    print(snapshot)
