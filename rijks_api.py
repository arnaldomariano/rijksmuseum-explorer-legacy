# rijks_api.py
"""
Utility functions for interacting with the Rijksmuseum API.

This module handles:
- Search queries to the Rijksmuseum collection endpoint.
- Sorting (artist, chronologic, achronologic, relevance) via API parameters.
- Optional object type filtering (painting, print, drawing, etc.).
- Helper to pick the best image URL for an artwork.
- Helper to extract a numeric year from the API dating metadata.
"""

import os
import requests

# ============================================================
# API configuration
# ============================================================
# IMPORTANT:
# - In production, always prefer setting RIJKSMUSEUM_API_KEY as an environment variable.
# - The default value here is just a placeholder for local development.
API_KEY = os.getenv("RIJKSMUSEUM_API_KEY", "3VvngspN")
BASE_URL = "https://www.rijksmuseum.nl/api/en/collection"


# ============================================================
# Year extraction helper
# ============================================================
def extract_year(dating: dict) -> int | None:
    """
    Extract a numeric year from the 'dating' field of an artwork.

    Strategy:
    - If 'year' is present and is an integer, use it directly.
    - Otherwise, try to parse the first 4 characters of 'presentingDate'.

    Parameters
    ----------
    dating : dict
        'dating' field from the Rijksmuseum API artwork metadata.

    Returns
    -------
    int | None
        Parsed year as an integer, or None if extraction is not possible.
    """
    if not dating:
        return None

    # 1) Explicit integer year
    year = dating.get("year")
    if isinstance(year, int):
        return year

    # 2) Try parsing presentingDate (first 4 characters)
    pd = dating.get("presentingDate")
    if isinstance(pd, str) and len(pd) >= 4 and pd[:4].isdigit():
        try:
            return int(pd[:4])
        except Exception:
            return None

    return None


# ============================================================
# Image URL normalization helper (currently unused)
# ============================================================
def _normalize_rijks_url(url: str | None) -> str | None:
    """
    Normalize URLs coming from the Rijksmuseum API.

    Rules:
    - If the URL already starts with http/https → return as is.
    - If it starts with '//' → prefix with 'https:'.
    - If it starts with '/'  → prefix with Rijksmuseum domain.
    - Otherwise, build a basic absolute URL using the Rijksmuseum domain.
    """
    if not url:
        return None

    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url

    if url.startswith("//"):
        # Protocol-relative URL (starts with //)
        return "https:" + url

    if url.startswith("/"):
        # Absolute path on the Rijksmuseum website
        return "https://www.rijksmuseum.nl" + url

    # Fallback for relative paths like 'Static/Images/...'
    return "https://www.rijksmuseum.nl/" + url.lstrip("./")


# ============================================================
# Best image URL helper
# ============================================================
def get_best_image_url(art: dict) -> str | None:
    """
    Try to pick the best image URL available for a Rijksmuseum artwork.

    Priority:
        1. art["webImage"]["url"]      (larger image, intended for web use)
        2. art["headerImage"]["url"]  (banner-style image)

    Only returns URLs that look like valid http(s) URLs. If no suitable
    image is found, returns None.

    Parameters
    ----------
    art : dict
        Single artwork record from the Rijksmuseum API.

    Returns
    -------
    str | None
        Best image URL or None if no valid URL is found.
    """

    def _safe_url(container: dict | None) -> str | None:
        """Internal helper: safely extract a URL string from a nested dict."""
        if not isinstance(container, dict):
            return None
        url = container.get("url")
        if isinstance(url, str):
            u = url.strip()
            if u.startswith("http"):
                return u
        return None

    # 1) webImage (primary)
    url = _safe_url(art.get("webImage"))
    if url:
        return url

    # 2) headerImage (fallback)
    url = _safe_url(art.get("headerImage"))
    if url:
        return url

    # No reliable image found
    return None


# ============================================================
# Main search function (sorting handled by API)
# ============================================================
def search_artworks(
    query: str,
    object_type: str | None = None,
    sort: str = "relevance",
    page_size: int = 12,
    page: int = 1,
):
    """
    Query the Rijksmuseum API and return a list of artworks plus the total count.

    Parameters
    ----------
    query : str
        Search term (artist name, keyword, title, etc.).
    object_type : str | None
        Optional object type filter ("painting", "print", etc.).
        If None, no object type filter is sent to the API.
    sort : str
        Sorting mode supported by the API:
        'relevance', 'artist', 'chronologic', 'achronologic'.
    page_size : int
        Number of results to retrieve per API call (parameter 'ps').
    page : int
        Page of results to request (parameter 'p'). 1 = first page.

    Returns
    -------
    list[dict], int
        artworks, total_count

        - artworks: list of artwork dictionaries (API field 'artObjects').
        - total_count: integer 'count' returned by the API (all matching records).
    """
    params = {
        "key": API_KEY,
        "q": query,
        "ps": page_size,
        "s": sort,       # real sorting handled by the API
        "p": int(page),  # API pagination (page number)
    }

    if object_type:
        params["type"] = object_type

    response = requests.get(BASE_URL, params=params)

    # API key failure
    if response.status_code == 401:
        raise RuntimeError("Unauthorized (401): invalid or missing API key.")

    response.raise_for_status()

    data = response.json()
    artworks = data.get("artObjects", []) or []
    total = data.get("count", 0)

    return artworks, total