from __future__ import annotations

import json
from typing import Any

from src.config.settings import LLM_SETTINGS
from src.orchestration.logger import setup_logger

logger = setup_logger()


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_CRITIQUE_SYSTEM_PROMPT = """You are a quality-assurance agent reviewing a
business intelligence extraction result.

Given the original extraction JSON and a summary of the source data,
identify any gaps or obvious errors and return an IMPROVED version of the
JSON with those gaps filled in.

Return ONLY the corrected JSON object with the same top-level keys.
Do not add new keys. Do not change the structure."""

_CRITIQUE_USER_TEMPLATE = """
ORIGINAL EXTRACTION (may have gaps):
{extraction_json}

SOURCE SUMMARY (sample text from scraped pages):
{source_summary}

CONFIDENCE ISSUES DETECTED:
{issues}

Please return the improved extraction JSON with the gaps filled.
"""


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------

class SelfCorrectionAgent:
    """
    Wraps the extraction output in an iterative critique-and-repair loop.
    """

    def __init__(self):
        cfg = LLM_SETTINGS
        self._enabled         = cfg.get("enable_self_correction", True)
        self._max_iterations  = cfg.get("self_correction_max_iterations", 2)
        self._threshold       = cfg.get("self_correction_confidence_threshold", 0.6)
        logger.info(
            f"SelfCorrectionAgent initialized "
            f"[enabled={self._enabled}, threshold={self._threshold}, "
            f"max_iters={self._max_iterations}]"
        )

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    def run(
        self,
        extracted_data: dict,
        scraped_content: list[dict],
    ) -> dict:
        """
        Run the self-correction loop.

        Args:
            extracted_data:  Output from ExtractionEngine.process()
            scraped_content: Raw scraped pages (used as reference text)

        Returns:
            Potentially improved extracted_data dict.
        """
        if not self._enabled:
            logger.info("Self-correction disabled — skipping")
            return extracted_data

        confidence, issues = self._score_confidence(extracted_data)
        logger.info(
            f"Self-correction: initial confidence={confidence:.2f} "
            f"[threshold={self._threshold}] issues={issues}"
        )

        if confidence >= self._threshold:
            logger.info("Self-correction: confidence sufficient — no correction needed")
            extracted_data["meta"]["self_correction_applied"] = False
            extracted_data["meta"]["confidence_score"]        = round(confidence, 3)
            return extracted_data

        source_summary = self._build_source_summary(scraped_content)
        current        = extracted_data

        for iteration in range(1, self._max_iterations + 1):
            logger.info(f"Self-correction iteration {iteration}/{self._max_iterations}")
            try:
                current   = self._correct(current, source_summary, issues)
                new_conf, issues = self._score_confidence(current)
                logger.info(
                    f"Self-correction iter {iteration}: confidence={new_conf:.2f}"
                )
                if new_conf >= self._threshold:
                    logger.info("Self-correction: threshold reached — stopping early")
                    break
            except Exception as exc:
                logger.warning(f"Self-correction iteration {iteration} failed: {exc}")
                # Return the best version we have so far
                break

        current.setdefault("meta", {})
        current["meta"]["self_correction_applied"] = True
        current["meta"]["confidence_score"]        = round(
            self._score_confidence(current)[0], 3
        )
        return current

    # -----------------------------------------------------------------------
    # Confidence scoring
    # -----------------------------------------------------------------------

    def _score_confidence(self, data: dict) -> tuple[float, list[str]]:
        """
        Heuristic confidence score based on data completeness.
        Returns (score: float, issues: list[str]).
        """
        score  = 0.0
        issues = []

        # Entities
        orgs = data.get("entities", {}).get("organizations", [])
        if len(orgs) >= 3:
            score += 0.25
        elif orgs:
            score += 0.10
            issues.append("Few organizations extracted (<3)")
        else:
            issues.append("No organizations extracted")

        # Financial signals
        fm = data.get("financial_metrics", {})
        signal_count = sum(
            1 for k in ["startup_costs", "revenue_figures", "market_sizes", "growth_rates"]
            if fm.get(k)
        )
        score += min(signal_count * 0.10, 0.30)
        if signal_count == 0:
            issues.append("No financial signals extracted")
        elif signal_count < 2:
            issues.append("Sparse financial signals (< 2 categories)")

        # Keywords
        kws = data.get("keywords", [])
        if len(kws) >= 10:
            score += 0.20
        elif len(kws) >= 5:
            score += 0.10
            issues.append("Few keywords extracted (<10)")
        else:
            issues.append("Very few keywords extracted (<5)")

        # SWOT signals (new in Phase 1)
        swot = data.get("swot_signals", {})
        swot_items = sum(len(v) for v in swot.values() if isinstance(v, list))
        if swot_items >= 4:
            score += 0.15
        elif swot_items > 0:
            score += 0.07
            issues.append("Sparse SWOT signals")
        else:
            issues.append("No SWOT signals extracted")

        # Page coverage
        meta      = data.get("meta", {})
        num_pages = meta.get("num_pages", 0)
        if num_pages >= 5:
            score += 0.10
        elif num_pages >= 2:
            score += 0.05

        return min(score, 1.0), issues

    # -----------------------------------------------------------------------
    # LLM-driven correction
    # -----------------------------------------------------------------------

    def _correct(
        self,
        data:           dict,
        source_summary: str,
        issues:         list[str],
    ) -> dict:
        """
        Ask the LLM to critique the current extraction and return an
        improved version.
        """
        from src.orchestration.llm_client import call_llm_json

        extraction_json = json.dumps(data, indent=2, default=str)
        issues_text     = "\n".join(f"- {i}" for i in issues) or "- General quality review"

        user_prompt = _CRITIQUE_USER_TEMPLATE.format(
            extraction_json=extraction_json[:4_000],   # stay within context
            source_summary=source_summary[:2_000],
            issues=issues_text,
        )

        corrected = call_llm_json(_CRITIQUE_SYSTEM_PROMPT, user_prompt)

        if not isinstance(corrected, dict):
            raise ValueError(f"Correction LLM returned non-dict: {type(corrected)}")

        # Merge: keep original structure, overlay non-empty fields from corrected
        merged = dict(data)
        for k, v in corrected.items():
            if k not in merged:
                continue   # don't add unexpected keys
            orig = merged[k]
            if isinstance(orig, list) and isinstance(v, list) and v:
                # Deduplicated union
                merged[k] = list(dict.fromkeys(orig + v))
            elif isinstance(orig, dict) and isinstance(v, dict):
                # Recursive merge for dicts (e.g. entities, financial_metrics)
                for inner_k, inner_v in v.items():
                    if inner_k in orig and isinstance(orig[inner_k], list) and isinstance(inner_v, list):
                        merged[k][inner_k] = list(dict.fromkeys(orig[inner_k] + inner_v))
                    elif inner_v:
                        merged[k][inner_k] = inner_v
            elif v:
                merged[k] = v

        return merged

    # -----------------------------------------------------------------------
    # Source summary builder
    # -----------------------------------------------------------------------

    @staticmethod
    def _build_source_summary(scraped_content: list[dict], max_chars: int = 3_000) -> str:
        """
        Build a short representative text sample from scraped pages
        for use as grounding context in the correction prompt.
        """
        parts = []
        budget = max_chars
        for page in scraped_content[:5]:   # use top-5 pages by quality
            snippet = (page.get("text") or "")[:600]
            if snippet:
                parts.append(f"[{page.get('url', 'unknown')}]\n{snippet}")
                budget -= len(snippet)
                if budget <= 0:
                    break
        return "\n\n".join(parts)