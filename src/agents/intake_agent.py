from ..orchestration.logger import setup_logger
from ..orchestration.state_manager import StateManager

logger = setup_logger()


class IntakeAgent:

    def __init__(self):
        self.state = StateManager()
        logger.info("IntakeAgent initialized")

    # ----------------------------------
    # Simple Industry Classifier
    # ----------------------------------
    def classify_industry(self, idea_text, industry_field):

        if industry_field != "Unknown":
            return industry_field

        text = idea_text.lower()

        mapping = {
            "ai": "SaaS",
            "software": "SaaS",
            "ecommerce": "E-Commerce",
            "health": "HealthTech",
            "finance": "FinTech",
            "education": "EdTech",
            "marketplace": "Platform",
        }

        for keyword, category in mapping.items():
            if keyword in text:
                return category

        return "Other"

    # ----------------------------------
    # Generate Business-Idea Queries
    # ----------------------------------
    def generate_search_queries(self, data):

        idea = data["business_idea"]
        industry = data["industry"]
        market = data["target_market"]

        queries = [
            f"{idea} startup cost 2026",
            f"{idea} competitors {industry}",
            f"{industry} market size 2026",
            f"{industry} industry trends 2026",
            f"{idea} funding rounds",
        ]

        return queries

    # ----------------------------------
    # Main Processor
    # ----------------------------------
    def process(self, raw_input):

        logger.info("IntakeAgent processing started")

        structured = {}

        structured["business_idea"] = raw_input["business_idea"]

        structured["industry"] = self.classify_industry(
            raw_input["business_idea"],
            raw_input["industry"]
        )

        structured["budget"] = raw_input["budget"]
        structured["timeline_months"] = raw_input["timeline_months"]
        structured["target_market"] = raw_input["target_market"]
        structured["team_size"] = raw_input["team_size"]

        structured["search_queries"] = self.generate_search_queries(structured)

        self.state.add_data("structured_input", structured)

        logger.info("IntakeAgent processing completed")

        return structured
