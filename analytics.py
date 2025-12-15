# analytics.py
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import streamlit as st

from app_paths import ANALYTICS_EVENTS_FILE, ANALYTICS_DIR


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def track_event(
    event: str,
    page: str,
    props: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Append an anonymous analytics event as JSON Lines.

    - event: string id (e.g. "page_view", "search_run")
    - page: page name (e.g. "Explorer", "My_Selection")
    - props: small dict with metadata (no personal data)
    - session_id: optional anonymous session identifier
    """
    try:
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)

        record: Dict[str, Any] = {
            "ts": _utc_now_iso(),
            "event": str(event),
            "page": str(page),
            "props": props or {},
        }

        if session_id:
            record["session_id"] = str(session_id)

        with open(ANALYTICS_EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    except Exception:
        # Analytics must NEVER crash the app
        pass


def track_event_once(
    event: str,
    page: str,
    props: Optional[Dict[str, Any]] = None,
    once_key: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """
    Track an analytics event only once per Streamlit session.
    Good for: page_view, first_visit_to_page.
    """
    if once_key is None:
        once_key = f"analytics_once::{event}::{page}"

    if st.session_state.get(once_key):
        return

    st.session_state[once_key] = True

    track_event(
        event=event,
        page=page,
        props=props,
        session_id=session_id,
    )


def now_unix() -> float:
    return time.time()


def clear_analytics_events() -> bool:
    try:
        ANALYTICS_DIR.mkdir(parents=True, exist_ok=True)
        with open(ANALYTICS_EVENTS_FILE, "w", encoding="utf-8") as f:
            f.write("")
        return True
    except Exception:
        return False