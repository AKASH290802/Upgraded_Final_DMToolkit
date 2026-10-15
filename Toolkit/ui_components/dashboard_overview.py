import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime, timedelta
from typing import Dict
from .utils import get_recent_logs, format_file_size
from . import connection_manager
from .navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE, navigate_to

def show_dashboard(credentials: Dict):
    """Home screen: one status bar, four KPI tiles, then the session and the quick actions side by side.

    The banner above already names the app, so there is no second title; there are no
    dividers and no full-width warning boxes (they cost most of the old screen's height).
    """
    import html
    from . import step_flow, theme

    ss = st.session_state
    org, obj = ss.current_org, ss.current_object
    connected = bool(org) and connection_manager.is_sidebar_org_connected()

    # 1. Status bar + the main action
    col_status, col_start = st.columns([3.2, 1.3], vertical_alignment="center")
    with col_status:
        if connected:
            message = f"Connected to <b>{html.escape(org)}</b>" + (f" · object <b>{html.escape(obj)}</b>" if obj else "")
            st.markdown(theme.status_bar_html('ok', message), unsafe_allow_html=True)
        elif org:
            st.markdown(theme.status_bar_html('bad', f"<b>{html.escape(org)}</b> is selected but not connected",
                                              "see the sidebar"), unsafe_allow_html=True)
        else:
            st.markdown(theme.status_bar_html('none', "Select a Salesforce org in the sidebar to get started",
                                              "every screen uses it"), unsafe_allow_html=True)
    with col_start:
        if st.button("🚀 Start guided migration", type="primary", use_container_width=True, key="dash_start_flow",
                     help="Open 1️⃣ Source/Target Information"):
            navigate_to(STEP1_PAGE)

    # 2. KPI tiles (real numbers)
    groups = connection_manager.classify_credentials(connection_manager.get_credentials())
    sources = sum(len(groups[k]) for k in ('sqlserver', 'oracle', 'snowflake', 'postgres'))
    tiles = [
        ("🏢", "Salesforce orgs", len(groups['salesforce']), "saved in Configuration"),
        ("🗄️", "Source connections", sources, "SQL Server · Oracle · others"),
        ("📁", "Processed files", count_processed_files(), "data and load files"),
        ("✅", "Validation runs", _validation_runs_last_7_days(org),
         f"last 7 days · {org}" if org else "last 7 days · all orgs"),
    ]
    for col, (icon, label, value, sub) in zip(st.columns(4), tiles):
        col.markdown(theme.kpi_tile_html(icon, label, value, sub), unsafe_allow_html=True)

    # 3. Session (left) and quick actions (right)
    col_session, col_actions = st.columns([3, 2], gap="medium")
    with col_session:
        with st.container(border=True, key="dash_session"):
            st.markdown("#### 🎯 Session")
            done = sum(step_flow.step_done(n) for n in range(1, 5))
            if org:
                org_value = f"{html.escape(org)} · " + ("✅ connected" if connected else "❌ not connected")
            else:
                org_value = "none selected"
            source = connection_manager.current_source_key()
            st.markdown(theme.kv_rows_html([
                ("Salesforce org", org_value),
                ("Object", html.escape(obj) if obj else "none selected"),
                ("Source connection", html.escape(connection_manager.source_label(source)) if source else "none"),
                ("Guided migration", f"{done} of 4 steps done"),
            ]), unsafe_allow_html=True)
            if org and not connected:
                error = connection_manager.get_sf_connection_error()
                if error:
                    st.caption(f"Last connection error: {error.rstrip('. ')}. Check this org's credentials, "
                               "then click 🔁 Retry connection in the sidebar.")
            st.markdown("#### 📋 Recent activity")
            items = _recent_activity()
            if items:
                st.markdown('<ul class="dm-feed">' + "".join(
                    f'<li class="{kind}"><span class="d"></span><span class="t">{html.escape(when)}</span>'
                    f'<span>{html.escape(message)}</span></li>' for when, message, kind in items) + '</ul>',
                    unsafe_allow_html=True)
            else:
                st.caption("No activity yet in this session.")

    with col_actions:
        with st.container(border=True, key="dash_actions"):
            st.markdown("#### ⚡ Quick actions")
            no_org = None if org else "Select a Salesforce org in the sidebar first"
            actions = [("✅ Validation", "dash_validation", STEP2_PAGE),
                       ("📥 Data Operations", "dash_data_ops", STEP3_PAGE),
                       ("🧪 Unit Testing", "dash_testing", STEP4_PAGE),
                       ("🗺️ Mapping", "dash_mapping", "🗺️ Mapping")]
            for row in (actions[:2], actions[2:]):
                for col, (label, key, page) in zip(st.columns(2), row):
                    with col:
                        if st.button(label, key=key, use_container_width=True, disabled=not org, help=no_org):
                            navigate_to(page)
            with st.expander("📖 Getting started", expanded=False):
                st.markdown(
                    "0. 🏢 Pick the org (and SQL Server / Oracle if needed) in the sidebar — every screen uses them\n"
                    "1. 1️⃣ **Source/Target Information** — choose the source data once and the target object\n"
                    "2. 2️⃣ **Mapping & Validation** — map the columns and validate the rows\n"
                    "3. 3️⃣ **Data Operations** — load the valid rows into Salesforce or SQL Server\n"
                    "4. 4️⃣ **Unit Testing** — test the loaded records; this completes the cycle\n\n"
                    "Each step unlocks the next (**Next ➡️** at the bottom of a step). The tabs inside a step are "
                    "optional. Results are in 📋 **Logs & Reports**.")


def _validation_runs_last_7_days(org) -> int:
    try:
        from .file_store_manager import list_validation_runs
        since = (datetime.now() - timedelta(days=7)).isoformat(timespec='seconds')
        return sum(1 for r in list_validation_runs(org_name=org or None, limit=5000) if r['created_at'] >= since)
    except Exception:
        return 0


def _recent_activity(limit: int = 5):
    """[(HH:MM, message, 'info' | 'warning' | 'error'), ...] newest first: this session's steps, then the log."""
    items = []
    for status in reversed(list((st.session_state.get('processing_status') or {}).values())):
        try:
            when = status.get('timestamp', datetime.now()).strftime("%H:%M")
            kind = status.get('type', 'info')
            items.append((when, str(status.get('message', '')), kind if kind in ('warning', 'error') else 'info'))
        except Exception:
            continue
    for log in get_recent_logs(limit=limit) or []:
        try:
            if isinstance(log, dict):
                stamp = log.get('timestamp', datetime.now())
                when = stamp.strftime("%H:%M") if hasattr(stamp, 'strftime') else str(stamp)[11:16]
                kind = log.get('type', 'info')
                items.append((when, str(log.get('message', '')), kind if kind in ('warning', 'error') else 'info'))
            else:
                items.append(("", str(log)[:120], 'info'))
        except Exception:
            continue
    return items[:limit]


@st.cache_data(ttl=60, show_spinner=False)  # folder scan: at most once a minute
def count_processed_files() -> int:
    """Count total processed files across all operations"""
    count = 0
    try:
        # Count files in DataFiles folder
        datafiles_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DataFiles')
        if os.path.exists(datafiles_path):
            for root, dirs, files in os.walk(datafiles_path):
                count += len([f for f in files if f.endswith(('.csv', '.xlsx', '.xls', '.psv'))])
        
        # Count files in DataLoader_Logs
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DataLoader_Logs')
        if os.path.exists(logs_path):
            for root, dirs, files in os.walk(logs_path):
                count += len([f for f in files if f.endswith(('.csv', '.xlsx', '.xls', '.psv'))])
    except:
        pass
    
    return count