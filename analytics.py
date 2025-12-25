# analytics.py
"""
Simple local analytics for Rijksmuseum Explorer.

- Stores events as JSON lines in `analytics_events.jsonl`
- Uses Streamlit session_state to keep a session_id
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

ANALYTICS_FILE = Path("analytics_events.jsonl")


def _get_session_id() -> str:
    """Return a stable session_id for the current Streamlit session."""
    key = "_analytics_session_id"
    sid = st.session_state.get(key)
    if not sid:
        sid = str(uuid.uuid4())
        st.session_state[key] = sid
    return sid


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
    record = {
        "ts": time.time(),
        "event": event,
        "page": page,
        "session_id": _get_session_id(),
        "props": props or {},
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