"""
server.py
─────────
FastAPI backend for the YouTube RAG Chrome Extension.

Exposes the existing RAG pipeline over REST so the Chrome
extension can call it from the browser.

Run with:
    uvicorn server:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sys
import traceback

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="YouTube RAG API",
    description="REST API for the YouTube RAG Chatbot Chrome Extension",
    version="1.0.0",
)

# Allow requests from Chrome extensions and localhost dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Chrome extensions use chrome-extension:// origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request / Response Models ─────────────────────────────────────────────────

class IndexRequest(BaseModel):
    """Request body for indexing a video."""
    video_url: str = Field(..., description="YouTube URL or video ID")


class IndexResponse(BaseModel):
    """Response after indexing a video."""
    success: bool
    video_id: str
    video_title: str = "Unknown Title"
    video_author: str = "Unknown Author"
    chunks_indexed: int = 0
    already_indexed: bool = False
    message: str = ""


class ChatRequest(BaseModel):
    """Request body for a chat query."""
    video_id: str = Field(..., description="YouTube video ID")
    question: str = Field(..., description="User's question")
    chat_history: list[dict[str, str]] = Field(default_factory=list, description="Previous chat messages")


class SourceDoc(BaseModel):
    """A single source citation."""
    timestamp: str = ""
    start_seconds: float = 0.0
    text_snippet: str = ""
    jump_link: str = ""


class ChatResponse(BaseModel):
    """Response from a chat query."""
    answer: str
    sources: list[SourceDoc] = []
    is_summary: bool = False


class StatusResponse(BaseModel):
    """Response for video index status check."""
    video_id: str
    is_indexed: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "youtube-rag-api"}


@app.get("/api/status/{video_id}", response_model=StatusResponse)
async def check_status(video_id: str):
    """Check whether a video is already indexed in Pinecone."""
    try:
        from core.vector_store import is_video_indexed

        indexed = is_video_indexed(video_id)
        return StatusResponse(video_id=video_id, is_indexed=indexed)

    except Exception as exc:
        logger.exception("Error checking index status for %s", video_id)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/index", response_model=IndexResponse)
async def index_video(req: IndexRequest):
    """
    Index a YouTube video: fetch transcript → chunk → embed → upsert to Pinecone.
    Skips re-indexing if the video is already in the index.
    """
    try:
        from utils.url_parser import extract_video_id
        from core.transcript_loader import YouTubeTranscriptLoader
        from core.chunker import chunk_documents
        from core.vector_store import is_video_indexed, upsert_documents

        video_id = extract_video_id(req.video_url)
        logger.info("Index request for video_id=%s", video_id)

        # ── Check cache ───────────────────────────────────────────────────
        if is_video_indexed(video_id):
            # Still fetch metadata for display
            loader = YouTubeTranscriptLoader(req.video_url, fetch_metadata=True)
            docs = loader.load()
            title = docs[0].metadata.get("video_title", "Unknown Title") if docs else "Unknown Title"
            author = docs[0].metadata.get("video_author", "Unknown Author") if docs else "Unknown Author"

            return IndexResponse(
                success=True,
                video_id=video_id,
                video_title=title,
                video_author=author,
                already_indexed=True,
                message="Video already indexed. Ready to chat!",
            )

        # ── Fetch transcript ──────────────────────────────────────────────
        loader = YouTubeTranscriptLoader(req.video_url, fetch_metadata=True)
        docs = loader.load()

        if not docs:
            return IndexResponse(
                success=False,
                video_id=video_id,
                message="No transcript found for this video.",
            )

        title = docs[0].metadata.get("video_title", "Unknown Title")
        author = docs[0].metadata.get("video_author", "Unknown Author")

        # ── Chunk ─────────────────────────────────────────────────────────
        chunks = chunk_documents(docs)

        # ── Embed & Upsert ────────────────────────────────────────────────
        n_upserted = upsert_documents(chunks)

        logger.info("Indexed %d chunks for video_id=%s", n_upserted, video_id)

        return IndexResponse(
            success=True,
            video_id=video_id,
            video_title=title,
            video_author=author,
            chunks_indexed=n_upserted,
            already_indexed=False,
            message=f"Successfully indexed {n_upserted} chunks!",
        )

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:
        logger.exception("Error indexing video")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Run a RAG query against an indexed video."""
    try:
        from core.rag_chain import run_rag_query
        from utils.timestamp_formatter import (
            seconds_to_hms,
            build_jump_link,
        )

        logger.info("Chat request: video=%s question=%r", req.video_id, req.question)

        result = run_rag_query(
            question=req.question,
            video_id=req.video_id,
            chat_history=req.chat_history,
        )

        # Build source citations
        sources: list[SourceDoc] = []
        seen_timestamps: set[int] = set()

        for doc in result.get("source_documents", []):
            start = doc.metadata.get("start_seconds")
            if start is None:
                continue
            start_int = int(start)
            if start_int in seen_timestamps:
                continue
            seen_timestamps.add(start_int)

            sources.append(SourceDoc(
                timestamp=seconds_to_hms(float(start)),
                start_seconds=float(start),
                text_snippet=doc.page_content[:150] + "…" if len(doc.page_content) > 150 else doc.page_content,
                jump_link=build_jump_link(req.video_id, float(start)),
            ))

        # Sort by timestamp, limit to 5
        sources.sort(key=lambda s: s.start_seconds)
        sources = sources[:5]

        return ChatResponse(
            answer=result["answer"],
            sources=sources,
            is_summary=result.get("is_summary", False),
        )

    except Exception as exc:
        logger.exception("Error during chat query")
        raise HTTPException(status_code=500, detail=str(exc))
