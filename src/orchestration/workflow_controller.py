from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input
from .cache_manager import CacheManager
from ..config.settings import SCRAPING_SETTINGS

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
                    self.finish_workflow()
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

                elif current_state == SystemState.EXTRACTING:
                    self.handle_analysis()

                elif current_state == SystemState.ANALYZING:
                    self.handle_analysis()

                elif current_state == SystemState.CONSOLIDATING:
                    self.handle_consolidation()

                elif current_state == SystemState.GENERATING_REPORT:
                    self.handle_report_generation()

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
        """Hard failure: Stop workflow entirely (for critical stages)."""
        self.logger.error(message)
        self.state_manager.add_error(message)
        self.state_manager.update_state(SystemState.ERROR)

    def _warn_partial(self, message):
        """Soft failure: Log warning but continue with partial data (graceful degradation)."""
        self.logger.warning(message)
        self.state_manager.add_error(f"[PARTIAL] {message}")

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
    # SCRAPING (GRACEFUL DEGRADATION: Issue #12)
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

            # GRACEFUL DEGRADATION: Check if we have minimum useful data
            min_threshold = SCRAPING_SETTINGS.get("min_pages_threshold", 3)
            
            if not scraped_content:
                self._fail("Scraping returned no usable data")
                return
            
            if len(scraped_content) < min_threshold:
                # Only ONE page scraped, but allow it to proceed with a warning
                self._warn_partial(
                    f"Scraping returned only {len(scraped_content)} page(s), "
                    f"minimum threshold is {min_threshold}. Proceeding with partial data."
                )
            else:
                self.logger.info(
                    f"Successfully scraped {len(scraped_content)} pages "
                    f"(threshold: {min_threshold})"
                )

            self.state_manager.add_data("scraped_content", scraped_content)
            self.state_manager.add_data("scraping_partial", len(scraped_content) < min_threshold)
            self.state_manager.update_progress(60)
            self.state_manager.update_state(SystemState.SCRAPING)

        except Exception as e:
            self._fail(f"Scraping failed: {str(e)}")


    # ===================================================
    # EXTRACTION (GRACEFUL DEGRADATION: Issue #7)
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

            # GRACEFUL DEGRADATION: Allow empty entities but with warning
            if not structured_data:
                self._warn_partial("Extraction returned minimal output (empty extraction)")
                # Create a minimal valid structure to continue
                structured_data = {
                    "entities": {"organizations": [], "people": [], "locations": []},
                    "financial_metrics": {
                        "startup_costs": [],
                        "revenue_figures": [],
                        "funding_amounts": [],
                        "market_sizes": [],
                        "growth_rates": []
                    },
                    "keywords": []
                }
            
            extraction_partial = any([
                not structured_data.get("entities", {}).get("organizations", []),
                not structured_data.get("financial_metrics", {}).get("growth_rates", []),
                not structured_data.get("keywords", [])
            ])
            
            if extraction_partial:
                self._warn_partial("Extraction returned partial data (missing some entities/metrics)")

            self.state_manager.add_data("extracted_data", structured_data)
            self.state_manager.add_data("extraction_partial", extraction_partial)
            self.state_manager.update_progress(75)
            self.state_manager.update_state(SystemState.EXTRACTING)

        except Exception as e:
            self._fail(f"Extraction failed: {str(e)}")


    # ===================================================
    # ANALYSIS (GRACEFUL DEGRADATION: Issue #7)
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
            analysis_failures = []

            # FINANCIAL ANALYSIS
            try:
                financial_agent = FinancialAnalysisAgent(FinancialConfig())
                results["financial"] = financial_agent.run(
                    extracted_data=raw_extracted,
                    budget=structured_input.get("budget", 0)
                )
            except Exception as e:
                self._warn_partial(f"Financial analysis failed: {str(e)}")
                analysis_failures.append("financial")
                results["financial"] = self._default_analysis_output("financial")

            # COMPETITIVE ANALYSIS
            try:
                competitive_agent = CompetitiveAnalysisAgent()
                results["competitive"] = competitive_agent.run(raw_extracted)
            except Exception as e:
                self._warn_partial(f"Competitive analysis failed: {str(e)}")
                analysis_failures.append("competitive")
                results["competitive"] = self._default_analysis_output("competitive")

            # MARKET ANALYSIS
            try:
                market_agent = MarketAnalysisAgent()
                results["market"] = market_agent.run(raw_extracted)
            except Exception as e:
                self._warn_partial(f"Market analysis failed: {str(e)}")
                analysis_failures.append("market")
                results["market"] = self._default_analysis_output("market")

            # If ALL analyses failed, that's a real problem
            if len(analysis_failures) == 3:
                self._fail("All analysis stages failed - cannot proceed")
                return

            if analysis_failures:
                self._warn_partial(
                    f"Partial analysis: {', '.join(analysis_failures)} stages failed"
                )

            self.state_manager.add_data("analysis_results", results)
            self.state_manager.add_data("analysis_partial", bool(analysis_failures))
            self.state_manager.update_progress(85)
            self.state_manager.update_state(SystemState.CONSOLIDATING)

        except Exception as e:
            self._fail(f"Analysis failed: {str(e)}")

    def _default_analysis_output(self, analysis_type):
        """Return a minimal valid output for failed analysis stages."""
        defaults = {
            "financial": {
                "metrics": {},
                "runway_months": 0,
                "viability_score": 0.3,
                "risks": [],
                "recommendations": ["Insufficient financial data available"],
                "summary": "Financial analysis could not be completed"
            },
            "competitive": {
                "competitors_found": 0,
                "top_competitors": [],
                "competitive_intensity": "Unknown",
                "swot_analysis": {
                    "strengths": [],
                    "weaknesses": [],
                    "opportunities": [],
                    "threats": []
                },
                "market_gaps": [],
                "summary": "Competitive analysis could not be completed"
            },
            "market": {
                "market_size": {"global": 0, "currency": "USD"},
                "tam_sam_som": {"tam": 0, "sam": 0, "som": 0},
                "growth_rate": 0,
                "sentiment": {"score": 0, "label": "Unknown"},
                "opportunity_score": 0.3,
                "key_insights": [],
                "summary": "Market analysis could not be completed"
            }
        }
        return defaults.get(analysis_type, {})


    # ===================================================
    # CONSOLIDATION (GRACEFUL DEGRADATION: Issue #7)
    # ===================================================
    def handle_consolidation(self):
        self.logger.info("Handling consolidation phase")

        analysis_results = self.state_manager.data.get("analysis_results")

        if not analysis_results:
            self._fail("No analysis results found for consolidation")
            return

        try:
            cached = self.cache_manager.get_consolidation_cache()

            if cached:
                self.logger.info("Using cached consolidation results")
                consolidated = cached
            else:
                from ..agents.consolidation_agent import ConsolidationAgent
                agent = ConsolidationAgent()
                consolidated = agent.run(analysis_results)
                self.cache_manager.set_consolidation_cache(consolidated)

            # Check if consolidation is based on partial data
            is_partial = (
                self.state_manager.data.get("analysis_partial", False) or
                self.state_manager.data.get("extraction_partial", False) or
                self.state_manager.data.get("scraping_partial", False)
            )
            
            if is_partial:
                self._warn_partial(
                    "Consolidation based on partial analysis data. "
                    "Final report represents best-effort assessment."
                )

            self.state_manager.add_data("consolidated_output", consolidated)
            self.state_manager.add_data("consolidation_partial", is_partial)
            self.state_manager.update_progress(95)
            self.state_manager.update_state(SystemState.GENERATING_REPORT)

        except Exception as e:
            self._fail(f"Consolidation failed: {str(e)}")


    # ===================================================
    # REPORT GENERATION (PHASE 7)
    # ===================================================
    def handle_report_generation(self):
        self.logger.info("Handling report generation phase")

        consolidated = self.state_manager.data.get("consolidated_output")

        if not consolidated:
            self._fail("No consolidated output found for report generation")
            return

        try:
            from ..output.report_generator import ReportGenerator

            generator = ReportGenerator()
            report_paths = generator.generate(consolidated)

            if not report_paths:
                self._fail("Report generation returned no output paths")
                return

            self.state_manager.add_data("report_paths", report_paths)
            self.state_manager.update_progress(100)
            self.state_manager.update_state(SystemState.COMPLETED)

        except Exception as e:
            self._fail(f"Report generation failed: {str(e)}")

    # ===================================================
    # FINALIZATION
    # ===================================================
    def finish_workflow(self):
        self.logger.info("Workflow finalized")
        self.state_manager.dump_to_file()
