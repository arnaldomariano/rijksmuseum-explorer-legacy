import json

import streamlit as st

from app_paths import FAV_FILE
from rijks_api import get_best_image_url
from analytics import track_event


# ============================================================
# Helpers to load favorites & comparison candidates
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


def get_compare_candidates_from_favorites(favorites: dict) -> list[str]:
    """
    Return objectNumbers marked as comparison candidates inside favorites.

    We use the metadata flag `_compare_candidate` attached to each artwork
    (set on the 'My Selection' page).
    """
    return [
        obj_id
        for obj_id, art in favorites.items()
        if isinstance(art, dict) and art.get("_compare_candidate")
    ]


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
    "comparison candidates using **Mark for comparison (up to 4)**. "
    "Those artworks will appear here so you can choose two of them."
)

# ------------------------------------------------------------
# Ensure favorites are available in session state
# ------------------------------------------------------------
if "favorites" not in st.session_state:
    st.session_state["favorites"] = load_favorites_from_disk()

favorites = st.session_state.get("favorites", {})
if not isinstance(favorites, dict):
    favorites = {}

# Comparison candidates now come from favorites metadata
compare_candidates = get_compare_candidates_from_favorites(favorites)
st.session_state["compare_candidates"] = compare_candidates

# ------------------------------------------------------------
# Guards for empty states
# ------------------------------------------------------------
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
        "*Mark for comparison (up to 4)*, and then come back to this page."
    )
    st.stop()

# ============================================================
# Candidate thumbnails + pair checkboxes
# ============================================================

st.markdown("### Candidates from My Selection")

# Generation key for pair checkboxes:
# each time we want to reset all checkboxes, we simply bump this counter.
if "cmp_pair_generation" not in st.session_state:
    st.session_state["cmp_pair_generation"] = 0

pair_gen = st.session_state["cmp_pair_generation"]

candidate_arts = [
    (obj_id, favorites[obj_id])
    for obj_id in compare_candidates
    if obj_id in favorites
]

cols = st.columns(len(candidate_arts))

for col, (obj_id, art) in zip(cols, candidate_arts):
    with col:
        img_url = get_best_image_url(art)
        if img_url:
            try:
                st.image(img_url, use_container_width=True)
            except Exception:
                st.write("Error displaying image.")
        else:
            st.caption("No public image available.")

        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")
        dating = art.get("dating", {}) or {}
        date = dating.get("presentingDate") or dating.get("year") or ""
        obj_label = art.get("objectNumber") or obj_id

        st.markdown(f"**{title}**")
        st.markdown(f"*{maker}*")
        if date:
            st.caption(str(date))
        st.code(obj_label, language=None)

        # Checkbox to include this artwork in the comparison pair.
        # IMPORTANT: the key includes the generation so we can reset all
        # checkboxes by bumping `cmp_pair_generation` (no direct assignment).
        checkbox_key = f"cmp_pair_{obj_id}_{pair_gen}"
        st.checkbox(
            "Include in comparison pair",
            key=checkbox_key,
        )

st.markdown("---")

# ============================================================
# Controls for the current pair
# ============================================================

st.markdown("### Choose two artworks to compare")

# Read which candidates are currently checked for this generation
selected_ids = [
    obj_id
    for obj_id in compare_candidates
    if st.session_state.get(f"cmp_pair_{obj_id}_{pair_gen}", False)
]

num_selected = len(selected_ids)
st.caption(f"Currently selected for comparison: **{num_selected}**")

# ---- Pair control buttons (left) and global clear (right) ----
col_btn_pair, col_btn_all = st.columns(2)

with col_btn_pair:
    if st.button("Clear current pair (keep candidates)"):
        # We DO NOT touch any checkbox keys directly.
        # Instead, we bump the generation id so that all checkboxes
        # get new keys and start unchecked on the next run.
        st.session_state["cmp_pair_generation"] = pair_gen + 1
        st.rerun()

with col_btn_all:
    if st.button("Clear comparison marks in My Selection"):
        # Remove the `_compare_candidate` flag from all artworks in favorites
        changed = False
        for obj_id, art in favorites.items():
            if isinstance(art, dict) and art.get("_compare_candidate"):
                art.pop("_compare_candidate", None)
                favorites[obj_id] = art
                changed = True

        if changed:
            st.session_state["favorites"] = favorites
            try:
                with open(FAV_FILE, "w", encoding="utf-8") as f:
                    json.dump(favorites, f, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Reset candidates + pair generation
        st.session_state["compare_candidates"] = []
        st.session_state["cmp_pair_generation"] = pair_gen + 1

        st.success(
            "All comparison marks were cleared. "
            "You can now mark new candidates in **My Selection**."
        )
        st.rerun()

# ============================================================
# Pair validation and side-by-side rendering
# ============================================================

# If more than 2 are selected, we still show only the first 2
# but warn the user so they can adjust.
if num_selected < 2:
    st.info("Select **two** artworks above to see the side-by-side comparison.")
    st.stop()

if num_selected > 2:
    st.warning(
        "You selected more than **2** artworks. "
        "Only the first two checked artworks will be used below."
    )

# Use only the first 2 IDs for the actual comparison
id_a, id_b = selected_ids[:2]
art_a = favorites.get(id_a)
art_b = favorites.get(id_b)

if not art_a or not art_b:
    st.error("Could not retrieve both artworks for comparison.")
    st.stop()

# Analytics: log each time a pair is displayed
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
    """Render one side of the comparison (thumbnail + metadata)."""
    with container:
        st.subheader(label)

        img_url = get_best_image_url(art)
        if img_url:
            try:
                st.image(img_url, use_container_width=True)
            except Exception:
                st.write("Error displaying image.")
        else:
            st.caption("No public image available for this artwork via API.")

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