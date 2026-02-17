from ..orchestration.logger import setup_logger
from ..orchestration.state_manager import StateManager

logger = setup_logger()


class IntakeAgent:

    def __init__(self):
        self.state = StateManager()
        logger.info("IntakeAgent initialized")

    # -----------------------------
    # Industry Classification
    # -----------------------------
    def classify_industry(self, industry_text):
        industry_text = industry_text.lower()

        mapping = {
            "saas": "SaaS",
            "software": "SaaS",
            "fintech": "FinTech",
            "bank": "FinTech",
            "health": "HealthTech",
            "medical": "HealthTech",
            "education": "EdTech",
            "ecommerce": "E-Commerce",
            "retail": "E-Commerce",
        }

        for keyword, category in mapping.items():
            if keyword in industry_text:
                return category

        return "Other"

    # -----------------------------
    # Expand Analysis Type
    # -----------------------------
    def expand_analysis_domains(self, analysis_type):

        if analysis_type == "all":
            return ["financial", "market", "competitive"]

        return [analysis_type]

    # -----------------------------
    # Query Generator
    # -----------------------------
    def generate_search_queries(self, data):

        company = data["company_name"]
        industry = data["industry"]
        geo = data["geographic_focus"]
        years = data["time_horizon_years"]

        queries = []

        if "financial" in data["analysis_domains"]:
            queries.append(f"{company} financial performance last {years} years")
            queries.append(f"{company} revenue profit trends {geo}")

        if "competitive" in data["analysis_domains"]:
            queries.append(f"{company} competitors in {industry}")
            queries.append(f"{industry} top companies {geo}")

        if "market" in data["analysis_domains"]:
            queries.append(f"{industry} market size {geo}")
            queries.append(f"{industry} industry trends {years} year forecast")

        return queries

    # -----------------------------
    # Main Processor
    # -----------------------------
    def process(self, raw_input):

        logger.info("IntakeAgent processing started")

        structured = {}

        structured["company_name"] = raw_input["company_name"]
        structured["industry"] = raw_input["industry"]

        # Industry classification
        structured["industry_category"] = self.classify_industry(
            raw_input["industry"]
        )

        # Expand domains
        structured["analysis_domains"] = self.expand_analysis_domains(
            raw_input["analysis_type"]
        )

        structured["geographic_focus"] = raw_input["geographic_focus"]
        structured["time_horizon_years"] = raw_input["time_horizon_years"]

        # Generate search queries
        structured["search_queries"] = self.generate_search_queries(structured)

        # Save to state
        self.state.add_data("structured_input", structured)

        logger.info("IntakeAgent processing completed")

        return structured
