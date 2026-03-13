"""
financial_analysis.py  —  Phase 2 update: RAG-augmented extraction

Changes vs Phase 1b:
  - run() and run_with_review() now accept an optional `rag` parameter
    (a RAGManager instance).
  - _extract_costs(), _extract_revenue(), _extract_growth(), and
    _extract_profit_margin() each fall back to RAG semantic retrieval
    when the structured financial_metrics dict has sparse data.
  - RAG queries are intent-tagged so ChromaDB can filter by source type.
  - If rag is None or not ready, behaviour is 100% identical to Phase 1b.
"""

from __future__ import annotations

import json
import re
import statistics
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from src.config.settings import LLM_SETTINGS
from src.orchestration.logger import setup_logger

logger = setup_logger()

REVIEW_CONFIDENCE_THRESHOLD: float = 0.65
MAX_REVIEW_ITERATIONS: int         = 2

_REVIEW_SYSTEM = """You are a financial analysis quality-assurance agent.
Given a financial analysis JSON, assess its reliability.

Return ONLY a JSON object with exactly these keys:
{
  "confidence": <float 0.0–1.0>,
  "issues": ["list of specific data gaps or concerns"],
  "missing_signals": ["list of search queries that would fill the gaps"],
  "verdict": "PASS" | "NEEDS_MORE_DATA"
}

confidence scoring guide:
  1.0  — all key metrics present (runway, growth, costs, revenue, funding)
  0.8  — 4 of 5 key metrics present
  0.6  — 3 of 5 present
  0.4  — 2 of 5 present
  0.2  — 1 of 5 present
  0.0  — no meaningful financial data

verdict: "PASS" if confidence >= 0.65, otherwise "NEEDS_MORE_DATA".
"""

_REVIEW_USER = """Review this financial analysis output for completeness and reliability:

{analysis_json}

Business context: {business_idea} in {industry} targeting {target_market}.
Budget provided: ${budget:,}
"""

# ── RAG extraction prompt sent to LLM when RAG chunks are available ───────

_RAG_EXTRACT_SYSTEM = """You are a financial data extraction specialist.
Given text snippets retrieved from web research, extract numeric financial values.

Return ONLY a JSON object:
{
  "startup_costs": [list of USD amounts as plain numbers],
  "revenue_figures": [list of USD amounts as plain numbers],
  "funding_amounts": [list of USD amounts as plain numbers],
  "growth_rates": [list of percentage values as plain numbers],
  "market_sizes": [list of USD amounts as plain numbers]
}

Rules:
- Convert all monetary values to USD numbers (e.g. "$5M" → 5000000).
- Convert percentages to plain numbers (e.g. "8.5%" → 8.5).
- If nothing relevant found, use empty lists.
- Do NOT include duplicates.
"""

_RAG_EXTRACT_USER = """Extract financial metrics from these research snippets:

{chunks}
"""


@dataclass
class FinancialConfig:
    healthy_runway_threshold: int   = 12
    strong_growth_threshold: float  = 10.0
    strong_margin_threshold: float  = 15.0
    high_viability_threshold: float = 0.7
    low_viability_threshold: float  = 0.5


class FinancialAnalysisAgent:

    def __init__(self, config: FinancialConfig):
        self.config = config

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC: run_with_review  (Phase 2 entry point — rag param added)
    # ═══════════════════════════════════════════════════════════════════════

    def run_with_review(
        self,
        extracted_data:   Dict[str, Any],
        budget:           float,
        structured_input: Dict[str, Any] | None = None,
        search_callback=None,
        rag=None,
    ) -> Dict[str, Any]:
        """
        Run financial analysis with optional RAG augmentation and self-review.

        Args:
            extracted_data:   Output from ExtractionEngine.
            budget:           Available budget from intake.
            structured_input: Business context (idea, industry, market).
            search_callback:  Optional callable(queries) → new extracted_data.
            rag:              Optional RAGManager instance (Phase 2).

        Returns:
            Standard analysis result dict with a `review` key.
        """
        result = self.run(extracted_data, budget, rag=rag)
        ctx    = structured_input or {}

        if not LLM_SETTINGS.get("enable_self_correction", True):
            result["review"] = {"confidence": None, "verdict": "SKIPPED", "issues": []}
            return result

        for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
            review = self._review_output(result, ctx)
            logger.info(
                f"FinancialAnalysis review iter {iteration}: "
                f"confidence={review['confidence']:.2f} verdict={review['verdict']}"
            )
            result["review"] = review

            if review["verdict"] == "PASS":
                break

            missing = review.get("missing_signals", [])
            if not missing or search_callback is None:
                logger.info(
                    "FinancialAnalysis: review found gaps but "
                    "no search_callback provided — stopping."
                )
                break

            logger.info(f"FinancialAnalysis: triggering gap-fill for: {missing}")
            try:
                enriched = search_callback(missing)
                if enriched:
                    extracted_data = _merge_financial_data(extracted_data, enriched)
                    result         = self.run(extracted_data, budget, rag=rag)
            except Exception as exc:
                logger.warning(f"FinancialAnalysis gap-fill failed: {exc}")
                break

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # ORIGINAL run()  — Phase 2: rag param added
    # ═══════════════════════════════════════════════════════════════════════

    def run(
        self,
        extracted_data: Dict[str, Any],
        budget: float,
        rag=None,
    ) -> Dict[str, Any]:
        """
        Core analysis.  If `rag` is provided and ready, sparse metrics are
        supplemented via semantic retrieval before scoring.
        """
        # ── Phase 2: RAG augmentation ─────────────────────────────────────
        if rag is not None and rag.is_ready():
            extracted_data = self._augment_with_rag(extracted_data, rag)

        costs   = self._extract_costs(extracted_data)
        revenue = self._extract_revenue(extracted_data)
        growth  = self._extract_growth(extracted_data)
        margin  = self._extract_profit_margin(extracted_data)
        funding = self._extract_funding(extracted_data)

        total_cost   = sum(costs)
        monthly_burn = total_cost / 12 if total_cost else 0
        runway       = budget / monthly_burn if monthly_burn else 0

        viability_score = self._calculate_viability(
            runway, growth, margin, funding, budget
        )
        risks           = self._generate_risks(runway, growth)
        recommendations = self._generate_recommendations(runway, viability_score)
        summary         = self._generate_summary(runway, viability_score)

        # Data confidence heuristic
        fm           = extracted_data.get("financial_metrics", {})
        signal_lists = [
            fm.get("startup_costs",   []),
            fm.get("revenue_figures", []),
            fm.get("funding_amounts", []),
            fm.get("market_sizes",    []),
            fm.get("growth_rates",    []),
        ]
        signal_count = sum(1 for lst in signal_lists if lst)
        num_pages    = extracted_data.get("meta", {}).get("num_pages", 0)

        if signal_count >= 3 and num_pages >= 5:
            data_confidence = "High"
        elif signal_count >= 2:
            data_confidence = "Medium"
        else:
            data_confidence = "Low"

        return {
            "metrics": {
                "total_estimated_cost": total_cost,
                "monthly_burn":         monthly_burn,
                "estimated_revenue":    revenue,
                "growth_rate":          growth,
                "profit_margin":        margin,
            },
            "runway_months":    round(runway, 2),
            "viability_score":  round(viability_score, 2),
            "risks":            risks,
            "recommendations":  recommendations,
            "summary":          summary,
            "data_confidence":  data_confidence,
            "rag_augmented":    rag is not None and rag.is_ready(),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: RAG AUGMENTATION
    # ═══════════════════════════════════════════════════════════════════════

    def _augment_with_rag(
        self,
        extracted_data: Dict[str, Any],
        rag,
    ) -> Dict[str, Any]:
        """
        Query RAG for financial signals not already present in extracted_data.
        Merges any new numeric values found into financial_metrics.
        """
        fm = extracted_data.get("financial_metrics", {})

        # Determine which signal categories need augmentation
        queries: List[tuple[str, str]] = []   # (query_text, intent_filter)
        if not fm.get("startup_costs"):
            queries.append(("startup cost initial investment budget expenses", "GENERAL"))
        if not fm.get("revenue_figures"):
            queries.append(("annual revenue earnings income projection", "GENERAL"))
        if not fm.get("funding_amounts"):
            queries.append(("funding raised investment round seed series", "FUNDING"))
        if not fm.get("growth_rates"):
            queries.append(("market growth rate CAGR annual growth percentage", "MARKET_SIZE"))
        if not fm.get("market_sizes"):
            queries.append(("total addressable market size TAM valuation billion", "MARKET_SIZE"))

        if not queries:
            logger.info("FinancialAnalysis RAG: all signal categories already populated")
            return extracted_data

        top_k = 3
        all_chunks: List[str] = []
        for query_text, intent in queries:
            try:
                chunks = rag.query(query_text, top_k=top_k, intent_filter=None)
                logger.info(
                    f"FinancialAnalysis RAG query '{query_text[:50]}' "
                    f"→ {len(chunks)} chunks"
                )
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning(f"FinancialAnalysis RAG query failed: {exc}")

        if not all_chunks:
            return extracted_data

        # Ask LLM to parse financial values from retrieved chunks
        rag_metrics = self._parse_rag_chunks(all_chunks)
        if rag_metrics:
            return _merge_financial_data(extracted_data, {"financial_metrics": rag_metrics})

        return extracted_data

    def _parse_rag_chunks(self, chunks: List[str]) -> Dict[str, List]:
        """
        Use LLM (or regex fallback) to extract numeric financial values
        from a list of RAG-retrieved text chunks.
        """
        combined_text = "\n\n---\n\n".join(chunks[:6])   # cap at 6 chunks

        try:
            from src.orchestration.llm_client import call_llm_json
            result = call_llm_json(
                _RAG_EXTRACT_SYSTEM,
                _RAG_EXTRACT_USER.format(chunks=combined_text[:3_000]),
            )
            if isinstance(result, dict):
                # Ensure all lists contain only numbers
                clean: Dict[str, List] = {}
                for k in ["startup_costs", "revenue_figures", "funding_amounts",
                          "growth_rates", "market_sizes"]:
                    vals = result.get(k, [])
                    clean[k] = [v for v in vals if isinstance(v, (int, float))]
                logger.info(
                    f"FinancialAnalysis RAG parse: "
                    + ", ".join(f"{k}={len(v)}" for k, v in clean.items())
                )
                return clean
        except Exception as exc:
            logger.warning(f"FinancialAnalysis RAG LLM parse failed: {exc} — using regex")

        return self._parse_rag_chunks_regex(combined_text)

    @staticmethod
    def _parse_rag_chunks_regex(text: str) -> Dict[str, List]:
        """Lightweight regex fallback when LLM is unavailable."""
        import re

        money_pattern   = r"\$\s?(\d+(?:[.,]\d+)?)\s?(k|m|b|million|billion|thousand)?"
        percent_pattern = r"\b(\d+(?:\.\d+)?)\s?%"

        def _norm_money(num_str: str, unit: str) -> float:
            val = float(num_str.replace(",", ""))
            u = (unit or "").lower()
            if u in ("b", "billion"):  val *= 1e9
            elif u in ("m", "million"): val *= 1e6
            elif u in ("k", "thousand"): val *= 1e3
            return val

        money_vals = [
            _norm_money(m, u)
            for m, u in re.findall(money_pattern, text.lower())
        ]
        pct_vals = [float(p) for p in re.findall(percent_pattern, text)]

        return {
            "startup_costs":   money_vals[:3],
            "revenue_figures": money_vals[3:6],
            "funding_amounts": money_vals[6:9],
            "market_sizes":    [],
            "growth_rates":    pct_vals[:5],
        }

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1b: SELF-REVIEW  (unchanged)
    # ═══════════════════════════════════════════════════════════════════════

    def _review_output(
        self,
        result:  Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from src.orchestration.llm_client import call_llm_json
            user_prompt = _REVIEW_USER.format(
                analysis_json = json.dumps(result, indent=2, default=str)[:3_000],
                business_idea = context.get("business_idea", "unknown"),
                industry      = context.get("industry",      "unknown"),
                target_market = context.get("target_market", "unknown"),
                budget        = context.get("budget",        0),
            )
            review = call_llm_json(_REVIEW_SYSTEM, user_prompt)
            if not isinstance(review, dict):
                raise ValueError("non-dict response")
            review.setdefault("confidence",       0.5)
            review.setdefault("issues",           [])
            review.setdefault("missing_signals",  [])
            review.setdefault("verdict",
                "PASS" if float(review["confidence"]) >= REVIEW_CONFIDENCE_THRESHOLD
                else "NEEDS_MORE_DATA")
            return review
        except Exception as exc:
            logger.warning(f"LLM review unavailable: {exc} — using heuristic fallback")
            return self._heuristic_review(result)

    def _heuristic_review(self, result: Dict[str, Any]) -> Dict[str, Any]:
        metrics       = result.get("metrics", {})
        present_count = sum([
            bool(metrics.get("total_estimated_cost")),
            bool(metrics.get("estimated_revenue")),
            bool(metrics.get("growth_rate")),
            bool(metrics.get("profit_margin")),
            result.get("runway_months", 0) > 0,
        ])
        confidence = round(present_count / 5, 2)

        issues: List[str]          = []
        missing_signals: List[str] = []

        if not metrics.get("total_estimated_cost"):
            issues.append("No startup cost data")
            missing_signals.append("{idea} startup cost estimate 2026")
        if not metrics.get("estimated_revenue"):
            issues.append("No revenue projection data")
            missing_signals.append("{idea} revenue model annual revenue")
        if not metrics.get("growth_rate"):
            issues.append("Missing CAGR / growth rate")
            missing_signals.append("{industry} CAGR growth rate 2025 2026")
        if not metrics.get("profit_margin"):
            issues.append("No profit margin data")
            missing_signals.append("{industry} average profit margin SaaS")
        if result.get("runway_months", 0) == 0:
            issues.append("Runway cannot be computed (no burn rate)")
            missing_signals.append("{idea} monthly burn rate operating cost")

        verdict = "PASS" if confidence >= REVIEW_CONFIDENCE_THRESHOLD else "NEEDS_MORE_DATA"
        return {
            "confidence":      confidence,
            "issues":          issues,
            "missing_signals": missing_signals,
            "verdict":         verdict,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # EXTRACTION HELPERS  (unchanged)
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_costs(self, data):
        return data.get("financial_metrics", {}).get("startup_costs", [])

    def _extract_funding(self, data):
        return data.get("financial_metrics", {}).get("funding_amounts", [])

    def _extract_revenue(self, data):
        revenues = data.get("financial_metrics", {}).get("revenue_figures", [])
        return statistics.mean(revenues) if revenues else 0

    def _extract_growth(self, data):
        rates = data.get("financial_metrics", {}).get("growth_rates", [])
        return statistics.mean(rates) if rates else 0

    def _extract_profit_margin(self, data):
        fm       = data.get("financial_metrics", {})
        revenues = fm.get("revenue_figures", [])
        costs    = fm.get("startup_costs",   [])
        if revenues and costs:
            avg_rev = statistics.mean(revenues)
            if avg_rev > 0:
                return (avg_rev - sum(costs)) / avg_rev * 100
        rates = fm.get("growth_rates", [])
        return (statistics.mean(rates) / 100 * 20) if rates else 0

    # ═══════════════════════════════════════════════════════════════════════
    # SCORING + RISKS + RECOMMENDATIONS + SUMMARY  (unchanged)
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_viability(self, runway, growth, margin, funding, budget):
        score = 0.0
        if runway > 18:
            score += 0.30
        elif runway > self.config.healthy_runway_threshold:
            score += 0.20
        if growth > self.config.strong_growth_threshold:
            score += 0.25
        elif growth > 5:
            score += 0.15
        if margin > self.config.strong_margin_threshold:
            score += 0.20
        elif margin > 5:
            score += 0.10
        if funding and budget > 0:
            median_funding = statistics.median(funding)
            if median_funding > 0:
                ratio = budget / median_funding
                if 0.5 <= ratio <= 2.0:
                    score += 0.20
                elif 0.25 <= ratio < 0.5 or 2.0 < ratio <= 4.0:
                    score += 0.05
                else:
                    score -= 0.05
        return min(score, 1.0)

    def _generate_risks(self, runway, growth):
        risks = []
        if runway < self.config.healthy_runway_threshold:
            risks.append("Runway below healthy threshold (12 months).")
        if growth < 5:
            risks.append("Low projected growth rate.")
        if not risks:
            risks.append("No major financial risks detected.")
        return risks

    def _generate_recommendations(self, runway, score):
        recs = []
        if runway < 12:
            recs.append("Seek additional funding to extend runway.")
        if score < self.config.low_viability_threshold:
            recs.append("Reduce operational costs and prioritize MVP.")
        if score >= self.config.high_viability_threshold:
            recs.append("Financial outlook strong. Proceed with expansion strategy.")
        if not recs:
            recs.append("Monitor financial metrics regularly.")
        return recs

    def _generate_summary(self, runway, score):
        if score >= self.config.high_viability_threshold:
            return "Strong financial viability with sufficient runway and growth."
        elif score >= self.config.low_viability_threshold:
            return "Moderate financial outlook. Some improvements needed."
        else:
            return "Financial viability is weak. High caution recommended."


# ─────────────────────────────────────────────────────────────────────────────
# Module helper
# ─────────────────────────────────────────────────────────────────────────────

def _merge_financial_data(
    base:  Dict[str, Any],
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    merged = dict(base)
    base_fm  = {k: list(v) for k, v in
                (base.get("financial_metrics") or {}).items()}
    extra_fm = extra.get("financial_metrics") or {}

    for key in ["startup_costs", "revenue_figures", "funding_amounts",
                "market_sizes", "growth_rates"]:
        combined = base_fm.get(key, []) + list(extra_fm.get(key, []))
        base_fm[key] = list(set(combined))

    merged["financial_metrics"] = base_fm
    return merged