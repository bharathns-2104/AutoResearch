from typing import Dict, Any, List
from collections import Counter
from difflib import SequenceMatcher
from src.config.settings import COMPETITIVE_INTENSITY_THRESHOLDS

class CompetitiveAnalysisAgent:

    # ===============================
    # MAIN ENTRY POINT
    # ===============================
    def run(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:

        competitors = self._extract_competitors(extracted_data)
        clustered_competitors = self._cluster_entities(competitors)

        features = self._extract_features(extracted_data)
        feature_distribution = Counter(features)

        intensity = self._calculate_competitive_intensity(clustered_competitors)

        swot = self._generate_swot(
            intensity,
            clustered_competitors,
            feature_distribution
        )

        market_gaps = self._identify_market_gaps(
            feature_distribution,
            len(clustered_competitors)
        )

        summary = self._generate_summary(intensity)

        # Data confidence heuristic for competitive landscape
        competitor_count = len(clustered_competitors)
        distinct_features = len(feature_distribution)

        meta = extracted_data.get("meta", {})
        num_pages = meta.get("num_pages", 0)

        if competitor_count >= 10 and distinct_features >= 5 and num_pages >= 5:
            data_confidence = "High"
        elif competitor_count >= 3 and distinct_features >= 2:
            data_confidence = "Medium"
        else:
            data_confidence = "Low"

        return {
            "competitors_found": len(clustered_competitors),
            "top_competitors": clustered_competitors[:10],
            "competitive_intensity": intensity,
            "swot_analysis": swot,
            "market_gaps": market_gaps,
            "summary": summary,
            "data_confidence": data_confidence,
        }

    # ===============================
    # COMPETITOR EXTRACTION
    # ===============================
    def _extract_competitors(self, data: Dict[str, Any]) -> List[str]:
        """
        Handles two formats:
          1. ExtractionEngine format:
               {"entities": {"organizations": [...], "people": [...], "locations": [...]}}
          2. Test / legacy format:
               {"entities": [{"text": "CompanyA", "label": "ORG"}, ...]}
        """
        competitors = []

        entities = data.get("entities", {})

        # --- Format 1: dict with sub-keys (ExtractionEngine output) ---
        if isinstance(entities, dict):
            orgs = entities.get("organizations", [])
            if isinstance(orgs, list):
                competitors.extend([org for org in orgs if org])

        # --- Format 2: list of dicts (test / legacy format) ---
        elif isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict) and entity.get("label") == "ORG":
                    text = entity.get("text", "")
                    if text:
                        competitors.append(text)

        return list(set(competitors))

    # ===============================
    # ENTITY CLUSTERING
    # ===============================
    def _cluster_entities(self, competitors: List[str]) -> List[str]:

        clustered = []

        for comp in competitors:
            if not any(self._similar(comp, existing) > 0.85 for existing in clustered):
                clustered.append(comp)

        return clustered

    def _similar(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    # ===============================
    # FEATURE EXTRACTION
    # ===============================
    def _extract_features(self, data: Dict[str, Any]) -> List[str]:
        """
        Handles keywords as either:
          - list of strings  (ExtractionEngine output)
          - dict / Counter   (fallback)
        """
        features = []

        raw_keywords = data.get("keywords", [])

        # Normalise to a flat list of strings
        if isinstance(raw_keywords, dict):
            keywords = list(raw_keywords.keys())
        elif isinstance(raw_keywords, list):
            keywords = raw_keywords
        else:
            keywords = []

        for keyword in keywords:
            if not isinstance(keyword, str):
                continue
            if any(word in keyword.lower() for word in
                   ["api", "mobile", "ai", "automation",
                    "integration", "analytics", "dashboard"]):
                features.append(keyword.lower())

        return features

    # ===============================
    # COMPETITIVE INTENSITY (CONFIGURABLE: Issue #9)
    # ===============================
    def _calculate_competitive_intensity(self, competitors: List[str]) -> str:
        """
        Classify competitive intensity based on number of competitors.
        
        Thresholds are configurable in src/config/settings.py:
        COMPETITIVE_INTENSITY_THRESHOLDS
        
        Industry rationale:
        - Low (< 5): Niche markets with few established players
        - Medium (5-15): Moderate competition with differentiation opportunities
        - High (> 15): Saturated markets with many competitors
        """
        count = len(competitors)
        low_max = COMPETITIVE_INTENSITY_THRESHOLDS.get("low_max", 5)
        medium_max = COMPETITIVE_INTENSITY_THRESHOLDS.get("medium_max", 15)

        if count < low_max:
            return "Low"
        elif count <= medium_max:
            return "Medium"
        else:
            return "High"

    # ===============================
    # SWOT GENERATION
    # ===============================
    def _generate_swot(self, intensity, competitors, feature_distribution):

        strengths = []
        weaknesses = []
        opportunities = []
        threats = []

        competitor_count = len(competitors)
        sample_names = ", ".join(competitors[:3])

        # Strengths
        if competitor_count >= 5:
            label = f"{competitor_count} identified competitors"
            if sample_names:
                strengths.append(
                    f"Market validated by {label} (e.g. {sample_names})."
                )
            else:
                strengths.append("Market validated by multiple named competitors.")
        elif 1 <= competitor_count < 5:
            strengths.append(
                "Early competitive activity observed, indicating a live problem space."
            )

        # Weaknesses
        if intensity == "High":
            msg = "Highly saturated market with many established players."
            if sample_names:
                msg += f" Notable incumbents include {sample_names}."
            weaknesses.append(msg)

        # Opportunities: under-served features
        rare_features = []
        for feature, count in feature_distribution.items():
            if competitor_count > 0 and count / competitor_count < 0.3:
                rare_features.append(feature)

        if rare_features:
            top_rare = ", ".join(rare_features[:5])
            opportunities.append(
                f"Feature gaps identified: relatively few competitors mention {top_rare}."
            )

        if "ai automation" not in feature_distribution:
            opportunities.append("AI-driven automation appears underrepresented among current competitors.")

        # Threats
        if intensity == "High":
            threats.append("Strong established competitors create high barriers to entry.")

        if intensity == "Low" and competitor_count == 0:
            opportunities.append(
                "No direct competitors identified, suggesting potential first-mover advantage."
            )

        if not opportunities:
            opportunities.append("Explore niche positioning strategies.")

        return {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "opportunities": opportunities,
            "threats": threats
        }

    # ===============================
    # MARKET GAPS
    # ===============================
    def _identify_market_gaps(self, feature_distribution, competitor_count):

        gaps = []

        for feature, count in feature_distribution.items():
            if competitor_count > 0 and count / competitor_count < 0.3:
                gaps.append(f"{feature} present in few competitors.")

        if not gaps:
            gaps.append("No obvious feature gaps identified.")

        return gaps[:5]

    # ===============================
    # SUMMARY
    # ===============================
    def _generate_summary(self, intensity):

        if intensity == "High":
            return "Market is highly competitive with significant rivalry."
        elif intensity == "Medium":
            return "Moderate competition with room for differentiation."
        else:
            return "Low competition environment. Opportunity to capture early market share."