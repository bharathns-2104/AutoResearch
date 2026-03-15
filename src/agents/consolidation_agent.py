"""
consolidation_agent.py  —  Phase 2 update: cross-agent RAG synthesis

Fixes vs previous version:
  - Line ~150: key[:80] guarded with `or ""` so Pyre2/mypy don't flag
    slicing a potentially-None value.
  - Line ~248: explicit float() cast before round() so the overload
    resolves correctly for Pyre2.
"""

from __future__ import annotations

import json
from typing import Dict, Any, List, Optional

from src.orchestration.logger import setup_logger

logger = setup_logger()

_CROSS_SYSTEM = """You are a senior business strategy analyst.
Given research text snippets spanning financial, market, and competitive data,
synthesise the most important strategic insights for a new business venture.

Return ONLY a JSON object:
{
  "executive_insights":       ["list of 3-5 sharp, evidence-based insights"],
  "strategic_recommendations": ["list of 3-5 concrete action recommendations"],
  "key_risks":                 ["list of 2-3 cross-cutting risks"],
  "confidence_note":           "one sentence on data quality / gaps"
}

Rules:
- Each insight or recommendation must be a complete, actionable sentence.
- Do NOT repeat the same point across sections.
- If data is thin, say so in confidence_note rather than padding with generics.
"""

_CROSS_USER = """Synthesise strategic intelligence from these research snippets:

{chunks}

Agent outputs summary:
Financial viability: {financial_summary}
Market opportunity:  {market_summary}
Competitive landscape: {competitive_summary}
"""


class ConsolidationAgent:

    def consolidate(
        self,
        financial_result:    Dict[str, Any],
        market_result:       Dict[str, Any],
        competitive_result:  Dict[str, Any],
        business_input:      Dict[str, Any],
        rag=None,
    ) -> Dict[str, Any]:
        financial_result   = financial_result   or {}
        market_result      = market_result      or {}
        competitive_result = competitive_result or {}
        business_input     = business_input     or {}

        overall_viability = self._calculate_overall_viability(
            financial_result, market_result, competitive_result
        )
        executive_summary = self._generate_executive_summary(
            financial_result, market_result, competitive_result, business_input
        )
        key_findings  = self._extract_key_findings(
            financial_result, market_result, competitive_result
        )
        recommendations = self._compile_recommendations(
            financial_result, market_result, competitive_result
        )
        risks          = self._compile_risks(
            financial_result, market_result, competitive_result
        )
        swot           = self._compile_swot(competitive_result)
        data_quality   = self._assess_data_quality(
            financial_result, market_result, competitive_result
        )

        cross_synthesis: Dict[str, Any] = {}
        if rag is not None and rag.is_ready():
            cross_synthesis = self._cross_agent_synthesis(
                rag, financial_result, market_result, competitive_result,
            )
            if cross_synthesis:
                for insight in cross_synthesis.get("executive_insights", []):
                    if insight and insight not in key_findings:
                        key_findings.append(insight)
                for rec in cross_synthesis.get("strategic_recommendations", []):
                    if rec and rec not in recommendations:
                        recommendations.append(rec)
                for risk in cross_synthesis.get("key_risks", []):
                    if risk and risk not in risks:
                        risks.append(risk)

        return {
            "overall_viability_score":   overall_viability,
            "executive_summary":         executive_summary,
            "key_findings":              key_findings[:10],
            "strategic_recommendations": recommendations[:8],
            "risk_assessment":           risks[:8],
            "swot_analysis":             swot,
            "data_quality":              data_quality,
            "metadata": {
                "data_confidence": data_quality,
            },
            "rag_cross_synthesis": cross_synthesis,
            "rag_augmented":       rag is not None and rag.is_ready(),
            "agent_results": {
                "financial":   financial_result,
                "market":      market_result,
                "competitive": competitive_result,
            },
        }

    # ── Cross-agent RAG synthesis ──────────────────────────────────────────

    def _cross_agent_synthesis(
        self,
        rag,
        financial_result:   Dict[str, Any],
        market_result:      Dict[str, Any],
        competitive_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        queries = [
            "business opportunity competitive advantage differentiation",
            "market risk barrier entry threat competition",
            "revenue model monetization pricing strategy",
            "funding investment growth scaling strategy",
            "regulatory compliance legal risk industry challenge",
        ]

        all_chunks: List[str] = []
        for query in queries:
            try:
                chunks = rag.query(query, top_k=3, intent_filter=None)
                all_chunks.extend(chunks)
            except Exception as exc:
                logger.warning(f"ConsolidationAgent RAG query failed '{query[:45]}': {exc}")

        if not all_chunks:
            return {}

        seen: set = set()
        unique_chunks: List[str] = []
        for c in all_chunks:
            # FIX (line ~150): guard against None before slicing
            key = (c or "")[:80]
            if key not in seen:
                seen.add(key)
                unique_chunks.append(c)

        combined_chunks = "\n\n---\n\n".join(unique_chunks[:8])

        try:
            from src.orchestration.llm_client import call_llm_json
            user_prompt = _CROSS_USER.format(
                chunks              = combined_chunks[:3_500],
                financial_summary   = financial_result.get("summary", "N/A"),
                market_summary      = market_result.get("summary", "N/A"),
                competitive_summary = competitive_result.get("summary", "N/A"),
            )
            result = call_llm_json(_CROSS_SYSTEM, user_prompt)
            if not isinstance(result, dict):
                raise ValueError(f"Expected dict, got {type(result)}")

            return {
                "executive_insights": [
                    i for i in result.get("executive_insights", [])
                    if isinstance(i, str) and i.strip()
                ][:5],
                "strategic_recommendations": [
                    r for r in result.get("strategic_recommendations", [])
                    if isinstance(r, str) and r.strip()
                ][:5],
                "key_risks": [
                    r for r in result.get("key_risks", [])
                    if isinstance(r, str) and r.strip()
                ][:3],
                "confidence_note": result.get("confidence_note", ""),
            }
        except Exception as exc:
            logger.warning(f"ConsolidationAgent cross-synthesis LLM failed: {exc} — using heuristic")
            return self._heuristic_cross_synthesis(
                unique_chunks, financial_result, market_result, competitive_result
            )

    def _heuristic_cross_synthesis(
        self,
        chunks:             List[str],
        financial_result:   Dict[str, Any],
        market_result:      Dict[str, Any],
        competitive_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        insights: List[str] = []
        recs: List[str]     = []
        risks: List[str]    = []

        runway = float(financial_result.get("runway_months") or 0)
        if runway >= 18:
            insights.append(f"Strong financial runway of {runway:.0f} months supports sustained growth.")
        elif 0 < runway < 12:
            insights.append(f"Runway of {runway:.0f} months is tight — prioritise early revenue.")
            risks.append("Short runway may constrain ability to pivot or respond to market changes.")

        growth = float(market_result.get("growth_rate") or 0)
        tam    = float((market_result.get("market_size") or {}).get("global") or 0)
        if growth > 10:
            insights.append(f"High market growth rate ({growth:.1f}%) signals strong tailwinds.")
        if tam > 1e9:
            recs.append("Target a well-defined sub-segment of the large TAM to reduce go-to-market risk.")

        intensity  = competitive_result.get("competitive_intensity", "")
        comp_count = competitive_result.get("competitors_found", 0)
        if intensity == "High":
            risks.append(f"High competitive intensity ({comp_count} identified players) requires clear differentiation.")
        elif intensity == "Low":
            insights.append("Low competitive density offers a first-mover window — move quickly.")

        recs.append("Validate unit economics before scaling marketing spend.")
        recs.append("Invest in a proprietary data moat to create long-term defensibility.")

        return {
            "executive_insights":        insights[:5],
            "strategic_recommendations": recs[:5],
            "key_risks":                 risks[:3],
            "confidence_note": (
                "Heuristic synthesis used — LLM unavailable. "
                "Insights derived from agent scores, not raw research text."
            ),
        }

    # ── Standard consolidation helpers ────────────────────────────────────

    def _calculate_overall_viability(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
    ) -> float:
        fin_score  = float(financial.get("viability_score",    0.0) or 0.0)
        mkt_score  = float(market.get("opportunity_score",     0.0) or 0.0)
        comp_level = competitive.get("competitive_intensity", "Medium") or "Medium"

        comp_penalty = {"Low": 0.0, "Medium": 0.05, "High": 0.15}.get(comp_level, 0.05)
        overall = (fin_score * 0.4 + mkt_score * 0.6) - comp_penalty
        # FIX (line ~248): explicit float() so Pyre2 resolves round() overload correctly
        return round(float(max(0.0, min(overall, 1.0))), 2)

    def _generate_executive_summary(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
        business:    Dict[str, Any],
    ) -> str:
        idea      = business.get("business_idea",  "the proposed business")
        industry  = business.get("industry",       "the target industry")
        fin_score = float(financial.get("viability_score",   0) or 0)
        mkt_score = float(market.get("opportunity_score",    0) or 0)
        intensity = competitive.get("competitive_intensity", "moderate") or "moderate"
        growth    = float(market.get("growth_rate", 0) or 0)

        return (
            f"{idea} operates in {industry} with a market growing at "
            f"{growth:.1f}% annually. "
            f"Financial viability score is {fin_score:.0%} and market opportunity "
            f"score is {mkt_score:.0%}. "
            f"Competitive intensity is {intensity.lower()}. "
            f"{'Strong fundamentals support moving forward.' if fin_score > 0.6 and mkt_score > 0.6 else 'Further validation and risk mitigation are recommended before committing full resources.'}"
        )

    def _extract_key_findings(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
    ) -> List[str]:
        findings: List[str] = []

        runway = financial.get("runway_months", 0)
        if runway:
            findings.append(f"Estimated runway: {runway:.0f} months at projected burn rate.")

        growth = market.get("growth_rate", 0)
        if growth:
            findings.append(f"Market growing at {growth:.1f}% CAGR.")

        tam = (market.get("market_size") or {}).get("global", 0)
        if tam:
            findings.append(f"Total addressable market estimated at ${tam:,.0f}.")

        sentiment = market.get("sentiment", {}) or {}
        if sentiment.get("label"):
            findings.append(f"Market sentiment is {sentiment['label'].lower()}.")

        n_comp    = competitive.get("competitors_found", 0)
        intensity = competitive.get("competitive_intensity", "")
        if n_comp:
            findings.append(f"{n_comp} competitors identified; competitive intensity is {intensity.lower()}.")

        confs = [
            financial.get("data_confidence",   "Unknown"),
            market.get("data_confidence",      "Unknown"),
            competitive.get("data_confidence", "Unknown"),
        ]
        for label, conf in zip(["Financial", "Market", "Competitive"], confs):
            if conf and conf != "Unknown":
                findings.append(f"{label} data confidence: {conf}.")

        return findings

    def _compile_recommendations(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
    ) -> List[str]:
        recs: List[str] = []
        recs.extend(financial.get("recommendations", []) or [])
        recs.extend(market.get("key_insights",      []) or [])
        swot = competitive.get("swot_analysis", {}) or {}
        recs.extend(swot.get("opportunities", []) or [])
        return list(dict.fromkeys(r for r in recs if r))

    def _compile_risks(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
    ) -> List[str]:
        risks: List[str] = []
        risks.extend(financial.get("risks", []) or [])
        sentiment = market.get("sentiment", {}) or {}
        if isinstance(sentiment, dict) and sentiment.get("label") == "Negative":
            risks.append("Negative market sentiment may hinder adoption.")
        swot = competitive.get("swot_analysis", {}) or {}
        risks.extend(swot.get("threats",    []) or [])
        risks.extend(swot.get("weaknesses", []) or [])
        return list(dict.fromkeys(r for r in risks if r))

    def _compile_swot(self, competitive: Dict[str, Any]) -> Dict[str, List[str]]:
        default = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}
        return competitive.get("swot_analysis", default) or default

    def _assess_data_quality(
        self,
        financial:   Dict[str, Any],
        market:      Dict[str, Any],
        competitive: Dict[str, Any],
    ) -> Dict[str, Any]:
        levels = {"High": 3, "Medium": 2, "Low": 1, "Unknown": 0}
        scores = [
            levels.get(financial.get("data_confidence",   "Unknown"), 0),
            levels.get(market.get("data_confidence",      "Unknown"), 0),
            levels.get(competitive.get("data_confidence", "Unknown"), 0),
        ]
        avg = sum(scores) / len(scores)
        overall = "High" if avg >= 2.5 else ("Medium" if avg >= 1.5 else "Low")
        return {
            "overall":     overall,
            "financial":   financial.get("data_confidence",   "Unknown"),
            "market":      market.get("data_confidence",      "Unknown"),
            "competitive": competitive.get("data_confidence", "Unknown"),
        }