"""
rag_manager.py  —  Phase 2: ChromaDB RAG Layer

Architecture:
  1. Post-scrape, each page's cleaned text is chunked into ~500-token segments.
  2. Each chunk is embedded locally via sentence-transformers/all-MiniLM-L6-v2.
  3. Chunks are stored in a ChromaDB collection keyed by session_id.
  4. Analysis agents (financial, market, competitive) call RAGManager.query()
     with a natural-language prompt and receive the top-k most relevant chunks
     as plain text — a semantic drop-in for their existing keyword scans.
  5. If ChromaDB or sentence-transformers are unavailable, all methods degrade
     gracefully to empty results and log a warning — the pipeline never breaks.

Zero external cost:
  - sentence-transformers runs fully offline after the first model download.
  - ChromaDB persists to disk at ./chroma_db/{session_id}/ and is cleaned up
    at the end of each session via cleanup().

Usage (in an agent):
    from src.orchestration.rag_manager import RAGManager
    rag = RAGManager(session_id="abc123")
    snippets = rag.query("cotton textile market size CAGR", top_k=3)
    # snippets → ["chunk text 1", "chunk text 2", "chunk text 3"]

Usage (in workflow_controller):
    rag = RAGManager(session_id=session_id)
    rag.index(scraped_content)           # after scraping
    state_manager.add_data("rag", rag)   # pass to agents
    ...
    rag.cleanup()                        # after report generation
"""

from __future__ import annotations

import os
import re
import uuid
import shutil
from typing import Optional

from src.orchestration.logger import setup_logger
from src.config.settings import RAG_SETTINGS

logger = setup_logger()

# ---------------------------------------------------------------------------
# Lazy imports — avoid hard crash if deps aren't installed
# ---------------------------------------------------------------------------

def _import_chromadb():
    try:
        import chromadb
        return chromadb
    except ImportError:
        return None

def _import_sentence_transformers():
    try:
        from sentence_transformers import SentenceTransformer
        return SentenceTransformer
    except ImportError:
        return None


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Split text into overlapping word-level chunks.

    chunk_size  — approximate number of words per chunk (≈ 500 tokens for English)
    overlap     — number of words shared between consecutive chunks for context continuity
    """
    words = text.split()
    if not words:
        return []

    chunks: list[str] = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start += chunk_size - overlap   # slide forward with overlap

    return chunks


def _clean_text(text: str) -> str:
    """Minimal cleaning: collapse whitespace, strip nav/JS noise."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"(function\s*\(.*?\)\s*\{.*?\})", "", text, flags=re.DOTALL)
    return text.strip()


# ---------------------------------------------------------------------------
# RAGManager
# ---------------------------------------------------------------------------

class RAGManager:
    """
    Manages a ChromaDB collection for one pipeline session.

    Parameters
    ----------
    session_id  : str
        Unique identifier for this run. Used to namespace the ChromaDB
        collection and the on-disk persist directory.
    persist_dir : str
        Root directory for ChromaDB storage. A sub-folder named after
        session_id is created automatically.
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        persist_dir: str = RAG_SETTINGS.get("persist_dir", "./chroma_db"),
    ):
        self.session_id  = session_id or str(uuid.uuid4())[:8]
        self.persist_dir = os.path.join(persist_dir, self.session_id)
        self._ready      = False         # True once index() succeeds
        self._collection = None
        self._model      = None

        chromadb = _import_chromadb()
        SentenceTransformer = _import_sentence_transformers()

        if chromadb is None:
            logger.warning(
                "RAGManager: chromadb not installed — RAG disabled. "
                "Run: pip install chromadb"
            )
            return

        if SentenceTransformer is None:
            logger.warning(
                "RAGManager: sentence-transformers not installed — RAG disabled. "
                "Run: pip install sentence-transformers"
            )
            return

        try:
            model_name = RAG_SETTINGS.get("embedding_model", "all-MiniLM-L6-v2")
            logger.info(f"RAGManager: loading embedding model '{model_name}' …")
            self._model = SentenceTransformer(model_name)

            client = chromadb.PersistentClient(path=self.persist_dir)
            # Collection name must be unique per session; ChromaDB names
            # must be 3–63 chars, alphanumeric + hyphens.
            safe_name = f"ar-{self.session_id}"
            self._collection = client.get_or_create_collection(
                name=safe_name,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                f"RAGManager initialised [session={self.session_id}] "
                f"[persist={self.persist_dir}]"
            )
        except Exception as exc:
            logger.warning(f"RAGManager init failed (RAG disabled): {exc}")

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    def index(self, scraped_content: list[dict]) -> int:
        """
        Chunk and embed all scraped pages, then upsert into ChromaDB.

        Parameters
        ----------
        scraped_content : list[dict]
            Each dict must have at minimum a "text" key.
            Optional keys: "url", "title", "intent" (from IntentRouter).

        Returns
        -------
        int  — number of chunks indexed (0 if RAG is disabled).
        """
        if not self._is_ready_to_write():
            return 0

        chunk_size      = RAG_SETTINGS.get("chunk_size_words",       250)
        overlap         = RAG_SETTINGS.get("chunk_overlap_words",     25)
        quality_thresh  = RAG_SETTINGS.get("quality_score_threshold", 0.05)

        all_texts:    list[str]  = []
        all_ids:      list[str]  = []
        all_metadata: list[dict] = []

        skipped = 0
        for page_idx, page in enumerate(scraped_content):
            raw_text = page.get("text", "")
            if not raw_text:
                continue

            # ── Quality gate: skip low-value pages (nav/cookie pages etc.) ──
            page_quality = float(page.get("quality_score", 0.0))
            if page_quality < quality_thresh:
                skipped += 1
                logger.debug(
                    f"RAGManager: skipping page {page_idx} "
                    f"(quality={page_quality:.3f} < threshold={quality_thresh})"
                )
                continue

            clean = _clean_text(raw_text)
            chunks = _chunk_text(clean, chunk_size=chunk_size, overlap=overlap)

            url    = page.get("url",    "")
            title  = page.get("title",  "")
            intent = page.get("intent", "GENERAL")

            for chunk_idx, chunk in enumerate(chunks):
                if not chunk.strip():
                    continue
                chunk_id = f"{self.session_id}-p{page_idx}-c{chunk_idx}"
                all_ids.append(chunk_id)
                all_texts.append(chunk)
                all_metadata.append({
                    "url":        url,
                    "title":      title,
                    "intent":     intent,
                    "page_index": page_idx,
                })

        if not all_texts:
            logger.warning("RAGManager.index(): no text chunks to embed")
            return 0

        try:
            logger.info(
                f"RAGManager: embedding {len(all_texts)} chunks "
                f"from {len(scraped_content)} pages …"
            )
            embeddings = self._model.encode(
                all_texts,
                batch_size=RAG_SETTINGS.get("embed_batch_size", 32),
                show_progress_bar=False,
                convert_to_list=True,
            )

            # ChromaDB upsert in one batch
            self._collection.upsert(
                ids=all_ids,
                documents=all_texts,
                embeddings=embeddings,
                metadatas=all_metadata,
            )
            self._ready = True
            logger.info(
                f"RAGManager: indexed {len(all_texts)} chunks successfully"
            )
            return len(all_texts)

        except Exception as exc:
            logger.warning(f"RAGManager.index() failed (RAG disabled): {exc}")
            return 0

    def query(
        self,
        prompt: str,
        top_k: int = 3,
        intent_filter: Optional[str] = None,
    ) -> list[str]:
        """
        Semantic search: return the top-k most relevant text chunks.

        Parameters
        ----------
        prompt        : str   Natural-language query (e.g. "cotton market CAGR 2025")
        top_k         : int   Number of chunks to return
        intent_filter : str   Optional ChromaDB where-filter on the "intent" metadata
                              field (e.g. "MARKET_SIZE", "COMPETITOR").

        Returns
        -------
        list[str]  — chunk texts ordered by relevance (empty list if RAG disabled).
        """
        if not self._ready or self._collection is None or self._model is None:
            return []

        try:
            query_embedding = self._model.encode([prompt], convert_to_list=True)[0]

            kwargs: dict = dict(
                query_embeddings=[query_embedding],
                n_results=min(top_k, self._collection.count()),
                include=["documents", "distances"],
            )
            if intent_filter:
                kwargs["where"] = {"intent": intent_filter}

            results = self._collection.query(**kwargs)
            docs = results.get("documents", [[]])[0]
            return [d for d in docs if d]

        except Exception as exc:
            logger.warning(f"RAGManager.query() failed: {exc}")
            return []

    def is_ready(self) -> bool:
        """True if the index has been built and queries can be served."""
        return self._ready

    def cleanup(self):
        """
        Delete the on-disk ChromaDB directory for this session.
        Call this at the end of the pipeline to avoid unbounded disk growth.
        """
        if os.path.exists(self.persist_dir):
            try:
                shutil.rmtree(self.persist_dir)
                logger.info(
                    f"RAGManager: cleaned up session store at {self.persist_dir}"
                )
            except Exception as exc:
                logger.warning(f"RAGManager.cleanup() failed: {exc}")

    # -----------------------------------------------------------------------
    # Internal helpers
    # -----------------------------------------------------------------------

    def _is_ready_to_write(self) -> bool:
        if self._collection is None:
            logger.warning("RAGManager: collection not available — skipping index")
            return False
        if self._model is None:
            logger.warning("RAGManager: embedding model not loaded — skipping index")
            return False
        return True