from datetime import datetime


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

    # ======================================================
    # MAIN MAPPING ENTRY
    # ======================================================

    def map(self, consolidated_data):

        self._validate(consolidated_data)

        return {
            "title_page": self._map_title_page(),
            "executive_summary": self._map_executive_summary(consolidated_data),
            "score_overview": self._map_score_overview(consolidated_data),
            "domain_scores": self._map_domain_scores(consolidated_data),
            "risk_analysis": self._map_risk_analysis(consolidated_data),
            "recommendations": self._map_recommendations(consolidated_data),
            "decision": self._map_decision(consolidated_data),
            "data_confidence": self._map_data_confidence(consolidated_data),
            "financial_details": self._map_financial_details(consolidated_data),
            "market_details": self._map_market_details(consolidated_data),
            "competitive_details": self._map_competitive_details(consolidated_data),
            "sources": self._map_sources(consolidated_data),
        }

    # ======================================================
    # VALIDATION
    # ======================================================

    def _validate(self, data):

        if not isinstance(data, dict):
            raise ValueError("Consolidated data must be a dictionary.")

        for field in self.REQUIRED_FIELDS:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

    # ======================================================
    # TITLE PAGE
    # ======================================================

    def _map_title_page(self):
        return {
            "project_title": "AutoResearch – Automated Corporate Analysis Report",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    # ======================================================
    # EXECUTIVE SUMMARY
    # ======================================================

    def _map_executive_summary(self, data):
        return {
            "summary_text": data.get("executive_summary", "")
        }

    # ======================================================
    # OVERALL SCORE SECTION
    # ======================================================

    def _map_score_overview(self, data):
        return {
            "overall_score": data.get("overall_viability_score", 0),
            "rating": data.get("overall_rating", "")
        }

    # ======================================================
    # DOMAIN SCORES
    # ======================================================

    def _map_domain_scores(self, data):
        return {
            "financial_score": data.get("financial_score", 0),
            "market_score": data.get("market_score", 0),
            "competitive_score": data.get("competitive_score", 0)
        }

    # ======================================================
    # RISK SECTION
    # ======================================================

    def _map_risk_analysis(self, data):
        risks = data.get("aggregated_risks", [])

        normalized_risks = []

        for risk in risks:
            normalized_risks.append({
                "category": risk.get("category", "Unknown"),
                "severity": risk.get("severity", "Medium"),
                "message": risk.get("message", "")
            })

        return {
            "risks": normalized_risks
        }

    # ======================================================
    # RECOMMENDATIONS
    # ======================================================

    def _map_recommendations(self, data):
        return {
            "recommendations": data.get("final_recommendations", [])
        }

    # ======================================================
    # FINAL DECISION
    # ======================================================

    def _map_decision(self, data):
        return {
            "final_decision": data.get("decision", "")
        }

    # ======================================================
    # DATA CONFIDENCE (PER DOMAIN + OVERALL)
    # ======================================================

    def _map_data_confidence(self, data):
        metadata = data.get("metadata", {})
        confidence = metadata.get("data_confidence", {})

        return {
            "financial": confidence.get("financial", "Medium"),
            "market": confidence.get("market", "Medium"),
            "competitive": confidence.get("competitive", "Medium"),
            "overall": confidence.get("overall", "Medium"),
        }

    # ======================================================
    # ANALYSIS DETAIL SECTIONS
    # ======================================================

    def _map_financial_details(self, data):
        details = data.get("financial_details", {}) or {}
        metrics = details.get("metrics", {}) or {}

        return {
            "runway_months": details.get("runway_months", 0),
            "viability_score": details.get("viability_score", 0.0),
            "monthly_burn": metrics.get("monthly_burn", 0),
            "estimated_revenue": metrics.get("estimated_revenue", 0),
            "growth_rate": metrics.get("growth_rate", 0),
            "profit_margin": metrics.get("profit_margin", 0),
        }

    def _map_market_details(self, data):
        details = data.get("market_details", {}) or {}
        tam_sam_som = details.get("tam_sam_som", {}) or {}
        market_size = details.get("market_size", {}) or {}
        sentiment = details.get("sentiment", {}) or {}

        return {
            "tam": tam_sam_som.get("tam", 0),
            "sam": tam_sam_som.get("sam", 0),
            "som": tam_sam_som.get("som", 0),
            "tam_currency": market_size.get("currency", "USD"),
            "growth_rate": details.get("growth_rate", 0),
            "sentiment_label": sentiment.get("label", "Neutral"),
            "sentiment_score": sentiment.get("score", 0),
            "key_insights": details.get("key_insights", []),
        }

    def _map_competitive_details(self, data):
        details = data.get("competitive_details", {}) or {}
        swot = details.get("swot_analysis", {}) or {}

        return {
            "competitors_found": details.get("competitors_found", 0),
            "top_competitors": details.get("top_competitors", []),
            "competitive_intensity": details.get("competitive_intensity", "Unknown"),
            "swot": {
                "strengths": swot.get("strengths", []),
                "weaknesses": swot.get("weaknesses", []),
                "opportunities": swot.get("opportunities", []),
                "threats": swot.get("threats", []),
            },
            "market_gaps": details.get("market_gaps", []),
        }

    def _map_sources(self, data):
        """
        Normalise scraped sources (URLs + titles) into a simple list
        for the appendix section.
        """
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
                "url": url,
            })

        return normalised
