from typing import Dict, List, Any
from dataclasses import dataclass
import statistics


@dataclass
class FinancialConfig:
    healthy_runway_threshold: int = 12
    strong_growth_threshold: float = 10.0
    strong_margin_threshold: float = 15.0
    high_viability_threshold: float = 0.7
    low_viability_threshold: float = 0.5


class FinancialAnalysisAgent:
    def __init__(self, config: FinancialConfig):
        self.config = config

    # ===============================
    # MAIN ENTRY POINT
    # ===============================
    def run(self, extracted_data: Dict[str, Any], budget: float) -> Dict[str, Any]:
        costs = self._extract_costs(extracted_data)
        revenue = self._extract_revenue(extracted_data)
        growth = self._extract_growth(extracted_data)
        margin = self._extract_profit_margin(extracted_data)

        total_cost = sum(costs)
        monthly_burn = total_cost / 12 if total_cost else 0
        runway = budget / monthly_burn if monthly_burn else 0

        viability_score = self._calculate_viability(
            runway, growth, margin
        )

        risks = self._generate_risks(runway, growth)
        recommendations = self._generate_recommendations(
            runway, viability_score
        )

        summary = self._generate_summary(
            runway, viability_score
        )

        return {
            "metrics": {
                "total_estimated_cost": total_cost,
                "monthly_burn": monthly_burn,
                "estimated_revenue": revenue,
                "growth_rate": growth,
                "profit_margin": margin
            },
            "runway_months": round(runway, 2),
            "viability_score": round(viability_score, 2),
            "risks": risks,
            "recommendations": recommendations,
            "summary": summary
        }

    # ===============================
    # EXTRACTION HELPERS
    # ===============================

    def _extract_costs(self, data: Dict[str, Any]) -> List[float]:
        financial_metrics = data.get("financial_metrics", {})
        costs = financial_metrics.get("startup_costs", [])
        return costs

    def _extract_revenue(self, data: Dict[str, Any]) -> float:
        financial_metrics = data.get("financial_metrics", {})
        revenues = financial_metrics.get("revenue_figures", [])
        return statistics.mean(revenues) if revenues else 0

    def _extract_growth(self, data: Dict[str, Any]) -> float:
        financial_metrics = data.get("financial_metrics", {})
        growth_rates = financial_metrics.get("growth_rates", [])
        return statistics.mean(growth_rates) if growth_rates else 0

    def _extract_profit_margin(self, data: Dict[str, Any]) -> float:
        # Profit margin is not directly extracted; use growth rate as proxy
        financial_metrics = data.get("financial_metrics", {})
        growth_rates = financial_metrics.get("growth_rates", [])
        # Use average growth as proxy for profitability potential
        return (statistics.mean(growth_rates) / 100 * 20) if growth_rates else 0  # 20% baseline

    # ===============================
    # SCORING LOGIC
    # ===============================

    def _calculate_viability(self, runway, growth, margin) -> float:
        score = 0.0

        # Runway scoring
        if runway > 18:
            score += 0.3
        elif runway > self.config.healthy_runway_threshold:
            score += 0.2

        # Growth scoring
        if growth > self.config.strong_growth_threshold:
            score += 0.3

        # Margin scoring
        if margin > self.config.strong_margin_threshold:
            score += 0.2

        return min(score, 1.0)

    # ===============================
    # RISK + RECOMMENDATION
    # ===============================

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

    # ===============================
    # SUMMARY
    # ===============================

    def _generate_summary(self, runway, score):
        if score >= self.config.high_viability_threshold:
            return "Strong financial viability with sufficient runway and growth."
        elif score >= self.config.low_viability_threshold:
            return "Moderate financial outlook. Some improvements needed."
        else:
            return "Financial viability is weak. High caution recommended."
