"""
core/embeddings.py
──────────────────
NVIDIA NIM embedding wrapper.

Returns a cached singleton NVIDIAEmbeddings instance using the
llama-nemotron-embed-1b-v2 model (2048-dimensional, MRL-enabled).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from config.settings import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model():
    """
    Return a cached NVIDIAEmbeddings instance.

    The model is initialised once and reused across the entire application
    to avoid redundant API calls and object creation overhead.

    Returns
    -------
    NVIDIAEmbeddings
        Configured NVIDIA embedding model ready for use with LangChain.
    """
    from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings  # type: ignore

    settings = get_settings()

    # Ensure the API key is available in the environment for the SDK.
    os.environ.setdefault("NVIDIA_API_KEY", settings.nvidia_api_key)

    logger.info(
        "Initialising NVIDIA embedding model: %s (dim=%d)",
        settings.embedding_model,
        settings.embedding_dim,
    )

    embeddings = NVIDIAEmbeddings(
        model=settings.embedding_model,
        api_key=settings.nvidia_api_key,
        truncate="END",          # Truncate inputs longer than max_seq_len
    )

    logger.info("NVIDIA embeddings ready.")
    return embeddings
