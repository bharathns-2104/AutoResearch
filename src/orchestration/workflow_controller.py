"""
workflow_controller.py  —  Phase 1b/1c patch

Replaces handle_analysis() to:
  1. Call run_with_review() on Financial and Market agents (Phase 1b).
  2. Pass a search_callback so gap-fill queries go through the routed
     SearchEngine + WebScraper + ExtractionEngine pipeline automatically.
  3. Attach review metadata to the consolidated output for reporting.

All other methods (handle_initialization, handle_search, handle_scraping,
handle_consolidation, handle_report_generation, finish_workflow) are
identical to the Phase 1a version — only handle_analysis changes here.

DROP-IN: copy this file over src/orchestration/workflow_controller.py.
"""

from .state_manager import StateManager, SystemState
from .logger import setup_logger
from .input_handler import save_structured_input
from .cache_manager import CacheManager
from ..config.settings import SCRAPING_SETTINGS, LLM_SETTINGS, RAG_SETTINGS

from ..ui.cli_interface import collect_user_input
from ..agents.intake_agent import IntakeAgent
from ..agents.financial_analysis import FinancialAnalysisAgent, FinancialConfig
from ..agents.competitive_analysis import CompetitiveAnalysisAgent
from ..agents.market_analysis import MarketAnalysisAgent

# Imported at module level so unittest.mock.patch() can target them reliably
from ..agents.search_engine import SearchEngine
from ..agents.web_scraper import WebScraper
from ..agents.extraction_engine import ExtractionEngine
from ..orchestration.rag_manager import RAGManager


class WorkflowController:

    def __init__(self):
        self.logger        = setup_logger()
        self.state_manager = StateManager()
        self.cache_manager = CacheManager()
        self.logger.info("WorkflowController initialized")

    # ═══════════════════════════════════════════════════════════════════════
    # MAIN FSM LOOP
    # ═══════════════════════════════════════════════════════════════════════

    def run(self):
        self.logger.info("Workflow started")
        try:
            while True:
                state = self.state_manager.current_state

                if state == SystemState.COMPLETED:
                    self.finish_workflow(); break
                if state == SystemState.ERROR:
                    self.logger.error("Workflow stopped due to error"); break

                if   state == SystemState.INITIALIZED:        self.handle_initialization()
                elif state == SystemState.INPUT_RECEIVED:     self.handle_search()
                elif state == SystemState.SEARCHING:          self.handle_scraping()
                elif state == SystemState.SCRAPING:           self.handle_rag_indexing()
                elif state == SystemState.RAG_INDEXING:       self.handle_extraction()
                elif state == SystemState.EXTRACTING:         self.handle_analysis()
                elif state == SystemState.CONSOLIDATING:      self.handle_consolidation()
                elif state == SystemState.GENERATING_REPORT:  self.handle_report_generation()
                else:
                    self.logger.error(f"Unknown state: {state}")
                    self.state_manager.update_state(SystemState.ERROR)

        except Exception as exc:
            self.logger.error(f"Critical workflow failure: {exc}")
            self.state_manager.update_state(SystemState.ERROR)

    # ── error helpers ─────────────────────────────────────────────────────

    def _fail(self, msg: str):
        self.logger.error(msg)
        self.state_manager.add_error(msg)
        self.state_manager.update_state(SystemState.ERROR)

    def _warn_partial(self, msg: str):
        self.logger.warning(msg)
        self.state_manager.add_error(f"[PARTIAL] {msg}")

    # ═══════════════════════════════════════════════════════════════════════
    # INITIALIZATION / SEARCH / SCRAPING / EXTRACTION
    # (identical to Phase 1a — included for completeness)
    # ═══════════════════════════════════════════════════════════════════════

    def handle_initialization(self):
        self.logger.info("Starting intake pipeline")
        raw_input = self.state_manager.data.get("test_input") or collect_user_input()
        try:
            agent            = IntakeAgent()
            structured_input = agent.process(raw_input)
            save_structured_input(structured_input)
            self.state_manager.add_data("structured_input", structured_input)
            self.state_manager.update_progress(20)
            self.state_manager.update_state(SystemState.INPUT_RECEIVED)
        except Exception as exc:
            self._fail(f"Initialization failed: {exc}")

    def handle_search(self):
        self.logger.info("Handling search phase")
        structured_input = self.state_manager.data.get("structured_input")
        if not structured_input:
            self._fail("No structured input found for search"); return
        try:
            se      = SearchEngine(max_results_per_query=5)
            results = se.search(structured_input)
            if not results:
                self._fail("Search returned empty results"); return
            self.state_manager.add_data("search_results", results)
            self.state_manager.update_progress(40)
            self.state_manager.update_state(SystemState.SEARCHING)
        except Exception as exc:
            self._fail(f"Search failed: {exc}")

    def handle_scraping(self):
        self.logger.info("Handling scraping phase")
        search_results = self.state_manager.data.get("search_results")
        if not search_results:
            self._fail("No search results available for scraping"); return
        try:
            scraper        = WebScraper(max_parallel=5)
            scraped        = scraper.scrape(search_results)
            min_threshold  = SCRAPING_SETTINGS.get("min_pages_threshold", 3)
            if not scraped:
                self._fail("Scraping returned no usable data"); return
            if len(scraped) < min_threshold:
                self._warn_partial(
                    f"Scraping returned only {len(scraped)} page(s) "
                    f"(min={min_threshold}). Proceeding with partial data."
                )
            self.state_manager.add_data("scraped_content",  scraped)
            self.state_manager.add_data("scraping_partial", len(scraped) < min_threshold)
            self.state_manager.update_progress(60)
            self.state_manager.update_state(SystemState.SCRAPING)
        except Exception as exc:
            self._fail(f"Scraping failed: {exc}")

    def handle_rag_indexing(self):
        """
        Phase 2: Build the ChromaDB semantic index from scraped pages.

        - Creates a RAGManager for this session.
        - Chunks + embeds all scraped pages (~1-2s per page on CPU).
        - Stores the RAGManager instance in state so analysis agents can query it.
        - If RAG is disabled or fails, skips silently and advances to extraction.
        """
        self.logger.info("Handling RAG indexing phase")
        scraped_content = self.state_manager.data.get("scraped_content", [])

        if not RAG_SETTINGS.get("enabled", True):
            self.logger.info("RAG disabled via RAG_ENABLED=false — skipping")
            self.state_manager.update_state(SystemState.RAG_INDEXING)
            return

        try:
            session_id = getattr(self.state_manager, "session_id", None)
            rag = RAGManager(session_id=session_id)
            chunks_indexed = rag.index(scraped_content)
            self.logger.info(f"RAG indexing complete: {chunks_indexed} chunks stored")
            self.state_manager.add_data("rag", rag)
        except Exception as exc:
            self._warn_partial(f"RAG indexing failed (non-fatal): {exc}")

        self.state_manager.update_state(SystemState.RAG_INDEXING)

    def handle_extraction(self):
        self.logger.info("Handling extraction phase")
        scraped_content  = self.state_manager.data.get("scraped_content")
        structured_input = self.state_manager.data.get("structured_input", {})
        if not scraped_content:
            self._fail("No scraped content found for extraction"); return
        try:
            from ..agents.extraction_engine import ExtractionEngine
            engine = ExtractionEngine()
            data   = engine.process(scraped_content)
            if not data:
                self._warn_partial("Extraction returned empty output — using stub")
                data = _empty_extraction()

            # Self-correction
            try:
                from ..agents.self_correction_agent import SelfCorrectionAgent
                data = SelfCorrectionAgent().run(data, scraped_content)
            except Exception as exc:
                self._warn_partial(f"Self-correction failed (non-fatal): {exc}")

            # Routing
            routing_config: dict = _default_routing()
            try:
                from ..agents.routing_agent import RoutingAgent
                routing_config = RoutingAgent().route(data, structured_input)
                self.logger.info(
                    f"Routing: financial={routing_config['run_financial']} "
                    f"competitive={routing_config['run_competitive']} "
                    f"market={routing_config['run_market']} "
                    f"tier={routing_config['confidence_tier']}"
                )
            except Exception as exc:
                self._warn_partial(f"Smart routing failed (non-fatal): {exc}")

            # Supplemental scraping for routing-identified gaps
            for q in routing_config.get("additional_queries", []):
                try:
                    data = self._run_supplemental_scraping([q], data, structured_input)
                except Exception as exc:
                    self._warn_partial(f"Supplemental scraping failed: {exc}")

            extraction_partial = any([
                not data.get("entities", {}).get("organizations", []),
                not data.get("financial_metrics", {}).get("growth_rates", []),
                not data.get("keywords", []),
            ])
            if extraction_partial:
                self._warn_partial("Extraction produced partial data")

            self.state_manager.add_data("extracted_data",    data)
            self.state_manager.add_data("extraction_partial", extraction_partial)
            self.state_manager.add_data("routing_config",    routing_config)
            self.state_manager.update_progress(75)
            self.state_manager.update_state(SystemState.EXTRACTING)
        except Exception as exc:
            self._fail(f"Extraction failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS  —  Phase 1b: run_with_review() + search_callback
    # ═══════════════════════════════════════════════════════════════════════

    def handle_analysis(self):
        self.logger.info("Handling analysis phase (Phase 1b: self-review enabled)")

        raw_extracted    = self.state_manager.data.get("extracted_data")
        structured_input = self.state_manager.data.get("structured_input")
        routing_config   = self.state_manager.data.get("routing_config", _default_routing())

        if not raw_extracted or not structured_input:
            self._fail("Missing data for analysis"); return

        # ── build the gap-fill search callback ────────────────────────────
        # When an agent's reviewer requests extra queries, this callback:
        #   1. Runs each query through the routed SearchEngine.
        #   2. Scrapes the resulting URLs.
        #   3. Re-extracts the scraped pages.
        #   4. Returns the new extracted_data so the agent can merge it.
        def search_callback(queries: list[str]) -> dict | None:
            return self._gap_fill_search(queries, structured_input)

        results           = {}
        analysis_failures = []
        review_metadata   = {}

        # ── FINANCIAL ────────────────────────────────────────────────────
        if routing_config.get("run_financial", True):
            try:
                fa     = FinancialAnalysisAgent(FinancialConfig())
                result = fa.run_with_review(
                    extracted_data   = raw_extracted,
                    budget           = structured_input.get("budget", 0),
                    structured_input = structured_input,
                    search_callback  = search_callback,
                )
                review_metadata["financial"] = result.pop("review", {})
                results["financial"]         = result
                self.logger.info(
                    f"Financial review: "
                    f"confidence={review_metadata['financial'].get('confidence')} "
                    f"verdict={review_metadata['financial'].get('verdict')}"
                )
            except Exception as exc:
                self._warn_partial(f"Financial analysis failed: {exc}")
                analysis_failures.append("financial")
                results["financial"] = self._default_analysis_output("financial")
        else:
            self.logger.info("Routing: financial analysis skipped")
            results["financial"] = self._default_analysis_output("financial")

        # ── COMPETITIVE ──────────────────────────────────────────────────
        # CompetitiveAnalysisAgent has no review loop yet (Phase 2 scope);
        # it runs as before but benefits from the enriched extracted_data
        # that gap-fill may have added during financial/market reviews.
        if routing_config.get("run_competitive", True):
            try:
                results["competitive"] = CompetitiveAnalysisAgent().run(raw_extracted)
            except Exception as exc:
                self._warn_partial(f"Competitive analysis failed: {exc}")
                analysis_failures.append("competitive")
                results["competitive"] = self._default_analysis_output("competitive")
        else:
            self.logger.info("Routing: competitive analysis skipped")
            results["competitive"] = self._default_analysis_output("competitive")

        # ── MARKET ───────────────────────────────────────────────────────
        if routing_config.get("run_market", True):
            try:
                ma     = MarketAnalysisAgent()
                result = ma.run_with_review(
                    extracted_data   = raw_extracted,
                    structured_input = structured_input,
                    search_callback  = search_callback,
                )
                review_metadata["market"] = result.pop("review", {})
                results["market"]         = result
                self.logger.info(
                    f"Market review: "
                    f"confidence={review_metadata['market'].get('confidence')} "
                    f"verdict={review_metadata['market'].get('verdict')}"
                )
            except Exception as exc:
                self._warn_partial(f"Market analysis failed: {exc}")
                analysis_failures.append("market")
                results["market"] = self._default_analysis_output("market")
        else:
            self.logger.info("Routing: market analysis skipped")
            results["market"] = self._default_analysis_output("market")

        # ── guard ─────────────────────────────────────────────────────────
        if len(analysis_failures) == 3:
            self._fail("All analysis stages failed — cannot proceed"); return
        if analysis_failures:
            self._warn_partial(
                f"Partial analysis: {', '.join(analysis_failures)} stage(s) failed"
            )

        self.state_manager.add_data("analysis_results",  results)
        self.state_manager.add_data("review_metadata",   review_metadata)
        self.state_manager.add_data("analysis_partial",  bool(analysis_failures))
        self.state_manager.update_progress(85)
        self.state_manager.update_state(SystemState.CONSOLIDATING)

    # ═══════════════════════════════════════════════════════════════════════
    # CONSOLIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def handle_consolidation(self):
        self.logger.info("Handling consolidation phase")
        analysis_results = self.state_manager.data.get("analysis_results")
        if not analysis_results:
            self._fail("No analysis results for consolidation"); return
        try:
            structured_input = self.state_manager.data.get("structured_input", {})
            cached           = self.cache_manager.get_consolidation_cache(structured_input)
            if cached:
                self.logger.info("Using cached consolidation results")
                consolidated = cached
            else:
                from ..agents.consolidation_agent import ConsolidationAgent
                consolidated = ConsolidationAgent().run(analysis_results)
                self.cache_manager.set_consolidation_cache(structured_input, consolidated)

            extracted_data = self.state_manager.data.get("extracted_data", {})
            consolidated["financial_details"]   = analysis_results.get("financial",   {})
            consolidated["market_details"]      = analysis_results.get("market",      {})
            consolidated["competitive_details"] = analysis_results.get("competitive", {})
            consolidated["sources"]             = extracted_data.get("sources",       [])

            # ── attach all Phase 1 metadata for reporting ─────────────────
            routing_config  = self.state_manager.data.get("routing_config", {})
            review_metadata = self.state_manager.data.get("review_metadata", {})
            consolidated["routing_metadata"] = {
                "confidence_tier":    routing_config.get("confidence_tier",    "medium"),
                "rationale":          routing_config.get("rationale",          ""),
                "self_correction":    extracted_data.get("meta", {}).get(
                    "self_correction_applied", False
                ),
                "confidence_score":   extracted_data.get("meta", {}).get(
                    "confidence_score", None
                ),
                "extraction_method":  extracted_data.get("meta", {}).get(
                    "extraction_method", "regex"
                ),
                "agent_reviews": {
                    "financial": {
                        "confidence": review_metadata.get("financial", {}).get("confidence"),
                        "verdict":    review_metadata.get("financial", {}).get("verdict"),
                        "issues":     review_metadata.get("financial", {}).get("issues", []),
                    },
                    "market": {
                        "confidence": review_metadata.get("market", {}).get("confidence"),
                        "verdict":    review_metadata.get("market", {}).get("verdict"),
                        "issues":     review_metadata.get("market", {}).get("issues", []),
                    },
                },
            }

            is_partial = (
                self.state_manager.data.get("analysis_partial",   False) or
                self.state_manager.data.get("extraction_partial",  False) or
                self.state_manager.data.get("scraping_partial",    False)
            )
            if is_partial:
                self._warn_partial("Consolidation based on partial data.")

            self.state_manager.add_data("consolidated_output",   consolidated)
            self.state_manager.add_data("consolidation_partial", is_partial)
            self.state_manager.update_progress(95)
            self.state_manager.update_state(SystemState.GENERATING_REPORT)
        except Exception as exc:
            self._fail(f"Consolidation failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # REPORT GENERATION
    # ═══════════════════════════════════════════════════════════════════════

    def handle_report_generation(self):
        self.logger.info("Handling report generation phase")
        consolidated = self.state_manager.data.get("consolidated_output")
        if not consolidated:
            self._fail("No consolidated output for report generation"); return
        try:
            from ..output.report_generator import ReportGenerator
            paths = ReportGenerator().generate(consolidated)
            if not paths:
                self._fail("Report generation returned no paths"); return
            self.state_manager.add_data("report_paths", paths)
            self.state_manager.update_progress(100)
            self.state_manager.update_state(SystemState.COMPLETED)
        except Exception as exc:
            self._fail(f"Report generation failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _gap_fill_search(
        self,
        queries:         list[str],
        structured_input: dict,
    ) -> dict | None:
        """
        Run targeted queries through the routed SearchEngine + Scraper + Extractor
        and return a fresh extracted_data dict (or None on total failure).

        Queries may contain {idea} / {industry} placeholders from the heuristic
        review; these are filled from structured_input before executing.
        """
        idea     = structured_input.get("business_idea", "")
        industry = structured_input.get("industry",      "")
        filled   = [
            q.replace("{idea}", idea).replace("{industry}", industry)
            for q in queries
        ]
        self.logger.info(f"Gap-fill search: {filled}")

        try:
            se          = SearchEngine(max_results_per_query=3)
            all_results = []
            for q in filled:
                all_results.extend(se.search_query(q))

            if not all_results:
                return None

            scraper = WebScraper(max_parallel=3)
            scraped = scraper.scrape(all_results)
            if not scraped:
                return None

            return ExtractionEngine().process(scraped)

        except Exception as exc:
            self.logger.warning(f"Gap-fill search failed: {exc}")
            return None

    def _run_supplemental_scraping(
        self,
        extra_queries:    list[str],
        structured_data:  dict,
        structured_input: dict,
    ) -> dict:
        idea     = structured_input.get("business_idea", "")
        industry = structured_input.get("industry",      "")
        filled   = [
            q.format(idea=idea, industry=industry) for q in extra_queries
        ]
        se          = SearchEngine(max_results_per_query=3)
        all_results = []
        for q in filled:
            all_results.extend(se.search_query(q))
        if not all_results:
            return structured_data
        scraper = WebScraper(max_parallel=3)
        extra   = scraper.scrape(all_results)
        if not extra:
            return structured_data
        from ..agents.extraction_engine import ExtractionEngine
        extra_data = ExtractionEngine().process(extra)
        merged     = dict(structured_data)
        _merge_entities(merged,   extra_data)
        _merge_financials(merged, extra_data)
        _merge_keywords(merged,   extra_data)
        return merged

    @staticmethod
    def _default_analysis_output(kind: str) -> dict:
        defaults = {
            "financial":   {"metrics": {}, "runway_months": 0, "viability_score": 0.3,
                            "risks": [], "recommendations": ["Insufficient financial data"],
                            "summary": "Financial analysis could not be completed"},
            "competitive": {"competitors_found": 0, "top_competitors": [],
                            "competitive_intensity": "Unknown",
                            "swot_analysis": {"strengths": [], "weaknesses": [],
                                              "opportunities": [], "threats": []},
                            "market_gaps": [],
                            "summary": "Competitive analysis could not be completed"},
            "market":      {"market_size": {"global": 0, "currency": "USD"},
                            "tam_sam_som": {"tam": 0, "sam": 0, "som": 0},
                            "growth_rate": 0, "sentiment": {"score": 0, "label": "Unknown"},
                            "opportunity_score": 0.3, "key_insights": [],
                            "summary": "Market analysis could not be completed"},
        }
        return defaults.get(kind, {})

    def finish_workflow(self):
        self.logger.info("Workflow finalized")
        # Clean up ChromaDB session store
        rag = self.state_manager.data.get("rag")
        if rag is not None:
            try:
                rag.cleanup()
            except Exception as exc:
                self.logger.warning(f"RAG cleanup failed (non-fatal): {exc}")
        self.state_manager.dump_to_file()


# ─────────────────────────────────────────────────────────────────────────────
# Module-level helpers
# ─────────────────────────────────────────────────────────────────────────────

def _empty_extraction() -> dict:
    return {
        "entities":          {"organizations": [], "people": [], "locations": []},
        "financial_metrics": {k: [] for k in ["startup_costs", "revenue_figures",
                                               "funding_amounts", "market_sizes",
                                               "growth_rates"]},
        "keywords":          [],
        "swot_signals":      {"strengths": [], "weaknesses": [],
                              "opportunities": [], "threats": []},
        "meta":              {"num_pages": 0, "avg_page_quality": 0.0,
                              "pages_with_any_financial_signals": 0,
                              "pages_with_any_market_signals": 0,
                              "pages_with_any_growth_signals": 0},
        "sources":           [],
    }


def _default_routing() -> dict:
    return {"run_financial": True, "run_competitive": True, "run_market": True,
            "additional_queries": [], "confidence_tier": "medium",
            "rationale": "Default routing."}


def _merge_entities(base: dict, extra: dict) -> None:
    for key in ["organizations", "people", "locations"]:
        base.setdefault("entities", {}).setdefault(key, [])
        base["entities"][key] = list(dict.fromkeys(
            base["entities"][key] + extra.get("entities", {}).get(key, [])
        ))


def _merge_financials(base: dict, extra: dict) -> None:
    for key in ["startup_costs", "revenue_figures", "funding_amounts",
                "market_sizes", "growth_rates"]:
        base.setdefault("financial_metrics", {}).setdefault(key, [])
        base["financial_metrics"][key] = list(set(
            base["financial_metrics"][key] +
            extra.get("financial_metrics", {}).get(key, [])
        ))


def _merge_keywords(base: dict, extra: dict) -> None:
    base["keywords"] = list(set(base.get("keywords", [])) |
                            set(extra.get("keywords", [])))