from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input
from .cache_manager import CacheManager

from ..ui.cli_interface import collect_user_input
from ..agents.intake_agent import IntakeAgent
from ..agents.search_engine import SearchEngine
from ..agents.web_scraper import WebScraper


logger = setup_logger()


class WorkflowController:

    def __init__(self):
        self.state_manager = StateManager()
        self.cache_manager = CacheManager()
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
                    logger.error(f"Unknown state encountered: {current_state}")
                    break

        except Exception as e:
            logger.error(f"Critical workflow failure: {str(e)}")
            self.state_manager.add_error(str(e))

    # ---------------------------------------------------
    # INITIALIZED → INPUT_RECEIVED
    # Collect user input and run it through Intake Agent
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
    # Run search queries from structured input
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

        if results:
            self.state_manager.update_progress(40)
            # SearchEngine.search() sets state to SEARCHING internally.
            # If for any reason it didn't, we enforce it here.
            if self.state_manager.current_state != SystemState.SEARCHING:
                self.state_manager.update_state(SystemState.SEARCHING)
        else:
            self.state_manager.add_error("Search returned empty result list")

    # ---------------------------------------------------
    # SEARCHING → SCRAPING
    # Scrape URLs returned by search engine.
    # Cache is checked per-URL before fetching.
    # ---------------------------------------------------
    def handle_scraping(self):
        logger.info("Handling scraping phase")

        search_results = self.state_manager.data.get("search_results")

        if not search_results:
            self.state_manager.add_error("No search results available for scraping")
            return

        # --- Cache-aware scraping ---
        # Split URLs into cached hits and those that need live fetching
        urls_to_scrape = []
        cached_pages = []

        for item in search_results:
            url = item.get("url")
            if not url:
                continue

            cached = self.cache_manager.get(url)
            if cached:
                cached_pages.append(cached)
                logger.info(f"Cache hit — skipping fetch for: {url}")
            else:
                urls_to_scrape.append(item)

        logger.info(
            f"Cache hits: {len(cached_pages)} | "
            f"URLs to scrape live: {len(urls_to_scrape)}"
        )

        # Scrape only the URLs not in cache
        freshly_scraped = []
        if urls_to_scrape:
            scraper = WebScraper(max_parallel=5)
            # WebScraper.scrape() sets state to SCRAPING internally
            freshly_scraped = scraper.scrape(urls_to_scrape)

            # Save each freshly scraped page to cache for future runs
            for page in freshly_scraped:
                if page and page.get("url"):
                    self.cache_manager.set(page["url"], page)
        else:
            # No live scraping needed — manually set state to SCRAPING
            # so the FSM loop advances correctly
            self.state_manager.update_state(SystemState.SCRAPING)

        # Combine cached + fresh results
        all_scraped = cached_pages + freshly_scraped

        logger.info(f"Total pages available after scraping: {len(all_scraped)}")

        if all_scraped:
            self.state_manager.add_data("scraped_content", all_scraped)
            self.state_manager.update_progress(70)
            self.state_manager.update_state(SystemState.SCRAPING)
        else:
            self.state_manager.add_error("Scraping returned no usable data")

    # ---------------------------------------------------
    # SCRAPING → EXTRACTING
    # Placeholder — Phase 4 will replace this with
    # regex + spaCy extraction engine
    # ---------------------------------------------------
    def handle_extraction(self):
        logger.info("Handling extraction phase")

        scraped_content = self.state_manager.data.get("scraped_content")
        if not scraped_content:
            self.state_manager.add_error("No scraped content found for extraction")
            return

        # ------------------------------------
        # Check Extraction Cache
        # ------------------------------------
        cached_extraction = self.cache_manager.get_extraction_cache()

        if cached_extraction:
            logger.info("Using cached extraction results")
            self.state_manager.add_data("extracted_data", cached_extraction)
            self.state_manager.update_progress(80)
            self.state_manager.update_state(SystemState.ANALYZING)
            return

        # ------------------------------------
        # Run Extraction Engine
        # ------------------------------------
        from src.agents.extraction_engine import ExtractionEngine

        extraction_engine = ExtractionEngine()
        structured_data = extraction_engine.process(scraped_content)

        if structured_data:
            # Cache result
            self.cache_manager.set_extraction_cache(structured_data)

            self.state_manager.update_progress(80)
            self.state_manager.update_state(SystemState.ANALYZING)
        else:
            self.state_manager.add_error("Extraction failed")

    def handle_analysis(self):
        logger.info("Handling analysis phase (placeholder for Phase 4/5)")

        self.state_manager.add_data("analysis_summary", {
            "note": "Full analysis implemented in Phase 4/5"
        })

        self.state_manager.update_progress(85)
        self.state_manager.update_state(SystemState.ANALYZING)

    # ---------------------------------------------------
    # ANALYZING → CONSOLIDATING
    # Placeholder — Phase 5 will add Consolidation Agent
    # ---------------------------------------------------
    def handle_consolidation(self):
        logger.info("Handling consolidation phase (placeholder for Phase 5)")

        self.state_manager.add_data("consolidated_report", {
            "note": "Full consolidation implemented in Phase 5"
        })

        self.state_manager.update_progress(90)
        self.state_manager.update_state(SystemState.CONSOLIDATING)

    # ---------------------------------------------------
    # CONSOLIDATING → GENERATING_REPORT
    # Placeholder — Phase 4 will add PDF/PPT generators
    # ---------------------------------------------------
    def handle_report_generation(self):
        logger.info("Handling report generation phase (placeholder for Phase 4)")

        self.state_manager.update_progress(95)
        self.state_manager.update_state(SystemState.GENERATING_REPORT)

    # ---------------------------------------------------
    # GENERATING_REPORT → COMPLETED
    # ---------------------------------------------------
    def finish_workflow(self):
        logger.info("Workflow completed successfully")

        self.state_manager.dump_to_file()
        self.state_manager.update_progress(100)
        self.state_manager.update_state(SystemState.COMPLETED)