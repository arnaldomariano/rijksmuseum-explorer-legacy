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

def get_compare_candidates_from_favorites(favorites: dict) -> list[str]:
    """Return objectNumbers marked as comparison candidates inside favorites."""
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
    "Those artworks will appear here so you can pick two to compare in detail."
)

# Make sure favorites are available in session_state
if "favorites" not in st.session_state:
    st.session_state["favorites"] = load_favorites_from_disk()

favorites = st.session_state.get("favorites", {})
if not isinstance(favorites, dict):
    favorites = {}

# Comparison candidates now come from favorites metadata
compare_candidates = get_compare_candidates_from_favorites(favorites)
st.session_state["compare_candidates"] = compare_candidates

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
        "*Mark for comparison (up to 4)*, and then come back to this page."
    )
    st.stop()

# ============================================================
# Candidate thumbnails
# ============================================================
st.markdown("### Candidates from My Selection")

candidate_arts = [
    (obj_id, favorites[obj_id])
    for obj_id in compare_candidates
    if obj_id in favorites
]

# Linha de miniaturas
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

# Botão para limpar TODAS as marcas de comparação na My Selection
st.markdown("---")
if st.button("Clear comparison marks in My Selection"):
    # Apaga a lista de candidatos
    old_candidates = st.session_state.get("compare_candidates", [])
    st.session_state["compare_candidates"] = []

    # Também remove os checkboxes marcados na My Selection (chaves cmp_candidate_*)
    for cid in old_candidates:
        key = f"cmp_candidate_{cid}"
        if key in st.session_state:
            del st.session_state[key]

    # Limpa o par atual (se houver) e reroda
    if "cmp_multiselect" in st.session_state:
        del st.session_state["cmp_multiselect"]

    st.success("All comparison marks have been cleared in **My Selection**.")
    st.rerun()

st.markdown("---")

st.markdown("### Choose two artworks to compare")

# Linha de botões de limpeza
col_btn_pair, col_btn_all = st.columns(2)

with col_btn_pair:
    if st.button("Clear current pair (keep candidates)", key="btn_clear_pair"):
        # Limpa apenas o par escolhido, mas mantém as obras marcadas em My Selection
        st.session_state["cmp_multiselect"] = []
        st.rerun()

with col_btn_all:
    if st.button("Clear comparison marks in My Selection", key="btn_clear_all_marks"):
        # Limpa a flag _compare_candidate em todas as obras
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

        # Limpa lista de candidatos e o multiselect
        st.session_state["compare_candidates"] = []
        st.session_state["cmp_multiselect"] = []

        # Remove também os estados dos checkboxes em My Selection
        keys_to_delete = [
            k for k in st.session_state.keys()
            if k.startswith("cmp_candidate_")
        ]
        for k in keys_to_delete:
            del st.session_state[k]

        st.success("All comparison marks were cleared. You can now mark new candidates in My Selection.")
        st.rerun()

# Agora definimos o valor padrão do multiselect
current_saved = st.session_state.get("cmp_multiselect", [])
if current_saved:
    default_selected = current_saved
else:
    default_selected = (
        compare_candidates[:2] if len(compare_candidates) >= 2 else compare_candidates
    )

def format_label(obj_id: str) -> str:
    """
    Return a human-readable label for an artwork ID in the compare multiselect.

    The label includes:
    - title
    - artist
    - objectNumber in square brackets
    """
    # Read favorites directly from session_state to avoid order-of-definition issues
    favorites = st.session_state.get("favorites", {})
    if not isinstance(favorites, dict):
        favorites = {}

    art = favorites.get(obj_id, {}) if isinstance(obj_id, str) else {}

    title = art.get("title", "Untitled")
    maker = art.get("principalOrFirstMaker", "Unknown artist")

    # Final label shown in the dropdown
    return f"{title} — {maker} [{obj_id}]"

selected_ids = st.multiselect(
    "Pick exactly two artworks:",
    options=compare_candidates,
    default=default_selected,
    key="cmp_multiselect",
    format_func=lambda obj_id: format_label(obj_id),
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