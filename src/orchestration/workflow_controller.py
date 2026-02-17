from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input

from ..ui.cli_interface import collect_user_input
from ..agents.intake_agent import IntakeAgent
from ..agents.search_engine import SearchEngine
from ..agents.web_scraper import WebScraper


logger = setup_logger()


class WorkflowController:

    def __init__(self):
        self.state_manager = StateManager()
        logger.info("WorkflowController initialized")

    # ---------------------------------------------------
    # MAIN FSM LOOP
    # ---------------------------------------------------
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

                elif current_state == SystemState.EXTRACTING:
                    self.handle_extraction()

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
                    logger.error(f"Unknown state encountered: {current_state}")
                    break

        except Exception as e:
            logger.error(f"Critical workflow failure: {str(e)}")
            self.state_manager.add_error(str(e))

    # ---------------------------------------------------
    # INITIALIZED → Collect Input
    # ---------------------------------------------------
    def handle_initialization(self):
        logger.info("Starting Phase 2 intake pipeline")

        raw_input = collect_user_input()

        agent = IntakeAgent()
        structured_input = agent.process(raw_input)

        save_structured_input(structured_input)

        self.state_manager.update_progress(20)
        self.state_manager.update_state(SystemState.INPUT_RECEIVED)

    # ---------------------------------------------------
    # INPUT_RECEIVED → SEARCHING
    # ---------------------------------------------------
    def handle_search(self):
        logger.info("Handling search phase")

        structured_input = self.state_manager.data.get("structured_input")

        if not structured_input:
            self.state_manager.add_error("No structured input found for search")
            return

        search_engine = SearchEngine(max_results_per_query=5)
        results = search_engine.search(structured_input)

        logger.info(f"Search returned {len(results)} results")

        if results and len(results) > 0:
            self.state_manager.update_progress(40)
            self.state_manager.update_state(SystemState.SEARCHING)
        else:
            self.state_manager.add_error("Search returned empty result list")

    # ---------------------------------------------------
    # SEARCHING → EXTRACTING (via Scraper)
    # ---------------------------------------------------
    def handle_scraping(self):
        logger.info("Handling scraping phase")

        search_results = self.state_manager.data.get("search_results")

        if not search_results:
            self.state_manager.add_error("No search results available for scraping")
            return

        scraper = WebScraper(max_parallel=5)
        scraped_data = scraper.scrape(search_results)

        logger.info(f"Scraped {len(scraped_data)} pages")

        if scraped_data and len(scraped_data) > 0:
            self.state_manager.update_progress(70)
            self.state_manager.update_state(SystemState.EXTRACTING)
        else:
            self.state_manager.add_error("Scraping returned no usable data")

    # ---------------------------------------------------
    # EXTRACTING → ANALYZING (Placeholder until Phase 4)
    # ---------------------------------------------------
    def handle_extraction(self):
        logger.info("Handling extraction phase (placeholder)")

        scraped_content = self.state_manager.data.get("scraped_content")

        if not scraped_content:
            self.state_manager.add_error("No scraped content found for extraction")
            return

        # Placeholder extraction logic (Phase 4 will replace this)
        self.state_manager.add_data("extracted_entities", {
            "sample_metric": 12345
        })

        self.state_manager.update_progress(80)
        self.state_manager.update_state(SystemState.ANALYZING)

    # ---------------------------------------------------
    # ANALYZING → CONSOLIDATING (Placeholder)
    # ---------------------------------------------------
    def handle_consolidation(self):
        logger.info("Handling analysis/consolidation phase (placeholder)")

        self.state_manager.add_data("analysis_summary", {
            "financial_score": 0.65
        })

        self.state_manager.update_progress(90)
        self.state_manager.update_state(SystemState.CONSOLIDATING)

    # ---------------------------------------------------
    # CONSOLIDATING → GENERATING_REPORT (Placeholder)
    # ---------------------------------------------------
    def handle_report_generation(self):
        logger.info("Handling report generation phase (placeholder)")

        self.state_manager.update_progress(95)
        self.state_manager.update_state(SystemState.GENERATING_REPORT)

    # ---------------------------------------------------
    # FINAL STATE
    # ---------------------------------------------------
    def finish_workflow(self):
        logger.info("Workflow completed successfully")

        self.state_manager.update_progress(100)
        self.state_manager.update_state(SystemState.COMPLETED)
