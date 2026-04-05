from __future__ import annotations

import re
import json
import spacy
from collections import Counter
from typing import Any

from src.orchestration.logger import setup_logger
from src.orchestration.state_manager import StateManager, SystemState
from src.config.settings import EXTRACTION_SETTINGS, LLM_SETTINGS

logger = setup_logger()


# ---------------------------------------------------------------------------
# LLM extraction prompt
# ---------------------------------------------------------------------------
_EXTRACTION_SYSTEM_PROMPT = """You are a business intelligence extraction engine.
Given a web page's text, extract structured business data in JSON format.

Your output MUST be a single JSON object with these exact keys:
{
  "organizations": ["list of company/org names mentioned"],
  "people": ["list of person names mentioned"],
  "locations": ["list of geographic locations mentioned"],
  "startup_costs": [list of numeric USD values for costs/expenses/budgets],
  "revenue_figures": [list of numeric USD values for revenue/income/earnings],
  "funding_amounts": [list of numeric USD values for funding/investment rounds],
  "market_sizes": [list of numeric USD values for market size/TAM/valuation],
  "growth_rates": [list of numeric percentage values for growth/CAGR],
  "keywords": ["list of up to 15 important business/industry keywords from the text"],
  "swot": {
    "strengths": ["brief phrases"],
    "weaknesses": ["brief phrases"],
    "opportunities": ["brief phrases"],
    "threats": ["brief phrases"]
  }
}

Rules:
- All monetary values must be plain numbers in USD (e.g. 5000000 not "$5M").
- All percentage values must be plain numbers (e.g. 8.5 not "8.5%").
- If a field has no data, use an empty list [].
- Keep keywords concise (1-3 words each), lowercase.
- Do not include duplicates.
"""

_EXTRACTION_USER_TEMPLATE = """Extract business intelligence from the following web page text.
Page URL: {url}
Page Title: {title}

TEXT:
{text}
"""


class ExtractionEngine:

    def __init__(self):
        self.state = StateManager()
        # spaCy is kept as a lightweight fallback NER tool
        try:
            self.nlp = spacy.load("en_core_web_sm")
        except OSError:
            self.nlp = None
            logger.warning("spaCy model not found — falling back to regex-only NER")

        self._use_llm = LLM_SETTINGS.get("use_llm_extraction", True)
        logger.info(
            f"ExtractionEngine initialized "
            f"[llm_extraction={'enabled' if self._use_llm else 'disabled'}]"
        )

    # ===================================================
    # MAIN PROCESS METHOD
    # ===================================================

    def process(self, scraped_content: list[dict]) -> dict:
        logger.info("Extraction phase started")
        self.state.update_state(SystemState.EXTRACTING)
        self.state.update_progress(75)

        # Aggregation buckets
        org_counter:    Counter = Counter()
        people_set:     set     = set()
        location_set:   set     = set()
        keyword_counter: Counter = Counter()
        swot_aggregate: dict    = {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []}

        structured_financials: dict[str, list] = {
            "startup_costs":    [],
            "revenue_figures":  [],
            "funding_amounts":  [],
            "market_sizes":     [],
            "growth_rates":     [],
        }

        # Dataset-level meta
        total_quality_score        = 0.0
        pages_with_financial       = 0
        pages_with_market          = 0
        pages_with_growth          = 0
        sources: list[dict]        = []

        for page in scraped_content:
            text = page.get("text", "")
            if not text:
                continue

            url   = page.get("url",   "")
            title = page.get("title", "")
            if url:
                sources.append({"url": url, "title": title or ""})
            total_quality_score += float(page.get("quality_score", 0.0))

            # --------------------------------------------------
            # EXTRACTION (LLM-first, regex fallback)
            # --------------------------------------------------
            page_data = self._extract_page(text, url, title)

            # Merge entities
            for org in page_data.get("organizations", []):
                if org and isinstance(org, str):
                    org_counter[self.normalize_org_name(org)] += 1
            people_set.update(
                p for p in page_data.get("people", []) if isinstance(p, str) and p
            )
            location_set.update(
                l for l in page_data.get("locations", []) if isinstance(l, str) and l
            )

            # Merge financials
            for key in structured_financials:
                vals = page_data.get(key, [])
                if isinstance(vals, list):
                    structured_financials[key].extend(
                        v for v in vals if isinstance(v, (int, float))
                    )

            # Merge SWOT
            page_swot = page_data.get("swot", {})
            if isinstance(page_swot, dict):
                for quadrant in swot_aggregate:
                    items = page_swot.get(quadrant, [])
                    if isinstance(items, list):
                        swot_aggregate[quadrant].extend(items)

            # Keywords
            for kw in page_data.get("keywords", []):
                if isinstance(kw, str) and kw.strip():
                    keyword_counter[kw.strip().lower()] += 1

            # Per-page signal flags
            if any(structured_financials[k] for k in
                   ["startup_costs", "revenue_figures", "funding_amounts"]):
                pages_with_financial += 1
            if structured_financials["market_sizes"]:
                pages_with_market += 1
            if structured_financials["growth_rates"]:
                pages_with_growth += 1

        # --------------------------------------------------
        # Post-processing
        # --------------------------------------------------
        top_organizations = [
            org for org, _ in org_counter.most_common(20)
        ]

        num_pages         = len(scraped_content)
        dynamic_threshold = self._get_keyword_threshold(num_pages)
        logger.info(
            f"Filtering keywords: threshold={dynamic_threshold} for {num_pages} pages"
        )
        top_keywords = [
            word for word, count in keyword_counter.most_common(30)
            if count > dynamic_threshold
        ][:EXTRACTION_SETTINGS.get("max_keywords_output", 20)]

        if len(top_keywords) < 5:
            logger.warning(f"Only {len(top_keywords)} keywords after filtering.")

        avg_quality = total_quality_score / num_pages if num_pages else 0.0

        # De-duplicate sources
        seen_urls: set = set()
        deduped_sources = []
        for src in sources:
            u = src.get("url")
            if not u or u in seen_urls:
                continue
            seen_urls.add(u)
            deduped_sources.append(src)

        # De-duplicate SWOT items
        for q in swot_aggregate:
            swot_aggregate[q] = list(dict.fromkeys(swot_aggregate[q]))[:6]

        structured_output = {
            "entities": {
                "organizations": top_organizations,
                "people":        list(people_set),
                "locations":     list(location_set),
            },
            "financial_metrics": {
                key: list(set(vals))
                for key, vals in structured_financials.items()
            },
            "keywords": top_keywords,
            "swot_signals": swot_aggregate,        # ← new: SWOT signals from LLM
            "meta": {
                "num_pages":                        num_pages,
                "avg_page_quality":                 round(avg_quality, 3),
                "pages_with_any_financial_signals": pages_with_financial,
                "pages_with_any_market_signals":    pages_with_market,
                "pages_with_any_growth_signals":    pages_with_growth,
                "extraction_method":                "llm" if self._use_llm else "regex",
            },
            "sources": deduped_sources,
        }

        logger.info("Extraction completed successfully")
        self.state.add_data("extracted_data", structured_output)
        return structured_output

    # ===================================================
    # PER-PAGE EXTRACTION  (LLM → fallback)
    # ===================================================

    def _extract_page(self, text: str, url: str, title: str) -> dict:
        """
        Try LLM extraction first; fall back to regex on any failure.
        Returns a normalised dict with all expected keys.
        """
        if self._use_llm:
            try:
                return self._extract_page_llm(text, url, title)
            except Exception as exc:
                logger.warning(
                    f"LLM extraction failed for {url!r}: {exc}. "
                    "Falling back to regex extraction."
                )

        return self._extract_page_regex(text)

    def _extract_page_llm(self, text: str, url: str, title: str) -> dict:
        """
        Send page text to the LLM and return a parsed extraction dict.
        Truncates text to 6 000 chars to stay within context limits.
        """
        from src.orchestration.llm_client import call_llm_json

        truncated = text[:2_000]   # 6_000 causes llama3 to exceed timeout on local hardware
        user_prompt = _EXTRACTION_USER_TEMPLATE.format(
            url=url, title=title, text=truncated
        )
        result = call_llm_json(_EXTRACTION_SYSTEM_PROMPT, user_prompt)

        if not isinstance(result, dict):
            raise ValueError(f"LLM returned non-dict: {type(result)}")

        # Ensure all expected keys exist with correct types
        defaults: dict[str, Any] = {
            "organizations": [], "people": [], "locations": [],
            "startup_costs": [], "revenue_figures": [], "funding_amounts": [],
            "market_sizes": [], "growth_rates": [], "keywords": [],
            "swot": {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        }
        for k, v in defaults.items():
            if k not in result:
                result[k] = v

        return result

    def _extract_page_regex(self, text: str) -> dict:
        """
        Legacy regex + spaCy extraction — used when LLM is disabled or fails.
        Returns the same schema as _extract_page_llm.
        """
        entities     = self.extract_entities(text)
        financials   = self.extract_contextual_financials(text)
        kw_counter   = self.extract_keywords(text)
        top_keywords = [w for w, _ in kw_counter.most_common(15)]

        return {
            "organizations": entities["organizations"],
            "people":        entities["people"],
            "locations":     entities["locations"],
            "startup_costs":   financials["startup_costs"],
            "revenue_figures": financials["revenue_figures"],
            "funding_amounts": financials["funding_amounts"],
            "market_sizes":    financials["market_sizes"],
            "growth_rates":    financials["growth_rates"],
            "keywords":        top_keywords,
            "swot":            {"strengths": [], "weaknesses": [], "opportunities": [], "threats": []},
        }

    # ===================================================
    # DYNAMIC KEYWORD THRESHOLD  (Issue #11)
    # ===================================================

    def _get_keyword_threshold(self, num_pages: int) -> int:
        s = EXTRACTION_SETTINGS
        if num_pages <= 10:
            return s.get("keyword_frequency_threshold_small", 1)
        elif num_pages <= 30:
            return s.get("keyword_frequency_threshold_medium", 2)
        else:
            return s.get("keyword_frequency_threshold_large", 3)

    # ===================================================
    # NORMALIZATION UTILITIES
    # ===================================================

    def normalize_currency(self, value_str: str) -> int | None:
        value_str = value_str.replace(",", "").lower()
        number_match = re.findall(r"[\d.]+", value_str)
        if not number_match:
            return None
        number = float(number_match[0])
        if "b" in value_str:
            number *= 1_000_000_000
        elif "m" in value_str:
            number *= 1_000_000
        elif "k" in value_str:
            number *= 1_000
        return int(number)

    def normalize_org_name(self, name: str) -> str:
        name = name.lower().strip()
        suffixes = ["inc", "inc.", "ltd", "ltd.", "corp", "corp.",
                    "llc", "plc", "company", "co", "co."]
        words = name.split()
        if words and words[-1] in suffixes:
            words = words[:-1]
        return " ".join(words)

    # ===================================================
    # LEGACY REGEX HELPERS  (used as fallback)
    # ===================================================

    def extract_entities(self, text: str) -> dict:
        organizations, people, locations = [], [], []

        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == "ORG":
                    organizations.append(ent.text)
                elif ent.label_ == "PERSON":
                    people.append(ent.text)
                elif ent.label_ in ["GPE", "LOC"]:
                    locations.append(ent.text)

        return {"organizations": organizations, "people": people, "locations": locations}

    def extract_contextual_financials(self, text: str) -> dict:
        money_pattern   = r"\$\s?\d+(?:[\.,]\d+)?\s?[kmbKMB]?"
        percent_pattern = r"\b\d+(?:\.\d+)?%"

        financial_data: dict[str, list] = {
            "startup_costs": [], "revenue_figures": [],
            "funding_amounts": [], "market_sizes": [], "growth_rates": []
        }

        for sentence in re.split(r"(?<=[.!?])\s+", text):
            sl  = sentence.lower()
            mon = [self.normalize_currency(m) for m in re.findall(money_pattern, sentence)]
            mon = [v for v in mon if v]
            pct = []
            for p in re.findall(percent_pattern, sentence):
                try:
                    pct.append(float(p.replace("%", "").strip()))
                except ValueError:
                    pass

            if any(k in sl for k in ["cost", "expense", "investment", "budget"]):
                financial_data["startup_costs"].extend(mon)
            if any(k in sl for k in ["revenue", "income", "earnings"]):
                financial_data["revenue_figures"].extend(mon)
            if any(k in sl for k in ["funding", "raised", "seed", "series"]):
                financial_data["funding_amounts"].extend(mon)
            if any(k in sl for k in ["market size", "valuation", "worth"]):
                financial_data["market_sizes"].extend(mon)
            if any(k in sl for k in ["growth", "cagr", "increase", "expansion"]):
                financial_data["growth_rates"].extend(pct)

        return financial_data

    def extract_keywords(self, text: str) -> Counter:
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        stopwords = set(self.nlp.Defaults.stop_words) if self.nlp else set()
        return Counter(w for w in words if w not in stopwords)