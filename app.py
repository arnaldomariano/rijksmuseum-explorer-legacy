# app.py
"""
Rijksmuseum Explorer - main page
"""
import json
import io
import csv
import streamlit as st

from app_paths import FAV_FILE, NOTES_FILE, HERO_IMAGE_PATH
from analytics import track_event_once
from rijks_api import search_artworks, extract_year, get_best_image_url


# ============================================================
# Page config
# ============================================================
st.set_page_config(page_title="Rijksmuseum Explorer", page_icon="🎨", layout="wide")


# ============================================================
# CSS & footer
# ============================================================
def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background-color: #111111; color: #f5f5f5; }
        div.block-container { max-width: 1200px; padding-top: 1.5rem; padding-bottom: 3rem; }

        section[data-testid="stSidebar"] { background-color: #181818 !important; }
        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3,
        section[data-testid="stSidebar"] label { color: #f5f5f5 !important; }

        div[data-testid="stMarkdownContainer"] a { color: #ff9900 !important; text-decoration: none; }
        div[data-testid="stMarkdownContainer"] a:hover { text-decoration: underline; }

        .rijks-hero {
            border-radius: 14px;
            overflow: hidden;
            box-shadow: 0 4px 18px rgba(0,0,0,0.6);
            margin-bottom: 0.85rem;
        }

        .rijks-summary-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background-color: #262626;
            color: #f5f5f5;
            font-size: 0.85rem;
            margin-top: 0.35rem;
            margin-bottom: 1.0rem;
        }
        .rijks-summary-pill strong { color: #ff9900; }

        .rijks-card {
            background-color: #181818;
            border-radius: 12px;
            padding: 0.75rem 0.75rem 0.9rem 0.75rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            border: 1px solid #262626;
            margin-bottom: 1rem;
            margin-top: 0.35rem;
        }
        .rijks-card img {
            width: 100%;
            height: 260px;
            object-fit: cover;
            border-radius: 8px;
        }
        .rijks-card-title {
            font-size: 1rem;
            font-weight: 600;
            margin-top: 0.35rem;
            margin-bottom: 0.1rem;
            min-height: 1.3rem;
        }
        .rijks-card-caption { font-size: 0.9rem; color: #c7c7c7; margin-bottom: 0.25rem; }

        .rijks-badge-row { margin-top: 0.15rem; margin-bottom: 0.35rem; }
        .rijks-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 999px;
            font-size: 0.73rem;
            margin-right: 0.25rem;
            background-color: #262626;
            color: #f5f5f5;
            border: 1px solid #333333;
        }
        .rijks-badge-primary { background-color: #ff9900; color: #111111; border-color: #ff9900; }
        .rijks-badge-secondary { background-color: #262626; color: #ffddaa; border-color: #444444; }

        .rijks-no-image-msg {
            font-size: 0.8rem;
            color: #cccccc;
            background-color: #202020;
            border-radius: 8px;
            padding: 0.45rem 0.55rem;
            margin-top: 0.25rem;
            border: 1px dashed #444444;
        }

        .rijks-footer {
            margin-top: 2.5rem;
            padding-top: 0.75rem;
            border-top: 1px solid #262626;
            font-size: 0.8rem;
            color: #aaaaaa;
            text-align: center;
        }

        .stButton > button { border-radius: 999px; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_footer() -> None:
    st.markdown(
        """
        <div class="rijks-footer">
            Rijksmuseum Explorer — prototype created for study & research purposes.<br>
            Data & images provided by the Rijksmuseum API.
        </div>
        """,
        unsafe_allow_html=True,
    )


inject_custom_css()


# ============================================================
# Helpers (cache for faster reruns)
# ============================================================
@st.cache_data(show_spinner=False)
def _read_json_file(path_str: str) -> dict:
    try:
        with open(path_str, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_favorites() -> None:
    if "favorites" in st.session_state:
        return
    st.session_state["favorites"] = _read_json_file(str(FAV_FILE)) if FAV_FILE.exists() else {}


def load_notes() -> None:
    if "notes" in st.session_state:
        return
    st.session_state["notes"] = _read_json_file(str(NOTES_FILE)) if NOTES_FILE.exists() else {}


def save_favorites() -> None:
    try:
        with open(FAV_FILE, "w", encoding="utf-8") as f:
            json.dump(st.session_state["favorites"], f, ensure_ascii=False, indent=2)
        _read_json_file.clear()  # evita cache “velho”
    except Exception:
        pass


def passes_metadata_filters(art: dict, year_min: int, year_max: int, material_filter: str, place_filter: str) -> bool:
    dating = art.get("dating") or {}
    year = extract_year(dating)
    if year is not None and (year < year_min or year > year_max):
        return False

    if material_filter:
        materials = art.get("materials") or []
        if material_filter.lower() not in ", ".join(materials).lower():
            return False

    if place_filter:
        places = art.get("productionPlaces") or []
        if place_filter.lower() not in ", ".join(places).lower():
            return False

    return True


# ============================================================
# Session init (state FIRST)
# ============================================================
load_favorites()
st.session_state.setdefault("favorites", {})
favorites = st.session_state["favorites"]

load_notes()
st.session_state.setdefault("notes", {})
notes = st.session_state["notes"]

st.session_state.setdefault("results", [])
st.session_state.setdefault("search_meta", {})

# Analytics: page view (Explorer) — once per session
track_event_once(
    event="page_view",
    page="Explorer",
    once_key="page_view::Explorer",
    props={"has_favorites": bool(favorites), "favorites_count": len(favorites)},
)

# ============================================================
# Sidebar (sem form, botão no final)
# ============================================================
sidebar = st.sidebar
sidebar.header("🧭 Explore & Filter")

# ------------------------
# Search
# ------------------------
sidebar.subheader("Search")
search_term = sidebar.text_input(
    "Search term",
    value="Rembrandt",
    help="Type artist name, title, theme, etc.",
)

# ------------------------
# Basic filters
# ------------------------
sidebar.subheader("Basic filters")
object_type = sidebar.selectbox(
    "Object type",
    options=["Any", "painting", "print", "drawing", "sculpture", "photo", "other"],
    help="Filter by broad object category.",
)

sort_label = sidebar.selectbox(
    "Sort results by",
    options=[
        "Relevance (default)",
        "Artist name (A–Z)",
        "Date (oldest → newest)",
        "Date (newest → oldest)",
    ],
)
sort_map = {
    "Relevance (default)": "relevance",
    "Artist name (A–Z)": "artist",
    "Date (oldest → newest)": "chronologic",
    "Date (newest → oldest)": "achronologic",
}
sort_by = sort_map[sort_label]

num_results = sidebar.slider(
    "Number of results to request",
    min_value=6,
    max_value=30,
    value=12,
    step=3,
)

result_page = sidebar.number_input(
    "Result page",
    min_value=1,
    value=1,
    step=1,
    help="Page of results to request from the API (1 = first page).",
)

# Detecta mudança de página para disparar nova busca automaticamente
if "last_result_page" not in st.session_state:
    st.session_state["last_result_page"] = int(result_page)

page_changed = int(result_page) != int(st.session_state["last_result_page"])
if page_changed:
    st.session_state["last_result_page"] = int(result_page)

# ------------------------
# Advanced filters
# ------------------------
sidebar.subheader("Advanced filters")
year_min, year_max = sidebar.slider(
    "Year range (approx.)",
    min_value=1500,
    max_value=2025,
    value=(1600, 1900),
    step=10,
)
sidebar.caption(
    "Year range is applied after the API search, based on metadata returned by the Rijksmuseum API."
)

# ------------------------
# Text filters (helper)
# ------------------------
sidebar.markdown(
    """
**Text filters (helper)**

Text filters search inside the textual metadata of each artwork (title, long
title, description and notes returned by the API).

Use short keywords, for example:

- `self-portrait`
- `landscape`
- `night watch`
- `religious`
"""
)

# ------------------------
# Text filters (optional)
# ------------------------
sidebar.subheader("Text filters (optional)")
sidebar.caption(
    "These filters search inside the artwork metadata: materials and production places. "
    "Leave as '(any)' if you do not want to filter by text."
)

material_presets = [
    "(any)",
    "oil on canvas",
    "paper",
    "wood",
    "ink",
    "etching",
    "bronze",
    "silver",
    "porcelain",
]
material_choice = sidebar.selectbox(
    "Material contains",
    options=material_presets + ["Custom…"],
)
if material_choice == "(any)":
    material_filter = ""
elif material_choice == "Custom…":
    material_filter = sidebar.text_input(
        "Custom material filter",
        value="",
    )
else:
    material_filter = material_choice

place_presets = [
    "(any)",
    "Amsterdam",
    "Haarlem",
    "Delft",
    "Utrecht",
    "The Hague",
    "Rotterdam",
    "Leiden",
    "Antwerp",
    "Paris",
    "London",
    "Italy",
    "Germany",
    "Brazil",
]
place_choice = sidebar.selectbox(
    "Production place contains",
    options=place_presets + ["Custom…"],
)
if place_choice == "(any)":
    place_filter = ""
elif place_choice == "Custom…":
    place_filter = sidebar.text_input(
        "Custom production place filter",
        value="",
    )
else:
    place_filter = place_choice

# pequeno espaço antes do botão
sidebar.markdown("<div style='height: 0.75rem'></div>", unsafe_allow_html=True)

# Botão FINAL da sidebar (sem form, sem box)
run_search = sidebar.button(
    "🔍 Apply filters & search",
    use_container_width=True,
)

# aviso logo abaixo do botão
sidebar.caption(
    "Artworks marked as **In my selection** remain saved across searches and sessions. "
    "If you do not want previous selections to appear pre-selected in new searches, "
    "clear your selection on the **My Selection** page."
)

# mapeia o tipo para o parâmetro da API
object_type_param = None if object_type == "Any" else object_type
# ============================================================
# Main page
# ============================================================
st.markdown("### 🎨 Rijksmuseum Explorer")

if HERO_IMAGE_PATH.exists():
    st.markdown('<div class="rijks-hero">', unsafe_allow_html=True)
    st.image(str(HERO_IMAGE_PATH), width="stretch")
    st.markdown("</div>", unsafe_allow_html=True)

st.write(
    "Explore artworks from the Rijksmuseum collection. Use the sidebar to set your search term and filters, "
    "then view the results below. You can mark artworks to be part of your personal selection."
)

st.caption(
    "Tip: use the checkbox **“In my selection”** in each card to build your personal selection. "
    "You can then review, compare and export it on the **My Selection** page."
)

with st.expander("ℹ️ How the search works (quick guide)", expanded=False):
    st.markdown(
        """
- **Search term** → sent to the Rijksmuseum API as `q`.
- **Object type** → high-level category passed to the API (`type`).
- **Sort by** → official API sort modes (`relevance`, `artist`, `chronologic`, `achronologic`).
- **Advanced filters (year, material, production place)** → applied **locally** on top of the API results.

**Why can the header say “323 artworks” but the grid be empty?**

- The Rijksmuseum API may find many artworks that match your search term.
- Then the app applies your local filters (year range, *Material contains*, *Production place contains*).
- The line `Displaying A of B artwork(s)` means:
    - **B** = artworks reported by the API.
    - **A** = artworks that still match your **local filters**.
- If **A = 0** but **B > 0**, try broadening the local filters:
    - expand the year range,
    - set *Material contains* to **(any)**,
    - set *Production place contains* to **(any)**,
    - or relax one filter at a time to see what is excluding the artworks.
        """
    )

# placeholder para o contador de obras salvas (fica visualmente aqui em cima)
saved_pill_placeholder = st.empty()
# desenha o pill já com o número ATUAL de favoritos
saved_pill_placeholder.markdown(
    f'<div class="rijks-summary-pill">Saved artworks: '
    f'<strong>{len(favorites)}</strong></div>',
    unsafe_allow_html=True,
)


# ============================================================
# Search execution (when button or page changes)
# ============================================================
if run_search or page_changed:
    if not search_term.strip():
        st.warning("Please enter a search term before running the search.")
        st.session_state["results"] = []
        st.session_state["search_meta"] = {}
    else:
        try:
            with st.spinner("Searching artworks in the Rijksmuseum collection..."):
                # agora pedimos também a "page" da API
                raw_results, total_found = search_artworks(
                    query=search_term,
                    object_type=object_type_param,
                    sort=sort_by,
                    page_size=num_results,
                    page=result_page,
                )

            filtered_results = [
                art
                for art in (raw_results or [])
                if passes_metadata_filters(
                    art,
                    year_min=year_min,
                    year_max=year_max,
                    material_filter=material_filter,
                    place_filter=place_filter,
                )
            ]

            st.session_state["results"] = filtered_results
            # guardamos também page e page_size em meta
            st.session_state["search_meta"] = {
                "total_found": total_found,
                "api_count": len(raw_results or []),
                "filtered_count": len(filtered_results),
                "page": int(result_page),
                "page_size": int(num_results),
            }

            # garante que o pill está sincronizado com o favorites atual
            saved_pill_placeholder.markdown(
                f'<div class="rijks-summary-pill">Saved artworks: '
                f'<strong>{len(st.session_state.get("favorites", {}))}</strong></div>',
                unsafe_allow_html=True,
            )

        except RuntimeError as e:
            st.error(str(e))
            st.session_state["results"] = []
            st.session_state["search_meta"] = {}
        except Exception as e:
            st.error(f"Unexpected error while calling the Rijksmuseum API: {e}")
            st.session_state["results"] = []
            st.session_state["search_meta"] = {}

results = st.session_state.get("results", [])

# info de quantas obras estamos mostrando (sempre usando o meta ATUAL)
meta = st.session_state.get("search_meta", {})
if meta.get("filtered_count") is not None and meta.get("total_found") is not None:
    st.caption(
        f"Displaying **{meta['filtered_count']}** of **{meta['total_found']}** artwork(s) "
        f"that match your current filters."
    )

# ============================================================
# Results grid + selection tools
# ============================================================

results = st.session_state.get("results", [])

# ============================================================
# Selection tools for current results
# ============================================================
if results:
    st.markdown("### Selection tools for current results")

    col_add, col_remove = st.columns(2)

    # -------------------------------
    # ADD ALL results to selection
    # -------------------------------
    with col_add:
        add_all_clicked = st.button(
            "⭐ Add ALL results to my selection",
            use_container_width=True,
            key="btn_add_all_results",
        )

    # -------------------------------
    # REMOVE ALL results from selection
    # -------------------------------
    with col_remove:
        remove_all_clicked = st.button(
            "🗑️ Remove ALL results from my selection",
            use_container_width=True,
            key="btn_remove_all_results",
        )

    # 🔹 AVISO IMPORTANTE SOBRE ESSES BOTÕES
    st.caption(
        "Note: these buttons update your **global selection** "
        "(the same one shown on the *My Selection* page). "
        "If you want to remove only a few artworks, use the individual "
        "“In my selection” checkboxes in each card instead."
    )

    # Lógica ADD ALL
    if add_all_clicked:
        added = 0
        for art in results:
            obj_num = art.get("objectNumber")
            if not obj_num:
                continue
            if obj_num not in favorites:
                favorites[obj_num] = art
                added += 1
            st.session_state[f"fav_{obj_num}"] = True

        st.session_state["favorites"] = favorites
        save_favorites()

        saved_pill_placeholder.markdown(
            f'<div class="rijks-summary-pill">Saved artworks: '
            f'<strong>{len(favorites)}</strong></div>',
            unsafe_allow_html=True,
        )

        if added > 0:
            st.success(f"Added {added} artwork(s) to your selection.")
        else:
            st.info("All artworks in the current results were already in your selection.")

    # Lógica REMOVE ALL
    if remove_all_clicked:
        removed = 0
        for art in results:
            obj_num = art.get("objectNumber")
            if not obj_num:
                continue
            if obj_num in favorites:
                favorites.pop(obj_num)
                removed += 1
            st.session_state[f"fav_{obj_num}"] = False

        st.session_state["favorites"] = favorites
        save_favorites()

        saved_pill_placeholder.markdown(
            f'<div class="rijks-summary-pill">Saved artworks: '
            f'<strong>{len(favorites)}</strong></div>',
            unsafe_allow_html=True,
        )

        if removed > 0:
            st.success(f"Removed {removed} artwork(s) from your selection.")
        else:
            st.info("None of the current results were in your selection.")

# ------------------------------------------------------------
# Results grid (cards)
# ------------------------------------------------------------
if results:
    cards_per_row = 3
    for start_idx in range(0, len(results), cards_per_row):
        row_items = results[start_idx : start_idx + cards_per_row]
        cols = st.columns(len(row_items))

        for col, art in zip(cols, row_items):
            with col:
                st.markdown('<div class="rijks-card">', unsafe_allow_html=True)
                object_number = art.get("objectNumber")
                title = art.get("title", "Untitled")
                maker = art.get("principalOrFirstMaker", "Unknown artist")
                web_link = art.get("links", {}).get("web")

                note_text = notes.get(object_number, "") if object_number else ""
                has_notes = isinstance(note_text, str) and note_text.strip() != ""

                img_url = get_best_image_url(art)
                if img_url:
                    try:
                        st.image(img_url, width="stretch")
                    except Exception:
                        st.write("Error displaying image from API.")
                        st.markdown(
                            """
                            <div class="rijks-no-image-msg">
                            No public image is available via the API for this artwork.
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )
                else:
                    st.write("No valid image available via API.")
                    st.markdown(
                        """
                        <div class="rijks-no-image-msg">
                        No public image is available via the API for this artwork.
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                st.markdown(
                    f'<div class="rijks-card-title">{title}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="rijks-card-caption">{maker}</div>',
                    unsafe_allow_html=True,
                )

                # checkbox + favorites
                if object_number:
                    was_fav = object_number in favorites
                    checked = st.checkbox(
                        "In my selection",
                        value=was_fav,
                        key=f"fav_{object_number}",
                    )

                    if checked != was_fav:
                        if checked:
                            favorites[object_number] = art
                        else:
                            favorites.pop(object_number, None)
                        st.session_state["favorites"] = favorites
                        save_favorites()

                        saved_pill_placeholder.markdown(
                            f'<div class="rijks-summary-pill">Saved artworks: '
                            f'<strong>{len(favorites)}</strong></div>',
                            unsafe_allow_html=True,
                        )

                    is_fav = checked
                else:
                    is_fav = False

                badge_parts = []
                if is_fav:
                    badge_parts.append(
                        '<span class="rijks-badge rijks-badge-primary">⭐ In my selection</span>'
                    )
                if has_notes:
                    badge_parts.append(
                        '<span class="rijks-badge rijks-badge-secondary">📝 Notes</span>'
                    )
                if badge_parts:
                    st.markdown(
                        '<div class="rijks-badge-row">'
                        + " ".join(badge_parts)
                        + "</div>",
                        unsafe_allow_html=True,
                    )

                dating = art.get("dating") or {}
                presenting_date = dating.get("presentingDate")
                year = extract_year(dating) if dating else None
                if presenting_date:
                    st.text(f"Date: {presenting_date}")
                elif year:
                    st.text(f"Year: {year}")

                st.text(f"Object ID: {object_number}")
                if web_link:
                    st.markdown(f"[View on Rijksmuseum website]({web_link})")

                st.markdown("</div>", unsafe_allow_html=True)
else:
    meta = st.session_state.get("search_meta", {})
    total_found = meta.get("total_found", 0)

    if total_found and total_found > 0:
        st.warning(
            "The Rijksmuseum API found "
            f"**{total_found} artwork(s)** for your search term, "
            "but none match your **local filters** "
            "(year range, material or production place). "
            "Try broadening these filters to see the artworks."
        )
    else:
        st.info(
            "No artworks to display yet. Use the filters on the left and click "
            "“Apply filters & search” to retrieve artworks from the Rijksmuseum API."
        )