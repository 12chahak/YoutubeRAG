"""
config/settings.py
──────────────────
Centralised, validated configuration for the YouTube RAG Chatbot.
All values are read from environment variables (or a .env file).
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application-wide settings loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────────────────────
    nvidia_api_key: str = Field(..., description="NVIDIA NIM API key")
    pinecone_api_key: str = Field(..., description="Pinecone API key")
    groq_api_key: str = Field(..., description="Groq API key")

    # ── Pinecone ──────────────────────────────────────────────────────────────
    pinecone_index_name: str = Field(default="youtuberag")
    pinecone_cloud: str = Field(default="aws")
    pinecone_region: str = Field(default="us-east-1")

    # ── Embedding Model (NVIDIA NIM) ──────────────────────────────────────────
    embedding_model: str = Field(default="nvidia/llama-nemotron-embed-1b-v2")
    embedding_dim: int = Field(default=2048)

    # ── LLM (Groq) ────────────────────────────────────────────────────────────
    llm_model: str = Field(default="llama-3.3-70b-versatile")
    llm_temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=1024, ge=64)

    # ── Chunking ──────────────────────────────────────────────────────────────
    chunk_size: int = Field(default=500, ge=100)
    chunk_overlap: int = Field(default=50, ge=0)

    # ── Retrieval ─────────────────────────────────────────────────────────────
    top_k: int = Field(default=5, ge=1, le=20)

    # ── Fallback message ──────────────────────────────────────────────────────
    fallback_message: str = Field(
        default="I couldn't find this information in the uploaded video."
    )

    @field_validator("chunk_overlap")
    @classmethod
    def overlap_less_than_chunk(cls, v: int, info) -> int:
        chunk_size = info.data.get("chunk_size", 500)
        if v >= chunk_size:
            raise ValueError("chunk_overlap must be less than chunk_size")
        return v


# Single global instance — created once when the module loads.
# No lru_cache so .env changes are always picked up on fresh runs.
_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the application settings, loading from .env if needed."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force a fresh reload from .env (used when config changes at runtime)."""
    global _settings
    _settings = Settings()
    return _settings
