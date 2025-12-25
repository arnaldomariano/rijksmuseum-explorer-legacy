# analytics.py
"""
Simple local analytics for Rijksmuseum Explorer.

- Stores events as JSON lines in `analytics_events.json`
- Uses Streamlit session_state to keep a session_id
- Optional config file with installation metadata (city/country/timezone)
- Provides:
    track_event(event, page, props=None)
    track_event_once(event, page, once_key, props=None)
"""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional
import streamlit as st
from app_paths import ANALYTICS_FILE, ANALYTICS_CONFIG_FILE
# -------------------------------------------------------------------
# Paths
# -------------------------------------------------------------------

# Config file with installation metadata (same folder)
ANALYTICS_CONFIG_FILE = ANALYTICS_FILE.with_name("analytics_config.json")

# cache em memória para não reler o config toda hora
_INSTALL_META_CACHE: Dict[str, Any] | None = None


def _get_session_id() -> str:
    """Return a stable session_id for the current Streamlit session."""
    key = "_analytics_session_id"
    sid = st.session_state.get(key)
    if not sid:
        sid = str(uuid.uuid4())
        st.session_state[key] = sid
    return sid


def _get_installation_metadata() -> Dict[str, Any]:
    """
    Read installation metadata from analytics_config.json, if present.

    Expected keys (all optional):
        - installation_city
        - installation_country
        - installation_timezone
    """
    global _INSTALL_META_CACHE

    if _INSTALL_META_CACHE is not None:
        return _INSTALL_META_CACHE

    meta: Dict[str, Any] = {}
    try:
        if ANALYTICS_CONFIG_FILE.exists():
            with ANALYTICS_CONFIG_FILE.open("r", encoding="utf-8") as f:
                loaded = json.load(f) or {}
                if isinstance(loaded, dict):
                    meta = loaded
    except Exception:
        # nunca quebrar o app por causa de analytics
        meta = {}

    # valores default (caso não estejam no arquivo)
    meta.setdefault("installation_city", "Unknown")
    meta.setdefault("installation_country", "Unknown")
    meta.setdefault("installation_timezone", "UTC")

    _INSTALL_META_CACHE = meta
    return meta

def _load_installation_metadata() -> Dict[str, Any]:
    """
    Read installation metadata (city/country/timezone) from analytics_config.json.

    This is optional and purely local — no network calls.
    """
    cache_key = "_analytics_installation_meta"
    if cache_key in st.session_state:
        return st.session_state[cache_key]

    meta: Dict[str, Any] = {}
    try:
        if ANALYTICS_CONFIG_FILE.exists():
            with ANALYTICS_CONFIG_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                meta = {
                    "install_city": data.get("installation_city"),
                    "install_country": data.get("installation_country"),
                    "install_timezone": data.get("installation_timezone"),
                }
    except Exception:
        meta = {}

    st.session_state[cache_key] = meta
    return meta

def _write_event(record: Dict[str, Any]) -> None:
    """Append a single event as JSON line. Fail silently if anything breaks."""
    try:
        ANALYTICS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with ANALYTICS_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # analytics nunca deve quebrar o app
        pass


def track_event(
    event: str,
    page: str,
    props: Optional[Dict[str, Any]] = None,
) -> None:
    """Log a generic analytics event."""
    base_props = props.copy() if isinstance(props, dict) else {}

    # anexamos metadados de instalação em todos os eventos
    base_props.update(_load_installation_metadata())

    record = {
        "ts": time.time(),
        "event": event,
        "page": page,
        "session_id": _get_session_id(),
        "props": base_props,
    }
    _write_event(record)

def track_event_once(
    event: str,
    page: str,
    once_key: str,
    props: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Log an event only once per session, based on `once_key`.
    Used for page_view etc.
    """
    state_key = f"_analytics_once::{once_key}"
    if st.session_state.get(state_key):
        return

    st.session_state[state_key] = True
    track_event(event=event, page=page, props=props)