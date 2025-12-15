# pdf_setup.py
"""
PDF Setup & Customization

This page lets the user configure:
- A global opening text for the PDF (introduction).
- Per-artwork commentary to be included in the PDF.
- Basic flags (include cover, intro, notes, commentary).

The actual PDF generation happens on the "My selection" page,
which reads these settings from pdf_meta.json.
"""

import os
import json

import streamlit as st
from rijks_api import get_best_image_url
from app_paths import FAV_FILE, NOTES_FILE, PDF_META_FILE

# ============================================================
# CSS
# ============================================================
def inject_custom_css() -> None:
    """Inject CSS so this page matches the dark theme of the app."""
    st.markdown(
        """
        <style>
        .stApp {
            background-color: #111111;
            color: #f5f5f5;
        }

        div.block-container {
            max-width: 1000px;
            padding-top: 1.5rem;
            padding-bottom: 3rem;
        }

        section[data-testid="stSidebar"] {
            background-color: #181818 !important;
        }

        h1, h2, h3 {
            font-weight: 600;
        }

        .pdf-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background-color: #262626;
            color: #f5f5f5;
            font-size: 0.85rem;
            margin-top: 0.5rem;
            margin-bottom: 1rem;
        }
        .pdf-pill strong {
            color: #ff9900;
        }

        .pdf-artwork-box {
            background-color: #181818;
            border-radius: 12px;
            padding: 0.8rem 0.9rem 0.9rem 0.9rem;
            border: 1px solid #262626;
            margin-bottom: 0.75rem;
        }

        .pdf-artwork-title {
            font-weight: 600;
            font-size: 0.98rem;
            margin-bottom: 0.1rem;
        }

        .pdf-artwork-meta {
            font-size: 0.85rem;
            color: #c7c7c7;
            margin-bottom: 0.35rem;
        }

        .pdf-note-tag {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 999px;
            font-size: 0.7rem;
            background-color: #262626;
            color: #ffddaa;
            border: 1px solid #444444;
            margin-left: 0.25rem;
        }

        textarea {
            font-size: 0.9rem !important;
        }

        .pdf-preview-card {
            display: flex;
            gap: 0.8rem;
            align-items: flex-start;
        }

        .pdf-preview-left {
            flex: 0 0 120px;
        }

        .pdf-preview-right {
            flex: 1;
        }

        .pdf-preview-img {
            width: 120px;
            height: 90px;
            object-fit: cover;
            border-radius: 6px;
        }

        .pdf-preview-img--empty {
            width: 120px;
            height: 90px;
            border-radius: 6px;
            background-color: #202020;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.75rem;
            color: #aaaaaa;
        }

        .pdf-tag {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 999px;
            font-size: 0.7rem;
            background-color: #262626;
            color: #f5f5f5;
            border: 1px solid #444444;
            margin-right: 0.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

inject_custom_css()


# ============================================================
# Helpers: load favorites, notes, pdf_meta
# ============================================================
def load_favorites() -> dict:
    """Load favorites from JSON file, return empty dict if not available."""
    if FAV_FILE.exists( ):
        try:
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def load_notes() -> dict:
    """
    Load research notes from NOTES_FILE.
    Notes are not edited here, only displayed as a hint.
    """
    if FAV_FILE.exists( ):
        try:
            with open(NOTES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {}


def load_pdf_meta() -> dict:
    """
    Load PDF customization metadata from PDF_META_FILE.

    Expected structure:
        {
            "opening_text": "...",
            "include_cover": true,
            "include_opening_text": true,
            "include_notes": true,
            "include_comments": true,
            "artwork_comments": {
                "objectNumber": "custom commentary text",
                ...
            }
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

    if FAV_FILE.exists( ):
        try:
            with open(PDF_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Merge saved data on top of defaults
                    base.update(data)
        except Exception:
            pass

    st.session_state["pdf_meta"] = base
    return base


def save_pdf_meta(pdf_meta: dict) -> None:
    """Persist PDF customization metadata to disk and session_state."""
    st.session_state["pdf_meta"] = pdf_meta
    try:
        with open(PDF_META_FILE, "w", encoding="utf-8") as f:
            json.dump(pdf_meta, f, ensure_ascii=False, indent=2)
    except Exception:
        # In a real app you might want to log this.
        pass


# ============================================================
# Page content
# ============================================================

st.markdown("## 📄 PDF setup & customization")

st.write(
    "Use this page to configure how your **PDF report** will look. "
    "You can define an opening text for your selection and add specific commentary "
    "for each artwork. These texts will be used when generating the illustrated PDF "
    "on the **My selection** page."
)

st.markdown(
    '<div class="pdf-pill">'
    '<strong>Status:</strong> PDF customization settings are stored locally '
    'in <code>pdf_meta.json</code>.'
    "</div>",
    unsafe_allow_html=True,
)

# Load data
favorites = load_favorites()
notes = load_notes()
pdf_meta = load_pdf_meta()

if not favorites:
    st.info(
        "You do not have any artworks in your selection yet. "
        "Go to the **Rijksmuseum Explorer** page, mark a few artworks "
        "as **In my selection**, and then return here to configure the PDF."
    )
    st.stop()

artwork_comments: dict = pdf_meta.get("artwork_comments") or {}
pdf_meta["artwork_comments"] = artwork_comments  # ensure it exists


# ============================================================
# Global PDF settings
# ============================================================
st.markdown("### 1. Global PDF settings")

col_flags = st.columns(2)

with col_flags[0]:
    include_cover = st.checkbox(
        "Include cover page",
        value=bool(pdf_meta.get("include_cover", True)),
        help="Cover with title, date and basic information.",
    )

    include_opening_text = st.checkbox(
        "Include opening text page",
        value=bool(pdf_meta.get("include_opening_text", True)),
        help="A dedicated page for your introduction or research context.",
    )

with col_flags[1]:
    include_notes = st.checkbox(
        "Include research notes",
        value=bool(pdf_meta.get("include_notes", True)),
        help="Include the notes you wrote in the **My selection** page.",
    )

    include_comments = st.checkbox(
        "Include commentary per artwork",
        value=bool(pdf_meta.get("include_comments", True)),
        help="Include the custom commentary defined below for each artwork.",
    )

pdf_meta["include_cover"] = include_cover
pdf_meta["include_opening_text"] = include_opening_text
pdf_meta["include_notes"] = include_notes
pdf_meta["include_comments"] = include_comments

st.markdown("#### Opening text for the PDF (optional)")

opening_text = st.text_area(
    "This text will appear as an introductory page in the PDF.",
    value=pdf_meta.get("opening_text", ""),
    height=180,
    help=(
        "Use this space to explain the aim of your selection, "
        "your research questions, or any contextual information "
        "you want to appear at the beginning of the PDF."
    ),
)
pdf_meta["opening_text"] = opening_text

# ============================================================
# Per-artwork commentary
# ============================================================
st.markdown("### 2. Commentary per artwork")

st.write(
    "You can add a short commentary for each artwork. "
    "This commentary will appear on the same page as the artwork in the PDF, "
    "together with basic metadata and (optionally) your research notes."
)

st.caption(
    "Tip: use this for your own interpretation, classroom notes, or references "
    "to other sources. It is separate from the research notes used inside the app."
)

# Sort artworks by artist then title for a stable order
sorted_items = sorted(
    favorites.items(),
    key=lambda item: (
        (item[1] or {}).get("principalOrFirstMaker", ""),
        (item[1] or {}).get("title", ""),
    ),
)

# ------------------------------------------------------------
# Preview + commentary editor: one block per artwork
# ------------------------------------------------------------
for obj_num, art in sorted_items:
    title = art.get("title", "Untitled")
    maker = art.get("principalOrFirstMaker", "Unknown artist")
    dating = art.get("dating", {}) or {}
    year = dating.get("year") or dating.get("presentingDate") or ""
    img_url = get_best_image_url(art)

    # Does this artwork have research notes?
    raw_note = notes.get(obj_num, "")
    has_note = isinstance(raw_note, str) and raw_note.strip() != ""

    # HTML snippet for the notes tag (only if there are notes)
    note_tag = ""
    if has_note:
        note_tag = '<span class="pdf-note-tag">📝 Has research notes</span>'

    # Small snippet for the image area
    if img_url:
        image_html = f'<img src="{img_url}" class="pdf-preview-img" />'
    else:
        image_html = (
            '<div class="pdf-preview-img pdf-preview-img--empty">'
            "No image available"
            "</div>"
        )

    # Get existing commentary (if any)
    existing_comment = artwork_comments.get(obj_num, "")

    # Layout: preview card + textarea logo abaixo
    card_html = (
        '<div class="pdf-artwork-box">'
        '  <div class="pdf-preview-card">'
        '    <div class="pdf-preview-left">'
        f'      {image_html}'
        '    </div>'
        '    <div class="pdf-preview-right">'
        f'      <div class="pdf-artwork-title">{title}</div>'
        '      <div class="pdf-artwork-meta">'
        f'        {maker}{(" — " + str(year)) if year else ""}<br/>'
        f'        <span class="pdf-tag">ID: {obj_num}</span>'
        f'        {note_tag}'
        '      </div>'
        '    </div>'
        '  </div>'
        '</div>'
    )

    st.markdown(card_html, unsafe_allow_html=True)

    # Commentary editor for this artwork
    comment_text = st.text_area(
        "Commentary for this artwork (optional):",
        value=existing_comment,
        height=110,
        key=f"comment_{obj_num}",
    )

    # Update in-memory dict: keep only non-empty comments
    if comment_text.strip():
        artwork_comments[obj_num] = comment_text
    else:
        artwork_comments.pop(obj_num, None)

# Ensure comments are stored back into pdf_meta
pdf_meta["artwork_comments"] = artwork_comments


# ============================================================
# Save button
# ============================================================
st.markdown("---")
if st.button("💾 Save PDF settings"):
    save_pdf_meta(pdf_meta)
    st.success(
        "PDF customization settings saved. You can now go to the "
        "**My selection** page and generate the PDF using these options."
    )

st.caption(
    "Note: PDF settings are stored locally in the application folder. "
    "They will be reused the next time you open the app, as long as the files "
    "are kept together."
)