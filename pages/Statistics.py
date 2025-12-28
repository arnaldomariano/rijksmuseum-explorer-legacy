# pages/Statistics.py
import json
import io
import csv
from collections import Counter
from datetime import datetime

import streamlit as st
from typing import Optional

from app_paths import ANALYTICS_EVENTS_FILE

def clear_analytics_events() -> bool:
    try:
        p = ANALYTICS_EVENTS_FILE
        p.parent.mkdir(parents=True, exist_ok=True)

        # zera o arquivo
        with open(p, "w", encoding="utf-8") as f:
            f.write("")

        return True
    except Exception:
        return False

st.set_page_config(page_title="Statistics", layout="wide")
st.markdown("## 📊 Usage statistics (local, anonymous)")

st.caption(
    "This dashboard reads the local file `analytics_events.json` created by the app. "
    "No data is sent anywhere."
)


@st.cache_data(show_spinner=False)
def load_events(path, version: float) -> list[dict]:
    events: list[dict] = []
    if not path.exists():
        return events

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


def events_to_csv_bytes(events: list[dict]) -> bytes:
    if not events:
        return b""

    keys = set()
    for e in events:
        if isinstance(e, dict):
            keys.update(e.keys())

    preferred = ["ts", "event", "page", "session_id"]
    columns = preferred + sorted([k for k in keys if k not in preferred])

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for e in events:
        writer.writerow(e)

    return buffer.getvalue().encode("utf-8")

p = ANALYTICS_EVENTS_FILE
version = p.stat().st_mtime if p.exists() else 0.0

events = load_events(ANALYTICS_EVENTS_FILE, version)

p = ANALYTICS_EVENTS_FILE
st.caption(
    f"DEBUG file: `{p}` | exists={p.exists()} | size={p.stat().st_size if p.exists() else '—'} bytes | mtime={datetime.fromtimestamp(p.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S') if p.exists() else '—'}"
)

if not events:
    st.info("No analytics events yet. Use the app normally and come back here.")
    st.stop()

# -------------------------
# Basic metrics
# -------------------------
total = len(events)
event_types = Counter(e.get("event") for e in events if e.get("event"))

ts_values = [e.get("ts") for e in events if isinstance(e.get("ts"), (int, float))]
min_ts = min(ts_values) if ts_values else None
max_ts = max(ts_values) if ts_values else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total events", total)
col2.metric("Event types", len(event_types))

# Time window (supports ISO string or unix seconds)
def parse_ts(e: dict) -> Optional[datetime]:
    ts = e.get("ts")
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(ts)
    if isinstance(ts, str):
        try:
            # handles "2025-12-13T..." (with timezone)
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except Exception:
            return None
    return None

dt_values = [parse_ts(e) for e in events]
dt_values = [d for d in dt_values if isinstance(d, datetime)]

dt_min = min(dt_values) if dt_values else None
dt_max = max(dt_values) if dt_values else None

if dt_min and dt_max:
    col3.metric("First event", dt_min.strftime("%Y-%m-%d %H:%M"))
    col4.metric("Last event", dt_max.strftime("%Y-%m-%d %H:%M"))
else:
    col3.metric("First event", "—")
    col4.metric("Last event", "—")

st.markdown("---")

# -------------------------
# Filters
# -------------------------
all_types = sorted(event_types.keys())
selected_types = st.multiselect(
    "Filter by event type",
    options=all_types,
    default=all_types,
)

selected_set = set(selected_types)
filtered = [e for e in events if e.get("event") in selected_set]

# -------------------------
# Export filtered events (CSV)
# -------------------------
csv_bytes = events_to_csv_bytes(filtered)
filename = f"analytics_events_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"

st.download_button(
    "📄 Download events (CSV)",
    data=csv_bytes,
    file_name=filename,
    mime="text/csv",
    key="dl_analytics_csv",
)
# -------------------------
# Aggregations
# -------------------------
counts_by_type = Counter(e.get("event") for e in filtered if e.get("event"))

page_views_by_page = Counter()
views_by_object = Counter()
views_by_artist = Counter()
exports_by_format = Counter()
search_queries = Counter()
search_configs = Counter()

for e in filtered:
    ev = e.get("event")
    page_name = e.get("page") or "(unknown page)"
    props = e.get("props") or {}

    # Page views
    if ev == "page_view":
        page_views_by_page[page_name] += 1

    # Artwork views / detail opens
    # “view” de obra: qualquer evento que indique interesse direto na obra
    if ev in ("artwork_detail_opened", "artwork_view", "selection_add_item"):
        obj = props.get("object_id")
        artist = props.get("artist")
        if obj:
            views_by_object[obj] += 1
        if artist:
            views_by_artist[artist] += 1

    # Exports
    if ev in ("export_download", "export_prepare"):
        fmt = (props.get("format") or "").lower().strip()
        if fmt:
            exports_by_format[fmt] += 1

    # Searches
    if ev == "search_executed":
        q = (props.get("query_sample") or "").strip()
        if q:
            search_queries[q] += 1

        cfg_key = (
            f"type={props.get('object_type', 'Any')}; "
            f"sort={props.get('sort_by', 'relevance')}; "
            f"year={props.get('year_min', '')}-{props.get('year_max', '')}; "
            f"material={bool(props.get('has_material_filter'))}; "
            f"place={bool(props.get('has_place_filter'))}"
        )
        search_configs[cfg_key] += 1

# -------------------------
# Export aggregated stats (CSV)
# -------------------------
stats_rows: list[dict] = []

# 1) Contagem por tipo de evento
for ev_type, count in counts_by_type.most_common():
    stats_rows.append(
        {"category": "event_type", "key": ev_type or "(none)", "count": count}
    )

# 2) Page views por página
for page_name, count in page_views_by_page.most_common():
    stats_rows.append(
        {"category": "page_view", "key": page_name, "count": count}
    )

# 3) Exportações por formato
for fmt, count in exports_by_format.most_common():
    stats_rows.append(
        {"category": "export_format", "key": fmt or "(none)", "count": count}
    )

# 4) Visualizações por objeto
for obj, count in views_by_object.most_common():
    stats_rows.append(
        {"category": "object_id", "key": obj, "count": count}
    )

# 5) Visualizações por artista
for artist, count in views_by_artist.most_common():
    stats_rows.append(
        {"category": "artist", "key": artist, "count": count}
    )

# 6) Buscas por termo (query_sample)
for query, count in search_queries.most_common():
    stats_rows.append(
        {"category": "search_query", "key": query, "count": count}
    )

# 7) Buscas por configuração (tipo, sort, filtros locais)
for cfg, count in search_configs.most_common():
    stats_rows.append(
        {"category": "search_config", "key": cfg, "count": count}
    )

if stats_rows:
    stats_buffer = io.StringIO()
    writer = csv.DictWriter(
        stats_buffer,
        fieldnames=["category", "key", "count"],
        extrasaction="ignore",
    )
    writer.writeheader()
    writer.writerows(stats_rows)
    stats_csv_bytes = stats_buffer.getvalue().encode("utf-8")

    st.download_button(
        "📊 Download aggregated stats (CSV)",
        data=stats_csv_bytes,
        file_name=f"analytics_stats_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
        key="dl_analytics_stats_csv",
    )
else:
    st.caption("No aggregated stats available yet for current filters.")

st.markdown("---")
# -------------------------
# Maintenance: clear file
# -------------------------
st.subheader("🧹 Maintenance")

if "confirm_clear_analytics" not in st.session_state:
    st.session_state["confirm_clear_analytics"] = False

col_a, col_b = st.columns([1, 2])

with col_a:
    if not st.session_state["confirm_clear_analytics"]:
        if st.button("Clear analytics data", key="btn_clear_analytics_step1"):
            st.session_state["confirm_clear_analytics"] = True
            st.rerun()
    else:
        if st.button("✅ Confirm clear", key="btn_clear_analytics_step2"):
            ok = clear_analytics_events()  # <-- AQUI você realmente limpa o arquivo
            st.session_state["confirm_clear_analytics"] = False

            if ok:
                # 1) limpa cache global (garante que o loader releia o arquivo zerado)
                st.cache_data.clear()

                # 2) remove flags que bloqueiam re-track na mesma sessão
                for k in list(st.session_state.keys()):
                    if k.startswith("analytics_"):
                        del st.session_state[k]

                st.success("Analytics file cleared (and session analytics flags reset).")
            else:
                st.error("Could not clear analytics file.")

            st.rerun()

with col_b:
    if st.session_state["confirm_clear_analytics"]:
        st.warning(
            f"This will permanently clear your local analytics file:\n\n`{ANALYTICS_EVENTS_FILE}`\n\n"
            "Click **Confirm clear** to proceed."
        )
    else:
        st.caption("Clears the local file only. No data is sent anywhere.")

st.markdown("---")

# -------------------------
# Display panels
# -------------------------
cA, cB = st.columns([1, 1])

with cA:
    st.subheader("Events by type")
    for k, v in counts_by_type.most_common():
        st.write(f"- **{k}**: {v}")

with cB:
    st.subheader("Exports by format")
    if exports_by_format:
        for k, v in exports_by_format.most_common():
            st.write(f"- **{k.upper()}**: {v}")
    else:
        st.write("No export events yet.")

st.markdown("---")

c1, c2 = st.columns(2)

with c1:
    st.subheader("Top artworks (views)")
    top_n = st.slider("How many artworks to show", 5, 50, 15, key="top_artworks_n")
    if views_by_object:
        for obj, n in views_by_object.most_common(top_n):
            st.write(f"- **{obj}**: {n}")
    else:
        st.write("No artwork view events yet.")

with c2:
    st.subheader("Top artists (views)")
    top_n_a = st.slider("How many artists to show", 5, 50, 15, key="top_artists_n")
    if views_by_artist:
        for artist, n in views_by_artist.most_common(top_n_a):
            st.write(f"- **{artist}**: {n}")
    else:
        st.write("No artist view events yet.")

c3, c4 = st.columns(2)

with c3:
    st.subheader("Page views by page")
    if page_views_by_page:
        for page_name, count in page_views_by_page.most_common():
            st.write(f"- **{page_name}**: {count}")
    else:
        st.write("No page view events yet.")

with c4:
    st.subheader("Top search queries")
    max_q = st.slider(
        "How many queries to show",
        5,
        50,
        10,
        key="top_queries_n",
    )
    if search_queries:
        for query, n in search_queries.most_common(max_q):
            label = query or "(empty search)"
            st.write(f"- **{label}**: {n}")
    else:
        st.write("No search events yet.")

st.markdown("---")

with st.expander("🔎 Raw events (debug)", expanded=False):
    st.write(f"File: `{ANALYTICS_EVENTS_FILE}`")
    st.json(filtered[-50:])