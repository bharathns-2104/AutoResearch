import matplotlib.pyplot as plt
from pathlib import Path


class ChartBuilder:

    def __init__(self, temp_dir="reports/temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    # ======================================================
    # DOMAIN SCORE BAR CHART
    # ======================================================

    def build_domain_score_chart(self, mapped_data):
        """
        Generates a bar chart comparing financial,
        market, and competitive scores.
        """

        try:
            scores = mapped_data["domain_scores"]

            labels = ["Financial", "Market", "Competitive"]
            values = [
                scores.get("financial_score", 0),
                scores.get("market_score", 0),
                scores.get("competitive_score", 0)
            ]

            file_path = self.temp_dir / "domain_scores.png"

            plt.figure()
            plt.bar(labels, values)
            plt.ylim(0, 1)
            plt.xlabel("Domain")
            plt.ylabel("Score (0–1)")
            plt.title("Domain Score Comparison")
            plt.tight_layout()
            plt.savefig(file_path)
            plt.close()

            return str(file_path)

        except Exception as e:
            print(f"Domain score chart generation failed: {e}")
            return None

    # ======================================================
    # OVERALL SCORE HORIZONTAL BAR
    # ======================================================

    def build_overall_score_chart(self, mapped_data):
        """
        Generates a horizontal bar chart for
        overall viability score.
        """

        try:
            overall = mapped_data["score_overview"].get("overall_score", 0)

            file_path = self.temp_dir / "overall_score.png"

            plt.figure()
            plt.barh(["Overall Score"], [overall])
            plt.xlim(0, 1)
            plt.xlabel("Score (0–1)")
            plt.title("Overall Viability Score")
            plt.tight_layout()
            plt.savefig(file_path)
            plt.close()

            return str(file_path)

        except Exception as e:
            print(f"Overall score chart generation failed: {e}")
            return None

    # ======================================================
    # CLEANUP METHOD (OPTIONAL)
    # ======================================================

    def clear_temp_charts(self):
        """
        Removes generated chart images.
        """

        try:
            for file in self.temp_dir.glob("*.png"):
                file.unlink()
        except Exception:
            pass
