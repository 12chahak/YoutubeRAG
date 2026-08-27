"""
core/transcript_loader.py
─────────────────────────
Custom LangChain-compatible YouTube transcript loader.

Compatible with youtube-transcript-api >= 1.2.0 (new instance-based API).

Each transcript segment is returned as a LangChain Document with:
  • page_content  — the spoken text
  • metadata      — {video_id, start_seconds, start_formatted,
                     source_url, video_title, video_author}

The loader merges very short consecutive segments (< 3 words) to avoid
producing micro-chunks that confuse the chunker downstream.
"""

from __future__ import annotations

import logging
from typing import Iterator

from langchain_core.document_loaders import BaseLoader
from langchain_core.documents import Document

from utils.url_parser import extract_video_id, build_watch_url
from utils.timestamp_formatter import seconds_to_hms

logger = logging.getLogger(__name__)


# ── Optional: fetch video metadata via pytubefix ──────────────────────────────
def _fetch_video_metadata(video_id: str) -> dict:
    """
    Attempt to fetch video title and author via pytubefix.
    Returns empty dict on failure (metadata is best-effort).
    """
    try:
        from pytubefix import YouTube  # type: ignore
        yt = YouTube(build_watch_url(video_id))
        return {
            "video_title": yt.title or "Unknown Title",
            "video_author": yt.author or "Unknown Author",
            "video_length_seconds": yt.length or 0,
        }
    except Exception as exc:
        logger.warning("Could not fetch video metadata via pytubefix: %s", exc)
        return {
            "video_title": "Unknown Title",
            "video_author": "Unknown Author",
            "video_length_seconds": 0,
        }


class YouTubeTranscriptLoader(BaseLoader):
    """
    Load a YouTube video transcript as a list of LangChain Documents.

    Compatible with youtube-transcript-api >= 1.2.0.

    Parameters
    ----------
    url : str
        Any YouTube URL or bare video ID.
    languages : list[str]
        Preferred transcript languages in priority order.
        Defaults to English.
    fetch_metadata : bool
        If True (default), attempt to fetch video title/author via pytubefix.
    """

    def __init__(
        self,
        url: str,
        languages: list[str] | None = None,
        fetch_metadata: bool = True,
    ) -> None:
        self.url = url
        self.video_id = extract_video_id(url)
        self.languages = languages or ["en", "en-US", "en-GB"]
        self.fetch_metadata = fetch_metadata

    # ── Public API ────────────────────────────────────────────────────────────

    def lazy_load(self) -> Iterator[Document]:
        """Yield one Document per transcript segment."""
        from youtube_transcript_api import YouTubeTranscriptApi  # type: ignore

        logger.info("Fetching transcript for video_id=%s", self.video_id)

        try:
            # ── New API (v1.2+): instance-based ──────────────────────────────
            api = YouTubeTranscriptApi()

            # Try to get the transcript directly with preferred languages.
            # The new .fetch() accepts a languages kwarg for fallback order.
            try:
                fetched = api.fetch(
                    self.video_id,
                    languages=self.languages,
                )
            except Exception:
                # Fallback: list all available and pick first one
                logger.warning(
                    "Could not fetch transcript in preferred languages %s. "
                    "Listing available transcripts...",
                    self.languages,
                )
                transcript_list = api.list(self.video_id)
                # Try manually created first, then generated
                try:
                    transcript = transcript_list.find_manually_created_transcript(
                        self.languages
                    )
                except Exception:
                    transcript = transcript_list.find_generated_transcript(
                        self.languages
                    )
                fetched = transcript.fetch()

            # ── Extract snippets ──────────────────────────────────────────────
            # In v1.2+, FetchedTranscript has a .snippets attribute (list of
            # FetchedTranscriptSnippet dataclass objects with .text, .start, .duration)
            if hasattr(fetched, "snippets"):
                segments = [
                    {
                        "text": s.text,
                        "start": s.start,
                        "duration": getattr(s, "duration", 0.0),
                    }
                    for s in fetched.snippets
                ]
            else:
                # Fallback: iterable of dict-like objects
                segments = [
                    {
                        "text": getattr(s, "text", s.get("text", "")),
                        "start": getattr(s, "start", s.get("start", 0.0)),
                        "duration": getattr(s, "duration", s.get("duration", 0.0)),
                    }
                    for s in fetched
                ]

        except Exception as exc:
            error_msg = str(exc)
            if "disabled" in error_msg.lower():
                raise ValueError(
                    f"Transcripts are disabled for video '{self.video_id}'. "
                    "Please choose a video with captions enabled."
                )
            elif "unavailable" in error_msg.lower() or "private" in error_msg.lower():
                raise ValueError(
                    f"Video '{self.video_id}' is unavailable or private."
                )
            else:
                raise RuntimeError(
                    f"Failed to fetch transcript for '{self.video_id}': {exc}"
                ) from exc

        # ── Fetch video metadata (best-effort) ────────────────────────────────
        meta_extra = (
            _fetch_video_metadata(self.video_id) if self.fetch_metadata else {}
        )

        # ── Yield Documents ───────────────────────────────────────────────────
        source_url = build_watch_url(self.video_id)
        buffer_text = ""
        buffer_start: float = 0.0

        for seg in segments:
            text: str = str(seg.get("text", "")).strip()
            # Clean up common transcript artifacts
            text = text.replace("\n", " ").replace("[Music]", "").replace("[Applause]", "").strip()
            start: float = float(seg.get("start", 0.0))

            if not text:
                continue

            # Merge very short segments (< 3 words) into the next one
            word_count = len(text.split())
            if word_count < 3:
                if not buffer_text:
                    buffer_start = start
                buffer_text = (buffer_text + " " + text).strip()
                continue

            # Flush buffer + current segment
            if buffer_text:
                text = (buffer_text + " " + text).strip()
                start = buffer_start
                buffer_text = ""

            yield Document(
                page_content=text,
                metadata={
                    "video_id": self.video_id,
                    "source_url": source_url,
                    "start_seconds": start,
                    "start_formatted": seconds_to_hms(start),
                    **meta_extra,
                },
            )

        # Flush any remaining buffer
        if buffer_text:
            yield Document(
                page_content=buffer_text,
                metadata={
                    "video_id": self.video_id,
                    "source_url": source_url,
                    "start_seconds": buffer_start,
                    "start_formatted": seconds_to_hms(buffer_start),
                    **meta_extra,
                },
            )

    def load(self) -> list[Document]:
        """Load all transcript segments as a list."""
        docs = list(self.lazy_load())
        logger.info(
            "Loaded %d transcript segments for video_id=%s",
            len(docs),
            self.video_id,
        )
        return docs
