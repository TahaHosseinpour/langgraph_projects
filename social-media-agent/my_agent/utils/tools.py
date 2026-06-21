"""Tools for the social media agent."""

import re

import httpx
from langchain_core.tools import tool

# Strip HTML tags so the model receives mostly readable text.
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


@tool
def fetch_url(url: str) -> str:
    """Fetch a URL and return its text content (HTML stripped, truncated)."""
    try:
        response = httpx.get(url, timeout=15, follow_redirects=True)
        response.raise_for_status()
    except Exception as exc:  # noqa: BLE001 - surface any fetch error as text
        return f"Failed to fetch {url}: {exc}"

    # Drop scripts/styles, then remaining tags, then collapse whitespace.
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", response.text, flags=re.S)
    text = _TAG_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text[:4000]
