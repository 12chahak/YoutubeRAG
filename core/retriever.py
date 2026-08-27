"""
core/retriever.py
─────────────────
Semantic similarity retriever with query-aware strategies.

- SUMMARY queries  → MMR retrieval, k=20, fetch_k=60
  (Maximum Marginal Relevance gives diverse chunks across the whole video)
- SPECIFIC queries → similarity retrieval, k=8
  (Standard similarity gives the most relevant focused chunks)
"""

from __future__ import annotations

import logging
import re

from langchain_core.documents import Document

from config.settings import get_settings
from core.vector_store import get_vector_store

logger = logging.getLogger(__name__)

# ── Summary query detection ───────────────────────────────────────────────────

_SUMMARY_PATTERNS = re.compile(
    r"\b("
    r"summar(y|ize|ise|ization)|overview|outline|brief|recap|synopsis|"
    r"what (is|was|does) (this|the) video (about|cover|discuss|explain)|"
    r"what (did|do) (they|he|she|the (speaker|presenter|host)) (talk|discuss|say|cover|teach|explain)|"
    r"(main|key|important|core|primary|central) (point|topic|idea|takeaway|lesson|message|theme|concept|thing)s?|"
    r"explain (the|this) video|tell me about (the|this) video|"
    r"what (happen|cover|discuss|talk|explain)s?|"
    r"(cover|discuss|talk about|explain)ed|"
    r"what did (you|they|the video|it) (cover|say|discuss|talk|explain|teach)"
    r")\b",
    re.IGNORECASE,
)


def is_summary_query(question: str) -> bool:
    """Return True if the question is asking for a summary or overview."""
    return bool(_SUMMARY_PATTERNS.search(question))


# ── Retrieval ─────────────────────────────────────────────────────────────────

def retrieve_chunks(
    question: str,
    video_id: str,
) -> list[Document]:
    """
    Retrieve relevant chunks using a query-aware strategy.

    - Summary / overview queries → MMR (diverse, broad coverage), k=20
    - Specific questions         → Similarity search, k=8

    All results are scoped to the given video_id via metadata filter.

    Parameters
    ----------
    question : str
        The user's question.
    video_id : str
        YouTube video ID to scope retrieval to.

    Returns
    -------
    list[Document]
        Retrieved chunks with metadata (timestamps, etc.).
    """
    settings = get_settings()
    vector_store = get_vector_store()

    summarizing = is_summary_query(question)

    if summarizing:
        # MMR: fetch many candidates, return the most diverse subset
        k = 20
        fetch_k = 80
        logger.info(
            "SUMMARY query detected — using MMR retrieval "
            "(k=%d, fetch_k=%d, video_id=%s)",
            k, fetch_k, video_id,
        )
        docs = vector_store.max_marginal_relevance_search(
            query=question,
            k=k,
            fetch_k=fetch_k,
            filter={"video_id": {"$eq": video_id}},
        )
    else:
        # Standard similarity: focused, precise retrieval
        k = max(settings.top_k, 8)
        logger.info(
            "SPECIFIC query — using similarity retrieval (k=%d, video_id=%s)",
            k, video_id,
        )
        docs = vector_store.similarity_search(
            query=question,
            k=k,
            filter={"video_id": {"$eq": video_id}},
        )

    # Sort by timestamp so context is chronological
    docs.sort(key=lambda d: float(d.metadata.get("start_seconds", 0)))

    logger.info("Retrieved %d chunks (summary_mode=%s).", len(docs), summarizing)
    return docs
