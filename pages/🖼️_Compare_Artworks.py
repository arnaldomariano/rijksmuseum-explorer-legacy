import json

import streamlit as st

from app_paths import FAV_FILE
from rijks_api import get_best_image_url
from analytics import track_event, track_event_once


# ============================================================
# Helpers to load favorites
# ============================================================
def load_favorites_from_disk() -> dict:
    """Load favorites from the local JSON file if needed."""
    if FAV_FILE.exists():
        try:
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
                if isinstance(data, dict):
                    return data
        except Exception:
            return {}
    return {}


# ============================================================
# Compare Artworks page (uses My Selection only)
# ============================================================

st.markdown("## 🖼️ Compare Artworks")

st.write(
    "This page lets you compare **two artworks side by side** using only the "
    "artworks stored in your **My Selection**."
)

st.caption(
    "First, go to the **My Selection** page and mark up to **4 artworks** as "
    "comparison candidates. They will appear here so you can pick two to "
    "compare in detail."
)

# Make sure favorites are available in session_state
if "favorites" not in st.session_state:
    st.session_state["favorites"] = load_favorites_from_disk()

favorites = st.session_state.get("favorites", {})
if not isinstance(favorites, dict):
    favorites = {}

# Comparison candidates come from My Selection
compare_candidates = st.session_state.get("compare_candidates", [])
compare_candidates = [
    cid for cid in compare_candidates if isinstance(cid, str) and cid in favorites
]
st.session_state["compare_candidates"] = compare_candidates

# Analytics: page view (once per session)
track_event_once(
    event="page_view",
    page="Compare",
    once_key="page_view::Compare",
    props={
        "candidate_count": len(compare_candidates),
        "favorites_count": len(favorites),
    },
)

# Guards
if not favorites:
    st.warning(
        "You do not have any artworks in your selection yet. "
        "Go to the **Rijksmuseum Explorer** page, mark some artworks as "
        "**In my selection**, and then return here."
    )
    st.stop()

if not compare_candidates:
    st.info(
        "No comparison candidates have been marked yet. "
        "Go to **My Selection**, mark up to **4 artworks** as "
        "*Mark for comparison*, and then come back to this page."
    )
    st.stop()

# ============================================================
# Candidate thumbnails
# ============================================================
candidate_arts = [
    (obj_id, favorites[obj_id])
    for obj_id in compare_candidates
    if obj_id in favorites
]

st.markdown("### Candidates from My Selection")

cols = st.columns(len(candidate_arts))
for col, (obj_id, art) in zip(cols, candidate_arts):
    with col:
        img_url = get_best_image_url(art)
        if img_url:
            try:
                st.image(img_url, use_container_width=True)
            except Exception:
                st.write("Error displaying image.")
        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")
        st.markdown(f"**{title}**  \n*{maker}*  \n`{obj_id}`")

st.markdown("---")

# ============================================================
# Choose two artworks to compare
# ============================================================
st.markdown("### Choose two artworks to compare")


def format_label(obj_id: str) -> str:
    art = favorites.get(obj_id, {})
    title = art.get("title", "Untitled")
    maker = art.get("principalOrFirstMaker", "Unknown artist")
    return f"{maker} — {title} [{obj_id}]"


selected_ids = st.multiselect(
    "Pick exactly two artworks:",
    options=compare_candidates,
    default=(
        compare_candidates[:2] if len(compare_candidates) >= 2 else compare_candidates
    ),
    format_func=format_label,
)

num_selected = len(selected_ids)
st.write(f"Currently selected for comparison: **{num_selected}**")

if num_selected < 2:
    st.info("Select two artworks above to see the side-by-side comparison.")
elif num_selected > 2:
    st.warning("Please keep **exactly 2** artworks selected.")
else:
    # Exactly 2 → render comparison automatically
    id_a, id_b = selected_ids
    art_a = favorites.get(id_a)
    art_b = favorites.get(id_b)

    if not art_a or not art_b:
        st.error("Could not retrieve both artworks for comparison.")
    else:
        # Analytics: each time this pair is shown
        track_event(
            event="compare_clicked",
            page="Compare",
            props={
                "object_id_a": id_a,
                "object_id_b": id_b,
            },
        )

        st.markdown("### 🔍 Side-by-side comparison")
        col_a, col_b = st.columns(2)

        def render_side(label: str, obj_id: str, art: dict, container):
            with container:
                st.subheader(label)
                img_url = get_best_image_url(art)
                if img_url:
                    try:
                        st.image(img_url, use_container_width=True)
                    except Exception:
                        st.write("Error displaying image.")
                else:
                    st.caption(
                        "No public image available for this artwork via API."
                    )

                title = art.get("title", "Untitled")
                maker = art.get("principalOrFirstMaker", "Unknown artist")
                dating = art.get("dating", {}) or {}
                date = dating.get("presentingDate") or dating.get("year")
                link = art.get("links", {}).get("web")

                st.write(f"**Title:** {title}")
                st.write(f"**Artist:** {maker}")
                if date:
                    st.write(f"**Date:** {date}")
                st.write(f"**Object ID:** {obj_id}")
                if link:
                    st.markdown(f"[View on Rijksmuseum website]({link})")

        render_side("Artwork A", id_a, art_a, col_a)
        render_side("Artwork B", id_b, art_b, col_b)