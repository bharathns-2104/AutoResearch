from typing import Dict, Any, List
from collections import Counter
from difflib import SequenceMatcher


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

        return {
            "competitors_found": len(clustered_competitors),
            "top_competitors": clustered_competitors[:10],
            "competitive_intensity": intensity,
            "swot_analysis": swot,
            "market_gaps": market_gaps,
            "summary": summary
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
    # COMPETITIVE INTENSITY
    # ===============================
    def _calculate_competitive_intensity(self, competitors: List[str]) -> str:

        count = len(competitors)

        if count < 5:
            return "Low"
        elif 5 <= count <= 15:
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

        # Strengths
        if len(competitors) >= 5:
            strengths.append("Market validated by multiple competitors.")

        # Weaknesses
        if intensity == "High":
            weaknesses.append("Highly saturated market.")

        # Opportunities
        if "ai automation" not in feature_distribution:
            opportunities.append("AI features underutilized in competitors.")

        # Threats
        if intensity == "High":
            threats.append("Strong established competitors with market dominance.")

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