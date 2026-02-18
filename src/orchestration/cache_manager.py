import json
import hashlib
import time
from pathlib import Path

from .logger import setup_logger

logger = setup_logger()


class CacheManager:
    def __init__(self, cache_dir="data/cache/pages", expiry_hours=24):
        self.cache_dir = Path(cache_dir)
        self.expiry_seconds = expiry_hours * 3600
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("CacheManager initialized")

    # =====================================================
    # URL PAGE CACHE
    # =====================================================

    def _get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def _is_expired(self, timestamp):
        return (time.time() - timestamp) > self.expiry_seconds

    def get(self, url):
        path = self._get_cache_path(url)

        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            if self._is_expired(cached["timestamp"]):
                logger.info(f"Cache expired for {url}")
                return None

            logger.info(f"Cache hit for {url}")
            return cached["content"]

        except Exception as e:
            logger.warning(f"Cache read failed for {url}: {str(e)}")
            return None

    def set(self, url, content):
        path = self._get_cache_path(url)

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "content": content
                }, f)

            logger.info(f"Cached content for {url}")

        except Exception as e:
            logger.warning(f"Cache write failed for {url}: {str(e)}")

    # =====================================================
    # EXTRACTION CACHE
    # =====================================================

    def _get_extraction_cache_path(self):
        return self.cache_dir / "extracted_data.json"

    def get_extraction_cache(self):
        path = self._get_extraction_cache_path()

        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            if self._is_expired(cached["timestamp"]):
                logger.info("Extraction cache expired")
                return None

            logger.info("Extraction cache hit")
            return cached["content"]

        except Exception as e:
            logger.warning(f"Extraction cache read failed: {str(e)}")
            return None

    def set_extraction_cache(self, content):
        path = self._get_extraction_cache_path()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "content": content
                }, f)

            logger.info("Extraction results cached")

        except Exception as e:
            logger.warning(f"Failed to cache extraction results: {str(e)}")

    # =====================================================
    # CONSOLIDATION CACHE
    # =====================================================

    def _get_consolidation_cache_path(self):
        return self.cache_dir / "consolidated_output.json"

    def get_consolidation_cache(self):
        path = self._get_consolidation_cache_path()

        if not path.exists():
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                cached = json.load(f)

            if self._is_expired(cached["timestamp"]):
                logger.info("Consolidation cache expired")
                return None

            logger.info("Consolidation cache hit")
            return cached["content"]

        except Exception as e:
            logger.warning(f"Consolidation cache read failed: {str(e)}")
            return None

    def set_consolidation_cache(self, content):
        path = self._get_consolidation_cache_path()

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": time.time(),
                    "content": content
                }, f)

            logger.info("Consolidated output cached")

        except Exception as e:
            logger.warning(f"Failed to cache consolidation output: {str(e)}")
