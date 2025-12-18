
import json
import io
import csv
import base64
from datetime import datetime
from textwrap import wrap

import requests
import streamlit as st

from app_paths import FAV_FILE, NOTES_FILE, PDF_META_FILE
from rijks_api import get_best_image_url
from analytics import track_event


# ============================================================
# Try to import reportlab for illustrated PDF export
# ============================================================
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader

    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# ============================================================
# Cache helpers
# ============================================================
@st.cache_data(show_spinner=False)
def cached_best_image_url(art: dict):
    return get_best_image_url(art)


# ============================================================
# PDF meta loader (shared with PDF_Setup page)
# ============================================================
def load_pdf_meta() -> dict:
    """
    Structure:
        {
            "opening_text": "...",
            "include_cover": true,
            "include_opening_text": true,
            "include_notes": true,
            "include_comments": true,
            "artwork_comments": { "objectNumber": "text", ... }
        }
    """
    if "pdf_meta" in st.session_state:
        return st.session_state["pdf_meta"]

    base = {
        "opening_text": "",
        "include_cover": True,
        "include_opening_text": True,
        "include_notes": True,
        "include_comments": True,
        "artwork_comments": {},
    }

    if PDF_META_FILE.exists():
        try:
            with open(PDF_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    base.update(data)
        except Exception:
            pass

    st.session_state["pdf_meta"] = base
    return base


# ============================================================
# Notes helpers
# ============================================================
def load_notes() -> None:
    if "notes" in st.session_state:
        return

    if NOTES_FILE.exists():
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state["notes"] = data if isinstance(data, dict) else {}
        except Exception:
            st.session_state["notes"] = {}
    else:
        st.session_state["notes"] = {}


def save_notes() -> None:
    try:
        with open(NOTES_FILE, "w", encoding="utf-8") as f:
            json.dump(
                st.session_state.get("notes", {}),
                f,
                ensure_ascii=False,
                indent=2,
            )
    except Exception:
        pass


# ============================================================
# Selection statistics helper
# ============================================================
def compute_selection_stats(favorites_dict: dict) -> dict:
    if not favorites_dict:
        return {"count": 0, "artists": 0, "min_year": None, "max_year": None}

    artworks = list(favorites_dict.values())
    artists = set()
    years: list[int] = []

    for art in artworks:
        maker = art.get("principalOrFirstMaker")
        if maker:
            artists.add(maker)

        dating = art.get("dating") or {}
        year = None

        if isinstance(dating.get("year"), int):
            year = dating["year"]
        else:
            presenting_date = dating.get("presentingDate")
            if isinstance(presenting_date, str) and presenting_date[:4].isdigit():
                try:
                    year = int(presenting_date[:4])
                except Exception:
                    year = None

        if year is not None:
            years.append(year)

    return {
        "count": len(artworks),
        "artists": len(artists),
        "min_year": min(years) if years else None,
        "max_year": max(years) if years else None,
    }


# ============================================================
# Internal metadata filters helper (within selection)
# ============================================================
def passes_selection_filters(
    art: dict,
    text_filter: str,
    year_min: int,
    year_max: int,
    artist_filter: str,
    object_type_filter: str,
) -> bool:
    dating = art.get("dating") or {}
    year_val = None

    if isinstance(dating.get("year"), int):
        year_val = dating["year"]
    else:
        presenting_date = dating.get("presentingDate")
        if isinstance(presenting_date, str) and presenting_date[:4].isdigit():
            try:
                year_val = int(presenting_date[:4])
            except Exception:
                year_val = None

    if year_val is not None and not (year_min <= year_val <= year_max):
        return False

    if text_filter:
        needle = text_filter.lower().strip()
        if needle:
            parts: list[str] = []

            for field in ("title", "longTitle", "principalOrFirstMaker"):
                value = art.get(field)
                if isinstance(value, str):
                    parts.append(value.lower())

            for field in ("materials", "techniques", "productionPlaces", "objectTypes"):
                values = art.get(field) or []
                if isinstance(values, list):
                    parts.extend(str(v).lower() for v in values)

            if needle not in " | ".join(parts):
                return False

    if artist_filter:
        artist = (art.get("principalOrFirstMaker") or "").lower()
        if artist_filter.lower().strip() not in artist:
            return False

    if object_type_filter:
        obj_types = art.get("objectTypes") or []
        if object_type_filter.lower().strip() not in ", ".join(obj_types).lower():
            return False

    return True


# ============================================================
# Custom CSS
# ============================================================
def inject_custom_css() -> None:
    st.markdown(
        """
        <style>
        .stApp { background-color: #111111; color: #f5f5f5; }

        div.block-container {
            max-width: 95vw;
            padding-left: 2rem;
            padding-right: 2rem;
            padding-top: 1.2rem;
            padding-bottom: 2.5rem;
        }

        @media (min-width: 1400px) {
            div.block-container {
                padding-left: 3rem;
                padding-right: 3rem;
            }
        }

        section[data-testid="stSidebar"] {
            background-color: #181818 !important;
        }

        h1, h2, h3 { font-weight: 600; }
        h2 { font-size: 1.5rem; margin-top: 0.5rem; margin-bottom: 0.75rem; }
        h3 { font-size: 1.15rem; margin-top: 1.25rem; margin-bottom: 0.5rem; }

        div[data-testid="stMarkdownContainer"] a {
            color: #ff9900 !important;
            text-decoration: none;
        }
        div[data-testid="stMarkdownContainer"] a:hover { text-decoration: underline; }

        .rijks-card {
            background-color: #181818;
            border-radius: 12px;
            padding: 0.75rem 0.75rem 0.9rem 0.75rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            border: 1px solid #262626;
            margin-bottom: 1rem;
            margin-top: 0.35rem;
        }

        .rijks-card.rijks-card-has-notes {
            border-color: #ffb347;
            box-shadow: 0 0 0 1px #ffb347, 0 2px 10px rgba(0,0,0,0.6);
        }

        .rijks-card.rijks-card-no-notes { opacity: 0.95; }

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

        .rijks-card-caption {
            font-size: 0.9rem;
            color: #c7c7c7;
            margin-bottom: 0.35rem;
        }

        .rijks-summary-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background-color: #262626;
            color: #f5f5f5;
            font-size: 0.85rem;
            margin-top: 0.5rem;
            margin-bottom: 1rem;
        }
        .rijks-summary-pill strong { color: #ff9900; }

        .rijks-export-panel {
            background-color: #181818;
            border-radius: 12px;
            padding: 1rem 1.25rem 1.1rem 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            border: 1px solid #262626;
            margin-top: 0.75rem;
            margin-bottom: 1.5rem;
        }

        .export-card {
            background-color: #202020;
            border-radius: 12px;
            padding: 0.8rem 0.9rem 0.95rem 0.9rem;
            border: 1px solid #333333;
            box-shadow: 0 2px 6px rgba(0,0,0,0.45);
            text-align: center;
        }

        .export-card h4 { margin: 0 0 0.4rem 0; font-size: 0.95rem; }
        .export-card p { font-size: 0.8rem; color: #c7c7c7; margin-bottom: 0.6rem; }

        .rijks-footer {
            margin-top: 2.5rem;
            padding-top: 0.75rem;
            border-top: 1px solid #262626;
            font-size: 0.8rem;
            color: #aaaaaa;
            text-align: center;
        }

        /* =========================================
           Gallery card micro-refinements
        ========================================= */

        .rijks-card-title {
            font-size: 0.95rem;
            line-height: 1.25;
            margin-top: 0.5rem;
            color: #f1f1f1;
        }

        .rijks-card-caption {
            font-size: 0.8rem;
            color: #b8b8b8;
            margin-bottom: 0.25rem;
        }

        .rijks-card:hover {
            background-color: rgba(255, 255, 255, 0.02);
        }

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
# PDF builder (illustrated)
# ============================================================
def build_pdf_buffer(favorites: dict, notes: dict) -> bytes | None:
    if not REPORTLAB_AVAILABLE or not favorites:
        return None

    pdf_meta = load_pdf_meta()
    include_cover = bool(pdf_meta.get("include_cover", True))
    include_opening_text = bool(pdf_meta.get("include_opening_text", True))
    include_notes_flag = bool(pdf_meta.get("include_notes", True))
    include_comments_flag = bool(pdf_meta.get("include_comments", True))
    opening_text_cfg = (pdf_meta.get("opening_text") or "").strip()
    artwork_comments = pdf_meta.get("artwork_comments") or {}

    pdf_buffer = io.BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=A4)
    page_width, page_height = A4

    margin_left, margin_right = 50, 50
    margin_top = page_height - 80
    margin_bottom = 60

    def draw_footer():
        c.setFont("Helvetica", 8)
        footer_left = f"Rijksmuseum Explorer — My selection ({len(favorites)} artworks)"
        generated_on = datetime.now().strftime("%Y-%m-%d %H:%M")
        footer_right = f"Generated on {generated_on}"
        y_footer = margin_bottom
        c.drawString(margin_left, y_footer, footer_left)
        c.drawRightString(page_width - margin_right, y_footer, footer_right)

    def draw_text_block(title: str, text: str, y_start: float, cont_header: str) -> float:
        text = (text or "").strip()
        if not text:
            return y_start

        if y_start < margin_bottom + 40:
            draw_footer()
            c.showPage()
            c.setFont("Helvetica-Bold", 12)
            c.drawString(margin_left, margin_top, cont_header)
            y_start = margin_top - 30

        c.setFont("Helvetica-Oblique", 11)
        c.drawString(margin_left, y_start, title)

        y = y_start - 18
        c.setFont("Helvetica", 10)

        for line in wrap(text, width=90):
            if y < margin_bottom + 20:
                draw_footer()
                c.showPage()
                c.setFont("Helvetica-Bold", 12)
                c.drawString(margin_left, margin_top, cont_header)
                y = margin_top - 30
                c.setFont("Helvetica", 10)
            c.drawString(margin_left, y, line)
            y -= 14

        return y

    total = len(favorites)

    # Cover
    if include_cover:
        cover_title = "Rijksmuseum Explorer — My selection"
        generated_on = datetime.now().strftime("%Y-%m-%d %H:%M")

        c.setFont("Helvetica-Bold", 24)
        c.drawString(margin_left, page_height - 180, cover_title)

        c.setFont("Helvetica", 11)
        c.drawString(margin_left, page_height - 220, f"Generated on: {generated_on}")
        c.drawString(margin_left, page_height - 238, f"{total} artwork(s) in this selection")

        draw_footer()
        c.showPage()

    # Opening text
    if include_opening_text and opening_text_cfg:
        c.setFont("Helvetica-Bold", 16)
        c.drawString(margin_left, margin_top, "Introduction")

        y = margin_top - 35
        c.setFont("Helvetica", 11)

        for line in wrap(opening_text_cfg, width=90):
            if y < margin_bottom + 20:
                draw_footer()
                c.showPage()
                c.setFont("Helvetica-Bold", 16)
                c.drawString(margin_left, margin_top, "Introduction (cont.)")
                y = margin_top - 35
                c.setFont("Helvetica", 11)
            c.drawString(margin_left, y, line)
            y -= 15

        draw_footer()
        c.showPage()

    # Contents
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin_left, margin_top, "Contents")

    y = margin_top - 35
    c.setFont("Helvetica", 11)

    for idx, (obj_num, art) in enumerate(favorites.items(), start=1):
        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")
        line = f"{idx}. {title} — {maker} (ID: {obj_num})"

        for wrapped_line in wrap(line, width=90):
            if y < margin_bottom + 20:
                draw_footer()
                c.showPage()
                c.setFont("Helvetica-Bold", 16)
                c.drawString(margin_left, margin_top, "Contents (cont.)")
                y = margin_top - 35
                c.setFont("Helvetica", 11)
            c.drawString(margin_left, y, wrapped_line)
            y -= 15

    draw_footer()
    c.showPage()

    # One artwork per page
    for idx, (obj_num, art) in enumerate(favorites.items(), start=1):
        c.setFont("Helvetica-Bold", 18)
        c.drawString(margin_left, margin_top, "Rijksmuseum Selection")
        c.setFont("Helvetica", 11)
        c.drawString(margin_left, margin_top - 24, f"Artwork {idx} of {total}")

        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")
        dating = art.get("dating", {}) or {}
        date = dating.get("presentingDate") or dating.get("year") or ""
        link = art.get("links", {}).get("web", "")
        img_url = get_best_image_url(art)

        thumb_w, thumb_h = 170, 170
        x_image = margin_left
        y_image_top = margin_top - 80
        x_text = x_image + thumb_w + 25
        y_text = y_image_top

        image_drawn = False

        if img_url:
            try:
                resp = requests.get(img_url, timeout=8)
                resp.raise_for_status()
                image_data = io.BytesIO(resp.content)
                img_reader = ImageReader(image_data)

                iw, ih = img_reader.getSize()
                ratio = min(thumb_w / iw, thumb_h / ih)
                draw_w, draw_h = iw * ratio, ih * ratio

                c.drawImage(
                    img_reader,
                    x_image,
                    y_image_top - draw_h,
                    width=draw_w,
                    height=draw_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                image_drawn = True
            except Exception:
                pass

        c.setFont("Helvetica-Bold", 14)
        c.drawString(x_text, y_text, title)

        c.setFont("Helvetica", 11)
        y_text -= 18
        c.drawString(x_text, y_text, f"Artist: {maker}")

        if date:
            y_text -= 14
            c.drawString(x_text, y_text, f"Date: {date}")

        y_text -= 14
        c.drawString(x_text, y_text, f"Object ID: {obj_num}")

        if link:
            y_text -= 14
            short_link = link.replace("https://", "")
            c.drawString(x_text, y_text, f"Link: {short_link}")

        y_cursor = (y_image_top - thumb_h - 40) if image_drawn else (y_text - 28)
        y_cursor = min(y_cursor, y_text - 28)

        if include_comments_flag:
            comment_text = artwork_comments.get(obj_num, "")
            y_cursor = draw_text_block(
                "Commentary:",
                comment_text,
                y_cursor,
                f"Commentary (cont.) — {obj_num}",
            )

        if include_notes_flag:
            note_text = notes.get(obj_num, "")
            note_text = note_text.strip() if isinstance(note_text, str) else ""
            y_cursor = draw_text_block(
                "Research notes:",
                note_text,
                y_cursor,
                f"Notes (cont.) — {obj_num}",
            )

        draw_footer()
        c.showPage()

    c.save()
    pdf_buffer.seek(0)
    return pdf_buffer.getvalue()


# ============================================================
# Page header
# ============================================================
st.markdown("## ⭐ My selection")

st.write(
    "This page shows all artworks you have saved in your selection. "
    "Selections are stored locally in a small favorites file so they can be "
    "restored when you reopen or reload the app. "
    "From here you can also select two artworks to compare them side by side."
)

st.caption(
    "Selections and research notes are stored locally on this device "
    "(favorites and notes files). "
    "If you want to start a completely fresh search with no pre-selected artworks, "
    "use **Clear my entire selection** below."
)


# ============================================================
# Load favorites & notes
# ============================================================
if "favorites" not in st.session_state:
    if FAV_FILE.exists():
        try:
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                st.session_state["favorites"] = data if isinstance(data, dict) else {}
        except Exception:
            st.session_state["favorites"] = {}
    else:
        st.session_state["favorites"] = {}

favorites: dict = st.session_state["favorites"]

load_notes()
notes: dict = st.session_state.get("notes", {})

# UI hint: show sidebar collapse tip only once
if "sidebar_tip_dismissed" not in st.session_state:
    st.session_state["sidebar_tip_dismissed"] = False

if "sidebar_tip_version" not in st.session_state:
    st.session_state["sidebar_tip_version"] = 1


# ============================================================
# Analytics — page view (only once per session)
# ============================================================
if "analytics_my_selection_viewed" not in st.session_state:
    st.session_state["analytics_my_selection_viewed"] = True
    track_event(
        event="page_view",
        page="My_Selection",
        props={
            "has_favorites": bool(favorites),
            "favorites_count": len(favorites) if isinstance(favorites, dict) else 0,
        },
    )

# ============================================================
# Empty selection
# ============================================================
if not favorites:
    st.info(
        "You currently have no artworks in your selection. "
        "Go to the **Rijksmuseum Explorer** page and mark "
        "**In my selection** on any artwork you want to keep."
    )
    show_footer()
    st.stop()


# ============================================================
# Selection statistics
# ============================================================
stats = compute_selection_stats(favorites)

noted_ids = [
    obj_num
    for obj_num, text in notes.items()
    if isinstance(text, str) and text.strip() and obj_num in favorites
]
num_noted = len(noted_ids)

st.markdown(
    f'<div class="rijks-summary-pill">'
    f'You have <strong>{stats["count"]}</strong> artwork(s) in your selection.'
    f"</div>",
    unsafe_allow_html=True,
)

with st.expander("📊 Selection insights", expanded=True):
    st.write(f"- **Number of artworks:** {stats['count']}")
    st.write(f"- **Distinct artists:** {stats['artists']}")
    st.write(f"- **Artworks with research notes:** {num_noted}")

    if stats["min_year"] and stats["max_year"]:
        if stats["min_year"] == stats["max_year"]:
            st.write(f"- **Approximate date:** around **{stats['min_year']}**")
        else:
            st.write(
                f"- **Approximate date range:** "
                f"from **{stats['min_year']}** to **{stats['max_year']}**"
            )
    else:
        st.write("- **Date range:** not available from API metadata.")


# ============================================================
# Sidebar controls
# ============================================================
default_min_year = stats["min_year"] if stats["min_year"] is not None else 1400
default_max_year = stats["max_year"] if stats["max_year"] is not None else 2025

with st.sidebar:
    st.markdown("## 🔧 My Selection Controls")

    # One-time sidebar collapse hint
    if not st.session_state.get("sidebar_tip_dismissed", False):
        with st.container():
            st.info(
                "💡 Tip: You can collapse this panel using the « icon on the top left.",
                icon="ℹ️",
            )
            if st.button("Got it", key="dismiss_sidebar_tip"):
                st.session_state["sidebar_tip_dismissed"] = True
                st.rerun()

    # Internal filters
    with st.expander("🔍 Filter within selection", expanded=False):
        text_filter = st.text_input(
            "Search in title, artist, materials, techniques or places",
            value="",
            key="sb_text_filter",
        )

        year_min, year_max = st.slider(
            "Approximate year range",
            min_value=1400,
            max_value=2025,
            value=(default_min_year, default_max_year),
            step=10,
            key="sb_year_range",
        )

        artist_filter = st.text_input(
            "Artist contains",
            value="",
            key="sb_artist_filter",
        )

        object_type_filter = st.text_input(
            "Object type contains",
            value="",
            key="sb_object_type_filter",
        )

    # High-level notes filter
    total_artworks = stats["count"]
    total_with_notes = num_noted
    total_without_notes = total_artworks - total_with_notes

    options_labels = [
        f"All artworks ({total_artworks})",
        f"Only artworks with notes ({total_with_notes})",
        f"Only artworks without notes ({total_without_notes})",
    ]

    selection_filter_label = st.radio(
        "Show in gallery:",
        options=options_labels,
        index=0,
        key="selection_filter_radio",
    )

    # Notes keyword filter
    note_filter = st.text_input(
        "Notes keyword filter (optional)",
        value="",
        key="note_filter",
    )
    note_filter_lower = note_filter.strip().lower()

    # Gallery controls
    st.markdown("### 🧭 Gallery")

    sort_label = st.selectbox(
        "Order artworks by",
        options=[
            "Default (as saved)",
            "Artist (A–Z)",
            "Title (A–Z)",
            "Year (oldest → newest)",
            "Year (newest → oldest)",
            "Notes first",
        ],
        index=0,
        key="sb_sort_label",
    )

    gallery_view = st.selectbox(
        "Gallery view mode",
        options=["Grid (default)", "Group by artist"],
        index=0,
        key="sb_gallery_view",
    )

    show_images = st.toggle(
        "Show thumbnails",
        value=True,
        key="show_images_toggle",
    )

    compact_mode = st.toggle(
        "Compact gallery mode",
        value=False,
        key="compact_mode_toggle",
    )


# ============================================================
# Derived flags from sidebar
# ============================================================
if selection_filter_label.startswith("All artworks"):
    selection_filter_code = "all"
elif "with notes" in selection_filter_label:
    selection_filter_code = "with_notes"
else:
    selection_filter_code = "without_notes"

group_by_artist = (gallery_view == "Group by artist")
cards_per_row = 5 if compact_mode else 3

filters_active = any(
    [
        text_filter.strip(),
        artist_filter.strip(),
        object_type_filter.strip(),
        (year_min, year_max) != (1400, 2025),
    ]
)


# ============================================================
# Apply internal metadata filters
# ============================================================
filtered_favorites: dict = favorites
if filters_active:
    filtered_favorites = {
        obj_num: art
        for obj_num, art in favorites.items()
        if passes_selection_filters(
            art=art,
            text_filter=text_filter,
            year_min=year_min,
            year_max=year_max,
            artist_filter=artist_filter,
            object_type_filter=object_type_filter,
        )
    }
    st.caption(
        f"Showing {len(filtered_favorites)} of {len(favorites)} artworks "
        f"after internal metadata filters."
    )
else:
    st.caption("No internal metadata filter applied (showing all artworks in your selection).")


# ============================================================
# Export panel
# ============================================================
st.markdown('<div class="rijks-export-panel">', unsafe_allow_html=True)
st.markdown("### Export & share selection")

rows: list[list[str]] = []
for obj_num, art in favorites.items():
    title = art.get("title", "")
    maker = art.get("principalOrFirstMaker", "")
    dating = art.get("dating", {}) or {}
    date = dating.get("presentingDate") or dating.get("year") or ""
    link = art.get("links", {}).get("web", "")
    rows.append([obj_num, title, maker, date, link])

csv_data = None
if rows:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["objectNumber", "title", "artist", "date", "web_link"])
    writer.writerows(rows)
    csv_data = buffer.getvalue()

favorites_json_pretty = json.dumps(favorites, ensure_ascii=False, indent=2)
favorites_json_compact = json.dumps(favorites, ensure_ascii=False)
collection_code = base64.b64encode(favorites_json_compact.encode("utf-8")).decode("ascii")

notes_rows: list[list[str]] = []
for obj_num, art in favorites.items():
    note_text = notes.get(obj_num, "")
    note_text = note_text.strip() if isinstance(note_text, str) else ""
    if not note_text:
        continue

    title = art.get("title", "")
    maker = art.get("principalOrFirstMaker", "")
    notes_rows.append([obj_num, title, maker, note_text])

notes_csv_data = None
if notes_rows:
    notes_buffer = io.StringIO()
    notes_writer = csv.writer(notes_buffer)
    notes_writer.writerow(["objectNumber", "title", "artist", "note"])
    notes_writer.writerows(notes_rows)
    notes_csv_data = notes_buffer.getvalue()

notes_json = json.dumps(notes, ensure_ascii=False, indent=2)

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown('<div class="export-card">', unsafe_allow_html=True)
    st.markdown("<h4>CSV</h4>", unsafe_allow_html=True)
    st.markdown("<p>Table format for Excel/Sheets.</p>", unsafe_allow_html=True)
    if csv_data:
        clicked = st.download_button(
            "📄 Download CSV",
            csv_data,
            "rijks_selection.csv",
            "text/csv",
            key="dl_selection_csv",
        )
        if clicked:
            track_event(
                event="export_download",
                page="My_Selection",
                props={"format": "csv", "scope": "selection", "count": len(favorites)},
            )
    else:
        st.caption("No data.")
    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown('<div class="export-card">', unsafe_allow_html=True)
    st.markdown("<h4>JSON</h4>", unsafe_allow_html=True)
    st.markdown("<p>For scripts, apps and APIs.</p>", unsafe_allow_html=True)
    clicked = st.download_button(
        "🧾 Download JSON",
        favorites_json_pretty,
        "rijks_selection.json",
        "application/json",
        key="dl_selection_json",
    )
    if clicked:
        track_event(
            event="export_download",
            page="My_Selection",
            props={"format": "json", "scope": "selection", "count": len(favorites)},
        )
    st.markdown("</div>", unsafe_allow_html=True)

with col3:
    st.markdown('<div class="export-card">', unsafe_allow_html=True)
    st.markdown("<h4>PDF</h4>", unsafe_allow_html=True)
    st.markdown("<p>Printable report of your selection.</p>", unsafe_allow_html=True)

    if "pdf_buffer" not in st.session_state:
        st.session_state["pdf_buffer"] = None

    if st.button("Prepare PDF", key="prepare_pdf_btn"):
        track_event(
            event="export_prepare",
            page="My_Selection",
            props={"format": "pdf", "scope": "selection", "count": len(favorites)},
        )

        if not REPORTLAB_AVAILABLE:
            st.warning("Install `reportlab` to enable PDF export.")
        else:
            with st.spinner("Preparing PDF with thumbnails..."):
                buf = build_pdf_buffer(favorites, notes)
            if buf:
                st.session_state["pdf_buffer"] = buf
                st.success("PDF ready!")
            else:
                st.warning("PDF could not be generated.")

    if st.session_state["pdf_buffer"]:
        clicked = st.download_button(
            "📑 Download PDF",
            st.session_state["pdf_buffer"],
            "rijks_selection.pdf",
            "application/pdf",
            key="dl_selection_pdf",
        )
        if clicked:
            track_event(
                event="export_download",
                page="My_Selection",
                props={"format": "pdf", "scope": "selection", "count": len(favorites)},
            )

    st.markdown("</div>", unsafe_allow_html=True)

with col4:
    st.markdown('<div class="export-card">', unsafe_allow_html=True)
    st.markdown("<h4>Share & notes</h4>", unsafe_allow_html=True)
    st.markdown("<p>Share your selection and export research notes.</p>", unsafe_allow_html=True)

    with st.expander("🔗 Share selection code", expanded=False):
        st.caption("Copy this code to share your selection with another user:")
        st.code(collection_code, language=None)

        import_code = st.text_area(
            "Collection code to import",
            value="",
            height=80,
            key="import_code",
        )

        if st.button("Load selection from code"):
            if not import_code.strip():
                st.warning("Please paste a collection code first.")
            else:
                try:
                    decoded = base64.b64decode(import_code.encode("ascii")).decode("utf-8")
                    data = json.loads(decoded)
                    if isinstance(data, dict):
                        st.session_state["favorites"] = data
                        try:
                            with open(FAV_FILE, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        st.success("Selection loaded successfully from code.")
                        st.rerun()
                    else:
                        st.error("The code is valid text but not in the expected format.")
                except Exception as e:
                    st.error(f"Could not decode the collection code: {e}")

    with st.expander("📝 Export research notes", expanded=False):
        st.caption("Download your research notes for use in Excel/Sheets or in other tools.")

        if notes_csv_data:
            clicked = st.download_button(
                "📄 Download notes (CSV)",
                notes_csv_data,
                "rijks_notes.csv",
                "text/csv",
                key="dl_notes_csv",
            )
            if clicked:
                track_event(
                    event="export_download",
                    page="My_Selection",
                    props={"format": "csv", "scope": "notes", "count": len(notes_rows)},
                )
        else:
            st.caption("No notes available yet.")

        clicked = st.download_button(
            "🧾 Download notes (JSON)",
            notes_json,
            "rijks_notes.json",
            "application/json",
            key="dl_notes_json",
        )
        if clicked:
            track_event(
                event="export_download",
                page="My_Selection",
                props={"format": "json", "scope": "notes", "count": len(notes_rows)},
            )

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# Clear entire selection
# ============================================================
if st.button("Clear my entire selection"):
    st.session_state["favorites"] = {}
    try:
        with open(FAV_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    # limpa qualquer checkbox de comparação
    for key in list(st.session_state.keys()):
        if key.startswith("cmp_from_sel_"):
            del st.session_state[key]

    st.session_state["detail_art_id"] = None
    st.success("Your selection has been cleared.")
    st.rerun()


# ============================================================
# Gallery + comparison logic helpers
# ============================================================
def get_year_for_sort(art: dict):
    dating = art.get("dating") or {}
    y = dating.get("year")
    if isinstance(y, int):
        return y
    pd = dating.get("presentingDate")
    if isinstance(pd, str) and len(pd) >= 4 and pd[:4].isdigit():
        try:
            return int(pd[:4])
        except Exception:
            return None
    return None


def has_note_text(obj_num: str) -> bool:
    txt = notes.get(obj_num, "")
    return isinstance(txt, str) and txt.strip() != ""


def has_note(obj_id: str) -> bool:
    txt = notes.get(obj_id, "")
    return isinstance(txt, str) and txt.strip() != ""

# ------------------------------------------------------------
# Flag para limpar TODOS os checkboxes de comparação
# ------------------------------------------------------------
if "clear_compare_flag" not in st.session_state:
    st.session_state["clear_compare_flag"] = False

# Se o flag vier ligado de um clique em "Clear comparison",
# apagamos TODAS as chaves de comparação ANTES de criar qualquer checkbox.
if st.session_state["clear_compare_flag"]:
    for key in list(st.session_state.keys()):
        if key.startswith("cmp_from_sel_"):
            del st.session_state[key]
    st.session_state["clear_compare_flag"] = False

# ------------------------------------------------------------
# Base items = favoritos após filtros de METADADOS
# ------------------------------------------------------------
base_items: list[tuple[str, dict]] = list(filtered_favorites.items())

# -----------------------------
# Ordenação global
# -----------------------------
if sort_label == "Artist (A–Z)":
    base_items.sort(
        key=lambda item: (
            item[1].get("principalOrFirstMaker", ""),
            item[1].get("title", ""),
        )
    )
elif sort_label == "Title (A–Z)":
    base_items.sort(
        key=lambda item: (
            item[1].get("title", ""),
            item[1].get("principalOrFirstMaker", ""),
        )
    )
elif sort_label == "Year (oldest → newest)":
    base_items.sort(
        key=lambda item: (
            get_year_for_sort(item[1]) is None,
            get_year_for_sort(item[1]) or 10**9,
        )
    )
elif sort_label == "Year (newest → oldest)":
    base_items.sort(
        key=lambda item: (
            get_year_for_sort(item[1]) is None,
            -(get_year_for_sort(item[1]) or -10**9),
        )
    )
elif sort_label == "Notes first":
    base_items.sort(
        key=lambda item: (
            not has_note_text(item[0]),
            item[1].get("principalOrFirstMaker", ""),
            item[1].get("title", ""),
        )
    )

# -----------------------------
# Filtro por palavra nas notes
# -----------------------------
if note_filter_lower:
    base_items = [
        (obj_num, art)
        for obj_num, art in base_items
        if note_filter_lower in (notes.get(obj_num, "") or "").lower()
    ]

# -----------------------------
# Filtro de alto nível: com/sem notes
# -----------------------------
if selection_filter_code == "with_notes":
    base_items = [(obj_num, art) for obj_num, art in base_items if has_note(obj_num)]
elif selection_filter_code == "without_notes":
    base_items = [(obj_num, art) for obj_num, art in base_items if not has_note(obj_num)]

# ------------------------------------------------------------
# Resumo após TODOS os filtros
# ------------------------------------------------------------
total_after_filters = len(base_items)
artists_after_filters = len(
    {
        (art.get("principalOrFirstMaker") or "Unknown artist")
        for _, art in base_items
    }
)

st.caption(
    f"Current view: **{total_after_filters}** artwork(s) "
    f"from **{artists_after_filters}** artist(s) after all filters."
)

# -----------------------------
# Caso vazio
# -----------------------------
if not base_items:
    st.info(
        "No artworks match the current filters "
        "(metadata filters, notes keyword and notes status)."
    )

else:
    # ---------------------------------------------------------
    # Resumo dos filtros ativos
    # ---------------------------------------------------------
    filters_summary: list[str] = []

    if filters_active:
        if text_filter.strip():
            filters_summary.append(f"text contains '{text_filter.strip()}'")
        if (year_min, year_max) != (1400, 2025):
            filters_summary.append(f"year between {year_min}-{year_max}")
        if artist_filter.strip():
            filters_summary.append(f"artist contains '{artist_filter.strip()}'")
        if object_type_filter.strip():
            filters_summary.append(
                f"object type contains '{object_type_filter.strip()}'"
            )

    if selection_filter_code == "with_notes":
        filters_summary.append("only artworks with notes")
    elif selection_filter_code == "without_notes":
        filters_summary.append("only artworks without notes")

    if note_filter_lower:
        filters_summary.append(f"notes contain '{note_filter}'")

    filters_summary.append(
        "view: group by artist" if group_by_artist else "view: grid"
    )

    if filters_summary:
        st.caption("Active filters: " + " · ".join(filters_summary))
    else:
        st.caption("Active filters: none (full selection).")

    # =========================================================
    # RENDERIZAÇÃO DOS CARDS (sem mexer em comparação aqui)
    # =========================================================
    def render_cards(items: list[tuple[str, dict]], allow_compare: bool):
        for start_idx in range(0, len(items), cards_per_row):
            row_items = items[start_idx : start_idx + cards_per_row]
            cols = st.columns(len(row_items))

            for col, (obj_num, art) in zip(cols, row_items):
                with col:
                    note_for_this = notes.get(obj_num, "")
                    has_notes_flag = isinstance(note_for_this, str) and note_for_this.strip()

                    card_classes = "rijks-card"
                    card_classes += " rijks-card-has-notes" if has_notes_flag else " rijks-card-no-notes"

                    st.markdown(f'<div class="{card_classes}">', unsafe_allow_html=True)

                    img_url = cached_best_image_url(art)

                    if show_images:
                        if img_url:
                            try:
                                st.image(img_url, use_container_width=True)
                            except Exception:
                                st.write("Error displaying image.")
                        else:
                            st.write("No valid image available via API.")
                    else:
                        st.caption("Thumbnails hidden for faster browsing.")

                    title = art.get("title", "Untitled")
                    maker = art.get("principalOrFirstMaker", "Unknown artist")

                    if compact_mode and isinstance(title, str) and len(title) > 60:
                        title = title[:57] + "..."

                    web_link = art.get("links", {}).get("web")
                    dating = art.get("dating", {}) or {}
                    presenting_date = dating.get("presentingDate")
                    year = dating.get("year")

                    st.markdown(
                        f'<div class="rijks-card-title">{title}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="rijks-card-caption">{maker}</div>',
                        unsafe_allow_html=True,
                    )

                    if has_notes_flag:
                        st.caption("📝 Notes available for this artwork")

                    if presenting_date:
                        st.text(f"Date: {presenting_date}")
                    elif year:
                        st.text(f"Year: {year}")

                    st.text(f"Object ID: {obj_num}")

                    if web_link:
                        st.markdown(f"[View on Rijksmuseum website]({web_link})")

                    with st.expander("More details"):
                        long_title = art.get("longTitle")
                        object_types = art.get("objectTypes")
                        materials = art.get("materials")
                        techniques = art.get("techniques")
                        production_places = art.get("productionPlaces")

                        if long_title and long_title != title:
                            st.write(f"**Long title:** {long_title}")
                        if object_types:
                            st.write(f"**Object type(s):** {', '.join(object_types)}")
                        if materials:
                            st.write(f"**Materials:** {', '.join(materials)}")
                        if techniques:
                            st.write(f"**Techniques:** {', '.join(techniques)}")
                        if production_places:
                            st.write(f"**Production place(s): {', '.join(production_places)}")

                    if allow_compare:
                        cmp_key = f"cmp_from_sel_{obj_num}"
                        st.checkbox(
                            "Select for comparison",
                            key=cmp_key,
                        )

                    if st.button("View details", key=f"detail_btn_{obj_num}"):
                        st.session_state["detail_art_id"] = obj_num

                    if st.button("Remove from my selection", key=f"remove_card_{obj_num}"):

                        track_event(
                            event="selection_remove_item",
                            page="My_Selection",
                            props={
                                "object_id": obj_num,
                                "artist": art.get("principalOrFirstMaker"),
                                "had_notes": bool((st.session_state.get("notes", {}).get(obj_num) or "").strip()),
                                "prev_count": len(favorites),
                                "origin": "card",
                            },
                        )

                        favorites.pop(obj_num, None)
                        st.session_state["favorites"] = favorites

                        try:
                            with open(FAV_FILE, "w", encoding="utf-8") as f:
                                json.dump(favorites, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass

                        # limpa checkbox dessa obra, se existir
                        cmp_key = f"cmp_from_sel_{obj_num}"
                        if cmp_key in st.session_state:
                            del st.session_state[cmp_key]

                        if st.session_state.get("detail_art_id") == obj_num:
                            st.session_state["detail_art_id"] = None

                        if "notes" in st.session_state:
                            st.session_state["notes"].pop(obj_num, None)
                            try:
                                with open(NOTES_FILE, "w", encoding="utf-8") as f:
                                    json.dump(
                                        st.session_state["notes"],
                                        f,
                                        ensure_ascii=False,
                                        indent=2,
                                    )
                            except Exception:
                                pass

                        st.success("Artwork removed from your selection.")
                        st.rerun()

                    st.markdown("</div>", unsafe_allow_html=True)

    # =========================================================
    # MODE A) GROUP BY ARTIST
    # =========================================================
    if group_by_artist:
        st.markdown("### 👤 Artists overview")

        artists_per_page = st.select_slider(
            "Artists per page",
            options=[3, 5, 8, 12, 20],
            value=5,
        )

        sort_within_artist = st.selectbox(
            "Order artworks within each artist",
            options=[
                "Default (as saved)",
                "Title (A–Z)",
                "Year (oldest → newest)",
                "Year (newest → oldest)",
                "Notes first",
            ],
            index=0,
        )

        expand_artists = st.toggle(
            "Expand artist groups",
            value=False,
            help="Turn on to open all artist blocks by default.",
        )

        enable_compare_grouped = st.toggle(
            "Enable comparison in grouped view",
            value=False,
            help="Allow selecting artworks for comparison inside artist groups.",
            key="enable_compare_grouped_toggle",
        )

        # Agrupa por artista
        grouped: dict[str, list[tuple[str, dict]]] = {}
        for obj_num, art in base_items:
            artist = art.get("principalOrFirstMaker") or "Unknown artist"
            grouped.setdefault(artist, []).append((obj_num, art))

        artist_names = sorted(grouped.keys(), key=lambda x: x.lower())

        total_artists = len(artist_names)
        max_pages = max(1, (total_artists + artists_per_page - 1) // artists_per_page)

        page = st.number_input(
            "Artist page",
            min_value=1,
            max_value=max_pages,
            value=1,
            step=1,
        )

        start_a = (page - 1) * artists_per_page
        end_a = start_a + artists_per_page
        page_artists = artist_names[start_a:end_a]

        st.caption(
            f"Showing artist page {page} of {max_pages} — "
            f"{total_artists} artist(s) and {len(base_items)} artwork(s) total after filters."
        )

        def sort_items_for_artist(items: list[tuple[str, dict]]):
            if sort_within_artist == "Title (A–Z)":
                items.sort(
                    key=lambda it: (
                        it[1].get("title", ""),
                        it[1].get("principalOrFirstMaker", ""),
                    )
                )
            elif sort_within_artist == "Year (oldest → newest)":
                items.sort(
                    key=lambda it: (
                        get_year_for_sort(it[1]) is None,
                        get_year_for_sort(it[1]) or 10**9,
                    )
                )
            elif sort_within_artist == "Year (newest → oldest)":
                items.sort(
                    key=lambda it: (
                        get_year_for_sort(it[1]) is None,
                        -(get_year_for_sort(it[1]) or -10**9),
                    )
                )
            elif sort_within_artist == "Notes first":
                items.sort(
                    key=lambda it: (
                        not has_note_text(it[0]),
                        it[1].get("title", ""),
                    )
                )

        visible_items: list[tuple[str, dict]] = []

        for artist in page_artists:
            items = grouped.get(artist, [])
            sort_items_for_artist(items)
            visible_items.extend(items)

            years = [get_year_for_sort(a) for _, a in items]
            years = [y for y in years if isinstance(y, int)]
            min_y = min(years) if years else None
            max_y = max(years) if years else None
            notes_count = sum(1 for obj_id, _ in items if has_note_text(obj_id))

            subtitle_parts = [
                f"{len(items)} artwork(s)",
                f"{notes_count} with notes",
            ]
            if min_y and max_y:
                subtitle_parts.append(f"{min_y}–{max_y}")

            header_line = " • ".join(subtitle_parts)

            with st.expander(f"👤 {artist} — {header_line}", expanded=expand_artists):
                render_cards(items, allow_compare=enable_compare_grouped)

        # Painel de comparação no modo agrupado
        if enable_compare_grouped:
            comparison_ids = [
                obj_num
                for obj_num, _ in visible_items
                if st.session_state.get(f"cmp_from_sel_{obj_num}", False)
            ]
            num_selected = len(comparison_ids)

            st.info(
                f"Selected for comparison: {num_selected} "
                "(please select exactly 2 artworks to compare)."
            )

            c1, c2 = st.columns([1, 1])

            with c1:
                compare_clicked = st.button("Compare selected artworks", key="compare_grouped_btn")

            with c2:
                clear_clicked = st.button("Clear comparison", key="clear_compare_grouped_btn")

            with c2:
                clear_clicked = st.button("Clear comparison", key="clear_compare_grouped_btn")

            if clear_clicked:
                # Ligamos o flag; a limpeza REAL acontece no bloco lá de cima
                # antes de criar os checkboxes.
                st.session_state["clear_compare_flag"] = True
                st.rerun()

            if compare_clicked:
                if num_selected != 2:
                    st.warning("Please select exactly **two** artworks to compare.")
                else:
                    id_a, id_b = comparison_ids[0], comparison_ids[1]
                    art_a = favorites.get(id_a)
                    art_b = favorites.get(id_b)

                    if not art_a or not art_b:
                        st.error("Could not retrieve both artworks for comparison.")
                    else:
                        st.markdown("### 🔍 Side-by-side comparison")
                        col_a, col_b = st.columns(2)

                        with col_a:
                            st.subheader("Artwork A")
                            img_url_a = get_best_image_url(art_a)
                            if img_url_a:
                                try:
                                    st.image(img_url_a, use_container_width=True)
                                except Exception:
                                    st.write("Error displaying image.")

                            title_a = art_a.get("title", "Untitled")
                            maker_a = art_a.get("principalOrFirstMaker", "Unknown artist")
                            dating_a = art_a.get("dating", {}) or {}
                            date_a = dating_a.get("presentingDate") or dating_a.get("year")
                            link_a = art_a.get("links", {}).get("web")

                            st.write(f"**Title:** {title_a}")
                            st.write(f"**Artist:** {maker_a}")
                            if date_a:
                                st.write(f"**Date:** {date_a}")
                            st.write(f"**Object ID:** {id_a}")
                            if link_a:
                                st.markdown(f"[View on Rijksmuseum website]({link_a})")

                        with col_b:
                            st.subheader("Artwork B")
                            img_url_b = get_best_image_url(art_b)
                            if img_url_b:
                                try:
                                    st.image(img_url_b, use_container_width=True)
                                except Exception:
                                    st.write("Error displaying image.")

                            title_b = art_b.get("title", "Untitled")
                            maker_b = art_b.get("principalOrFirstMaker", "Unknown artist")
                            dating_b = art_b.get("dating", {}) or {}
                            date_b = dating_b.get("presentingDate") or dating_b.get("year")
                            link_b = art_b.get("links", {}).get("web")

                            st.write(f"**Title:** {title_b}")
                            st.write(f"**Artist:** {maker_b}")
                            if date_b:
                                st.write(f"**Date:** {date_b}")
                            st.write(f"**Object ID:** {id_b}")
                            if link_b:
                                st.markdown(f"[View on Rijksmuseum website]({link_b})")

    # =========================================================
    # MODE B) GRID (default)
    # =========================================================
    else:
        items_per_page = st.select_slider(
            "Artworks per page",
            options=[6, 9, 12, 18, 24, 36],
            value=12,
        )

        total_items = len(base_items)
        max_pages = max(1, (total_items + items_per_page - 1) // items_per_page)

        page = st.number_input(
            "Page",
            min_value=1,
            max_value=max_pages,
            value=1,
            step=1,
        )

        start_i = (page - 1) * items_per_page
        end_i = start_i + items_per_page
        page_items = base_items[start_i:end_i]

        st.caption(
            f"Showing page {page} of {max_pages} — "
            f"{total_items} artwork(s) total after filters."
        )

        st.markdown("### Select artworks from your selection to compare")
        render_cards(page_items, allow_compare=True)

        # Selecionados APENAS desta página
        comparison_ids = [
            obj_num
            for obj_num, _ in page_items
            if st.session_state.get(f"cmp_from_sel_{obj_num}", False)
        ]
        num_selected = len(comparison_ids)

        if num_selected == 0:
            st.info(
                "Select artworks above using **Select for comparison** "
                "to enable the comparison."
            )
        elif num_selected == 2:
            st.success(
                "Selected for comparison: **2 artworks**. "
                "You can now click **Compare selected artworks** below."
            )
        else:
            st.warning(
                f"Selected for comparison: **{num_selected}** "
                "(please select **exactly 2** artworks to compare)."
            )

        c1, c2 = st.columns([1, 1])

        with c1:
            compare_clicked = st.button(
                "Compare selected artworks",
                key="compare_grid_btn",
                use_container_width=True,
            )

        with c2:
            clear_clicked = st.button(
                "Clear comparison",
                key="clear_compare_grid_btn",
                use_container_width=True,
            )

        if clear_clicked:
            # Só liga o flag; quem apaga os estados é o bloco lá em cima
            st.session_state["clear_compare_flag"] = True
            st.rerun()

        if compare_clicked:
            if num_selected != 2:
                st.warning("Please select exactly **two** artworks to compare.")
            else:
                id_a, id_b = comparison_ids[0], comparison_ids[1]
                art_a = favorites.get(id_a)
                art_b = favorites.get(id_b)

                if not art_a or not art_b:
                    st.error("Could not retrieve both artworks for comparison.")
                else:
                    st.markdown("### 🔍 Side-by-side comparison")
                    col_a, col_b = st.columns(2)

                    with col_a:
                        st.subheader("Artwork A")
                        img_url_a = cached_best_image_url(art_a)
                        if img_url_a:
                            try:
                                st.image(img_url_a, use_container_width=True)
                            except Exception:
                                st.write("Error displaying image.")
                        else:
                            st.caption(
                                "No public image available for this artwork via API."
                            )

                        title_a = art_a.get("title", "Untitled")
                        maker_a = art_a.get("principalOrFirstMaker", "Unknown artist")
                        dating_a = art_a.get("dating", {}) or {}
                        date_a = dating_a.get("presentingDate") or dating_a.get("year")
                        link_a = art_a.get("links", {}).get("web")

                        st.write(f"**Title:** {title_a}")
                        st.write(f"**Artist:** {maker_a}")
                        if date_a:
                            st.write(f"**Date:** {date_a}")
                        st.write(f"**Object ID:** {id_a}")
                        if link_a:
                            st.markdown(f"[View on Rijksmuseum website]({link_a})")

                    with col_b:
                        st.subheader("Artwork B")
                        img_url_b = cached_best_image_url(art_b)
                        if img_url_b:
                            try:
                                st.image(img_url_b, use_container_width=True)
                            except Exception:
                                st.write("Error displaying image.")
                        else:
                            st.caption(
                                "No public image available for this artwork via API."
                            )

                        title_b = art_b.get("title", "Untitled")
                        maker_b = art_b.get("principalOrFirstMaker", "Unknown artist")
                        dating_b = art_b.get("dating", {}) or {}
                        date_b = dating_b.get("presentingDate") or dating_b.get("year")
                        link_b = art_b.get("links", {}).get("web")

                        st.write(f"**Title:** {title_b}")
                        st.write(f"**Artist:** {maker_b}")
                        if date_b:
                            st.write(f"**Date:** {date_b}")
                        st.write(f"**Object ID:** {id_b}")
                        if link_b:
                            st.markdown(f"[View on Rijksmuseum website]({link_b})")

# ============================================================
# Detail view + notes
# ============================================================
detail_id = st.session_state.get("detail_art_id")
if detail_id and detail_id in favorites:
    art = favorites[detail_id]

    analytics_key = f"analytics_detail_opened_{detail_id}"
    if analytics_key not in st.session_state:
        st.session_state[analytics_key] = True

        dating = art.get("dating") or {}
        year = dating.get("year") or dating.get("presentingDate")
        title = art.get("title")

        track_event(
            event="artwork_detail_opened",
            page="My_Selection",
            props={
                "object_id": detail_id,
                "artist": art.get("principalOrFirstMaker"),
                "title": title,
                "year": year,
                "has_notes": bool(
                    isinstance(st.session_state.get("notes", {}).get(detail_id), str)
                    and st.session_state["notes"][detail_id].strip()
                ),
            },
        )

    st.markdown("---")
    st.subheader("🔍 Detail view")

    img_url = get_best_image_url(art)
    title = art.get("title", "Untitled")
    maker = art.get("principalOrFirstMaker", "Unknown artist")
    web_link = art.get("links", {}).get("web")
    dating = art.get("dating", {}) or {}
    presenting_date = dating.get("presentingDate")
    year = dating.get("year")

    col_img, col_meta = st.columns([3, 2])

    with col_img:
        if img_url:
            zoom = st.slider(
                "Zoom (relative size)",
                min_value=50,
                max_value=200,
                value=120,
                step=10,
                key=f"zoom_{detail_id}",
            )
            base_width = 600
            width = int(base_width * zoom / 100)
            st.image(img_url, width=width)
        else:
            st.write("No valid image available via API.")

    with col_meta:
        st.write(f"**Title:** {title}")
        st.write(f"**Artist:** {maker}")
        st.write(f"**Object ID:** {detail_id}")
        if presenting_date:
            st.write(f"**Date:** {presenting_date}")
        elif year:
            st.write(f"**Year:** {year}")

        long_title = art.get("longTitle")
        object_types = art.get("objectTypes")
        materials = art.get("materials")
        techniques = art.get("techniques")
        production_places = art.get("productionPlaces")

        if long_title and long_title != title:
            st.write(f"**Long title:** {long_title}")
        if object_types:
            st.write(f"**Object type(s):** {', '.join(object_types)}")
        if materials:
            st.write(f"**Materials:** {', '.join(materials)}")
        if techniques:
            st.write(f"**Techniques:** {', '.join(techniques)}")
        if production_places:
            st.write(f"**Production place(s): {', '.join(production_places)}")

        if web_link:
            st.markdown(f"[Open on Rijksmuseum website for full zoom]({web_link})")

    st.markdown("### 📝 Research notes")

    existing_note = st.session_state["notes"].get(detail_id, "")
    note_text = st.text_area(
        "Write your notes for this artwork:",
        value=existing_note,
        height=160,
        key=f"note_{detail_id}",
    )

    if st.button("Save notes", key=f"save_note_{detail_id}"):
        st.session_state["notes"][detail_id] = note_text
        save_notes()
        st.success("Notes saved successfully.")

        track_event(
            event="note_saved",
            page="My_Selection",
            props={
                "object_id": detail_id,
                "note_len": len(note_text.strip()) if isinstance(note_text, str) else 0,
                "has_note": bool(isinstance(note_text, str) and note_text.strip()),
            },
        )

    if st.button("Remove from my selection", key=f"remove_detail_{detail_id}"):

        track_event(
            event="selection_remove_item",
            page="My_Selection",
            props={
                "object_id": detail_id,
                "artist": art.get("principalOrFirstMaker"),
                "had_notes": bool((st.session_state.get("notes", {}).get(detail_id) or "").strip()),
                "prev_count": len(favorites),
                "origin": "detail_view",
            },
        )

        favorites.pop(detail_id, None)
        st.session_state["favorites"] = favorites

        try:
            with open(FAV_FILE, "w", encoding="utf-8") as f:
                json.dump(favorites, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        # remove checkbox state associado, se existir
        cmp_key = f"cmp_from_sel_{detail_id}"
        if cmp_key in st.session_state:
            del st.session_state[cmp_key]

        if "notes" in st.session_state:
            st.session_state["notes"].pop(detail_id, None)
            try:
                with open(NOTES_FILE, "w", encoding="utf-8") as f:
                    json.dump(
                        st.session_state["notes"],
                        f,
                        ensure_ascii=False,
                        indent=2,
                    )
            except Exception:
                pass

        st.session_state["detail_art_id"] = None

        st.success("Artwork removed from your selection.")
        st.rerun()

    if st.button("Close detail view", key=f"close_detail_{detail_id}"):
        st.session_state["detail_art_id"] = None
        st.rerun()


# ============================================================
# Footer
# ============================================================
show_footer()
