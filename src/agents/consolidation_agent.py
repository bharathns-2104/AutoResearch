from dataclasses import dataclass, field
from typing import List, Dict, Any
from datetime import datetime


# ==========================================================
# DATA STRUCTURES
# ==========================================================

@dataclass
class RiskFlag:
    category: str
    severity: str  # Low / Medium / High
    message: str


@dataclass
class ConsolidatedOutput:
    financial_score: float
    market_score: float
    competitive_score: float
    overall_viability_score: float
    overall_rating: str

    aggregated_risks: List[RiskFlag] = field(default_factory=list)
    final_recommendations: List[str] = field(default_factory=list)
    executive_summary: str = ""
    decision: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return {
            "financial_score": self.financial_score,
            "market_score": self.market_score,
            "competitive_score": self.competitive_score,
            "overall_viability_score": self.overall_viability_score,
            "overall_rating": self.overall_rating,
            "aggregated_risks": [
                {
                    "category": r.category,
                    "severity": r.severity,
                    "message": r.message
                }
                for r in self.aggregated_risks
            ],
            "final_recommendations": self.final_recommendations,
            "executive_summary": self.executive_summary,
            "decision": self.decision,
            "metadata": self.metadata
        }


# ==========================================================
# CONSOLIDATION AGENT
# ==========================================================

class ConsolidationAgent:

    # ------------------------------------------------------
    # MAIN ENTRY POINT
    # ------------------------------------------------------
    def run(self, analysis_results: Dict[str, Any]) -> Dict[str, Any]:

        financial = analysis_results.get("financial")
        competitive = analysis_results.get("competitive")
        market = analysis_results.get("market")

        # Extract scores safely
        financial_score = self._extract_financial_score(financial)
        competitive_score = self._extract_competitive_score(competitive)
        market_score = self._extract_market_score(market)

        # Weighted merge
        overall_score = self._calculate_weighted_score(
            financial_score,
            competitive_score,
            market_score
        )

        # -------------------------------------------------
        # Aggregate risks FIRST
        # -------------------------------------------------
        risks = self._aggregate_risks(financial, competitive, market)

        # -------------------------------------------------
        # Apply risk penalties
        # -------------------------------------------------
        risk_adjusted_score, total_penalty = self._apply_risk_penalty(
            overall_score,
            risks
        )

        overall_rating = self._classify_overall_rating(risk_adjusted_score)

        # -------------------------------------------------
        # Recommendations + Decision should use adjusted score
        # -------------------------------------------------
        recommendations = self._generate_recommendations(
            risk_adjusted_score,
            risks
        )

        decision = self._make_decision(risk_adjusted_score)

        summary = self._generate_summary(
            risk_adjusted_score,
            overall_rating,
            financial,
            market,
            competitive
        )

        consolidated = ConsolidatedOutput(
            financial_score=round(financial_score, 2),
            market_score=round(market_score, 2),
            competitive_score=round(competitive_score, 2),
            overall_viability_score=round(risk_adjusted_score, 2),  # FIXED
            overall_rating=overall_rating,
            aggregated_risks=risks,
            final_recommendations=recommendations,
            executive_summary=summary,
            decision=decision,
            metadata={
                "generated_at": datetime.utcnow().isoformat(),
                "weights": {
                    "financial": 0.4,
                    "market": 0.3,
                    "competitive": 0.3
                },
                "risk_penalty_applied": round(total_penalty, 3)
            }
        )

        return consolidated.to_dict()


    # ======================================================
    # SCORE EXTRACTION
    # ======================================================

    def _extract_financial_score(self, financial):
        if not financial:
            return 0.0
        return financial.get("viability_score", 0.0)

    def _extract_market_score(self, market):
        if not market:
            return 0.0
        return market.get("opportunity_score", 0.0)

    def _extract_competitive_score(self, competitive):
        if not competitive:
            return 0.0

        intensity = competitive.get("competitive_intensity", "Medium")

        mapping = {
            "Low": 0.9,
            "Medium": 0.6,
            "High": 0.3
        }

        return mapping.get(intensity, 0.6)

    # ======================================================
    # WEIGHTED MERGE LOGIC
    # ======================================================

    def _calculate_weighted_score(self, financial, competitive, market):
        return (
            (0.4 * financial) +
            (0.3 * market) +
            (0.3 * competitive)
        )

    # ======================================================
    # RATING CLASSIFICATION
    # ======================================================

    def _classify_overall_rating(self, score):
        if score >= 0.7:
            return "Strong"
        elif score >= 0.5:
            return "Moderate"
        else:
            return "Weak"

    # ======================================================
    # RISK AGGREGATION
    # ======================================================

    def _aggregate_risks(self, financial, competitive, market):

        risk_flags = []

        # Financial risk
        if financial:
            runway = financial.get("runway_months", 0)

            if runway and runway < 6:
                risk_flags.append(RiskFlag(
                    category="Financial",
                    severity="High",
                    message="Runway below 6 months."
                ))
            elif runway and runway < 12:
                risk_flags.append(RiskFlag(
                    category="Financial",
                    severity="Medium",
                    message="Runway below 12 months."
                ))

        # Competitive risk
        if competitive:
            intensity = competitive.get("competitive_intensity", "Medium")

            if intensity == "High":
                risk_flags.append(RiskFlag(
                    category="Competitive",
                    severity="High",
                    message="Highly competitive market."
                ))

        # Market risk
        if market:
            sentiment = market.get("sentiment", {}).get("label", "Neutral")

            if sentiment == "Negative":
                risk_flags.append(RiskFlag(
                    category="Market",
                    severity="Medium",
                    message="Negative industry sentiment detected."
                ))

        return risk_flags

    # ======================================================
    # RECOMMENDATION ENGINE
    # ======================================================

    def _generate_recommendations(self, overall_score, risks):

        recommendations = []

        if overall_score >= 0.7:
            recommendations.append(
                "Proceed aggressively with expansion strategy."
            )
        elif overall_score >= 0.5:
            recommendations.append(
                "Proceed with phased investment and controlled scaling."
            )
        else:
            recommendations.append(
                "Re-evaluate business model before major investment."
            )

        for risk in risks:
            if risk.severity == "High":
                recommendations.append(
                    f"Immediate mitigation required in {risk.category.lower()} domain."
                )

        if not recommendations:
            recommendations.append("Monitor performance metrics regularly.")

        return recommendations

    # ======================================================
    # DECISION LOGIC
    # ======================================================

    def _make_decision(self, overall_score):

        if overall_score >= 0.7:
            return "Proceed"
        elif overall_score >= 0.5:
            return "Proceed with Caution"
        else:
            return "Re-evaluate"

    # ======================================================
    # EXECUTIVE SUMMARY GENERATOR
    # ======================================================

    def _generate_summary(
        self,
        overall_score,
        rating,
        financial,
        market,
        competitive
    ):

        summary = f"The business opportunity demonstrates {rating.lower()} viability. "

        if financial:
            runway = financial.get("runway_months", None)
            if runway:
                summary += f"Financial runway is approximately {runway} months. "

        if market:
            growth = market.get("growth_rate", 0)
            if growth:
                summary += f"Market growth is estimated at {growth}% annually. "

        if competitive:
            intensity = competitive.get("competitive_intensity", "Medium")
            summary += f"Competitive intensity is {intensity.lower()}. "

        summary += "Overall evaluation is based on weighted financial, market, and competitive analysis."

        return summary

    # ======================================================
    # RISK-ADJUSTED SCORING
    # ======================================================

    def _apply_risk_penalty(self, base_score, risks):

        penalty = 0.0

        for risk in risks:
            if risk.severity == "High":
                penalty += 0.05
            elif risk.severity == "Medium":
                penalty += 0.02
            elif risk.severity == "Low":
                penalty += 0.01

        adjusted_score = base_score - penalty

        # Clamp between 0 and 1
        adjusted_score = max(0.0, min(1.0, adjusted_score))

        return adjusted_score, penalty
