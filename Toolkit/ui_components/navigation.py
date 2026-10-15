"""
Sidebar page navigation.

The sidebar radio uses ONE fixed key ('nav_page'). Code that wants to change
page must not assign the radio key after it is drawn (Streamlit raises), so it
requests a page with request_page()/navigate_to(); the request is applied by
apply_pending_navigation() before the radio is drawn on the next run.

Old code that sets st.session_state.active_page directly and reruns keeps
working: apply_pending_navigation() notices active_page changed and follows it.
"""

import streamlit as st

DASHBOARD = "🏠 Dashboard"
STEP1_PAGE = "1️⃣ Source/Target Information"
STEP2_PAGE = "2️⃣ Mapping & Validation"
STEP3_PAGE = "3️⃣ Data Operations"
STEP4_PAGE = "4️⃣ Unit Testing"

# The sidebar menu, in order, under its section headings (drawn by theme.nav_section_css()).
NAV_SECTIONS = [
    ("Home", [DASHBOARD, "⚙️ Configuration"]),
    ("Guided migration", [STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE]),
    ("Tools", ["📊 Data Hub", "📁 File Library", "🎯 Migration Readiness", "🧩 Multi Data File",
               "🗺️ Mapping", "🔄 Org Migration", "🔍 Object Comparison"]),
    ("Reports", ["📋 Logs & Reports"]),
]

PAGE_LIST = [page for _, pages in NAV_SECTIONS for page in pages]

# Page names used before the guided flow was introduced.
LEGACY_PAGE_ALIASES = {
    "1️⃣ Mapping/Validation": STEP2_PAGE,
    "1️⃣ Data Loading": STEP1_PAGE,
    "2️⃣ Data Operations": STEP3_PAGE,
    "3️⃣ Unit Testing": STEP4_PAGE,
}

NAV_KEY = 'nav_page'


def resolve_page(page: str) -> str:
    page = LEGACY_PAGE_ALIASES.get(page, page)
    return page if page in PAGE_LIST else DASHBOARD


def request_page(page: str) -> None:
    """Callback-safe: switch page on the next run (use with on_click=)."""
    st.session_state._pending_nav = resolve_page(page)


def navigate_to(page: str) -> None:
    """Switch page now (use inside `if st.button(...):`)."""
    request_page(page)
    st.rerun()


def apply_pending_navigation() -> None:
    """Called by the sidebar before the navigation radio is drawn."""
    ss = st.session_state
    if NAV_KEY not in ss:
        ss[NAV_KEY] = resolve_page(ss.get('active_page', DASHBOARD))
    elif ss.get('active_page') and ss.get('active_page') != ss.get('_nav_synced_page'):
        # Legacy code assigned active_page and reran.
        ss[NAV_KEY] = resolve_page(ss.active_page)
    if '_pending_nav' in ss:
        ss[NAV_KEY] = ss.pop('_pending_nav')
    if ss[NAV_KEY] not in PAGE_LIST:
        ss[NAV_KEY] = resolve_page(ss[NAV_KEY])


def render_navigation_radio() -> str:
    """Draw the sidebar radio and return the selected page."""
    apply_pending_navigation()
    page = st.radio("Choose a module:", PAGE_LIST, key=NAV_KEY, label_visibility="collapsed", width="stretch")
    st.session_state.active_page = page
    st.session_state._nav_synced_page = page
    return page
