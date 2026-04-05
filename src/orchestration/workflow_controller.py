import sys
import threading
from pathlib import Path
from typing import Dict, Any, Optional

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
from ..agents.search_engine import SearchEngine, SearchEngineConfig
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
                # FIX: ANALYZING must transition to CONSOLIDATING, not call
                # handle_consolidation() directly (that caused the double-fire bug).
                elif state == SystemState.ANALYZING:          self.state_manager.update_state(SystemState.CONSOLIDATING)
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
    # INITIALIZATION
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

    # ═══════════════════════════════════════════════════════════════════════
    # SEARCH
    # ═══════════════════════════════════════════════════════════════════════

    def handle_search(self):
        self.logger.info("Handling search phase")
        structured_input = self.state_manager.data.get("structured_input")
        if not structured_input:
            self._fail("No structured input found for search"); return
        try:
            se    = SearchEngine(SearchEngineConfig(max_results=5))
            query = structured_input.get("business_idea") or structured_input.get("query", "")

            results = se.search(query)

            if not results:
                self.logger.warning("Primary search returned nothing — trying backup queries")
                for bq in structured_input.get("search_queries", []):
                    try:
                        results = se.search(bq)
                        if results:
                            self.logger.info(f"Got results via backup query: {bq[:60]}")
                            break
                    except Exception as bq_exc:
                        self.logger.warning(f"Backup query failed: {bq_exc}")

            if not results:
                self.logger.warning("Backup queries empty — falling back to Wikipedia")
                try:
                    results = se.wikipedia_search(query, max_results=5)
                    if results:
                        self.logger.info(f"Got {len(results)} results from Wikipedia fallback")
                except Exception as wiki_exc:
                    self.logger.warning(f"Wikipedia fallback failed: {wiki_exc}")

            if not results:
                self._fail("Search returned empty results from all sources"); return

            self.state_manager.add_data("search_results", results)
            self.state_manager.update_progress(40)
            self.state_manager.update_state(SystemState.SEARCHING)
        except Exception as exc:
            self._fail(f"Search failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # SCRAPING
    # ═══════════════════════════════════════════════════════════════════════

    def handle_scraping(self):
        self.logger.info("Handling scraping phase")
        search_results = self.state_manager.data.get("search_results")
        if not search_results:
            self._fail("No search results available for scraping"); return
        try:
            scraper       = WebScraper(max_parallel=5)
            scraped       = scraper.scrape(search_results)
            min_threshold = SCRAPING_SETTINGS.get("min_pages_threshold", 3)
            if not scraped:
                self._fail("Scraping returned no usable data"); return
            if len(scraped) < min_threshold:
                self._warn_partial(
                    f"Scraping returned only {len(scraped)} page(s) "
                    f"(min={min_threshold}). Proceeding with partial data."
                )
            self.state_manager.add_data("scraped_content",  scraped)
            self.state_manager.add_data("scraping_partial", len(scraped) < min_threshold)
            # FIX: after a _warn_partial the state gets set to ERROR then immediately
            # back to SCRAPING here — ensure we always leave in SCRAPING state.
            self.state_manager.update_progress(60)
            self.state_manager.update_state(SystemState.SCRAPING)
        except Exception as exc:
            self._fail(f"Scraping failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # RAG INDEXING
    # ═══════════════════════════════════════════════════════════════════════

    def handle_rag_indexing(self):
        self.logger.info("Handling RAG indexing phase")
        scraped_content = self.state_manager.data.get("scraped_content", [])

        if not RAG_SETTINGS.get("enabled", True):
            self.logger.info("RAG disabled via settings — skipping")
            self.state_manager.update_state(SystemState.RAG_INDEXING)
            return

        try:
            session_id = getattr(self.state_manager, "session_id", None)
            rag = RAGManager(session_id=session_id)

            def _index():
                rag.index(scraped_content)

            t = threading.Thread(target=_index, daemon=True)
            t.start()
            t.join(timeout=30)

            if rag.is_ready():
                self.logger.info("RAG indexing complete")
                self.state_manager.add_data("rag", rag)
            else:
                self.logger.warning(
                    "RAG indexing did not complete within timeout — "
                    "continuing without RAG augmentation"
                )
        except Exception as exc:
            self._warn_partial(f"RAG indexing failed (non-fatal): {exc}")

        self.state_manager.update_state(SystemState.RAG_INDEXING)

    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACTION
    # ═══════════════════════════════════════════════════════════════════════

    def handle_extraction(self):
        self.logger.info("Handling extraction phase")
        scraped_content  = self.state_manager.data.get("scraped_content")
        structured_input = self.state_manager.data.get("structured_input", {})
        if not scraped_content:
            self._fail("No scraped content found for extraction"); return
        try:
            engine = ExtractionEngine()
            data   = engine.process(scraped_content)
            if not data:
                self._warn_partial("Extraction returned empty output — using stub")
                data = _empty_extraction()

            try:
                from ..agents.self_correction_agent import SelfCorrectionAgent
                data = SelfCorrectionAgent().run(data, scraped_content)
            except Exception as exc:
                self._warn_partial(f"Self-correction failed (non-fatal): {exc}")

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

            self.state_manager.add_data("extracted_data",     data)
            self.state_manager.add_data("extraction_partial", extraction_partial)
            self.state_manager.add_data("routing_config",     routing_config)
            self.state_manager.update_progress(75)
            self.state_manager.update_state(SystemState.EXTRACTING)
        except Exception as exc:
            self._fail(f"Extraction failed: {exc}")

    # ═══════════════════════════════════════════════════════════════════════
    # ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════

    def handle_analysis(self):
        self.logger.info("Handling analysis phase")

        raw_extracted    = self.state_manager.data.get("extracted_data")
        structured_input = self.state_manager.data.get("structured_input")
        routing_config: Dict[str, Any] = self.state_manager.data.get("routing_config") or _default_routing()
        rag              = self.state_manager.data.get("rag")

        if not raw_extracted or not structured_input:
            self._fail("Missing data for analysis"); return

        def search_callback(queries: list) -> Optional[Dict[str, Any]]:
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
                    rag              = rag,
                )
                review_metadata["financial"] = result.pop("review", {})
                results["financial"]         = result
            except Exception as exc:
                self._warn_partial(f"Financial analysis failed: {exc}")
                analysis_failures.append("financial")
                results["financial"] = self._default_analysis_output("financial")
        else:
            results["financial"] = self._default_analysis_output("financial")

        # ── COMPETITIVE ──────────────────────────────────────────────────
        if routing_config.get("run_competitive", True):
            try:
                results["competitive"] = CompetitiveAnalysisAgent().run(
                    raw_extracted, rag=rag
                )
            except Exception as exc:
                self._warn_partial(f"Competitive analysis failed: {exc}")
                analysis_failures.append("competitive")
                results["competitive"] = self._default_analysis_output("competitive")
        else:
            results["competitive"] = self._default_analysis_output("competitive")

        # ── MARKET ───────────────────────────────────────────────────────
        if routing_config.get("run_market", True):
            try:
                ma     = MarketAnalysisAgent()
                result = ma.run_with_review(
                    extracted_data   = raw_extracted,
                    structured_input = structured_input,
                    search_callback  = search_callback,
                    rag              = rag,
                )
                review_metadata["market"] = result.pop("review", {})
                results["market"]         = result
            except Exception as exc:
                self._warn_partial(f"Market analysis failed: {exc}")
                analysis_failures.append("market")
                results["market"] = self._default_analysis_output("market")
        else:
            results["market"] = self._default_analysis_output("market")

        if len(analysis_failures) == 3:
            self._fail("All analysis stages failed — cannot proceed"); return

        self.state_manager.add_data("analysis_results", results)
        self.state_manager.add_data("review_metadata",  review_metadata)
        self.state_manager.add_data("analysis_partial", bool(analysis_failures))
        self.state_manager.update_progress(85)
        # FIX: set ANALYZING so the FSM loop picks it up and transitions
        # it to CONSOLIDATING on the next iteration (not a direct call).
        self.state_manager.update_state(SystemState.ANALYZING)

    # ═══════════════════════════════════════════════════════════════════════
    # CONSOLIDATION
    # ═══════════════════════════════════════════════════════════════════════

    def handle_consolidation(self):
        self.logger.info("Handling consolidation phase")
        analysis_results = self.state_manager.data.get("analysis_results")
        rag              = self.state_manager.data.get("rag")

        if not analysis_results:
            self._fail("No analysis results for consolidation"); return

        try:
            structured_input = self.state_manager.data.get("structured_input", {})
            extracted_data   = self.state_manager.data.get("extracted_data", {})
            routing_config   = self.state_manager.data.get("routing_config", {})
            review_metadata  = self.state_manager.data.get("review_metadata", {})

            cached = self.cache_manager.get_consolidation_cache(structured_input)
            if cached and _cache_is_valid(cached):
                self.logger.info("Using cached consolidation results")
                consolidated = cached
            else:
                if cached:
                    self.logger.warning("Cached consolidation is stale — regenerating")
                from ..agents.consolidation_agent import ConsolidationAgent
                consolidated = ConsolidationAgent().consolidate(
                    financial_result   = analysis_results.get("financial",   {}),
                    market_result      = analysis_results.get("market",      {}),
                    competitive_result = analysis_results.get("competitive", {}),
                    business_input     = structured_input,
                    rag                = rag,
                )

                consolidated["financial_details"]   = analysis_results.get("financial",   {})
                consolidated["market_details"]      = analysis_results.get("market",      {})
                consolidated["competitive_details"] = analysis_results.get("competitive", {})
                consolidated["sources"]             = extracted_data.get("sources", [])
                consolidated["routing_metadata"]    = {
                    "confidence_tier":   routing_config.get("confidence_tier",   "medium"),
                    "rationale":         routing_config.get("rationale",         ""),
                    "self_correction":   extracted_data.get("meta", {}).get("self_correction_applied", False),
                    "confidence_score":  extracted_data.get("meta", {}).get("confidence_score", None),
                    "extraction_method": extracted_data.get("meta", {}).get("extraction_method", "regex"),
                    "agent_reviews": {
                        "financial": review_metadata.get("financial", {}),
                        "market":    review_metadata.get("market",    {}),
                    },
                }

                consolidated = _normalise_for_report(consolidated, analysis_results)

                self.cache_manager.set_consolidation_cache(structured_input, consolidated)

            is_partial = any([
                self.state_manager.data.get("analysis_partial",    False),
                self.state_manager.data.get("extraction_partial",  False),
                self.state_manager.data.get("scraping_partial",    False),
            ])

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

    def _gap_fill_search(self, queries: list, structured_input: dict) -> Optional[Dict[str, Any]]:
        idea     = structured_input.get("business_idea", "")
        industry = structured_input.get("industry",      "")
        filled   = [q.replace("{idea}", idea).replace("{industry}", industry) for q in queries]

        self.logger.info(f"Gap-fill search: {filled}")
        try:
            se          = SearchEngine(SearchEngineConfig(max_results=3))
            all_results = []
            for q in filled:
                all_results.extend(se.search(q))
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

    def _run_supplemental_scraping(self, extra_queries: list, structured_data: dict, structured_input: dict) -> dict:
        idea     = structured_input.get("business_idea", "")
        industry = structured_input.get("industry",      "")
        filled   = [q.format(idea=idea, industry=industry) for q in extra_queries]

        se          = SearchEngine(SearchEngineConfig(max_results=3))
        all_results = []
        for q in filled:
            all_results.extend(se.search(q))
        if not all_results:
            return structured_data

        scraper    = WebScraper(max_parallel=3)
        extra      = scraper.scrape(all_results)
        if not extra:
            return structured_data

        extra_data = ExtractionEngine().process(extra)
        merged     = dict(structured_data)
        _merge_entities(merged,   extra_data)
        _merge_financials(merged, extra_data)
        _merge_keywords(merged,   extra_data)
        return merged

    @staticmethod
    def _default_analysis_output(kind: str) -> dict:
        defaults = {
            "financial":   {
                "viability_score":  0.3,
                "runway_months":    0,
                "recommendations":  ["Insufficient data — please provide more detail."],
                "risks":            [],
                "summary":          "Insufficient financial data.",
                "data_confidence":  "Low",
                "metrics": {
                    "total_estimated_cost": 0,
                    "monthly_burn":         0,
                    "estimated_revenue":    0,
                    "growth_rate":          0,
                    "profit_margin":        0,
                },
            },
            "competitive": {
                "competitors_found":      0,
                "top_competitors":        [],
                "competitive_intensity":  "Low",
                "swot_analysis": {
                    "strengths":     [],
                    "weaknesses":    [],
                    "opportunities": [],
                    "threats":       [],
                },
                "market_gaps":     ["Insufficient data."],
                "summary":         "No competitive data available.",
                "data_confidence": "Low",
            },
            "market": {
                "opportunity_score": 0.3,
                "growth_rate":       0,
                "market_size":       {"global": 0, "currency": "USD"},
                "sentiment":         {"label": "Neutral", "score": 0,
                                      "positive_signals": 0, "negative_signals": 0},
                "key_insights":      ["Insufficient market data."],
                "summary":           "No market data available.",
                "data_confidence":   "Low",
            },
        }
        return defaults.get(kind, {})

    def finish_workflow(self):
        self.logger.info("Workflow finalized")
        rag = self.state_manager.data.get("rag")
        if rag:
            try:
                rag.cleanup()
            except Exception as exc:
                self.logger.warning(f"RAG cleanup failed: {exc}")
        # dump_to_file now uses _safe_serializer so SearchResult objects won't crash it
        self.state_manager.dump_to_file()


# ─────────────────────────────────────────────────────────────────────────────
# Merge Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _empty_extraction() -> dict:
    return {
        "entities":          {"organizations": [], "people": [], "locations": []},
        "financial_metrics": {k: [] for k in ["startup_costs", "revenue_figures",
                                               "funding_amounts", "market_sizes", "growth_rates"]},
        "keywords":          [],
        "swot_signals":      {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        "meta":              {"num_pages": 0},
        "sources":           [],
    }


def _default_routing() -> dict:
    return {
        "run_financial":      True,
        "run_competitive":    True,
        "run_market":         True,
        "additional_queries": [],
        "confidence_tier":    "medium",
        "rationale":          "",
    }


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
            base["financial_metrics"][key] + extra.get("financial_metrics", {}).get(key, [])
        ))


def _merge_keywords(base: dict, extra: dict) -> None:
    base["keywords"] = list(set(base.get("keywords", [])) | set(extra.get("keywords", [])))


# ─────────────────────────────────────────────────────────────────────────────
# Cache validation
# ─────────────────────────────────────────────────────────────────────────────

def _cache_is_valid(cached: dict) -> bool:
    required = [
        "overall_viability_score", "overall_rating",
        "financial_score", "market_score", "competitive_score",
        "aggregated_risks", "final_recommendations",
        "executive_summary", "decision",
        "financial_details", "market_details", "competitive_details",
    ]
    return all(k in cached for k in required)


# ─────────────────────────────────────────────────────────────────────────────
# Schema Normalisation
# ─────────────────────────────────────────────────────────────────────────────

def _normalise_for_report(consolidated: dict, analysis_results: dict) -> dict:
    fin  = analysis_results.get("financial",   {}) or {}
    mkt  = analysis_results.get("market",      {}) or {}
    comp = analysis_results.get("competitive", {}) or {}

    financial_score   = float(fin.get("viability_score",   0.0) or 0.0)
    market_score      = float(mkt.get("opportunity_score", 0.0) or 0.0)
    intensity_map     = {"Low": 0.85, "Medium": 0.60, "High": 0.35}
    comp_intensity    = comp.get("competitive_intensity", "Medium")
    competitive_score = intensity_map.get(comp_intensity, 0.60)

    consolidated.setdefault("financial_score",   financial_score)
    consolidated.setdefault("market_score",      market_score)
    consolidated.setdefault("competitive_score", competitive_score)

    viability = float(consolidated.get("overall_viability_score", 0.0) or 0.0)
    if viability >= 0.65:
        rating = "Strong"
    elif viability >= 0.40:
        rating = "Moderate"
    else:
        rating = "Weak"
    consolidated.setdefault("overall_rating", rating)

    raw_risks        = consolidated.get("risk_assessment", []) or []
    aggregated_risks = []
    for risk in raw_risks:
        if isinstance(risk, dict):
            aggregated_risks.append({
                "category": risk.get("category", "General"),
                "severity": risk.get("severity", "Medium"),
                "message":  risk.get("message",  str(risk)),
            })
        elif isinstance(risk, str) and risk.strip():
            aggregated_risks.append({
                "category": "General",
                "severity": "Medium",
                "message":  risk,
            })
    consolidated.setdefault("aggregated_risks", aggregated_risks)

    recs = consolidated.get("strategic_recommendations", []) or []
    consolidated.setdefault(
        "final_recommendations",
        [r for r in recs if isinstance(r, str) and r.strip()],
    )

    if viability >= 0.60:
        decision = "Proceed"
    elif viability >= 0.35:
        decision = "Proceed with Caution"
    else:
        decision = "Re-evaluate"
    consolidated.setdefault("decision", decision)

    es = consolidated.get("executive_summary", "")
    if not isinstance(es, str):
        consolidated["executive_summary"] = str(es)

    return consolidated