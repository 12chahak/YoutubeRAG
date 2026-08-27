"""
core/chunker.py
───────────────
Text chunking pipeline for YouTube transcripts.

Merges many small YouTube transcript segments into larger semantic chunks 
(e.g., 500 characters) while preserving the earliest timestamp in the chunk.
"""

from __future__ import annotations

import logging

from langchain_core.documents import Document

from config.settings import get_settings

logger = logging.getLogger(__name__)


def chunk_documents(documents: list[Document]) -> list[Document]:
    """
    Merge small transcript segments into larger chunks of ~chunk_size.

    Because YouTube segments are very short (often 10-50 chars), standard 
    splitters don't work (they only split, they don't merge). This custom 
    chunker aggregates segments up to chunk_size and preserves the metadata 
    (like timestamp) of the FIRST segment in the chunk.

    Parameters
    ----------
    documents : list[Document]
        Raw transcript Documents (output of YouTubeTranscriptLoader).

    Returns
    -------
    list[Document]
        Merged Documents with full metadata including timestamps.
    """
    settings = get_settings()
    chunk_size = settings.chunk_size
    chunk_overlap = settings.chunk_overlap

    if not documents:
        logger.warning("chunk_documents received an empty document list.")
        return []

    chunks = []
    current_text = ""
    current_metadata = None

    for doc in documents:
        text = doc.page_content.strip()
        if not text:
            continue

        # Start a new chunk if we don't have one
        if current_metadata is None:
            current_metadata = doc.metadata.copy()

        # If adding this segment exceeds chunk size (and we already have some text),
        # yield the current chunk and start a new one
        if current_text and (len(current_text) + len(text) > chunk_size):
            chunks.append(Document(page_content=current_text, metadata=current_metadata))
            
            # Start new chunk with overlap (if overlap is configured)
            # We approximate overlap by taking the last N characters of the previous chunk,
            # but snapping to the nearest word boundary.
            if chunk_overlap > 0 and len(current_text) > chunk_overlap:
                overlap_text = current_text[-chunk_overlap:]
                # Snap to next space so we don't cut words
                if " " in overlap_text:
                    overlap_text = overlap_text.split(" ", 1)[-1]
                current_text = overlap_text + " " + text
            else:
                current_text = text
            
            current_metadata = doc.metadata.copy()
        else:
            if current_text:
                current_text += " " + text
            else:
                current_text = text

    # Yield the last chunk if anything remains
    if current_text:
        chunks.append(Document(page_content=current_text, metadata=current_metadata))

    logger.info(
        "Merged %d transcript segments → %d chunks (chunk_size=%d)",
        len(documents),
        len(chunks),
        chunk_size,
    )

    # Enrich each chunk with a chunk_index for traceability
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_index"] = i

    return chunks


def get_total_char_count(documents: list[Document]) -> int:
    """Return the total character count across all documents."""
    return sum(len(doc.page_content) for doc in documents)
