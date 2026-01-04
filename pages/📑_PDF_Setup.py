# pages/PDF_Setup.py

"""
PDF Setup page

This page configures how the illustrated PDF is generated from the
"My Selection" page. It controls:

- Whether to include a cover page.
- Whether to include a global opening text / introduction.
- Whether to include research notes and artwork commentary.
- Optional artwork-specific comments (per objectNumber).

Settings are stored in a small JSON file (PDF_META_FILE) and are
shared with the My_Selection page.
"""

import json
import streamlit as st

from app_paths import PDF_META_FILE, FAV_FILE
from analytics import track_event, track_event_once


# ============================================================
# CSS & footer
# ============================================================
def inject_custom_css() -> None:
    """Apply dark theme and basic layout for the PDF Setup page."""
    st.markdown(
        """
        <style>
        .stApp { background-color: #111111; color: #f5f5f5; }

        div.block-container {
            max-width: 900px;
            padding-top: 1.4rem;
            padding-bottom: 2.5rem;
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
        div[data-testid="stMarkdownContainer"] a:hover {
            text-decoration: underline;
        }

        .rijks-footer {
            margin-top: 2.5rem;
            padding-top: 0.75rem;
            border-top: 1px solid #262626;
            font-size: 0.8rem;
            color: #aaaaaa;
            text-align: center;
        }

        .rijks-panel {
            background-color: #181818;
            border-radius: 12px;
            padding: 1.0rem 1.25rem 1.1rem 1.25rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.4);
            border: 1px solid #262626;
            margin-bottom: 1.3rem;
        }

        .rijks-pill {
            display: inline-block;
            padding: 4px 10px;
            border-radius: 999px;
            background-color: #262626;
            color: #f5f5f5;
            font-size: 0.85rem;
            margin-top: 0.25rem;
            margin-bottom: 0.9rem;
        }
        .rijks-pill strong { color: #ff9900; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_footer() -> None:
    """Show a small footer acknowledging the Rijksmuseum API."""
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
# Helpers: load/save PDF meta + selection count
# ============================================================
def _default_pdf_meta() -> dict:
    """Return the default PDF configuration structure."""
    return {
        "opening_text": "",
        "include_cover": True,
        "include_opening_text": True,
        "include_notes": True,
        "include_comments": True,
        "artwork_comments": {},  # objectNumber -> text
    }


def load_pdf_meta() -> dict:
    """
    Load PDF configuration shared with the My_Selection page.

    Data is cached in st.session_state["pdf_meta"].
    """
    if "pdf_meta" in st.session_state:
        meta = st.session_state["pdf_meta"]
        if isinstance(meta, dict):
            # Make sure all expected keys exist
            base = _default_pdf_meta()
            base.update(meta)
            st.session_state["pdf_meta"] = base
            return base

    base = _default_pdf_meta()

    if PDF_META_FILE.exists():
        try:
            with open(PDF_META_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                base.update(data)
        except Exception:
            # PDF meta is optional; never break the app here
            pass

    st.session_state["pdf_meta"] = base
    return base


def save_pdf_meta(meta: dict) -> None:
    """Persist PDF configuration to disk and update session_state."""
    base = _default_pdf_meta()
    base.update(meta or {})
    st.session_state["pdf_meta"] = base

    try:
        with open(PDF_META_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f, ensure_ascii=False, indent=2)
    except Exception:
        # Never break the UI because of a save error
        pass


def load_selection_count() -> int:
    """
    Return the number of artworks currently in the global selection.

    Uses st.session_state['favorites'] when available, falling back
    to reading the local favorites file.
    """
    favorites = st.session_state.get("favorites")
    if isinstance(favorites, dict):
        return len(favorites)

    try:
        if FAV_FILE.exists():
            with open(FAV_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return len(data) if isinstance(data, dict) else 0
    except Exception:
        pass

    return 0


# ============================================================
# Analytics — page view (once per session)
# ============================================================
track_event_once(
    event="page_view",
    page="PDF_Setup",
    once_key="page_view::PDF_Setup",
    props={"has_existing_config": PDF_META_FILE.exists()},
)


# ============================================================
# Page content
# ============================================================
st.markdown("## 📑 PDF setup")

selection_count = load_selection_count()
if selection_count:
    st.markdown(
        f'<span class="rijks-pill">Current selection: '
        f'<strong>{selection_count}</strong> artwork(s)</span>',
        unsafe_allow_html=True,
    )

st.write(
    "Use this page to configure how the illustrated PDF is generated from your "
    "**My Selection** page. These settings affect the PDF built when you click "
    "**Prepare PDF** on My Selection."
)

pdf_meta = load_pdf_meta()

# ------------------------------------------------------------
# Main configuration panel
# ------------------------------------------------------------
st.markdown('<div class="rijks-panel">', unsafe_allow_html=True)
st.markdown("### General PDF settings")

include_cover = st.checkbox(
    "Include cover page",
    value=bool(pdf_meta.get("include_cover", True)),
    help="First page with title, generation date and total number of artworks.",
)

include_opening_text = st.checkbox(
    "Include opening text / introduction",
    value=bool(pdf_meta.get("include_opening_text", True)),
    help="Adds an introductory text section at the beginning of the PDF.",
)

include_notes_flag = st.checkbox(
    "Include research notes in each artwork page",
    value=bool(pdf_meta.get("include_notes", True)),
    help="When enabled, the PDF will include your notes from the My Selection page.",
)

include_comments_flag = st.checkbox(
    "Include commentary text in each artwork page",
    value=bool(pdf_meta.get("include_comments", True)),
    help="Optional commentary separate from research notes (see section below).",
)

opening_text = st.text_area(
    "Opening text (optional introduction)",
    value=pdf_meta.get("opening_text", ""),
    height=200,
    help=(
        "This text appears near the beginning of the PDF as an introduction. "
        "You can describe the purpose of this selection, the research context, "
        "or any narrative you want to add."
    ),
)

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Artwork-specific comments (advanced)
# ------------------------------------------------------------
st.markdown('<div class="rijks-panel">', unsafe_allow_html=True)
st.markdown("### Artwork-specific comments (optional)")

artwork_comments = dict(pdf_meta.get("artwork_comments") or {})

if artwork_comments:
    st.caption("Existing comments:")
    for obj_id, txt in artwork_comments.items():
        short_txt = (txt[:120] + "…") if isinstance(txt, str) and len(txt) > 120 else txt
        st.write(f"- **{obj_id}** — {short_txt}")
else:
    st.caption("No artwork-specific comments defined yet.")

st.markdown("---")

obj_id_input = st.text_input(
    "Artwork ID (objectNumber)",
    value="",
    help="Use the object ID as shown on the My Selection page (e.g. SK-A-3452).",
    key="pdf_comment_object_id",
)

comment_text_input = st.text_area(
    "Comment for this artwork",
    value="",
    height=140,
    help=(
        "Optional commentary that will appear in the PDF for this specific artwork, "
        "in addition to your research notes."
    ),
    key="pdf_comment_text",
)

col_c1, col_c2 = st.columns(2)

with col_c1:
    if st.button("Save / update comment for this artwork"):
        obj_id = obj_id_input.strip()
        if not obj_id:
            st.warning("Please enter a valid artwork ID (objectNumber).")
        else:
            artwork_comments[obj_id] = comment_text_input.strip()
            pdf_meta["artwork_comments"] = artwork_comments
            save_pdf_meta(pdf_meta)

            track_event(
                event="pdf_comment_saved",
                page="PDF_Setup",
                props={
                    "object_id": obj_id,
                    "comment_len": len(comment_text_input.strip()),
                    "total_comments": len(artwork_comments),
                },
            )

            st.success(f"Comment saved for artwork {obj_id}.")
            st.experimental_rerun()

with col_c2:
    if st.button("Remove comment for this artwork"):
        obj_id = obj_id_input.strip()
        if not obj_id:
            st.warning("Please enter an artwork ID to remove its comment.")
        elif obj_id not in artwork_comments:
            st.info("There is no saved comment for this artwork ID.")
        else:
            artwork_comments.pop(obj_id, None)
            pdf_meta["artwork_comments"] = artwork_comments
            save_pdf_meta(pdf_meta)

            track_event(
                event="pdf_comment_removed",
                page="PDF_Setup",
                props={"object_id": obj_id, "total_comments": len(artwork_comments)},
            )

            st.success(f"Comment removed for artwork {obj_id}.")
            st.experimental_rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Save / reset controls
# ------------------------------------------------------------
st.markdown('<div class="rijks-panel">', unsafe_allow_html=True)
st.markdown("### Save or reset PDF configuration")

col_s1, col_s2 = st.columns(2)

with col_s1:
    if st.button("💾 Save PDF configuration", use_container_width=True):
        updated = dict(pdf_meta)
        updated["include_cover"] = bool(include_cover)
        updated["include_opening_text"] = bool(include_opening_text)
        updated["include_notes"] = bool(include_notes_flag)
        updated["include_comments"] = bool(include_comments_flag)
        updated["opening_text"] = opening_text
        # Keep artwork_comments as edited above
        updated["artwork_comments"] = artwork_comments

        save_pdf_meta(updated)

        track_event(
            event="pdf_meta_saved",
            page="PDF_Setup",
            props={
                "include_cover": bool(include_cover),
                "include_opening_text": bool(include_opening_text),
                "include_notes": bool(include_notes_flag),
                "include_comments": bool(include_comments_flag),
                "has_opening_text": bool(opening_text.strip()),
                "num_artwork_comments": len(artwork_comments),
            },
        )

        st.success("PDF configuration saved. You can now prepare the PDF on the My Selection page.")

with col_s2:
    if st.button("↩️ Reset to default settings", use_container_width=True):
        base = _default_pdf_meta()
        save_pdf_meta(base)

        track_event(
            event="pdf_meta_reset",
            page="PDF_Setup",
            props={},
        )

        st.success("PDF settings reset to defaults.")
        st.experimental_rerun()

st.markdown("</div>", unsafe_allow_html=True)

# ------------------------------------------------------------
# Raw JSON (debug / advanced)
# ------------------------------------------------------------
with st.expander("🔍 View raw PDF configuration (advanced)", expanded=False):
    st.json(st.session_state.get("pdf_meta", {}))

# ============================================================
# Footer
# ============================================================
show_footer()