# rijks_api.py
"""
Utility functions for interacting with the Rijksmuseum API.
Handles:
- search query
- sorting (artist, chronologic, achronologic, relevance)
- object type filtering
- best image URL selection
- year extraction helper
"""

import os
import requests

# IMPORTANT: set your API key here or load from environment variable
API_KEY = os.getenv("RIJKSMUSEUM_API_KEY", "3VvngspN")
BASE_URL = "https://www.rijksmuseum.nl/api/en/collection"


# -----------------------------------------------------------
# Extract year helper
# -----------------------------------------------------------
def extract_year(dating: dict) -> int | None:
    """
    Extracts a numeric year from the 'dating' field of the API result.
    Returns an integer year or None if extraction is not possible.
    """
    if not dating:
        return None

    # If year is explicitly provided as int
    year = dating.get("year")
    if isinstance(year, int):
        return year

    # Try parsing presentingDate (first 4 chars)
    pd = dating.get("presentingDate")
    if isinstance(pd, str) and len(pd) >= 4 and pd[:4].isdigit():
        try:
            return int(pd[:4])
        except Exception:
            return None

    return None


# -----------------------------------------------------------
# Best image URL helper
# -----------------------------------------------------------
def get_best_image_url(art: dict) -> str | None:
    """
    Returns the best available image URL from the API result, if any.
    Prefers 'webImage' (largest), falling back to 'headerImage'.
    """
    if not art:
        return None

    web_img = art.get("webImage")
    if web_img and web_img.get("url"):
        return web_img["url"]

    header_img = art.get("headerImage")
    if header_img and header_img.get("url"):
        return header_img["url"]

    return None


# -----------------------------------------------------------
# Main search function (SORTING REAL via API)
# -----------------------------------------------------------
def search_artworks(
    query: str,
    object_type: str | None = None,
    sort: str = "relevance",
    page_size: int = 12,
    page: int = 1,
):
    """
    Query the Rijksmuseum API and return a list of artworks and the total count.

    Parameters
    ----------
    query : str
        Search term (artist name, keyword, title, etc.)
    object_type : str | None
        Optional object type filter ("painting", "print", etc.)
    sort : str
        Sorting mode supported by the API:
        'relevance', 'artist', 'chronologic', 'achronologic'
    page_size : int
        Number of results to retrieve (API parameter 'ps').
    page : int
        Page of results to request (API parameter 'p'). 1 = first page.

    Returns
    -------
    list[dict], int
        artworks, total_count
    """

    params = {
        "key": API_KEY,
        "q": query,
        "ps": page_size,
        "s": sort,       # ordenação real via API
        "p": int(page),  # paginação via API
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