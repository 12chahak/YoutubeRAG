"""
utils/timestamp_formatter.py
─────────────────────────────
Timestamp utilities for building human-readable timestamps and
clickable YouTube jump links from retrieved RAG source documents.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.documents import Document


def seconds_to_hms(seconds: float | int) -> str:
    """
    Convert a float/int number of seconds to a human-readable timestamp.

    Examples
    --------
    >>> seconds_to_hms(75)
    '1:15'
    >>> seconds_to_hms(3723)
    '1:02:03'
    >>> seconds_to_hms(45)
    '0:45'
    """
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def build_jump_link(video_id: str, seconds: float | int) -> str:
    """
    Build a YouTube deep-link that opens the video at a specific timestamp.

    Parameters
    ----------
    video_id : str
        The 11-character YouTube video ID.
    seconds : float | int
        The timestamp in seconds.

    Returns
    -------
    str
        A URL like ``https://youtu.be/VIDEO_ID?t=75``
    """
    return f"https://youtu.be/{video_id}?t={int(seconds)}"


def extract_best_timestamp(source_docs: list["Document"]) -> tuple[float, str] | None:
    """
    Find the earliest (most relevant) timestamp across a list of source Documents.

    Parameters
    ----------
    source_docs : list[Document]
        Retrieved LangChain Documents. Each must have ``metadata["start_seconds"]``.

    Returns
    -------
    tuple[float, str] | None
        ``(start_seconds, formatted_hms)`` for the earliest chunk,
        or ``None`` if no timestamp metadata is found.
    """
    timestamps: list[float] = []

    for doc in source_docs:
        start = doc.metadata.get("start_seconds")
        if start is not None:
            try:
                timestamps.append(float(start))
            except (TypeError, ValueError):
                continue

    if not timestamps:
        return None

    best = min(timestamps)
    return best, seconds_to_hms(best)


def format_sources_block(
    source_docs: list["Document"],
    video_id: str,
    max_sources: int = 3,
) -> str:
    """
    Build a Markdown-formatted block of timestamped source citations.

    Parameters
    ----------
    source_docs : list[Document]
        Retrieved source documents.
    video_id : str
        YouTube video ID for building jump links.
    max_sources : int
        Maximum number of source links to display (default 3).

    Returns
    -------
    str
        Markdown string with clickable jump links.
    """
    if not source_docs:
        return ""

    # Collect unique timestamps, preserving insertion order
    seen: set[int] = set()
    entries: list[tuple[float, str]] = []

    for doc in source_docs:
        start = doc.metadata.get("start_seconds")
        if start is None:
            continue
        start_int = int(start)
        if start_int not in seen:
            seen.add(start_int)
            entries.append((float(start), seconds_to_hms(float(start))))

    if not entries:
        return ""

    # Sort by timestamp and limit
    entries.sort(key=lambda x: x[0])
    entries = entries[:max_sources]

    lines = ["---", "📌 **Sources in this video:**"]
    for i, (secs, hms) in enumerate(entries, 1):
        link = build_jump_link(video_id, secs)
        lines.append(f"  {i}. [{hms}]({link})")

    return "\n".join(lines)
