"""
utils/url_parser.py
───────────────────
Robust YouTube URL → video_id extractor.

Handles all common YouTube URL formats:
  • https://www.youtube.com/watch?v=VIDEO_ID
  • https://youtu.be/VIDEO_ID
  • https://www.youtube.com/embed/VIDEO_ID
  • https://www.youtube.com/shorts/VIDEO_ID
  • https://m.youtube.com/watch?v=VIDEO_ID
  • Bare video IDs (11-character alphanumeric strings)
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse


# YouTube video IDs are always 11 characters: [A-Za-z0-9_-]
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Pattern to capture video_id from path-based URLs (embed / shorts)
_PATH_RE = re.compile(
    r"(?:v=|vi=|embed/|shorts/|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def extract_video_id(url: str) -> str:
    """
    Extract the 11-character YouTube video ID from a URL or bare ID.

    Parameters
    ----------
    url : str
        Any YouTube URL or a raw video ID string.

    Returns
    -------
    str
        The 11-character video ID.

    Raises
    ------
    ValueError
        If no valid video ID can be found in the input.
    """
    url = url.strip()

    # 1. Check if it's already a bare video ID.
    if _VIDEO_ID_RE.match(url):
        return url

    # 2. Parse as a URL.
    try:
        parsed = urlparse(url)
    except Exception as exc:
        raise ValueError(f"Cannot parse URL: {url!r}") from exc

    # 3. Try query-string parameter (?v= or ?vi=)
    qs = parse_qs(parsed.query)
    for key in ("v", "vi"):
        if key in qs:
            candidate = qs[key][0]
            if _VIDEO_ID_RE.match(candidate):
                return candidate

    # 4. Try path-based patterns (youtu.be, /embed/, /shorts/).
    full_url = url  # keep original for regex search
    match = _PATH_RE.search(full_url)
    if match:
        candidate = match.group(1)
        if _VIDEO_ID_RE.match(candidate):
            return candidate

    raise ValueError(
        f"Could not extract a valid YouTube video ID from: {url!r}\n"
        "Please provide a standard YouTube URL or a valid 11-character video ID."
    )


def build_watch_url(video_id: str) -> str:
    """Return the canonical watch URL for a video ID."""
    return f"https://www.youtube.com/watch?v={video_id}"
