import os
import matplotlib.pyplot as plt
from datetime import datetime


OUTPUT_DIR = "data/outputs/charts"


def _ensure_dir():
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def _generate_filename(prefix):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return os.path.join(OUTPUT_DIR, f"{prefix}_{timestamp}.png")


# ==========================================================
# 1. COST BREAKDOWN PIE CHART
# ==========================================================
def create_cost_pie(cost_data: dict):
    """
    cost_data example:
    {
        "development": 50000,
        "marketing": 30000,
        "operations": 20000
    }
    """
    if not cost_data:
        return None

    _ensure_dir()
    file_path = _generate_filename("cost_breakdown")

    labels = list(cost_data.keys())
    values = list(cost_data.values())

    plt.figure()
    plt.pie(values, labels=labels, autopct="%1.1f%%")
    plt.title("Startup Cost Breakdown")
    plt.tight_layout()
    plt.savefig(file_path)
    plt.close()

    return file_path


# ==========================================================
# 2. RUNWAY BAR CHART
# ==========================================================
def create_runway_chart(runway_months: int):
    if not runway_months:
        return None

    _ensure_dir()
    file_path = _generate_filename("runway")

    plt.figure()
    plt.bar(["Runway (Months)"], [runway_months])
    plt.title("Financial Runway")
    plt.ylabel("Months")
    plt.tight_layout()
    plt.savefig(file_path)
    plt.close()

    return file_path


# ==========================================================
# 3. MARKET SIZE BAR CHART
# ==========================================================
def create_market_size_chart(market_size: dict):
    """
    market_size example:
    {
        "global": 45000000000,
        "target_region": 15000000000
    }
    """
    if not market_size:
        return None

    _ensure_dir()
    file_path = _generate_filename("market_size")

    labels = ["Global Market", "Target Region"]
    values = [
        market_size.get("global", 0),
        market_size.get("target_region", 0)
    ]

    plt.figure()
    plt.bar(labels, values)
    plt.title("Market Size Comparison")
    plt.ylabel("USD")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(file_path)
    plt.close()

    return file_path


# ==========================================================
# 4. VIABILITY SCORE BAR
# ==========================================================
def create_score_chart(score: float):
    """
    score: 0 - 1 range
    """
    if score is None:
        return None

    _ensure_dir()
    file_path = _generate_filename("viability_score")

    plt.figure()
    plt.bar(["Viability Score"], [score])
    plt.ylim(0, 1)
    plt.title("Overall Viability Score")
    plt.tight_layout()
    plt.savefig(file_path)
    plt.close()

    return file_path