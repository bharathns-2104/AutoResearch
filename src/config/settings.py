# ======================================================
# REPORT GENERATION SETTINGS
# ======================================================
REPORT_SETTINGS = {
    "default_format": "pdf",
    "generate_ppt": True,
    "output_directory": "reports",
    "include_charts": True,
    "project_title": "AutoResearch - Batch 9",
    "section_order": [
        "title_page",
        "executive_summary",
        "score_overview",
        "domain_scores",
        "risk_analysis",
        "recommendations",
        "decision"
    ]
}

# ======================================================
# COMPETITIVE ANALYSIS THRESHOLDS
# ======================================================
# These thresholds control competitive intensity classification
# based on number of competitors found during analysis.
# Rationale: More competitors = more saturated market
COMPETITIVE_INTENSITY_THRESHOLDS = {
    "low_max": 5,        # < 5 competitors = Low intensity
    "medium_max": 15,    # 5-15 competitors = Medium intensity
    # > 15 = High intensity
    # Industry basis: Typical niche markets (5 or fewer), moderate
    # competition (5-15), and saturated markets (15+)
}

# ======================================================
# EXTRACTION & KEYWORD FILTERING
# ======================================================
EXTRACTION_SETTINGS = {
    # Minimum keyword frequency threshold. Dynamically adjusted
    # based on number of pages scraped (issue #11):
    # - Small scrape sets (3-10 pages): threshold = 1
    # - Medium (10-30 pages): threshold = 2
    # - Large (30+ pages): threshold = 3
    # This prevents discarding important keywords from small datasets.
    "keyword_frequency_threshold_small": 1,      # for 3-10 pages
    "keyword_frequency_threshold_medium": 2,     # for 10-30 pages
    "keyword_frequency_threshold_large": 3,      # for 30+ pages
    "max_keywords_output": 20                    # Top N keywords to keep
}

# ======================================================
# SCRAPING SETTINGS
# ======================================================
SCRAPING_SETTINGS = {
    # Minimum pages to scrape successfully before proceeding (issue #12)
    # If fewer than this exist, log warning but allow partial report
    "min_pages_threshold": 3,
    # Max pages to attempt (practical limit)
    "max_pages_threshold": 100,
    # Graceful degradation: If scraping succeeds for at least this
    # percentage of URLs, continue with partial data instead of failing
    "success_rate_threshold": 0.30  # 30% of URLs must succeed
}

