"""
market_analysis.py  —  Phase 2 update: RAG-augmented market analysis

Changes vs Phase 1b:
  - run() and run_with_review() accept an optional `rag` parameter.
  - _analyze_sentiment() now performs a semantic RAG query for sentiment-
    bearing chunks before falling back to keyword scanning.
  - _extract_market_size() and _extract_growth_rate() query RAG when
    the structured financial_metrics are empty.
  - All RAG usage degrades gracefully to the original behaviour when
    rag is None or not ready.
"""

from __future__ import annotations

import json
import statistics
from typing import Dict, Any, List, Optional

from src.config.settings import LLM_SETTINGS, MARKET_SETTINGS
from src.orchestration.logger import setup_logger

logger = setup_logger()

REVIEW_CONFIDENCE_THRESHOLD: float = 0.65
MAX_REVIEW_ITERATIONS: int         = 2

_REVIEW_SYSTEM = """You are a market analysis quality-assurance agent.
Given a market analysis JSON, assess its reliability and completeness.

Return ONLY a JSON object with exactly these keys:
{
  "confidence": <float 0.0–1.0>,
  "issues": ["list of specific data gaps"],
  "missing_signals": ["list of targeted search queries to fill the gaps"],
  "verdict": "PASS" | "NEEDS_MORE_DATA"
}

confidence scoring guide:
  1.0  — TAM > 0, growth rate > 0, sentiment signal, opportunity_score > 0
  0.75 — TAM > 0 and growth rate > 0, but weak sentiment
  0.5  — either TAM or growth rate present, not both
  0.25 — no TAM, no growth rate, only sentiment
  0.0  — completely empty output

verdict: "PASS" if confidence >= 0.65, otherwise "NEEDS_MORE_DATA".
"""

_REVIEW_USER = """Review this market analysis output:

{analysis_json}

Business context: {business_idea} in {industry} targeting {target_market}.
"""

# ── RAG sentiment extraction prompt ───────────────────────────────────────

_SENTIMENT_SYSTEM = """You are a market sentiment analyst.
Given research text snippets, identify positive and negative market signals.

Return ONLY a JSON object:
{
  "positive_phrases": ["list of short positive signals found in the text"],
  "negative_phrases": ["list of short negative signals found in the text"]
}

Examples of positive signals: growth, demand, expansion, adoption, rising, opportunity
Examples of negative signals: decline, saturation, risk, challenging, falling, crisis
"""

_SENTIMENT_USER = "Analyse market sentiment from these research snippets:\n\n{chunks}"


class MarketAnalysisAgent:

    # ═══════════════════════════════════════════════════════════════════════
    # PUBLIC: run_with_review  (Phase 2 entry point)
    # ═══════════════════════════════════════════════════════════════════════

    def run_with_review(
        self,
        extracted_data:   Dict[str, Any],
        structured_input: Dict[str, Any] | None = None,
        search_callback=None,
        rag=None,
    ) -> Dict[str, Any]:
        """
        Run market analysis with optional RAG augmentation and self-review.

        Args:
            extracted_data:   ExtractionEngine output.
            structured_input: Business context dict.
            search_callback:  Optional callable(queries) → new extracted_data.
            rag:              Optional RAGManager instance (Phase 2).

        Returns:
            Analysis result dict with an added `review` key.
        """
        result = self.run(extracted_data, rag=rag)
        ctx    = structured_input or {}

        if not LLM_SETTINGS.get("enable_self_correction", True):
            result["review"] = {"confidence": None, "verdict": "SKIPPED", "issues": []}
            return result

        for iteration in range(1, MAX_REVIEW_ITERATIONS + 1):
            review = self._review_output(result, ctx)
            logger.info(
                f"MarketAnalysis review iter {iteration}: "
                f"confidence={review['confidence']:.2f} verdict={review['verdict']}"
            )
            result["review"] = review

            if review["verdict"] == "PASS":
                break

            missing = review.get("missing_signals", [])
            if not missing or search_callback is None:
                logger.info(
                    "MarketAnalysis: review found gaps but "
                    "no search_callback provided — stopping."
                )
                break

            logger.info(f"MarketAnalysis: triggering gap-fill for: {missing}")
            try:
                enriched = search_callback(missing)
                if enriched:
                    extracted_data = _merge_market_data(extracted_data, enriched)
                    result         = self.run(extracted_data, rag=rag)
            except Exception as exc:
                logger.warning(f"MarketAnalysis gap-fill failed: {exc}")
                break

        return result

    # ═══════════════════════════════════════════════════════════════════════
    # ORIGINAL run()  — Phase 2: rag param added
    # ═══════════════════════════════════════════════════════════════════════

    def run(
        self,
        extracted_data: Dict[str, Any],
        rag=None,
    ) -> Dict[str, Any]:
        tam        = self._extract_market_size(extracted_data, rag=rag)
        growth     = self._extract_growth_rate(extracted_data, rag=rag)
        sentiment  = self._analyze_sentiment(extracted_data, rag=rag)
        tam_sam_som = self._calculate_tam_sam_som(tam)

        opportunity_score = self._calculate_opportunity_score(
            tam, growth, sentiment["score"]
        )
        summary = self._generate_summary(opportunity_score)

        fm           = extracted_data.get("financial_metrics", {})
        market_sizes = fm.get("market_sizes",  [])
        growth_rates = fm.get("growth_rates",  [])
        signal_count = (
            (1 if market_sizes else 0) +
            (1 if growth_rates else 0) +
            (1 if sentiment["positive_signals"] or sentiment["negative_signals"] else 0)
        )
        num_pages = extracted_data.get("meta", {}).get("num_pages", 0)

        if signal_count == 3 and num_pages >= 5:
            data_confidence = "High"
        elif signal_count >= 2:
            data_confidence = "Medium"
        else:
            data_confidence = "Low"

        return {
            "market_size":       tam,
            "tam_sam_som":       tam_sam_som,
            "growth_rate":       growth,
            "sentiment":         sentiment,
            "opportunity_score": round(opportunity_score, 2),
            "key_insights":      self._generate_insights(tam, growth, sentiment),
            "summary":           summary,
            "data_confidence":   data_confidence,
            "rag_augmented":     rag is not None and rag.is_ready(),
        }

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 2: RAG-AUGMENTED HELPERS
    # ═══════════════════════════════════════════════════════════════════════

    def _extract_market_size(
        self,
        data: Dict[str, Any],
        rag=None,
    ) -> Dict[str, Any]:
        sizes = data.get("financial_metrics", {}).get("market_sizes", [])

        if not sizes and rag is not None and rag.is_ready():
            logger.info("MarketAnalysis: market_sizes empty — querying RAG")
            chunks = rag.query(
                "total addressable market size TAM billion valuation industry",
                top_k=3,
                intent_filter=None,
            )
            if chunks:
                sizes = self._parse_money_from_chunks(chunks)
                logger.info(f"MarketAnalysis RAG extracted market sizes: {sizes}")

        if sizes:
            return {"global": statistics.mean(sizes), "currency": "USD"}
        return {"global": 0, "currency": "USD"}

    def _extract_growth_rate(
        self,
        data: Dict[str, Any],
        rag=None,
    ) -> float:
        rates = data.get("financial_metrics", {}).get("growth_rates", [])

        if not rates and rag is not None and rag.is_ready():
            logger.info("MarketAnalysis: growth_rates empty — querying RAG")
            chunks = rag.query(
                "market growth rate CAGR annual growth percentage forecast",
                top_k=3,
                intent_filter=None,
            )
            if chunks:
                rates = self._parse_percentages_from_chunks(chunks)
                logger.info(f"MarketAnalysis RAG extracted growth rates: {rates}")

        return statistics.mean(rates) if rates else 0

    def _analyze_sentiment(
        self,
        data: Dict[str, Any],
        rag=None,
    ) -> Dict[str, Any]:
        """
        Phase 2: First try a RAG semantic query for sentiment-bearing text,
        then run the keyword scan over both RAG chunks and existing keywords.
        """
        positive_words = ["growth", "expanding", "rising", "demand",
                          "opportunity", "adoption", "increase", "bullish",
                          "surge", "boom", "accelerat"]
        negative_words = ["decline", "falling", "crisis", "saturation",
                          "risk", "challenging", "bearish", "slowdown",
                          "contraction", "downturn"]

        positive = negative = 0

        # ── Phase 2: RAG sentiment retrieval ──────────────────────────────
        rag_positive_bonus = 0
        rag_negative_bonus = 0

        if rag is not None and rag.is_ready():
            try:
                pos_chunks = rag.query(
                    "market growth opportunity demand adoption expansion",
                    top_k=3,
                    intent_filter=None,
                )
                neg_chunks = rag.query(
                    "market risk decline saturation competition challenge",
                    top_k=3,
                    intent_filter=None,
                )

                # Count positive/negative signals in RAG chunks
                for chunk in pos_chunks:
                    chunk_lower = chunk.lower()
                    rag_positive_bonus += sum(
                        1 for w in positive_words if w in chunk_lower
                    )
                for chunk in neg_chunks:
                    chunk_lower = chunk.lower()
                    rag_negative_bonus += sum(
                        1 for w in negative_words if w in chunk_lower
                    )

                # Try LLM-assisted sentiment for better accuracy
                if pos_chunks or neg_chunks:
                    llm_sentiment = self._llm_sentiment(pos_chunks + neg_chunks)
                    if llm_sentiment:
                        rag_positive_bonus = max(
                            rag_positive_bonus, llm_sentiment["positive"]
                        )
                        rag_negative_bonus = max(
                            rag_negative_bonus, llm_sentiment["negative"]
                        )

                logger.info(
                    f"MarketAnalysis RAG sentiment: "
                    f"+{rag_positive_bonus} -{rag_negative_bonus}"
                )
            except Exception as exc:
                logger.warning(f"MarketAnalysis RAG sentiment query failed: {exc}")

        positive += rag_positive_bonus
        negative += rag_negative_bonus

        # ── Original keyword scan over extracted keywords ──────────────────
        for keyword in data.get("keywords", []):
            text = keyword.lower()
            if any(w in text for w in positive_words):
                positive += 1
            if any(w in text for w in negative_words):
                negative += 1

        total = positive + negative if positive + negative > 0 else 1
        score = (positive - negative) / total
        label = "Positive" if score > 0.2 else ("Negative" if score < -0.2 else "Neutral")
        return {
            "score":            score,
            "label":            label,
            "positive_signals": positive,
            "negative_signals": negative,
        }

    def _llm_sentiment(self, chunks: List[str]) -> Optional[Dict[str, int]]:
        """
        Ask the LLM to count positive/negative market signals in chunks.
        Returns None if LLM is unavailable.
        """
        try:
            from src.orchestration.llm_client import call_llm_json
            combined = "\n\n---\n\n".join(chunks[:4])
            result = call_llm_json(
                _SENTIMENT_SYSTEM,
                _SENTIMENT_USER.format(chunks=combined[:2_500]),
            )
            if isinstance(result, dict):
                pos = len(result.get("positive_phrases", []))
                neg = len(result.get("negative_phrases", []))
                return {"positive": pos, "negative": neg}
        except Exception as exc:
            logger.warning(f"MarketAnalysis LLM sentiment failed: {exc}")
        return None

    # ── Numeric parsers ────────────────────────────────────────────────────

    @staticmethod
    def _parse_money_from_chunks(chunks: List[str]) -> List[float]:
        import re
        pattern = r"\$?\s?(\d+(?:[.,]\d+)?)\s?(trillion|billion|million|bn|tn|b|m)?"
        results = []
        for chunk in chunks:
            for num_str, unit in re.findall(pattern, chunk.lower()):
                try:
                    val = float(num_str.replace(",", ""))
                    u   = unit.lower().strip()
                    if u in ("t", "tn", "trillion"):  val *= 1e12
                    elif u in ("b", "bn", "billion"): val *= 1e9
                    elif u in ("m", "million"):        val *= 1e6
                    if val > 1_000_000:   # filter out tiny numbers
                        results.append(val)
                except ValueError:
                    pass
        return results[:5]

    @staticmethod
    def _parse_percentages_from_chunks(chunks: List[str]) -> List[float]:
        import re
        pattern = r"\b(\d+(?:\.\d+)?)\s?%"
        results = []
        for chunk in chunks:
            for pct in re.findall(pattern, chunk):
                try:
                    val = float(pct)
                    if 0 < val < 200:   # sanity filter
                        results.append(val)
                except ValueError:
                    pass
        return results[:5]

    # ═══════════════════════════════════════════════════════════════════════
    # PHASE 1b: SELF-REVIEW  (unchanged)
    # ═══════════════════════════════════════════════════════════════════════

    def _review_output(
        self,
        result:  Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from src.orchestration.llm_client import call_llm_json
            user_prompt = _REVIEW_USER.format(
                analysis_json = json.dumps(result, indent=2, default=str)[:3_000],
                business_idea = context.get("business_idea", "unknown"),
                industry      = context.get("industry",      "unknown"),
                target_market = context.get("target_market", "unknown"),
            )
            review = call_llm_json(_REVIEW_SYSTEM, user_prompt)
            if not isinstance(review, dict):
                raise ValueError("non-dict response")
            review.setdefault("confidence",      0.5)
            review.setdefault("issues",          [])
            review.setdefault("missing_signals", [])
            review.setdefault(
                "verdict",
                "PASS" if float(review["confidence"]) >= REVIEW_CONFIDENCE_THRESHOLD
                else "NEEDS_MORE_DATA",
            )
            return review
        except Exception as exc:
            logger.warning(f"LLM market review unavailable: {exc} — using heuristic")
            return self._heuristic_review(result, context)

    def _heuristic_review(
        self,
        result:  Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        tam_value = result.get("market_size",  {}).get("global",  0) or 0
        growth    = result.get("growth_rate",  0) or 0
        sentiment = result.get("sentiment",    {})
        pos_sig   = sentiment.get("positive_signals", 0)
        neg_sig   = sentiment.get("negative_signals", 0)
        opp_score = result.get("opportunity_score", 0) or 0

        score = 0.0
        issues: List[str]          = []
        missing_signals: List[str] = []

        idea     = context.get("business_idea", "{idea}")
        industry = context.get("industry",      "{industry}")

        if tam_value > 0:
            score += 0.35
        else:
            issues.append("No TAM / market size data found")
            missing_signals.append(f"{industry} total addressable market size 2026")

        if growth > 0:
            score += 0.35
        else:
            issues.append("Missing CAGR / growth rate")
            missing_signals.append(f"{industry} market CAGR growth rate forecast")

        if pos_sig + neg_sig > 0:
            score += 0.20
        else:
            issues.append("No sentiment signals in keywords")
            missing_signals.append(f"{idea} industry trends outlook 2026")

        if opp_score > 0:
            score += 0.10

        verdict = "PASS" if score >= REVIEW_CONFIDENCE_THRESHOLD else "NEEDS_MORE_DATA"
        return {
            "confidence":      round(score, 2),
            "issues":          issues,
            "missing_signals": missing_signals,
            "verdict":         verdict,
        }

    # ═══════════════════════════════════════════════════════════════════════
    # ORIGINAL helpers  (unchanged)
    # ═══════════════════════════════════════════════════════════════════════

    def _calculate_tam_sam_som(self, market_data):
        tam       = market_data.get("global", 0)
        sam_ratio = MARKET_SETTINGS.get("sam_ratio", 0.30)
        som_ratio = MARKET_SETTINGS.get("som_ratio", 0.03)
        return {
            "tam": tam,
            "sam": tam * sam_ratio,
            "som": tam * sam_ratio * som_ratio,
            "assumptions": f"SAM = {sam_ratio:.0%} of TAM, SOM = {som_ratio:.0%} of SAM",
        }

    def _calculate_opportunity_score(self, tam_data, growth, sentiment_score):
        tam   = tam_data.get("global", 0)
        score = 0.0
        if tam > 10_000_000_000:
            score += 0.4
        elif tam > 1_000_000_000:
            score += 0.3
        elif tam > 100_000_000:
            score += 0.2
        if growth > 15:
            score += 0.3
        elif growth > 10:
            score += 0.25
        elif growth > 5:
            score += 0.15
        elif growth > 0:
            score += 0.05
        if sentiment_score > 0.2:
            score += 0.3
        elif sentiment_score > 0:
            score += 0.2
        elif sentiment_score < -0.2:
            score -= 0.1
        if tam > 1_000_000_000 and growth < 1 and sentiment_score >= 0:
            score -= 0.1
        return max(0.0, min(score, 1.0))

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

    def _generate_summary(self, score):
        if score >= 0.7:
            return "Strong market opportunity with favorable growth and sentiment."
        elif score >= 0.5:
            return "Moderate market opportunity. Further validation required."
        else:
            return "Limited market opportunity. High caution advised."


# ─────────────────────────────────────────────────────────────────────────────
# Module helper
# ─────────────────────────────────────────────────────────────────────────────

def _merge_market_data(
    base:  Dict[str, Any],
    extra: Dict[str, Any],
) -> Dict[str, Any]:
    merged   = dict(base)
    base_fm  = {k: list(v) for k, v in (base.get("financial_metrics") or {}).items()}
    extra_fm = extra.get("financial_metrics") or {}
    for key in ["market_sizes", "growth_rates"]:
        combined    = base_fm.get(key, []) + list(extra_fm.get(key, []))
        base_fm[key] = list(set(combined))
    extra_kw  = extra.get("keywords", [])
    base_kw   = list(base.get("keywords", []))
    merged["financial_metrics"] = base_fm
    merged["keywords"]          = list(dict.fromkeys(base_kw + extra_kw))
    return merged