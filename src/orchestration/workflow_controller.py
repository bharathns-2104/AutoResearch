from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input
from .cache_manager import CacheManager

from ..ui.cli_interface import collect_user_input
from ..agents.intake_agent import IntakeAgent
from ..agents.search_engine import SearchEngine
from ..agents.web_scraper import WebScraper
from ..agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig
from ..agents.competitive_analysis import CompetitiveAnalysisAgent
from ..agents.market_analysis import MarketAnalysisAgent


class WorkflowController:

    def __init__(self):
        self.logger = setup_logger()
        self.state_manager = StateManager()
        self.cache_manager = CacheManager()
        self.logger.info("WorkflowController initialized")

    # ===================================================
    # MAIN FSM LOOP
    # ===================================================
    def run(self):
        self.logger.info("Workflow started")

        try:
            while True:

                current_state = self.state_manager.current_state

                if current_state == SystemState.COMPLETED:
                    break

                if current_state == SystemState.ERROR:
                    self.logger.error("Workflow stopped due to error")
                    break

                if current_state == SystemState.INITIALIZED:
                    self.handle_initialization()

                elif current_state == SystemState.INPUT_RECEIVED:
                    self.handle_search()

                elif current_state == SystemState.SEARCHING:
                    self.handle_scraping()

                elif current_state == SystemState.SCRAPING:
                    self.handle_extraction()

                elif current_state == SystemState.ANALYZING:
                    self.handle_analysis()

                elif current_state == SystemState.CONSOLIDATING:
                    self.handle_consolidation()

                elif current_state == SystemState.GENERATING_REPORT:
                    self.finish_workflow()

                else:
                    self.logger.error(f"Unknown state encountered: {current_state}")
                    self.state_manager.update_state(SystemState.ERROR)

        except Exception as e:
            self.logger.error(f"Critical workflow failure: {str(e)}")
            self.state_manager.update_state(SystemState.ERROR)

    # ===================================================
    # ERROR HANDLER
    # ===================================================
    def _fail(self, message):
        self.logger.error(message)
        self.state_manager.add_error(message)
        self.state_manager.update_state(SystemState.ERROR)

    # ===================================================
    # INITIALIZATION
    # ===================================================
    def handle_initialization(self):
        self.logger.info("Starting intake pipeline")

        raw_input = self.state_manager.data.get("test_input")

        if not raw_input:
            raw_input = collect_user_input()

        try:
            agent = IntakeAgent()
            structured_input = agent.process(raw_input)

            save_structured_input(structured_input)

            self.state_manager.add_data("structured_input", structured_input)
            self.state_manager.update_progress(20)
            self.state_manager.update_state(SystemState.INPUT_RECEIVED)

        except Exception as e:
            self._fail(f"Initialization failed: {str(e)}")

    # ===================================================
    # SEARCH
    # ===================================================
    def handle_search(self):
        self.logger.info("Handling search phase")

        structured_input = self.state_manager.data.get("structured_input")

        if not structured_input:
            self._fail("No structured input found for search")
            return

        try:
            search_engine = SearchEngine(max_results_per_query=5)
            results = search_engine.search(structured_input)

            if not results:
                self._fail("Search returned empty results")
                return

            self.state_manager.add_data("search_results", results)
            self.state_manager.update_progress(40)
            self.state_manager.update_state(SystemState.SEARCHING)

        except Exception as e:
            self._fail(f"Search failed: {str(e)}")

    # ===================================================
    # SCRAPING
    # ===================================================
    def handle_scraping(self):
        self.logger.info("Handling scraping phase")

        search_results = self.state_manager.data.get("search_results")

        if not search_results:
            self._fail("No search results available for scraping")
            return

        try:
            scraper = WebScraper(max_parallel=5)
            scraped_content = scraper.scrape(search_results)

            if not scraped_content:
                self._fail("Scraping returned no usable data")
                return

            self.state_manager.add_data("scraped_content", scraped_content)
            self.state_manager.update_progress(60)
            self.state_manager.update_state(SystemState.SCRAPING)

        except Exception as e:
            self._fail(f"Scraping failed: {str(e)}")

    # ===================================================
    # EXTRACTION
    # ===================================================
    def handle_extraction(self):
        self.logger.info("Handling extraction phase")

        scraped_content = self.state_manager.data.get("scraped_content")

        if not scraped_content:
            self._fail("No scraped content found for extraction")
            return

        try:
            from ..agents.extraction_engine import ExtractionEngine

            extraction_engine = ExtractionEngine()
            structured_data = extraction_engine.process(scraped_content)

            if not structured_data:
                self._fail("Extraction returned empty output")
                return

            self.state_manager.add_data("extracted_data", structured_data)
            self.state_manager.update_progress(75)
            self.state_manager.update_state(SystemState.ANALYZING)

        except Exception as e:
            self._fail(f"Extraction failed: {str(e)}")

    # ===================================================
    # ANALYSIS (PHASE 5)
    # ===================================================
    def handle_analysis(self):
        self.logger.info("Handling analysis phase")

        raw_extracted = self.state_manager.data.get("extracted_data")
        structured_input = self.state_manager.data.get("structured_input")

        if not raw_extracted or not structured_input:
            self._fail("Missing data for analysis")
            return

        try:
            results = {}

            # ---------------- FINANCIAL ----------------
            financial_agent = FinancialAnalysisAgent(FinancialConfig())
            financial_output = financial_agent.run(
                extracted_data=raw_extracted,
                budget=structured_input.get("budget", 0)
            )
            results["financial"] = financial_output

            # ---------------- COMPETITIVE ----------------
            competitive_agent = CompetitiveAnalysisAgent()
            competitive_output = competitive_agent.run(raw_extracted)
            results["competitive"] = competitive_output

            # ---------------- MARKET ----------------
            market_agent = MarketAnalysisAgent()
            market_output = market_agent.run(raw_extracted)
            results["market"] = market_output

            self.state_manager.add_data("analysis_results", results)
            self.state_manager.update_progress(85)
            self.state_manager.update_state(SystemState.CONSOLIDATING)

        except Exception as e:
            self._fail(f"Analysis failed: {str(e)}")

    # ===================================================
    # CONSOLIDATION (PHASE 6)
    # ===================================================
    def handle_consolidation(self):
        self.logger.info("Handling consolidation phase")

        analysis_results = self.state_manager.data.get("analysis_results")

        if not analysis_results:
            self._fail("No analysis results found for consolidation")
            return

        try:
            # Check cache
            cached = self.cache_manager.get_consolidation_cache()

            if cached:
                self.logger.info("Using cached consolidation results")
                consolidated = cached
            else:
                from ..agents.consolidation_agent import ConsolidationAgent
                agent = ConsolidationAgent()
                consolidated = agent.run(analysis_results)
                self.cache_manager.set_consolidation_cache(consolidated)

            self.state_manager.add_data("consolidated_output", consolidated)
            self.state_manager.update_progress(95)
            self.state_manager.update_state(SystemState.GENERATING_REPORT)

        except Exception as e:
            self._fail(f"Consolidation failed: {str(e)}")

    # ===================================================
    # FINISH
    # ===================================================
    def finish_workflow(self):
        self.logger.info("Workflow completed successfully")

        self.state_manager.update_progress(100)
        self.state_manager.update_state(SystemState.COMPLETED)
        self.state_manager.dump_to_file()
