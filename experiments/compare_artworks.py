import streamlit as st
from rijks_api import search_artworks, extract_year, get_best_image_url

# ============================================================
# Compare Artworks page (independent selection)
# ============================================================

st.markdown("## 🖼️ Compare Artworks")

st.write(
    "Use this page to compare two artworks side by side. "
    "Search the collection, select exactly two items, and then click "
    "**Compare selected artworks**."
)

# -------------------------------------------------------------------
# Initialize session_state for comparison (independent from favorites)
# -------------------------------------------------------------------

if "compare_results" not in st.session_state:
    st.session_state["compare_results"] = {
        "artworks": [],
        "total_count": 0,
        "query": "",
    }

if "compare_selected_ids" not in st.session_state:
    # We'll store a list of objectNumbers selected for comparison
    st.session_state["compare_selected_ids"] = []

# -------------------------------------------------------------------
# Sidebar: search options
# -------------------------------------------------------------------

with st.sidebar:
    st.header("Search & Filters (Compare)")

    last_query = st.session_state["compare_results"].get("query") or "Rembrandt"

    query = st.text_input(
        "Search term for comparison",
        last_query,
        help="For example: Rembrandt, landscape, portrait...",
    )

    object_type = st.selectbox(
        "Object type",
        ["Any", "painting", "print", "drawing", "sculpture", "photograph"],
        index=0,
        help="Filter by object type in the metadata.",
    )

    sort_option = st.selectbox(
        "Sort results by",
        ["Relevance (default)", "Year ascending", "Year descending"],
        index=0,
    )

    page_size = st.slider(
        "Number of results to display",
        min_value=6,
        max_value=48,
        value=12,
        step=6,
    )

    search_clicked = st.button("Search for artworks")

# -------------------------------------------------------------------
# Perform search when requested
# -------------------------------------------------------------------

if search_clicked:
    if not query.strip():
        st.warning("Please enter a search term.")
    else:
        try:
            artworks, total_count = search_artworks(
                query.strip(),
                object_type=None if object_type == "Any" else object_type,
                page_size=page_size,
            )
        except Exception as e:
            st.error(f"Error while calling the Rijksmuseum API: {e}")
            st.session_state["compare_results"] = {
                "artworks": [],
                "total_count": 0,
                "query": query.strip(),
            }
        else:
            st.session_state["compare_results"] = {
                "artworks": artworks,
                "total_count": total_count,
                "query": query.strip(),
            }
            # Always reset selection after a new search
            st.session_state["compare_selected_ids"] = []

# -------------------------------------------------------------------
# Show search results with independent selection
# -------------------------------------------------------------------

results = st.session_state["compare_results"]
artworks = results["artworks"]
total_count = results["total_count"]

selected_ids = set(st.session_state["compare_selected_ids"])

if artworks:
    # Sorting by year if requested
    if sort_option == "Year ascending":
        artworks.sort(key=extract_year)
    elif sort_option == "Year descending":
        artworks.sort(key=extract_year, reverse=True)

    st.success(
        f"Found {total_count} artworks "
        f"(displaying the first {len(artworks)} results)."
    )

    st.markdown("### Select artworks to compare")

    new_selected_ids = set()

    for art in artworks:
        obj_num = art.get("objectNumber", "")
        title = art.get("title", "Untitled")
        maker = art.get("principalOrFirstMaker", "Unknown artist")

        # Uma linha com título + autor + checkbox
        cols = st.columns([6, 3])
        with cols[0]:
            st.write(f"**{title}** — *{maker}*")
        with cols[1]:
            if obj_num:
                checkbox_key = f"cmp_select_{obj_num}"
                is_selected = obj_num in selected_ids
                checked = st.checkbox("Select", value=is_selected, key=checkbox_key)
                if checked:
                    new_selected_ids.add(obj_num)

    # Atualiza seleção independente
    st.session_state["compare_selected_ids"] = list(new_selected_ids)

    st.write(
        f"**Selected artworks:** {len(st.session_state['compare_selected_ids'])} "
        "(you must select exactly 2 to compare)."
    )

    # Botão para gerar a comparação
    if st.button("Compare selected artworks"):
        ids = st.session_state["compare_selected_ids"]
        if len(ids) != 2:
            st.error("Please select exactly 2 artworks to compare.")
        else:
            # Mapeia objectNumber -> artwork
            art_by_id = {a.get("objectNumber", ""): a for a in artworks}
            id_a, id_b = ids[0], ids[1]
            art_a = art_by_id.get(id_a)
            art_b = art_by_id.get(id_b)

            if not art_a or not art_b:
                st.error("Could not retrieve both artworks for comparison.")
            else:
                st.markdown("### Comparison")
                col_a, col_b = st.columns(2)

                # ----- Artwork A -----
                with col_a:
                    st.subheader("Artwork A")
                    img_url_a = get_best_image_url(art_a)
                    if img_url_a:
                        try:
                            st.image(img_url_a, use_container_width=True)
                        except Exception:
                            st.write("Error displaying image.")
                    else:
                        st.write("No valid image available via API.")

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

                # ----- Artwork B -----
                with col_b:
                    st.subheader("Artwork B")
                    img_url_b = get_best_image_url(art_b)
                    if img_url_b:
                        try:
                            st.image(img_url_b, use_container_width=True)
                        except Exception:
                            st.write("Error displaying image.")
                    else:
                        st.write("No valid image available via API.")

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

else:
    st.info(
        "No results yet. Use the search controls in the sidebar and click "
        "**Search for artworks** to start comparing."
    )