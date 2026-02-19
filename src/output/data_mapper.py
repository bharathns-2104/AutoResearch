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
            "decision": self._map_decision(consolidated_data)
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
