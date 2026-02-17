from ddgs import DDGS
from ..orchestration.logger import setup_logger
from ..orchestration.state_manager import StateManager, SystemState

logger = setup_logger()


class SearchEngine:
    def __init__(self, max_results_per_query=5):
        self.state = StateManager()
        self.max_results = max_results_per_query
        logger.info("SearchEngine initialized")

    # ---------------------------------------------------
    # Execute single search query
    # ---------------------------------------------------
    def search_query(self, query):
        logger.info(f"Executing search query: {query}")
        results = []

        try:
            with DDGS() as ddgs:
                search_results = ddgs.text(
                    query,
                    region="wt-wt",
                    safesearch="moderate",
                    max_results=self.max_results
                )

                for result in search_results:
                    results.append({
                        "query": query,
                        "title": result.get("title"),
                        "url": result.get("href"),
                        "snippet": result.get("body"),
                    })

            logger.info(f"Search returned {len(results)} results for query")
            return results

        except Exception as e:
            logger.error(f"Search failed for query '{query}': {str(e)}")
            self.state.add_error(f"Search error: {str(e)}")
            return []

    # ---------------------------------------------------
    # Simple ranking logic (keyword overlap scoring)
    # ---------------------------------------------------
    def rank_results(self, results, query):
        logger.info("Ranking search results")

        query_terms = set(query.lower().split())

        for item in results:
            text = (item["title"] or "") + " " + (item["snippet"] or "")
            text_terms = set(text.lower().split())

            overlap = query_terms.intersection(text_terms)
            score = len(overlap) / (len(query_terms) + 1)

            item["score"] = round(score, 3)

        ranked = sorted(results, key=lambda x: x["score"], reverse=True)

        return ranked

    # ---------------------------------------------------
    # Main search function (used by workflow)
    # ---------------------------------------------------
    def search(self, structured_input):
        logger.info("SearchEngine processing started")

        self.state.update_state(SystemState.SEARCHING)
        self.state.update_progress(30)

        all_results = []

        queries = structured_input.get("search_queries", [])

        for query in queries:
            raw_results = self.search_query(query)
            ranked = self.rank_results(raw_results, query)
            all_results.extend(ranked)

        logger.info(f"Total URLs collected: {len(all_results)}")

        # Store in state
        self.state.add_data("search_results", all_results)

        return all_results
