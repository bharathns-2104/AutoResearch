from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input
from ..ui.cli_interface import collect_user_input
from ..agents.intake_agent import IntakeAgent
from .input_handler import save_structured_input

logger = setup_logger()


class WorkflowController:

    def __init__(self):
        self.state_manager = StateManager()
        logger.info("WorkflowController initialized")

    def run(self):
        logger.info("Workflow started")

        try:
            while self.state_manager.current_state != SystemState.COMPLETED:
                current_state = self.state_manager.current_state

                if current_state == SystemState.INITIALIZED:
                    self.handle_initialization()

                elif current_state == SystemState.INPUT_RECEIVED:
                    self.handle_search()

                elif current_state == SystemState.SEARCHING:
                    self.handle_scraping()

                elif current_state == SystemState.SCRAPING:
                    self.handle_extraction()

                elif current_state == SystemState.EXTRACTING:
                    self.handle_analysis()

                elif current_state == SystemState.ANALYZING:
                    self.handle_consolidation()

                elif current_state == SystemState.CONSOLIDATING:
                    self.handle_report_generation()

                elif current_state == SystemState.GENERATING_REPORT:
                    self.finish_workflow()

                elif current_state == SystemState.ERROR:
                    logger.error("Workflow stopped due to error")
                    break

                else:
                    logger.error("Unknown state encountered")
                    break

        except Exception as e:
            logger.error(f"Critical workflow failure: {str(e)}")
            self.state_manager.add_error(str(e))


    def handle_initialization(self):
        logger.info("Starting Phase 2 input pipeline")

        # Collect raw input
        raw_input = collect_user_input()

        # Process through Intake Agent
        agent = IntakeAgent()
        structured_input = agent.process(raw_input)

        # Save structured JSON
        save_structured_input(structured_input)

        # Move to next state (ready for Search Phase)
        self.state_manager.update_progress(20)
        self.state_manager.update_state(SystemState.INPUT_RECEIVED)

    def handle_search(self):
        logger.info("Handling search step")
        self.state_manager.update_progress(25)

        # Simulate successful search
        self.state_manager.add_data("search_results", ["url1", "url2"])

        self.state_manager.update_state(SystemState.SEARCHING)


    def handle_scraping(self):
        logger.info("Handling scraping step")
        self.state_manager.update_progress(40)

        # Simulate scraping
        self.state_manager.add_data("scraped_data", ["data1", "data2"])

        self.state_manager.update_state(SystemState.SCRAPING)


    def handle_extraction(self):
        logger.info("Handling extraction step")
        self.state_manager.update_progress(55)

        self.state_manager.add_data("extracted_entities", {"cost": 50000})

        self.state_manager.update_state(SystemState.EXTRACTING)


    def handle_analysis(self):
        logger.info("Handling analysis step")
        self.state_manager.update_progress(70)

        self.state_manager.add_data("financial_score", 0.65)

        self.state_manager.update_state(SystemState.ANALYZING)


    def handle_consolidation(self):
        logger.info("Handling consolidation step")
        self.state_manager.update_progress(85)

        self.state_manager.add_data("overall_score", 0.68)

        self.state_manager.update_state(SystemState.CONSOLIDATING)


    def handle_report_generation(self):
        logger.info("Handling report generation step")
        self.state_manager.update_progress(95)

        self.state_manager.update_state(SystemState.GENERATING_REPORT)


    def finish_workflow(self):
        logger.info("Workflow completed successfully")
        self.state_manager.update_progress(100)
        self.state_manager.update_state(SystemState.COMPLETED)
