# UI styling note: prefer width="stretch" or width="content" for Streamlit controls.
# Avoid using use_container_width anywhere in the app codebase.
import base64
import json
import os
from datetime import date as _date


def add_sidebar_logo(hide_sidebar_logo: bool = False):
    """Inject the site logo at the bottom-center of the sidebar."""
    import streamlit as st
    logo_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data_files", "logo.png")
    )
    with open(logo_path, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()

    # ── Watchlist sidebar panel ──────────────────────────────────────────────
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = []
    wl = st.session_state["watchlist"]
    if wl:
        st.sidebar.markdown("---")
        st.sidebar.markdown(f"**📌 Watchlist** ({len(wl)} case{'s' if len(wl) != 1 else ''})")
        for i, item in enumerate(wl):
            c1, c2 = st.sidebar.columns([4, 1])
            c1.caption(item.get("name", "Unknown case")[:38])
            if c2.button("✕", key=f"wl_remove_{i}", help="Remove from watchlist"):
                st.session_state["watchlist"].pop(i)
                st.rerun()
        if st.sidebar.button("Clear all", key="wl_clear_all"):
            st.session_state["watchlist"] = []
            st.rerun()

    if not hide_sidebar_logo:
        st.sidebar.markdown(
            f"""
            <div style="text-align:center; padding: 0.5rem 1rem 0 1rem;">
                <img src="data:image/png;base64,{logo_b64}"
                     style="width:100%;max-width:330px;height:auto;display:block;margin:0 auto;"
                     alt="Supreme Scrutiny Logo">
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Data freshness notice
    _changelog_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "data_files", "changelog.json")
    )
    if os.path.exists(_changelog_path):
        try:
            with open(_changelog_path, encoding="utf-8") as _f:
                _cl = json.load(_f)
            _updated = _cl.get("last_updated", "")
            if _updated:
                try:
                    _days = (_date.today() - _date.fromisoformat(_updated)).days
                    _age = "today" if _days == 0 else (f"{_days}d ago" if _days < 30 else f"{_days // 30}mo ago")
                    _rows = _cl.get("files", {}).get("cases_by_term.parquet", {}).get("rows", "")
                    _label = f"🗄️ Data: {_rows:,} cases · updated {_age}" if _rows else f"🗄️ Data updated {_age}"
                    st.sidebar.caption(_label)
                except (ValueError, TypeError):
                    pass
        except (OSError, json.JSONDecodeError):
            pass


def data_unavailable(message: str = "Data temporarily unavailable.") -> None:
    """Display a standardised data-unavailable warning in the Streamlit UI."""
    import streamlit as st
    st.warning(
        f"⚠️ {message} "
        "The local data files may be missing or corrupted. "
        "Run `scripts/refresh_parquet.py` to rebuild them.",
        icon="⚠️",
    )


def watchlist_button(case_name: str, oyez_url: str = "", key_suffix: str = "") -> None:
    """
    Render a small bookmark toggle button for a case.
    Adds/removes the case from st.session_state['watchlist'].
    """
    import streamlit as st
    if "watchlist" not in st.session_state:
        st.session_state["watchlist"] = []
    wl = st.session_state["watchlist"]
    is_saved = any(item.get("name") == case_name for item in wl)
    label = "🔖 Saved" if is_saved else "🔖 Save"
    btn_key = f"wl_btn_{case_name[:30]}_{key_suffix}"
    if st.button(label, key=btn_key, help="Add to / remove from watchlist"):
        if is_saved:
            st.session_state["watchlist"] = [i for i in wl if i.get("name") != case_name]
        else:
            st.session_state["watchlist"].append({"name": case_name, "oyez_url": oyez_url})
        st.rerun()


_JUSTICES_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data_files", "current_justices.json")
)


def get_current_justices() -> list[dict]:
    """Return the list of current SCOTUS justices from data_files/current_justices.json.

    Each entry has: short, full, lean, appointed_by, year_confirmed, seat.
    Falls back to a hardcoded list if the file is missing.
    """
    if os.path.exists(_JUSTICES_PATH):
        with open(_JUSTICES_PATH, encoding="utf-8") as f:
            return json.load(f)
    # Fallback — keeps the app functional if the file is accidentally deleted
    return [
        {"short": "Roberts",   "full": "John G. Roberts",      "lean": "Conservative"},
        {"short": "Thomas",    "full": "Clarence Thomas",       "lean": "Conservative"},
        {"short": "Alito",     "full": "Samuel Alito",          "lean": "Conservative"},
        {"short": "Sotomayor", "full": "Sonia Sotomayor",       "lean": "Liberal"},
        {"short": "Kagan",     "full": "Elena Kagan",           "lean": "Liberal"},
        {"short": "Gorsuch",   "full": "Neil Gorsuch",          "lean": "Conservative"},
        {"short": "Kavanaugh", "full": "Brett Kavanaugh",       "lean": "Moderate"},
        {"short": "Barrett",   "full": "Amy Coney Barrett",     "lean": "Conservative"},
        {"short": "Jackson",   "full": "Ketanji Brown Jackson", "lean": "Liberal"},
    ]
