import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup

from src.orchestration.cache_manager import CacheManager
from src.orchestration.logger import setup_logger
from src.orchestration.state_manager import StateManager, SystemState

logger = setup_logger()


class WebScraper:
    def __init__(
        self,
        max_parallel=5,
        timeout=10,
        retries=3,
        delay=2,
        user_agent="AutoResearchBot/1.0"
    ):
        self.state = StateManager()
        self.cache_manager = CacheManager()  # Cache for scraping (Issue #8)
        self.max_parallel = max_parallel
        self.timeout = timeout
        self.retries = retries
        self.delay = delay
        self.headers = {"User-Agent": user_agent}

        logger.info("WebScraper initialized with cache support")


    # ---------------------------------------------------
    # Fetch URL with retry logic
    # ---------------------------------------------------
    def fetch_url(self, url):
        for attempt in range(self.retries):
            try:
                response = requests.get(
                    url,
                    headers=self.headers,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return response.text

            except Exception as e:
                logger.warning(f"Attempt {attempt+1} failed for {url}")

            time.sleep(self.delay)

        logger.error(f"Failed to fetch {url}")
        self.state.add_error(f"Scraping failed for {url}")
        return None

    # ---------------------------------------------------
    # Clean HTML content
    # ---------------------------------------------------
    def clean_html(self, soup):
        # Remove scripts/styles
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        return soup
    # ---------------------------------------------------
    # Internal helper: basic page quality scoring
    # ---------------------------------------------------
    def _score_page_quality(self, text: str) -> dict:
        """
        Compute simple quality metrics for a scraped page.

        These metrics are intentionally lightweight and are later
        used by ExtractionEngine to derive dataset-level meta
        (e.g. data confidence).
        """
        if not text:
            return {
                "word_count": 0,
                "num_money_tokens": 0,
                "num_percent_tokens": 0,
                "num_business_keywords": 0,
                "quality_score": 0.0,
            }

        word_count = len(text.split())

        money_pattern = r"\$\s?\d+(?:[\.,]\d+)?\s?[kmbKMB]?"
        percent_pattern = r"\b\d+(?:\.\d+)?%"

        num_money = len(re.findall(money_pattern, text))
        num_percent = len(re.findall(percent_pattern, text))

        business_terms = [
            "funding",
            "seed round",
            "series a",
            "series b",
            "market size",
            "tam",
            "sam",
            "som",
            "revenue",
            "valuation",
            "cagr",
            "growth rate",
            "burn rate",
        ]
        lower_text = text.lower()
        num_business_keywords = sum(1 for term in business_terms if term in lower_text)

        # Heuristic quality score: more words + financial/market signals
        score = 0.0
        if word_count > 0:
            score += min(word_count / 2000.0, 0.4)  # cap contribution from length
        score += min(num_money * 0.05, 0.3)
        score += min(num_percent * 0.03, 0.15)
        score += min(num_business_keywords * 0.05, 0.15)

        return {
            "word_count": word_count,
            "num_money_tokens": num_money,
            "num_percent_tokens": num_percent,
            "num_business_keywords": num_business_keywords,
            "quality_score": round(score, 3),
        }

    # ---------------------------------------------------
    # Parse structured content
    # ---------------------------------------------------
    def parse_content(self, html, url):
        soup = BeautifulSoup(html, "html.parser")

        soup = self.clean_html(soup)

        title = soup.title.string.strip() if soup.title else ""

        # Extract main text
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")]
        text = "\n".join(paragraphs)

        # Quality metrics
        quality_meta = self._score_page_quality(text)

        # Extract headings
        headings = []
        for level in range(1, 7):
            for tag in soup.find_all(f"h{level}"):
                headings.append({
                    "level": level,
                    "text": tag.get_text(strip=True)
                })

        # Extract tables
        tables = []
        for table in soup.find_all("table"):
            rows = []
            for tr in table.find_all("tr"):
                cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"])]
                if cells:
                    rows.append(cells)
            if rows:
                tables.append(rows)

        result = {
            "url": url,
            "title": title,
            "text": text[:100000],  # limit huge pages
            "headings": headings,
            "tables": tables
        }
        result.update(quality_meta)
        return result

    # ---------------------------------------------------
    # Scrape single URL (with caching)
    # ---------------------------------------------------
    def scrape_single(self, url):
        # Check cache first (Issue #8).
        # Note: CacheManager applies an internal MD5 hash to this key;
        # the "scrape:" prefix is part of the logical namespace and
        # intentionally included in the hashed key.
        cached_result = self.cache_manager.get(f"scrape:{url}")
        if cached_result:
            logger.info(f"Cache hit for {url}")
            return cached_result

        # Fetch if not cached
        html = self.fetch_url(url)
        if html:
            result = self.parse_content(html, url)
            # Store in cache for future runs
            self.cache_manager.set(f"scrape:{url}", result)
            return result
        return None

    # ---------------------------------------------------
    # Parallel scraping entry point
    # ---------------------------------------------------
    def scrape(self, search_results):
        logger.info("Scraping phase started")

        self.state.update_state(SystemState.SCRAPING)
        self.state.update_progress(50)

        # Deduplicate URLs while preserving order
        url_seen = set()
        urls = []
        for item in search_results:
            url = item.get("url")
            if not url or url in url_seen:
                continue
            url_seen.add(url)
            urls.append(url)

        scraped_data = []

        with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
            futures = {executor.submit(self.scrape_single, url): url for url in urls}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    scraped_data.append(result)

        # Sort pages by quality score so downstream components see the richest pages first
        scraped_data.sort(key=lambda x: x.get("quality_score", 0.0), reverse=True)

        logger.info(f"Successfully scraped {len(scraped_data)} pages")

        self.state.add_data("scraped_content", scraped_data)

        return scraped_data
