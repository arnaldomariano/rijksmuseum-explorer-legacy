# app.py
"""
Rijksmuseum Explorer - main page
""


import json
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
# Sidebar (FORM to avoid rerun on every interaction)
# ============================================================
st.sidebar.header("🧭 Explore & Filter")

with st.sidebar.form("search_form", clear_on_submit=False):
    st.sidebar.subheader("Search")
    search_term = st.sidebar.text_input(
        "Search term", value="Rembrandt", help="Type artist name, title, theme, etc."
    )

    st.sidebar.subheader("Basic filters")
    object_type = st.sidebar.selectbox(
        "Object type",
        options=["Any", "painting", "print", "drawing", "sculpture", "photo", "other"],
        help="Filter by broad object category.",
    )

    sort_label = st.sidebar.selectbox(
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

    num_results = st.sidebar.slider(
        "Number of results to request", min_value=6, max_value=30, value=12, step=3
    )

    st.sidebar.subheader("Advanced filters")
    year_min, year_max = st.sidebar.slider(
        "Year range (approx.)",
        min_value=1500,
        max_value=2025,
        value=(1600, 1900),
        step=10,
    )
    st.sidebar.caption(
        "Year range is applied after the API search, based on metadata returned by the Rijksmuseum API."
    )

    st.sidebar.subheader("Text filters (optional)")
    st.sidebar.caption("These filters search inside the artwork metadata: materials and production places.")

    material_presets = [
        "(any)", "oil on canvas", "paper", "wood", "ink", "etching", "bronze", "silver", "porcelain"
    ]
    material_choice = st.sidebar.selectbox("Material contains", options=material_presets + ["Custom…"])
    if material_choice == "(any)":
        material_filter = ""
    elif material_choice == "Custom…":
        material_filter = st.sidebar.text_input("Custom material filter", value="")
    else:
        material_filter = material_choice

    place_presets = [
        "(any)", "Amsterdam", "Haarlem", "Delft", "Utrecht", "The Hague", "Rotterdam",
        "Leiden", "Antwerp", "Paris", "London", "Italy", "Germany", "Brazil"
    ]
    place_choice = st.sidebar.selectbox("Production place contains", options=place_presets + ["Custom…"])
    if place_choice == "(any)":
        place_filter = ""
    elif place_choice == "Custom…":
        place_filter = st.sidebar.text_input("Custom production place filter", value="")
    else:
        place_filter = place_choice

    st.sidebar.markdown("---")
    run_search = st.form_submit_button("🔍 Apply filters & search", use_container_width=True)

st.sidebar.caption(
    "Artworks marked as **In my selection** remain saved across searches and sessions. "
    "If you do not want previous selections to appear pre-selected in new searches, "
    "clear your selection on the **My Selection** page."
)

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
- **Search term** → sent to the Rijksmuseum API as `q`
- **Object type** → high-level category
- **Sort by** → official API sort modes
- **Advanced filters** → applied after API (year/material/place)
        """
    )

st.markdown(
    f'<div class="rijks-summary-pill">Saved artworks: <strong>{len(favorites)}</strong></div>',
    unsafe_allow_html=True,
)

meta = st.session_state.get("search_meta", {})
if meta.get("filtered_count") is not None and meta.get("total_found") is not None:
    st.caption(f"Displaying **{meta['filtered_count']}** of **{meta['total_found']}** artwork(s) that match your current filters.")


# ============================================================
# Search execution (only when form submitted)
# ============================================================
if run_search:
    if not search_term.strip():
        st.warning("Please enter a search term before running the search.")
        st.session_state["results"] = []
        st.session_state["search_meta"] = {}
    else:
        try:
            with st.spinner("Searching artworks in the Rijksmuseum collection..."):
                raw_results, total_found = search_artworks(
                    query=search_term,
                    object_type=object_type_param,
                    sort=sort_by,
                    page_size=num_results,
                )

            filtered_results = [
                art for art in (raw_results or [])
                if passes_metadata_filters(
                    art,
                    year_min=year_min,
                    year_max=year_max,
                    material_filter=material_filter,
                    place_filter=place_filter,
                )
            ]

            st.session_state["results"] = filtered_results
            st.session_state["search_meta"] = {
                "total_found": total_found,
                "api_count": len(raw_results or []),
                "filtered_count": len(filtered_results),
            }

        except RuntimeError as e:
            st.error(str(e))
            st.session_state["results"] = []
            st.session_state["search_meta"] = {}
        except Exception as e:
            st.error(f"Unexpected error while calling the Rijksmuseum API: {e}")
            st.session_state["results"] = []
            st.session_state["search_meta"] = {}

results = st.session_state.get("results", [])


# ============================================================
# Results grid
# ============================================================
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

                is_fav = object_number in favorites if object_number else False
                note_text = notes.get(object_number, "") if object_number else ""
                has_notes = isinstance(note_text, str) and note_text.strip() != ""

                img_url = get_best_image_url(art)
                if img_url:
                    st.image(img_url, width="stretch")
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

                st.markdown(f'<div class="rijks-card-title">{title}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="rijks-card-caption">{maker}</div>', unsafe_allow_html=True)

                badge_parts = []
                if is_fav:
                    badge_parts.append('<span class="rijks-badge rijks-badge-primary">⭐ In my selection</span>')
                if has_notes:
                    badge_parts.append('<span class="rijks-badge rijks-badge-secondary">📝 Notes</span>')
                if badge_parts:
                    st.markdown('<div class="rijks-badge-row">' + " ".join(badge_parts) + "</div>", unsafe_allow_html=True)

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

                if object_number:
                    checked = st.checkbox("In my selection", value=is_fav, key=f"fav_{object_number}")
                    if checked and not is_fav:
                        favorites[object_number] = art
                        st.session_state["favorites"] = favorites
                        save_favorites()
                    elif not checked and is_fav:
                        favorites.pop(object_number, None)
                        st.session_state["favorites"] = favorites
                        save_favorites()

                st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info(
        "No artworks to display yet. Use the filters on the left and click "
        "“Apply filters & search” to retrieve artworks from the Rijksmuseum API."
    )

show_footer()