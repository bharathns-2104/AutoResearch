class ReportValidator:

    REQUIRED_FIELDS = {
        "overall_viability_score": float,
        "overall_rating": str,
        "financial_score": float,
        "market_score": float,
        "competitive_score": float,
        "aggregated_risks": list,
        "final_recommendations": list,
        "executive_summary": str,
        "decision": str
    }

    def validate(self, data):

        if not isinstance(data, dict):
            raise ValueError("Consolidated output must be a dictionary.")

        for field, field_type in self.REQUIRED_FIELDS.items():
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

            if not isinstance(data[field], field_type):
                raise ValueError(
                    f"Field '{field}' must be of type {field_type.__name__}"
                )

        self._validate_scores(data)

    def _validate_scores(self, data):
        score_fields = [
            "overall_viability_score",
            "financial_score",
            "market_score",
            "competitive_score"
        ]

        for field in score_fields:
            score = data[field]
            if not (0 <= score <= 1):
                raise ValueError(
                    f"{field} must be between 0 and 1."
                )
