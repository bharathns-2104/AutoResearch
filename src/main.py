from .orchestration.workflow_controller import WorkflowController

if __name__ == "__main__":
    controller = WorkflowController()
    controller.run()