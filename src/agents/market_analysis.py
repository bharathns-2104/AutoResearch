from typing import Dict, Any, List
import statistics


class MarketAnalysisAgent:

    # ===============================
    # MAIN ENTRY POINT
    # ===============================
    def run(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:

        tam = self._extract_market_size(extracted_data)
        growth = self._extract_growth_rate(extracted_data)
        sentiment = self._analyze_sentiment(extracted_data)
        tam_sam_som = self._calculate_tam_sam_som(tam)

        opportunity_score = self._calculate_opportunity_score(
            tam, growth, sentiment["score"]
        )

        summary = self._generate_summary(opportunity_score)

        # Data confidence heuristic: market size + growth + sentiment signals
        financial_metrics = extracted_data.get("financial_metrics", {})
        market_sizes = financial_metrics.get("market_sizes", [])
        growth_rates = financial_metrics.get("growth_rates", [])

        signal_count = 0
        if market_sizes:
            signal_count += 1
        if growth_rates:
            signal_count += 1
        if sentiment["positive_signals"] or sentiment["negative_signals"]:
            signal_count += 1

        meta = extracted_data.get("meta", {})
        num_pages = meta.get("num_pages", 0)

        if signal_count == 3 and num_pages >= 5:
            data_confidence = "High"
        elif signal_count >= 2:
            data_confidence = "Medium"
        else:
            data_confidence = "Low"

        return {
            "market_size": tam,
            "tam_sam_som": tam_sam_som,
            "growth_rate": growth,
            "sentiment": sentiment,
            "opportunity_score": round(opportunity_score, 2),
            "key_insights": self._generate_insights(tam, growth, sentiment),
            "summary": summary,
            "data_confidence": data_confidence,
        }

    # ===============================
    # MARKET SIZE EXTRACTION
    # ===============================
    def _extract_market_size(self, data: Dict[str, Any]) -> Dict[str, Any]:
        financial_metrics = data.get("financial_metrics", {})
        market_sizes = financial_metrics.get("market_sizes", [])
        
        if market_sizes:
            return {
                "global": statistics.mean(market_sizes),
                "currency": "USD"
            }

        return {
            "global": 0,
            "currency": "USD"
        }

    # ===============================
    # GROWTH EXTRACTION
    # ===============================
    def _extract_growth_rate(self, data: Dict[str, Any]) -> float:
        financial_metrics = data.get("financial_metrics", {})
        growth_rates = financial_metrics.get("growth_rates", [])
        return statistics.mean(growth_rates) if growth_rates else 0

    # ===============================
    # TAM / SAM / SOM
    # ===============================
    def _calculate_tam_sam_som(self, market_data):

        tam = market_data.get("global", 0)

        sam = tam * 0.3  # Assume 30% reachable region
        som = sam * 0.03  # Assume 3% realistic startup share

        return {
            "tam": tam,
            "sam": sam,
            "som": som,
            "assumptions": "SAM = 30% of TAM, SOM = 3% of SAM"
        }

    # ===============================
    # SENTIMENT ANALYSIS (KEYWORD BASED)
    # ===============================
    def _analyze_sentiment(self, data: Dict[str, Any]):

        positive_words = [
            "growth", "expanding", "rising", "demand",
            "opportunity", "adoption", "increase"
        ]

        negative_words = [
            "decline", "falling", "crisis",
            "saturation", "risk", "challenging"
        ]

        positive = 0
        negative = 0

        for keyword in data.get("keywords", []):
            text = keyword.lower()

            if any(word in text for word in positive_words):
                positive += 1

            if any(word in text for word in negative_words):
                negative += 1

        total = positive + negative if positive + negative > 0 else 1

        score = (positive - negative) / total

        if score > 0.2:
            label = "Positive"
        elif score < -0.2:
            label = "Negative"
        else:
            label = "Neutral"

        return {
            "score": score,
            "label": label,
            "positive_signals": positive,
            "negative_signals": negative
        }

    # ===============================
    # OPPORTUNITY SCORING
    # ===============================
    def _calculate_opportunity_score(self, tam_data, growth, sentiment_score):

        tam_value = tam_data.get("global", 0)

        score = 0.0

        # Market size scoring (up to 0.4)
        if tam_value > 10_000_000_000:
            score += 0.4
        elif tam_value > 1_000_000_000:
            score += 0.3
        elif tam_value > 100_000_000:
            score += 0.2

        # Growth scoring (up to 0.3)
        if growth > 15:
            score += 0.3
        elif growth > 10:
            score += 0.25
        elif growth > 5:
            score += 0.15
        elif growth > 0:
            score += 0.05

        # Sentiment scoring (up to 0.3)
        if sentiment_score > 0.2:
            score += 0.3
        elif sentiment_score > 0:
            score += 0.2
        elif sentiment_score < -0.2:
            score -= 0.1  # Penalise clearly negative sentiment

        # Penalise large but stagnant/negative markets
        if tam_value > 1_000_000_000 and growth < 1 and sentiment_score <= 0:
            score -= 0.1

        return max(0.0, min(score, 1.0))

    # ===============================
    # INSIGHTS
    # ===============================
    def _generate_insights(self, tam, growth, sentiment):

        insights = []

        if tam.get("global", 0) > 0:
            insights.append("Large addressable market identified.")

        if growth > 5:
            insights.append("Market shows strong growth trends.")

        if sentiment["label"] == "Positive":
            insights.append("Industry sentiment is favorable.")

        if not insights:
            insights.append("Limited market signals detected.")

        return insights

    # ===============================
    # SUMMARY
    # ===============================
    def _generate_summary(self, score):

        if score >= 0.7:
            return "Strong market opportunity with favorable growth and sentiment."
        elif score >= 0.5:
            return "Moderate market opportunity. Further validation required."
        else:
            return "Limited market opportunity. High caution advised."
