"""
routing_agent.py  —  Phase 1c: Intelligent Routing

After extraction (and optional self-correction), the RoutingAgent inspects
the structured data and decides how the downstream analysis pipeline should
be configured:

  - Which analysis agents to run (financial / competitive / market).
  - Whether to request additional targeted scraping for a specific gap.
  - What confidence tier to assign (high / medium / low).
  - A short human-readable rationale for the routing decision.

Routing logic is LLM-assisted when the LLM is available, but always falls
back to a deterministic rule-based decision if the LLM is unavailable.
"""

from __future__ import annotations

from typing import Any

from src.config.settings import LLM_SETTINGS
from src.orchestration.logger import setup_logger

logger = setup_logger()


# ---------------------------------------------------------------------------
# Routing prompt
# ---------------------------------------------------------------------------

_ROUTING_SYSTEM_PROMPT = """You are a research orchestration agent.
Given a summary of extracted business intelligence data, decide how to
route the analysis pipeline.

Return a JSON object with exactly these keys:
{
  "run_financial":      true/false,
  "run_competitive":    true/false,
  "run_market":         true/false,
  "additional_queries": ["optional list of extra search queries to fill data gaps"],
  "confidence_tier":    "high" | "medium" | "low",
  "rationale":          "one-sentence explanation of the routing decision"
}

Rules:
- Set run_financial=false only if there are absolutely NO financial signals at all.
- Set run_competitive=false only if there are NO organizations/competitors at all.
- Set run_market=false only if there are NO market size or growth signals at all.
- additional_queries: suggest 0-3 targeted search queries to fill obvious gaps;
  leave empty if data quality is sufficient.
- confidence_tier: reflect overall data quality.
"""

_ROUTING_USER_TEMPLATE = """
DATA SUMMARY:
- Organizations found: {org_count}
- Financial signals: {financial_signals}
- Market size signals: {market_signals}
- Growth rate signals: {growth_signals}
- Keywords: {keyword_count}
- SWOT items: {swot_count}
- Pages scraped: {num_pages}
- Average page quality: {avg_quality}

Business idea: {business_idea}
Industry: {industry}
Target market: {target_market}

Decide the routing configuration for this analysis run.
"""


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class RoutingAgent:
    """
    Determines which analysis agents to activate and whether to request
    supplemental scraping before the analysis phase begins.
    """

    def __init__(self):
        self._enabled = LLM_SETTINGS.get("enable_smart_routing", True)
        logger.info(f"RoutingAgent initialized [enabled={self._enabled}]")

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def route(
        self,
        extracted_data:   dict,
        structured_input: dict,
    ) -> dict:
        """
        Determine routing configuration.

        Args:
            extracted_data:   Output from ExtractionEngine (after self-correction).
            structured_input: Output from IntakeAgent (business idea, budget, etc.)

        Returns:
            routing_config dict with keys:
                run_financial (bool)
                run_competitive (bool)
                run_market (bool)
                additional_queries (list[str])
                confidence_tier (str)
                rationale (str)
        """
        if self._enabled:
            try:
                return self._route_llm(extracted_data, structured_input)
            except Exception as exc:
                logger.warning(
                    f"LLM routing failed: {exc}. Falling back to rule-based routing."
                )

        return self._route_rules(extracted_data)

    # -----------------------------------------------------------------------
    # LLM routing
    # -----------------------------------------------------------------------

    def _route_llm(self, extracted_data: dict, structured_input: dict) -> dict:
        from src.orchestration.llm_client import call_llm_json

        summary = self._build_summary(extracted_data)
        user_prompt = _ROUTING_USER_TEMPLATE.format(
            org_count         = summary["org_count"],
            financial_signals = summary["financial_signals"],
            market_signals    = summary["market_signals"],
            growth_signals    = summary["growth_signals"],
            keyword_count     = summary["keyword_count"],
            swot_count        = summary["swot_count"],
            num_pages         = summary["num_pages"],
            avg_quality       = summary["avg_quality"],
            business_idea     = structured_input.get("business_idea", ""),
            industry          = structured_input.get("industry", ""),
            target_market     = structured_input.get("target_market", ""),
        )

        result = call_llm_json(_ROUTING_SYSTEM_PROMPT, user_prompt)

        if not isinstance(result, dict):
            raise ValueError(f"LLM routing returned non-dict: {type(result)}")

        return self._normalise_routing(result)

    # -----------------------------------------------------------------------
    # Rule-based fallback
    # -----------------------------------------------------------------------

    def _route_rules(self, extracted_data: dict) -> dict:
        """
        Deterministic routing based on signal presence.
        Mirrors the LLM routing logic but needs no network call.
        """
        s     = self._build_summary(extracted_data)
        fm    = extracted_data.get("financial_metrics", {})

        run_financial   = bool(
            fm.get("startup_costs") or fm.get("revenue_figures") or
            fm.get("funding_amounts") or fm.get("growth_rates")
        )
        run_competitive = s["org_count"] > 0
        run_market      = bool(fm.get("market_sizes") or fm.get("growth_rates"))

        # Always run at least one agent
        if not (run_financial or run_competitive or run_market):
            run_financial = run_competitive = run_market = True

        # Confidence tier
        if s["num_pages"] >= 5 and s["financial_signals"] >= 2:
            tier = "high"
        elif s["num_pages"] >= 2 or s["financial_signals"] >= 1:
            tier = "medium"
        else:
            tier = "low"

        # Suggest gap-filling queries
        additional_queries: list[str] = []
        if not run_financial:
            additional_queries.append("{idea} startup cost funding 2026")
        if not run_market:
            additional_queries.append("{industry} market size growth rate 2026")
        if not run_competitive:
            additional_queries.append("{idea} competitors market landscape")

        rationale_parts = []
        if not run_financial:
            rationale_parts.append("no financial signals found")
        if not run_competitive:
            rationale_parts.append("no competitor data found")
        if not run_market:
            rationale_parts.append("no market size data found")
        rationale = (
            "Skipping: " + "; ".join(rationale_parts) + "."
            if rationale_parts
            else "All analysis agents active based on available signals."
        )

        return {
            "run_financial":      run_financial,
            "run_competitive":    run_competitive,
            "run_market":         run_market,
            "additional_queries": additional_queries,
            "confidence_tier":    tier,
            "rationale":          rationale,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_summary(data: dict) -> dict:
        fm    = data.get("financial_metrics", {})
        meta  = data.get("meta", {})
        swot  = data.get("swot_signals", {})

        return {
            "org_count":         len(data.get("entities", {}).get("organizations", [])),
            "financial_signals": sum(
                1 for k in ["startup_costs", "revenue_figures", "funding_amounts"]
                if fm.get(k)
            ),
            "market_signals":    len(fm.get("market_sizes", [])),
            "growth_signals":    len(fm.get("growth_rates", [])),
            "keyword_count":     len(data.get("keywords", [])),
            "swot_count":        sum(len(v) for v in swot.values() if isinstance(v, list)),
            "num_pages":         meta.get("num_pages", 0),
            "avg_quality":       meta.get("avg_page_quality", 0),
        }

    @staticmethod
    def _normalise_routing(result: dict) -> dict:
        """Ensure all expected keys exist with safe defaults."""
        return {
            "run_financial":      bool(result.get("run_financial",      True)),
            "run_competitive":    bool(result.get("run_competitive",    True)),
            "run_market":         bool(result.get("run_market",         True)),
            "additional_queries": result.get("additional_queries", []) or [],
            "confidence_tier":    result.get("confidence_tier",    "medium"),
            "rationale":          result.get("rationale",          "LLM routing applied."),
        }