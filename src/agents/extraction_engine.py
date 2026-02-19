import re
import spacy
from collections import Counter
from src.orchestration.logger import setup_logger
from src.orchestration.state_manager import StateManager, SystemState
from src.config.settings import EXTRACTION_SETTINGS

logger = setup_logger()


class ExtractionEngine:
    def __init__(self):
        self.state = StateManager()
        self.nlp = spacy.load("en_core_web_sm")
        logger.info("ExtractionEngine initialized")

    # ===================================================
    # NORMALIZATION UTILITIES
    # ===================================================

    def normalize_currency(self, value_str):
        """
        Convert $2.5M, $50k, $1B into integer values.
        """
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

    def normalize_org_name(self, name):
        """
        Normalize organization names:
        Apple Inc. → apple
        Stripe LLC → stripe
        """
        name = name.lower().strip()

        suffixes = [
            "inc", "inc.", "ltd", "ltd.", "corp", "corp.",
            "llc", "plc", "company", "co", "co."
        ]

        words = name.split()
        if words and words[-1] in suffixes:
            words = words[:-1]

        return " ".join(words)

    # ===================================================
    # ENTITY EXTRACTION (spaCy)
    # ===================================================

    def extract_entities(self, text):
        doc = self.nlp(text)

        organizations = []
        people = []
        locations = []

        for ent in doc.ents:
            if ent.label_ == "ORG":
                organizations.append(ent.text)
            elif ent.label_ == "PERSON":
                people.append(ent.text)
            elif ent.label_ in ["GPE", "LOC"]:
                locations.append(ent.text)

        return {
            "organizations": organizations,
            "people": people,
            "locations": locations
        }

    # ===================================================
    # CONTEXTUAL FINANCIAL EXTRACTION
    # ===================================================

    def extract_contextual_financials(self, text):
        money_pattern = r"\$\s?\d+(?:[\.,]\d+)?\s?[kmbKMB]?"
        percent_pattern = r"\b\d+(?:\.\d+)?%"


        financial_data = {
            "startup_costs": [],
            "revenue_figures": [],
            "funding_amounts": [],
            "market_sizes": [],
            "growth_rates": []
        }

        sentences = re.split(r"(?<=[.!?])\s+", text)

        for sentence in sentences:
            sentence_lower = sentence.lower()

            money_matches = re.findall(money_pattern, sentence)
            percent_matches = re.findall(percent_pattern, sentence)

            normalized_money = []
            for match in money_matches:
                try:
                    value = self.normalize_currency(match)
                    if value:
                        normalized_money.append(value)
                except:
                    continue

            normalized_percent = []
            for p in percent_matches:
                try:
                    normalized_percent.append(float(p.replace("%", "").strip()))
                except:
                    continue

            # Categorization
            if any(k in sentence_lower for k in ["cost", "expense", "investment", "budget"]):
                financial_data["startup_costs"].extend(normalized_money)

            if any(k in sentence_lower for k in ["revenue", "income", "earnings"]):
                financial_data["revenue_figures"].extend(normalized_money)

            if any(k in sentence_lower for k in ["funding", "raised", "seed", "series"]):
                financial_data["funding_amounts"].extend(normalized_money)

            if any(k in sentence_lower for k in ["market size", "valuation", "worth"]):
                financial_data["market_sizes"].extend(normalized_money)

            if any(k in sentence_lower for k in ["growth", "cagr", "increase", "expansion"]):
                financial_data["growth_rates"].extend(normalized_percent)

        return financial_data

    # ===================================================
    # KEYWORD EXTRACTION
    # ===================================================

    def extract_keywords(self, text):
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text.lower())
        stopwords = set(self.nlp.Defaults.stop_words)

        filtered = [w for w in words if w not in stopwords]
        return Counter(filtered)

    # ===================================================
    # DYNAMIC KEYWORD FILTERING (Issue #11)
    # ===================================================
    def _get_keyword_threshold(self, num_pages):
        """
        Dynamically adjust keyword frequency threshold based on dataset size.
        
        Rationale: Small scrape sets (3-10 pages) will have low keyword frequencies.
        Filtering with count > 2 for a 5-page dataset loses important signals.
        
        Thresholds from EXTRACTION_SETTINGS:
        - 3-10 pages: threshold = 1 (small dataset)
        - 10-30 pages: threshold = 2 (medium dataset)
        - 30+ pages: threshold = 3 (large dataset)
        """
        threshold_small = EXTRACTION_SETTINGS.get("keyword_frequency_threshold_small", 1)
        threshold_medium = EXTRACTION_SETTINGS.get("keyword_frequency_threshold_medium", 2)
        threshold_large = EXTRACTION_SETTINGS.get("keyword_frequency_threshold_large", 3)
        
        if num_pages <= 10:
            return threshold_small
        elif num_pages <= 30:
            return threshold_medium
        else:
            return threshold_large

    # ===================================================
    # MAIN PROCESS METHOD
    # ===================================================

    def process(self, scraped_content):
        logger.info("Extraction phase started")
        self.state.update_state(SystemState.EXTRACTING)
        self.state.update_progress(75)

        organization_counter = Counter()
        people_set = set()
        location_set = set()
        keyword_counter = Counter()

        structured_financials = {
            "startup_costs": [],
            "revenue_figures": [],
            "funding_amounts": [],
            "market_sizes": [],
            "growth_rates": []
        }

        for page in scraped_content:
            text = page.get("text", "")
            if not text:
                continue

            # ---------------------------
            # ENTITY EXTRACTION
            # ---------------------------
            entities = self.extract_entities(text)

            for org in entities["organizations"]:
                normalized = self.normalize_org_name(org)
                if normalized:
                    organization_counter[normalized] += 1

            people_set.update(entities["people"])
            location_set.update(entities["locations"])

            # ---------------------------
            # FINANCIAL EXTRACTION
            # ---------------------------
            financials = self.extract_contextual_financials(text)

            for key in structured_financials:
                structured_financials[key].extend(financials[key])

            # ---------------------------
            # KEYWORDS
            # ---------------------------
            keyword_counter.update(self.extract_keywords(text))

        # Rank top organizations
        top_organizations = [
            org for org, count in organization_counter.most_common(20)
        ]

        # DYNAMIC KEYWORD FILTERING (Issue #11)
        # Adjust threshold based on number of pages (small sets need lower threshold)
        num_pages = len(scraped_content)
        dynamic_threshold = self._get_keyword_threshold(num_pages)
        
        logger.info(
            f"Filtering keywords with dynamic threshold={dynamic_threshold} "
            f"for {num_pages} pages (small:<10, medium:10-30, large:>30)"
        )
        
        top_keywords = [
            word for word, count in keyword_counter.most_common(30)
            if count > dynamic_threshold
        ][:EXTRACTION_SETTINGS.get("max_keywords_output", 20)]
        
        if len(top_keywords) < 5:
            logger.warning(
                f"Only {len(top_keywords)} keywords found after filtering. "
                f"Consider lowering threshold for small datasets."
            )

        structured_output = {
            "entities": {
                "organizations": top_organizations,
                "people": list(people_set),
                "locations": list(location_set)
            },
            "financial_metrics": {
                key: list(set(values))
                for key, values in structured_financials.items()
            },
            "keywords": top_keywords
        }

        logger.info("Extraction completed successfully")

        self.state.add_data("extracted_data", structured_output)

        return structured_output
