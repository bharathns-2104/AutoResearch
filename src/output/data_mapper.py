"""
data_mapper.py — Improved Report Data Mapper

Key fixes vs. original:
  1. _map_executive_summary() uses generate_executive_summary() for LLM/data-accurate text
  2. _map_financial_details() reads from BOTH financial_details AND agent_results.financial
  3. _map_market_details() reads from BOTH market_details AND agent_results.market
  4. _map_competitive_details() reads from BOTH competitive_details AND agent_results.competitive
  5. All numeric fields guarded with `or 0` / `or []` to prevent None errors
  6. Added tam_sam_som passthrough so PDF/PPT can access those values directly
  7. Data confidence mapping reads from metadata.data_confidence with fallback to data_quality
"""

from datetime import datetime
from typing import Any, Dict


class ReportDataMapper:

    REQUIRED_FIELDS = [
        "overall_viability_score",
        "overall_rating",
        "financial_score",
        "market_score",
        "competitive_score",
        "aggregated_risks",
        "final_recommendations",
        "executive_summary",
        "decision"
    ]

    def map(self, consolidated_data: Dict[str, Any]) -> Dict[str, Any]:
        self._validate(consolidated_data)
        
        # Generate improved executive summary
        exec_summary = self._map_executive_summary(consolidated_data)

        return {
            "title_page":           self._map_title_page(),
            "executive_summary":    exec_summary,
            "score_overview":       self._map_score_overview(consolidated_data),
            "domain_scores":        self._map_domain_scores(consolidated_data),
            "risk_analysis":        self._map_risk_analysis(consolidated_data),
            "recommendations":      self._map_recommendations(consolidated_data),
            "decision":             self._map_decision(consolidated_data),
            "data_confidence":      self._map_data_confidence(consolidated_data),
            "financial_details":    self._map_financial_details(consolidated_data),
            "market_details":       self._map_market_details(consolidated_data),
            "competitive_details":  self._map_competitive_details(consolidated_data),
            "sources":              self._map_sources(consolidated_data),
            # Pass raw consolidated for executive_summary generator
            "_consolidated_raw":    consolidated_data,
        }

    def _validate(self, data: Dict[str, Any]) -> None:
        if not isinstance(data, dict):
            raise ValueError("Consolidated data must be a dictionary.")
        for field in self.REQUIRED_FIELDS:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    # ── Title ──────────────────────────────────────────────────────────────────

    def _map_title_page(self) -> Dict[str, Any]:
        return {
            "project_title": "AutoResearch — Automated Business Intelligence Report",
            "generated_at":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    # ── Executive Summary ──────────────────────────────────────────────────────

    def _map_executive_summary(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use the improved executive summary generator.
        Falls back to the existing executive_summary field if generation fails.
        """
        try:
            # Try multiple import paths depending on how the module is deployed
            gen_fn = None
            for module_path in [
                "src.output.executive_summary",
                "executive_summary",
            ]:
                try:
                    import importlib
                    mod = importlib.import_module(module_path)
                    gen_fn = getattr(mod, "generate_executive_summary", None)
                    if gen_fn:
                        break
                except ImportError:
                    continue
            
            if gen_fn:
                summary_text = gen_fn(data)
                if summary_text and len(summary_text.strip()) > 50:
                    return {"summary_text": summary_text}
        except Exception:
            pass
        
        # Fallback: use existing executive_summary from consolidated data
        raw_summary = data.get("executive_summary", "")
        if not isinstance(raw_summary, str):
            raw_summary = str(raw_summary)
        return {"summary_text": raw_summary or "Executive summary not available."}

    # ── Score Overview ─────────────────────────────────────────────────────────

    def _map_score_overview(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "overall_score": float(data.get("overall_viability_score", 0) or 0),
            "rating":        data.get("overall_rating", "—"),
        }

    # ── Domain Scores ──────────────────────────────────────────────────────────

    def _map_domain_scores(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "financial_score":   float(data.get("financial_score",   0) or 0),
            "market_score":      float(data.get("market_score",      0) or 0),
            "competitive_score": float(data.get("competitive_score", 0) or 0),
        }

    # ── Risk Analysis ──────────────────────────────────────────────────────────

    def _map_risk_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        risks = data.get("aggregated_risks", []) or []
        normalized = []
        for risk in risks:
            if isinstance(risk, dict):
                normalized.append({
                    "category": risk.get("category", "General"),
                    "severity": risk.get("severity", "Medium"),
                    "message":  risk.get("message",  str(risk)),
                })
            elif isinstance(risk, str) and risk.strip():
                normalized.append({
                    "category": "General",
                    "severity": "Medium",
                    "message":  risk,
                })
        return {"risks": normalized}

    # ── Recommendations ────────────────────────────────────────────────────────

    def _map_recommendations(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"recommendations": data.get("final_recommendations", []) or []}

    # ── Decision ──────────────────────────────────────────────────────────────

    def _map_decision(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {"final_decision": data.get("decision", "—")}

    # ── Data Confidence ────────────────────────────────────────────────────────

    def _map_data_confidence(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Primary: metadata.data_confidence (set by consolidation_agent)
        confidence = (data.get("metadata") or {}).get("data_confidence") or {}
        # Secondary: data_quality
        if not confidence:
            confidence = data.get("data_quality") or {}
        # Fallback per-agent from agent_results
        if not confidence:
            ar = data.get("agent_results") or {}
            confidence = {
                "financial":   (ar.get("financial") or {}).get("data_confidence", "Unknown"),
                "market":      (ar.get("market") or {}).get("data_confidence", "Unknown"),
                "competitive": (ar.get("competitive") or {}).get("data_confidence", "Unknown"),
                "overall":     "Unknown",
            }
        return {
            "financial":   confidence.get("financial",   "Unknown"),
            "market":      confidence.get("market",      "Unknown"),
            "competitive": confidence.get("competitive", "Unknown"),
            "overall":     confidence.get("overall",     "Unknown"),
        }

    # ── Financial Details ──────────────────────────────────────────────────────

    def _map_financial_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Try financial_details first (from consolidation_agent), then agent_results.financial
        details: Dict[str, Any] = (
            data.get("financial_details") or
            (data.get("agent_results") or {}).get("financial") or
            {}
        )
        metrics: Dict[str, Any] = details.get("metrics") or {}

        return {
            "runway_months":      float(details.get("runway_months",    0) or 0),
            "viability_score":    float(details.get("viability_score",
                                    data.get("financial_score", 0)) or 0),
            "monthly_burn":       float(metrics.get("monthly_burn",     0) or 0),
            "estimated_revenue":  float(metrics.get("estimated_revenue", 0) or 0),
            "growth_rate":        float(metrics.get("growth_rate",      0) or 0),
            "profit_margin":      float(metrics.get("profit_margin",    0) or 0),
        }

    # ── Market Details ─────────────────────────────────────────────────────────

    def _map_market_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        details: Dict[str, Any] = (
            data.get("market_details") or
            (data.get("agent_results") or {}).get("market") or
            {}
        )
        tam_sam_som: Dict[str, Any] = details.get("tam_sam_som") or {}
        market_size: Dict[str, Any] = details.get("market_size") or {}
        sentiment:   Dict[str, Any] = details.get("sentiment") or {}

        # TAM can come from multiple places
        tam = float(
            details.get("tam") or
            tam_sam_som.get("tam") or
            market_size.get("global") or
            0
        )
        sam = float(details.get("sam") or tam_sam_som.get("sam") or 0)
        som = float(details.get("som") or tam_sam_som.get("som") or 0)

        return {
            "tam":              tam,
            "sam":              sam,
            "som":              som,
            "tam_currency":     market_size.get("currency", "USD"),
            "growth_rate":      float(details.get("growth_rate", 0) or 0),
            "sentiment_label":  sentiment.get("label", "Neutral"),
            "sentiment_score":  float(sentiment.get("score", 0) or 0),
            "key_insights":     details.get("key_insights", []) or [],
            # Also expose opportunity_score for reference
            "opportunity_score": float(details.get("opportunity_score",
                                    data.get("market_score", 0)) or 0),
        }

    # ── Competitive Details ────────────────────────────────────────────────────

    def _map_competitive_details(self, data: Dict[str, Any]) -> Dict[str, Any]:
        details: Dict[str, Any] = (
            data.get("competitive_details") or
            (data.get("agent_results") or {}).get("competitive") or
            {}
        )
        swot: Dict[str, Any] = details.get("swot_analysis") or details.get("swot") or {}

        return {
            "competitors_found":     int(details.get("competitors_found", 0) or 0),
            "top_competitors":       details.get("top_competitors", []) or [],
            "competitive_intensity": details.get("competitive_intensity", "Unknown"),
            "swot": {
                "strengths":     swot.get("strengths",     []) or [],
                "weaknesses":    swot.get("weaknesses",    []) or [],
                "opportunities": swot.get("opportunities", []) or [],
                "threats":       swot.get("threats",       []) or [],
            },
            "market_gaps": details.get("market_gaps", []) or [],
        }

    # ── Sources ────────────────────────────────────────────────────────────────

    def _map_sources(self, data: Dict[str, Any]) -> list:
        raw_sources = data.get("sources", []) or []
        normalised = []
        for src in raw_sources:
            if not isinstance(src, dict):
                continue
            url = src.get("url")
            if not url:
                continue
            normalised.append({
                "title": src.get("title", "") or url,
                "url":   url,
            })
        return normalised