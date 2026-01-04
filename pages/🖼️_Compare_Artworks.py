import json

import streamlit as st

from app_paths import FAV_FILE
from rijks_api import get_best_image_url
from analytics import track_event


# ============================================================
# Helpers to load favorites and comparison candidates
# ============================================================
def load_favorites_from_disk() -> dict:
    """Load favorites from the local JSON file if not already in session_state."""
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

    We use the metadata flag `_compare_candidate` stored in each artwork dict.
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
    "This page lets you compare **two artworks side by side**, using only the "
    "artworks stored in your **My Selection**."
)

st.caption(
    "First, go to the **My Selection** page and mark up to **4 artworks** as "
    "comparison candidates using **Mark for comparison (up to 4)**. "
    "Those artworks will appear here so you can choose two of them."
)

# ------------------------------------------------------------
# Make sure favorites are available in session_state
# ------------------------------------------------------------
if "favorites" not in st.session_state:
    st.session_state["favorites"] = load_favorites_from_disk()

favorites = st.session_state.get("favorites", {})
if not isinstance(favorites, dict):
    favorites = {}

# Comparison candidates now come from favorites metadata
compare_candidates = get_compare_candidates_from_favorites(favorites)
# Drop any candidate IDs no longer present in favorites
compare_candidates = [cid for cid in compare_candidates if cid in favorites]
st.session_state["compare_candidates"] = compare_candidates

# ------------------------------------------------------------
# Guards (no favorites / no candidates)
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
# Candidate thumbnails + checkboxes for the comparison pair
# ============================================================
st.markdown("### Candidates from My Selection")

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
            st.caption("No public image available for this artwork via API.")

        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")

        st.markdown(f"**{title}**  \n*{maker}*  \n`{obj_id}`")

        # Checkbox for choosing the pair **on this page**
        checkbox_key = f"cmp_pair_{obj_id}"
        current_flag = bool(st.session_state.get(checkbox_key, False))

        st.checkbox(
            "Include in comparison pair",
            value=current_flag,
            key=checkbox_key,
        )

st.markdown("---")

# ============================================================
# Current pair status
# ============================================================
st.markdown("### Choose two artworks to compare")

pair_ids = [
    obj_id
    for obj_id in compare_candidates
    if st.session_state.get(f"cmp_pair_{obj_id}", False)
]

num_selected = len(pair_ids)
st.caption(f"Currently selected for comparison: **{num_selected}**")

# ============================================================
# Controls in a compact expander (to reduce visual noise)
# ============================================================
with st.expander("Pair & comparison controls", expanded=False):
    st.write(
        "Use these controls when you want to reset the pair here or clear all "
        "comparison marks in **My Selection**."
    )

    col_btn_pair, col_btn_all = st.columns(2)

    with col_btn_pair:
        if st.button("Clear current pair (keep candidates)", key="btn_clear_pair"):
            # Clear only the checkboxes for the current pair selection on this page
            for obj_id in compare_candidates:
                checkbox_key = f"cmp_pair_{obj_id}"
                if checkbox_key in st.session_state:
                    st.session_state[checkbox_key] = False

            # Old multiselect key from previous versions can be removed safely
            if "cmp_multiselect" in st.session_state:
                del st.session_state["cmp_multiselect"]

            st.rerun()

    with col_btn_all:
        if st.button(
            "Clear comparison marks in My Selection", key="btn_clear_all_marks"
        ):
            """
            This button:
            - Clears the `_compare_candidate` flag in favorites (all artworks).
            - Saves the updated favorites to disk.
            - Clears all 'cmp_pair_*' checkbox states on this page.
            - Clears 'cmp_candidate_*' states that might exist from My Selection.
            """
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

            # Clear comparison candidates list and any local pair selection
            st.session_state["compare_candidates"] = []

            # Clear all cmp_pair_* keys (this page)
            keys_to_delete = [
                k for k in st.session_state.keys()
                if k.startswith("cmp_pair_")
            ]
            for k in keys_to_delete:
                del st.session_state[k]

            # Clear any cmp_candidate_* keys used in My Selection
            keys_to_delete = [
                k for k in st.session_state.keys()
                if k.startswith("cmp_candidate_")
            ]
            for k in keys_to_delete:
                del st.session_state[k]

            # Old multiselect state can be removed as well
            if "cmp_multiselect" in st.session_state:
                del st.session_state["cmp_multiselect"]

            st.success(
                "All comparison marks were cleared. "
                "You can now mark new candidates in **My Selection**."
            )
            st.rerun()

# ============================================================
# Render comparison (or guidance messages)
# ============================================================
if num_selected < 2:
    st.info("Select two artworks above to see the side-by-side comparison.")
elif num_selected > 2:
    st.warning("Please keep **exactly 2** artworks selected for the comparison pair.")
else:
    # Exactly two artworks selected → render comparison
    id_a, id_b = pair_ids
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
            """Render one side of the comparison."""
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