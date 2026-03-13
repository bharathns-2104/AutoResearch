import os

# ======================================================
# LLM SETTINGS  (Phase 1 — Intelligence Layer)
# ======================================================
# Provider is selected via LLM_PROVIDER env var or the dict below.
# Supported providers (via LiteLLM): ollama, openai, anthropic, groq, …
#
# Local / zero-cost default:
#   Install Ollama → https://ollama.ai
#   Pull a model  → ollama pull llama3
#   Leave LLM_API_KEY empty for local inference.
#
# Cloud example (OpenAI):
#   LLM_PROVIDER = "openai"
#   LLM_MODEL    = "gpt-4o-mini"
#   LLM_API_KEY  = "<your key>"
LLM_SETTINGS = {
    # Full LiteLLM model string: "<provider>/<model-name>"
    "model":           os.getenv("LLM_MODEL",    "ollama/llama3"),
    # API base URL — required for Ollama; leave None for cloud providers
    "api_base":        os.getenv("LLM_API_BASE", "http://localhost:11434"),
    # API key — empty string is treated as "none" for local models
    "api_key":         os.getenv("LLM_API_KEY",  ""),
    # Per-call timeout in seconds
    "timeout_seconds": int(os.getenv("LLM_TIMEOUT",      "60")),
    # Retry attempts on transient failures
    "max_retries":     int(os.getenv("LLM_MAX_RETRIES",   "2")),
    # Whether the extraction engine should use LLM (True) or regex fallback (False)
    "use_llm_extraction": os.getenv("LLM_EXTRACTION", "true").lower() == "true",
    # Whether the self-correction loop is enabled
    "enable_self_correction": os.getenv("LLM_SELF_CORRECTION", "true").lower() == "true",
    # Maximum self-correction iterations before giving up
    "self_correction_max_iterations": int(os.getenv("LLM_SELF_CORRECTION_ITERS", "2")),
    # Minimum confidence score to skip self-correction (0.0 – 1.0)
    "self_correction_confidence_threshold": float(
        os.getenv("LLM_CONFIDENCE_THRESHOLD", "0.6")
    ),
    # Whether smart routing is enabled
    "enable_smart_routing": os.getenv("LLM_SMART_ROUTING", "true").lower() == "true",
}

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
COMPETITIVE_INTENSITY_THRESHOLDS = {
    "low_max": 5,        # < 5 competitors = Low intensity
    "medium_max": 15,    # 5-15 competitors = Medium intensity
    # > 15 = High intensity
}

# ======================================================
# EXTRACTION & KEYWORD FILTERING
# ======================================================
EXTRACTION_SETTINGS = {
    "keyword_frequency_threshold_small": 1,
    "keyword_frequency_threshold_medium": 2,
    "keyword_frequency_threshold_large": 3,
    "max_keywords_output": 20
}

# ======================================================
# SCRAPING SETTINGS
# ======================================================
SCRAPING_SETTINGS = {
    "min_pages_threshold": 3,
    "max_pages_threshold": 100,
    "success_rate_threshold": 0.30
}

# ======================================================
# MARKET SIZING SETTINGS
# ======================================================
MARKET_SETTINGS = {
    "sam_ratio": 0.30,
    "som_ratio": 0.03,
}

# ======================================================
# RAG SETTINGS  (Phase 2 — ChromaDB RAG Layer)
# ======================================================
# sentence-transformers model used for embedding.
# all-MiniLM-L6-v2 is fast (~80ms/page on CPU), 22M params, zero-cost.
# Alternatives: all-mpnet-base-v2 (slower, higher quality)
#
# ChromaDB persists to ./chroma_db/{session_id}/ and is deleted after
# each pipeline run.  Set RAG_ENABLED=false to skip the layer entirely.
RAG_SETTINGS = {
    # Toggle the entire RAG layer on/off
    "enabled":              os.getenv("RAG_ENABLED", "true").lower() == "true",
    # Local sentence-transformers model name (downloaded on first use)
    "embedding_model":      os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
    # Root directory for ChromaDB on-disk storage
    "persist_dir":          os.getenv("RAG_PERSIST_DIR", "./chroma_db"),
    # Words per chunk (~500 words ≈ 600-700 tokens, fits MiniLM context)
    "chunk_size_words":     int(os.getenv("RAG_CHUNK_SIZE",    "500")),
    # Overlap between consecutive chunks (for context continuity)
    "chunk_overlap_words":  int(os.getenv("RAG_CHUNK_OVERLAP", "50")),
    # Sentence-transformers batch size for encoding
    "embed_batch_size":     int(os.getenv("RAG_BATCH_SIZE",    "32")),
    # Default number of chunks returned per query
    "default_top_k":        int(os.getenv("RAG_TOP_K",         "3")),
}