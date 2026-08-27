"""
core/vector_store.py
─────────────────────
Pinecone Serverless vector store management.

Responsibilities:
  1. Create the Pinecone index (if it doesn't exist yet).
  2. Upsert chunked Documents into the index.
  3. Check whether a given video_id is already indexed (skip re-indexing).
  4. Return a LangChain PineconeVectorStore for retrieval.
"""

from __future__ import annotations

import logging
import time

from langchain_core.documents import Document

from config.settings import get_settings
from core.embeddings import get_embedding_model

logger = logging.getLogger(__name__)

# ── Pinecone index initialisation ─────────────────────────────────────────────

def _get_pinecone_index():
    """
    Connect to (or create) the Pinecone serverless index.
    Returns the Pinecone Index object.
    """
    from pinecone import Pinecone, ServerlessSpec  # type: ignore

    settings = get_settings()
    pc = Pinecone(api_key=settings.pinecone_api_key)

    existing = [idx.name for idx in pc.list_indexes()]

    if settings.pinecone_index_name not in existing:
        logger.info(
            "Creating Pinecone index '%s' (dim=%d, metric=cosine).",
            settings.pinecone_index_name,
            settings.embedding_dim,
        )
        pc.create_index(
            name=settings.pinecone_index_name,
            dimension=settings.embedding_dim,
            metric="cosine",
            spec=ServerlessSpec(
                cloud=settings.pinecone_cloud,
                region=settings.pinecone_region,
            ),
        )
        # Wait until the index is ready.
        _wait_for_index_ready(pc, settings.pinecone_index_name)
    else:
        logger.info("Pinecone index '%s' already exists.", settings.pinecone_index_name)

    return pc.Index(settings.pinecone_index_name)


def _wait_for_index_ready(pc, index_name: str, timeout: int = 60) -> None:
    """Poll until the Pinecone index status is 'Ready'."""
    start = time.time()
    while True:
        desc = pc.describe_index(index_name)
        if desc.status.get("ready", False):
            logger.info("Pinecone index '%s' is ready.", index_name)
            return
        if time.time() - start > timeout:
            raise TimeoutError(
                f"Pinecone index '{index_name}' did not become ready within {timeout}s."
            )
        time.sleep(2)


# ── Public API ────────────────────────────────────────────────────────────────

def is_video_indexed(video_id: str) -> bool:
    """
    Check whether a video's chunks already exist in Pinecone.

    Uses a metadata filter query (fetch 1 vector where video_id matches).
    Returns True if at least one vector is found.
    """
    try:
        index = _get_pinecone_index()
        settings = get_settings()
        embeddings = get_embedding_model()

        # Embed a dummy query to perform a filtered search.
        dummy_vector = embeddings.embed_query("check")
        result = index.query(
            vector=dummy_vector,
            top_k=1,
            filter={"video_id": {"$eq": video_id}},
            include_metadata=False,
        )
        return bool(result.get("matches"))
    except Exception as exc:
        logger.warning("Could not check index for video_id '%s': %s", video_id, exc)
        return False


def upsert_documents(documents: list[Document]) -> int:
    """
    Embed and upsert a list of chunked Documents into Pinecone.

    Parameters
    ----------
    documents : list[Document]
        Chunked, metadata-enriched Documents.

    Returns
    -------
    int
        Number of vectors upserted.
    """
    from langchain_pinecone import PineconeVectorStore  # type: ignore

    if not documents:
        logger.warning("upsert_documents called with empty document list.")
        return 0

    settings = get_settings()
    embeddings = get_embedding_model()
    index = _get_pinecone_index()

    logger.info("Upserting %d documents into Pinecone...", len(documents))

    vector_store = PineconeVectorStore(
        index=index,
        embedding=embeddings,
        text_key="page_content",
    )

    # Upsert in batches to avoid request-size limits.
    batch_size = 100
    total_upserted = 0

    for i in range(0, len(documents), batch_size):
        batch = documents[i : i + batch_size]
        vector_store.add_documents(batch)
        total_upserted += len(batch)
        logger.info(
            "Upserted batch %d/%d (%d docs)",
            i // batch_size + 1,
            (len(documents) + batch_size - 1) // batch_size,
            len(batch),
        )

    logger.info("Total vectors upserted: %d", total_upserted)
    return total_upserted


def get_vector_store():
    """
    Return a LangChain PineconeVectorStore for retrieval queries.

    Returns
    -------
    PineconeVectorStore
        Ready-to-query vector store instance.
    """
    from langchain_pinecone import PineconeVectorStore  # type: ignore

    embeddings = get_embedding_model()
    index = _get_pinecone_index()

    return PineconeVectorStore(
        index=index,
        embedding=embeddings,
        text_key="page_content",
    )
