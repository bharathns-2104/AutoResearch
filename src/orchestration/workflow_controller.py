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

logger = setup_logger()


class WorkflowController:

    def __init__(self):
        self.state_manager = StateManager()
        self.cache_manager = CacheManager()
        logger.info("WorkflowController initialized")

    # ===================================================
    # MAIN FSM LOOP
    # ===================================================
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

                elif current_state == SystemState.ANALYZING:
                    self.handle_analysis()

                elif current_state == SystemState.CONSOLIDATING:
                    self.handle_consolidation()

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

    # ===================================================
    # INITIALIZATION
    # ===================================================
    def handle_initialization(self):
        logger.info("Starting intake pipeline")

        raw_input = self.state_manager.data.get("test_input")

        if not raw_input:
            raw_input = collect_user_input()

        agent = IntakeAgent()
        structured_input = agent.process(raw_input)

        save_structured_input(structured_input)

        self.state_manager.add_data("structured_input", structured_input)
        self.state_manager.update_progress(20)
        self.state_manager.update_state(SystemState.INPUT_RECEIVED)

    # ===================================================
    # SEARCH
    # ===================================================
    def handle_search(self):
        logger.info("Handling search phase")

        structured_input = self.state_manager.data.get("structured_input")

        if not structured_input:
            self.state_manager.add_error("No structured input found for search")
            return

        search_engine = SearchEngine(max_results_per_query=5)
        results = search_engine.search(structured_input)

        if results:
            self.state_manager.add_data("search_results", results)
            self.state_manager.update_progress(40)
            self.state_manager.update_state(SystemState.SEARCHING)
        else:
            self.state_manager.add_error("Search returned empty result list")

    # ===================================================
    # SCRAPING
    # ===================================================
    def handle_scraping(self):
        logger.info("Handling scraping phase")

        search_results = self.state_manager.data.get("search_results")

        if not search_results:
            self.state_manager.add_error("No search results available for scraping")
            return

        scraper = WebScraper(max_parallel=5)
        scraped_content = scraper.scrape(search_results)

        if scraped_content:
            self.state_manager.add_data("scraped_content", scraped_content)
            self.state_manager.update_progress(70)
            self.state_manager.update_state(SystemState.SCRAPING)
        else:
            self.state_manager.add_error("Scraping returned no usable data")

    # ===================================================
    # EXTRACTION
    # ===================================================
    def handle_extraction(self):
        logger.info("Handling extraction phase")

        scraped_content = self.state_manager.data.get("scraped_content")

        if not scraped_content:
            self.state_manager.add_error("No scraped content found for extraction")
            return

        from src.agents.extraction_engine import ExtractionEngine

        extraction_engine = ExtractionEngine()
        structured_data = extraction_engine.process(scraped_content)

        if structured_data:
            self.state_manager.add_data("extracted_data", structured_data)
            self.state_manager.update_progress(80)
            self.state_manager.update_state(SystemState.ANALYZING)
        else:
            self.state_manager.add_error("Extraction failed")

    # ===================================================
    # MERGE EXTRACTION OUTPUT
    # ===================================================
    def merge_extracted_data(self, extracted_pages):
        """
        Normalises ExtractionEngine output into the unified schema that all
        analysis agents expect:

        {
            "currencies":   [{"value": int, "context": str}, ...],
            "percentages":  [{"value": float, "context": str}, ...],
            "entities":     {"organizations": [...], "people": [...], "locations": [...]},
            "keywords":     [str, ...]
        }

        ExtractionEngine.process() returns a dict with this shape:
        {
            "entities":          {"organizations": [...], "people": [...], "locations": [...]},
            "financial_metrics": {"startup_costs": [...], "revenue_figures": [...],
                                  "funding_amounts": [...], "market_sizes": [...],
                                  "growth_rates": [...]},
            "keywords":          [str, ...]
        }
        """

        # -------------------------------------------------------
        # Already in the expected unified format — pass through
        # -------------------------------------------------------
        if isinstance(extracted_pages, dict):
            # If it already has currencies/percentages keys it's already merged
            if "currencies" in extracted_pages or "percentages" in extracted_pages:
                return extracted_pages

            # Convert ExtractionEngine dict → unified format
            return self._convert_extraction_engine_output(extracted_pages)

        # -------------------------------------------------------
        # Legacy list-of-pages format
        # -------------------------------------------------------
        if isinstance(extracted_pages, list):
            merged = {
                "currencies": [],
                "percentages": [],
                "entities": {"organizations": [], "people": [], "locations": []},
                "keywords": []
            }

            for page in extracted_pages:
                if not isinstance(page, dict):
                    continue

                # currencies / percentages may already be structured
                for key in ("currencies", "percentages"):
                    val = page.get(key, [])
                    if isinstance(val, list):
                        merged[key].extend(val)

                # entities
                page_entities = page.get("entities", {})
                if isinstance(page_entities, dict):
                    for sub in ("organizations", "people", "locations"):
                        items = page_entities.get(sub, [])
                        if isinstance(items, list):
                            merged["entities"][sub].extend(items)
                elif isinstance(page_entities, list):
                    # legacy list-of-dicts format
                    for ent in page_entities:
                        if isinstance(ent, dict):
                            label = ent.get("label", "")
                            text = ent.get("text", "")
                            if label == "ORG":
                                merged["entities"]["organizations"].append(text)
                            elif label == "PERSON":
                                merged["entities"]["people"].append(text)
                            elif label in ("GPE", "LOC"):
                                merged["entities"]["locations"].append(text)

                # keywords
                kw = page.get("keywords", [])
                if isinstance(kw, list):
                    merged["keywords"].extend(kw)
                elif isinstance(kw, dict):
                    merged["keywords"].extend(list(kw.keys()))

            return merged

        # Fallback — return empty structure
        logger.error("merge_extracted_data received unexpected type; returning empty structure")
        return {
            "currencies": [],
            "percentages": [],
            "entities": {"organizations": [], "people": [], "locations": []},
            "keywords": []
        }

    def _convert_extraction_engine_output(self, data: dict) -> dict:
        """
        Converts ExtractionEngine.process() output to unified analysis schema.

        financial_metrics keys → currencies / percentages lists with context tags
        so FinancialAnalysisAgent and MarketAnalysisAgent can consume them.
        """
        financial_metrics = data.get("financial_metrics", {})

        currencies = []
        percentages = []

        context_map = {
            "startup_costs":    "cost expense",
            "revenue_figures":  "revenue income",
            "funding_amounts":  "funding raised seed",
            "market_sizes":     "market size valuation",
        }

        for metric_key, context_hint in context_map.items():
            for value in financial_metrics.get(metric_key, []):
                try:
                    currencies.append({"value": float(value), "context": context_hint})
                except (TypeError, ValueError):
                    continue

        for rate in financial_metrics.get("growth_rates", []):
            try:
                percentages.append({"value": float(rate), "context": "growth cagr"})
            except (TypeError, ValueError):
                continue

        # keywords: ExtractionEngine returns a plain list of strings
        raw_keywords = data.get("keywords", [])
        if isinstance(raw_keywords, dict):
            keywords = list(raw_keywords.keys())
        else:
            keywords = list(raw_keywords)

        return {
            "currencies": currencies,
            "percentages": percentages,
            "entities": data.get("entities", {"organizations": [], "people": [], "locations": []}),
            "keywords": keywords
        }

    # ===================================================
    # ANALYSIS (PHASE 5)
    # ===================================================
    def handle_analysis(self):
        logger.info("Handling analysis phase")

        raw_extracted = self.state_manager.data.get("extracted_data")
        structured_input = self.state_manager.data.get("structured_input")

        if not raw_extracted or not structured_input:
            self.state_manager.add_error("Missing data for analysis")
            return

        extracted_data = self.merge_extracted_data(raw_extracted)

        results = {}

        # -------------------------
        # Financial
        # -------------------------
        try:
            financial_agent = FinancialAnalysisAgent(FinancialConfig())
            financial_output = financial_agent.run(
                extracted_data=extracted_data,
                budget=structured_input.get("budget", 0)
            )

            self.cache_manager.set("financial_analysis", financial_output)
            results["financial"] = financial_output

        except Exception as e:
            logger.error(f"Financial analysis failed: {e}")
            results["financial"] = None

        # -------------------------
        # Competitive
        # -------------------------
        try:
            competitive_agent = CompetitiveAnalysisAgent()
            competitive_output = competitive_agent.run(extracted_data)

            self.cache_manager.set("competitive_analysis", competitive_output)
            results["competitive"] = competitive_output

        except Exception as e:
            logger.error(f"Competitive analysis failed: {e}")
            results["competitive"] = None

        # -------------------------
        # Market
        # -------------------------
        try:
            market_agent = MarketAnalysisAgent()
            market_output = market_agent.run(extracted_data)

            self.cache_manager.set("market_analysis", market_output)
            results["market"] = market_output

        except Exception as e:
            logger.error(f"Market analysis failed: {e}")
            results["market"] = None

        self.state_manager.add_data("analysis_results", results)

        self.state_manager.update_progress(85)
        self.state_manager.update_state(SystemState.CONSOLIDATING)

    # ===================================================
    # CONSOLIDATION (PHASE 6 NEXT)
    # ===================================================
    def handle_consolidation(self):
        logger.info("Handling consolidation phase (placeholder)")

        analysis_results = self.state_manager.data.get("analysis_results")

        if not analysis_results:
            self.state_manager.add_error("No analysis results found for consolidation")
            return

        self.state_manager.add_data("consolidated_report", {
            "note": "Consolidation Agent will be implemented in Phase 6"
        })

        self.state_manager.update_progress(90)
        self.state_manager.update_state(SystemState.GENERATING_REPORT)

    # ===================================================
    # FINISH
    # ===================================================
    def finish_workflow(self):
        logger.info("Workflow completed successfully")

        self.state_manager.dump_to_file()
        self.state_manager.update_progress(100)
        self.state_manager.update_state(SystemState.COMPLETED)