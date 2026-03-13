"""
competitive_analysis.py  —  Phase 2 update: RAG-augmented competitive analysis

Changes vs Phase 1:
  - run() accepts an optional `rag` parameter.
  - _extract_competitors() first checks RAG for competitor names when the
    structured entities list is sparse (< 3 orgs).
  - _extract_features() queries RAG for product/feature signals to enrich
    the feature distribution used in SWOT and gap analysis.
  - _generate_swot() incorporates swot_signals from the ExtractionEngine's
    LLM extraction (already present in extracted_data) alongside RAG insights.
  - All RAG usage degrades gracefully when rag is None or not ready.
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
from collections import Counter
from difflib import SequenceMatcher

from src.config.settings import COMPETITIVE_INTENSITY_THRESHOLDS
from src.orchestration.logger import setup_logger

logger = setup_logger()

# ── RAG query strings ──────────────────────────────────────────────────────

_RAG_COMPETITOR_QUERY  = "company competitor startup business player market"
_RAG_FEATURE_QUERY     = "product feature service capability offering platform"
_RAG_SWOT_STRENGTH_Q   = "strength advantage differentiator unique value proposition"
_RAG_SWOT_WEAKNESS_Q   = "weakness challenge problem risk limitation"
_RAG_SWOT_OPP_Q        = "opportunity growth potential untapped market gap"
_RAG_SWOT_THREAT_Q     = "threat competition barrier disruption saturation"


class CompetitiveAnalysisAgent:

    # ===============================
    # MAIN ENTRY POINT
    # ===============================

    def run(
        self,
        extracted_data: Dict[str, Any],
        rag=None,
    ) -> Dict[str, Any]:
        """
        Run competitive analysis.

        Args:
            extracted_data: ExtractionEngine output dict.
            rag:            Optional RAGManager instance (Phase 2).
        """
        competitors         = self._extract_competitors(extracted_data, rag=rag)
        clustered_competitors = self._cluster_entities(competitors)

        features            = self._extract_features(extracted_data, rag=rag)
        feature_distribution = Counter(features)

        intensity = self._calculate_competitive_intensity(clustered_competitors)

        swot = self._generate_swot(
            intensity,
            clustered_competitors,
            feature_distribution,
            extracted_data,
            rag=rag,
        )

        market_gaps = self._identify_market_gaps(
            feature_distribution,
            len(clustered_competitors)
        )

        summary = self._generate_summary(intensity)

        # Data confidence heuristic
        competitor_count  = len(clustered_competitors)
        distinct_features = len(feature_distribution)
        meta              = extracted_data.get("meta", {})
        num_pages         = meta.get("num_pages", 0)

        if competitor_count >= 10 and distinct_features >= 5 and num_pages >= 5:
            data_confidence = "High"
        elif competitor_count >= 3 and distinct_features >= 2:
            data_confidence = "Medium"
        else:
            data_confidence = "Low"

        return {
            "competitors_found":    len(clustered_competitors),
            "top_competitors":      clustered_competitors[:10],
            "competitive_intensity": intensity,
            "swot_analysis":        swot,
            "market_gaps":          market_gaps,
            "summary":              summary,
            "data_confidence":      data_confidence,
            "rag_augmented":        rag is not None and rag.is_ready(),
        }

    # ===============================
    # COMPETITOR EXTRACTION
    # ===============================

    def _extract_competitors(
        self,
        data: Dict[str, Any],
        rag=None,
    ) -> List[str]:
        """
        Extract competitor names from structured entities.
        Phase 2: when the structured list is sparse, query RAG for
        additional organization names.

        Handles two entity formats:
          Format 1 (ExtractionEngine): {"organizations": [...]}
          Format 2 (legacy/test):      [{"text": "X", "label": "ORG"}, ...]
        """
        competitors: List[str] = []
        entities = data.get("entities", {})

        # Format 1
        if isinstance(entities, dict):
            orgs = entities.get("organizations", [])
            if isinstance(orgs, list):
                competitors.extend(org for org in orgs if org)

        # Format 2
        elif isinstance(entities, list):
            for entity in entities:
                if isinstance(entity, dict) and entity.get("label") == "ORG":
                    text = entity.get("text", "")
                    if text:
                        competitors.append(text)

        # ── Phase 2: RAG augmentation when sparse ─────────────────────────
        if len(competitors) < 3 and rag is not None and rag.is_ready():
            logger.info(
                f"CompetitiveAnalysis: only {len(competitors)} competitors "
                "from structured data — querying RAG"
            )
            rag_competitors = self._extract_competitors_from_rag(rag)
            # Merge, avoiding duplicates
            existing_lower = {c.lower() for c in competitors}
            for comp in rag_competitors:
                if comp.lower() not in existing_lower:
                    competitors.append(comp)
                    existing_lower.add(comp.lower())
            logger.info(
                f"CompetitiveAnalysis RAG added competitors: {rag_competitors}"
            )

        return list(set(competitors))

    def _extract_competitors_from_rag(self, rag) -> List[str]:
        """
        Query RAG for competitor mentions and extract organization names
        using the LLM (or a simple capitalization heuristic as fallback).
        """
        chunks = rag.query(_RAG_COMPETITOR_QUERY, top_k=5, intent_filter=None)
        if not chunks:
            return []

        combined = "\n\n".join(chunks[:4])

        # Try LLM extraction
        try:
            from src.orchestration.llm_client import call_llm_json
            result = call_llm_json(
                "You are a named entity recognizer. Given text, return ONLY a JSON "
                'object: {"organizations": ["list of company or startup names mentioned"]}. '
                "Keep each name short (1-3 words). No duplicates.",
                f"Extract company/organization names from:\n\n{combined[:2_500]}",
            )
            if isinstance(result, dict):
                return [
                    o for o in result.get("organizations", [])
                    if isinstance(o, str) and o.strip()
                ][:15]
        except Exception as exc:
            logger.warning(
                f"CompetitiveAnalysis RAG LLM org extraction failed: {exc} "
                "— using heuristic"
            )

        # Heuristic fallback: extract capitalized multi-word phrases
        import re
        orgs = re.findall(r'\b([A-Z][a-z]+ (?:[A-Z][a-z]+ )?(?:Inc|Corp|Ltd|AI|Tech|Labs|Motors|Energy|Health|Ventures)?)\b', combined)
        return list(set(o.strip() for o in orgs if len(o.strip()) > 3))[:10]

    # ===============================
    # ENTITY CLUSTERING
    # ===============================

    def _cluster_entities(self, competitors: List[str]) -> List[str]:
        if len(competitors) > 200:
            return sorted(list(set(competitors)))

        clustered: List[str] = []
        for comp in competitors:
            if not any(self._similar(comp, existing) > 0.85 for existing in clustered):
                clustered.append(comp)
        return clustered

    def _similar(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    # ===============================
    # FEATURE EXTRACTION
    # ===============================

    def _extract_features(
        self,
        data: Dict[str, Any],
        rag=None,
    ) -> List[str]:
        """
        Extract product/feature keywords.
        Phase 2: supplements structured keywords with RAG semantic retrieval.
        """
        features: List[str] = []
        raw_keywords = data.get("keywords", [])

        if isinstance(raw_keywords, dict):
            keywords = list(raw_keywords.keys())
        elif isinstance(raw_keywords, list):
            keywords = raw_keywords
        else:
            keywords = []

        feature_terms = [
            "api", "mobile", "ai", "automation", "integration",
            "analytics", "dashboard", "platform", "saas", "cloud",
            "ml", "marketplace", "subscription", "b2b", "b2c",
        ]

        for keyword in keywords:
            if not isinstance(keyword, str):
                continue
            if any(word in keyword.lower() for word in feature_terms):
                features.append(keyword.lower())

        # ── Phase 2: RAG feature augmentation ─────────────────────────────
        if rag is not None and rag.is_ready():
            try:
                chunks = rag.query(
                    _RAG_FEATURE_QUERY, top_k=4, intent_filter=None
                )
                rag_features = self._parse_features_from_chunks(chunks)
                existing = set(features)
                for feat in rag_features:
                    if feat not in existing:
                        features.append(feat)
                        existing.add(feat)
                logger.info(
                    f"CompetitiveAnalysis RAG features added: {rag_features}"
                )
            except Exception as exc:
                logger.warning(
                    f"CompetitiveAnalysis RAG feature extraction failed: {exc}"
                )

        return features

    @staticmethod
    def _parse_features_from_chunks(chunks: List[str]) -> List[str]:
        """Extract product feature keywords from RAG chunks."""
        feature_terms = [
            "api", "mobile app", "ai", "machine learning", "automation",
            "integration", "analytics", "dashboard", "platform", "saas",
            "cloud", "marketplace", "subscription", "real-time", "b2b", "b2c",
            "blockchain", "iot", "ml", "data pipeline", "workflow",
        ]
        found: List[str] = []
        combined = " ".join(chunks).lower()
        for term in feature_terms:
            if term in combined:
                found.append(term)
        return found

    # ===============================
    # COMPETITIVE INTENSITY
    # ===============================

    def _calculate_competitive_intensity(self, competitors: List[str]) -> str:
        count      = len(competitors)
        low_max    = COMPETITIVE_INTENSITY_THRESHOLDS.get("low_max",    5)
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

    def _generate_swot(
        self,
        intensity: str,
        competitors: List[str],
        feature_distribution: Counter,
        extracted_data: Dict[str, Any],
        rag=None,
    ) -> Dict[str, List[str]]:
        """
        Phase 2: merge three SWOT signal sources:
          1. Rule-based signals (original logic).
          2. LLM-extracted swot_signals from ExtractionEngine.
          3. RAG semantic retrieval (new in Phase 2).
        """
        strengths: List[str]    = []
        weaknesses: List[str]   = []
        opportunities: List[str] = []
        threats: List[str]      = []

        competitor_count = len(competitors)
        sample_names     = ", ".join(competitors[:3])

        # ── 1. Rule-based signals ──────────────────────────────────────────
        if competitor_count >= 5:
            label = f"{competitor_count} identified competitors"
            msg   = f"Market validated by {label}"
            if sample_names:
                msg += f" (e.g. {sample_names})."
            strengths.append(msg)
        elif 1 <= competitor_count < 5:
            strengths.append(
                "Early competitive activity observed, indicating a live problem space."
            )

        if intensity == "High":
            msg = "Highly saturated market with many established players."
            if sample_names:
                msg += f" Notable incumbents include {sample_names}."
            weaknesses.append(msg)

        rare_features = [
            f for f, cnt in feature_distribution.items()
            if competitor_count > 0 and cnt / competitor_count < 0.3
        ]
        if rare_features:
            opportunities.append(
                f"Feature gaps identified: relatively few competitors mention "
                f"{', '.join(rare_features[:5])}."
            )

        if "ai automation" not in feature_distribution:
            opportunities.append(
                "AI-driven automation appears underrepresented among current competitors."
            )

        if intensity == "High":
            threats.append("Strong established competitors create high barriers to entry.")

        if intensity == "Low" and competitor_count == 0:
            opportunities.append(
                "No direct competitors identified, suggesting potential first-mover advantage."
            )

        # ── 2. LLM-extracted swot_signals from ExtractionEngine ───────────
        swot_signals = extracted_data.get("swot_signals", {})
        if isinstance(swot_signals, dict):
            strengths.extend(
                s for s in swot_signals.get("strengths", [])
                if s and s not in strengths
            )
            weaknesses.extend(
                w for w in swot_signals.get("weaknesses", [])
                if w and w not in weaknesses
            )
            opportunities.extend(
                o for o in swot_signals.get("opportunities", [])
                if o and o not in opportunities
            )
            threats.extend(
                t for t in swot_signals.get("threats", [])
                if t and t not in threats
            )

        # ── 3. RAG semantic SWOT augmentation ─────────────────────────────
        if rag is not None and rag.is_ready():
            rag_swot = self._rag_swot(rag)
            for s in rag_swot.get("strengths", []):
                if s and s not in strengths:
                    strengths.append(s)
            for w in rag_swot.get("weaknesses", []):
                if w and w not in weaknesses:
                    weaknesses.append(w)
            for o in rag_swot.get("opportunities", []):
                if o and o not in opportunities:
                    opportunities.append(o)
            for t in rag_swot.get("threats", []):
                if t and t not in threats:
                    threats.append(t)

        if not opportunities:
            opportunities.append("Explore niche positioning strategies.")

        return {
            "strengths":     strengths[:6],
            "weaknesses":    weaknesses[:6],
            "opportunities": opportunities[:6],
            "threats":       threats[:6],
        }

    def _rag_swot(self, rag) -> Dict[str, List[str]]:
        """
        Retrieve and synthesise SWOT signals via RAG queries.
        Returns dict with up to 3 items per quadrant.
        """
        swot: Dict[str, List[str]] = {
            "strengths": [], "weaknesses": [], "opportunities": [], "threats": []
        }

        query_map = [
            ("strengths",     _RAG_SWOT_STRENGTH_Q),
            ("weaknesses",    _RAG_SWOT_WEAKNESS_Q),
            ("opportunities", _RAG_SWOT_OPP_Q),
            ("threats",       _RAG_SWOT_THREAT_Q),
        ]

        try:
            from src.orchestration.llm_client import call_llm_json

            for quadrant, query in query_map:
                chunks = rag.query(query, top_k=3, intent_filter=None)
                if not chunks:
                    continue

                combined = "\n\n---\n\n".join(chunks[:3])
                try:
                    result = call_llm_json(
                        f"You are a business analyst. Given research text, identify "
                        f"the top 2-3 {quadrant} for a new market entrant. "
                        f'Return ONLY: {{"{quadrant}": ["short phrase 1", "short phrase 2"]}}',
                        f"Text:\n{combined[:2_000]}",
                    )
                    if isinstance(result, dict):
                        items = result.get(quadrant, [])
                        swot[quadrant].extend(
                            i for i in items if isinstance(i, str) and i.strip()
                        )
                        logger.info(
                            f"CompetitiveAnalysis RAG SWOT {quadrant}: {items}"
                        )
                except Exception as exc:
                    logger.warning(
                        f"CompetitiveAnalysis RAG SWOT LLM call failed "
                        f"for {quadrant}: {exc}"
                    )

        except Exception as exc:
            logger.warning(f"CompetitiveAnalysis _rag_swot failed: {exc}")

        return swot

    # ===============================
    # MARKET GAPS
    # ===============================

    def _identify_market_gaps(
        self,
        feature_distribution: Counter,
        competitor_count: int,
    ) -> List[str]:
        gaps = [
            f"{feature} present in few competitors."
            for feature, count in feature_distribution.items()
            if competitor_count > 0 and count / competitor_count < 0.3
        ]
        if not gaps:
            gaps.append("No obvious feature gaps identified.")
        return gaps[:5]

    # ===============================
    # SUMMARY
    # ===============================

    def _generate_summary(self, intensity: str) -> str:
        if intensity == "High":
            return "Market is highly competitive with significant rivalry."
        elif intensity == "Medium":
            return "Moderate competition with room for differentiation."
        else:
            return "Low competition environment. Opportunity to capture early market share."