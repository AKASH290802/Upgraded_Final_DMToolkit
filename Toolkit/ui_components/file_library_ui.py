"""
file_library_ui.py
------------------
Option A : show_file_library()
    Full "📁 File Library" tab — browse, preview, download, delete all
    source and output files, with search/filter controls.

Option B : show_file_picker_inline(key, org_name, object_name)
    Lightweight inline picker rendered inside any upload section.
    Returns (DataFrame, filename) or (None, None).
"""

import streamlit as st
import os
import json
from datetime import datetime

try:
    from .file_store_manager import (
        initialize_db, list_source_files, list_output_files,
        delete_source_file, delete_output_file, register_source_file,
        get_file_stats, scan_and_register_existing, repair_index,
    )
    from .utils import load_data_file
    from . import projects
except ImportError:
    from file_store_manager import (
        initialize_db, list_source_files, list_output_files,
        delete_source_file, delete_output_file, register_source_file,
        get_file_stats, scan_and_register_existing, repair_index,
    )
    from utils import load_data_file
    import projects


# ─────────────────────── helpers ────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _fmt_date(iso_str: str) -> str:
    try:
        return datetime.fromisoformat(iso_str).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return iso_str or '—'


PAGE_SIZE = 20


def _read_bytes(path: str) -> bytes:
    with open(path, 'rb') as handle:
        return handle.read()


def _paginate(files: list, key: str) -> list:
    """Show one page of files (the list used to render every stored file on every rerun)."""
    pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
    page_key = f"{key}_files_page"
    if st.session_state.get(page_key, 1) > pages:
        st.session_state[page_key] = 1
    col_info, col_page = st.columns([4, 1])
    with col_page:
        page = st.number_input("Page", min_value=1, max_value=pages, step=1, key=page_key,
                               disabled=pages == 1) if pages > 1 else 1
    start = (int(page) - 1) * PAGE_SIZE
    with col_info:
        st.caption(f"{len(files)} file(s) found — showing {start + 1}–{min(start + PAGE_SIZE, len(files))}"
                   + (f" (page {int(page)} of {pages})" if pages > 1 else ""))
    return files[start:start + PAGE_SIZE]


def _load_and_preview(file_path: str, file_id_key: str):
    """Render a preview button that expands an inline dataframe."""
    if not os.path.exists(file_path):
        st.warning("⚠️ File not found on disk.")
        return

    preview_key = f"preview_state_{file_id_key}"
    if st.button("👁️ Preview", key=f"btn_prev_{file_id_key}"):
        st.session_state[preview_key] = not st.session_state.get(preview_key, False)

    if st.session_state.get(preview_key, False):
        try:
            if file_path.endswith('.json'):
                with open(file_path) as jf:
                    st.json(json.load(jf))
            else:
                df = load_data_file(file_path)
                if df is not None:
                    st.dataframe(df.head(100), use_container_width=True)
                    st.caption(f"Showing up to 100 rows of {len(df)} total.")
        except Exception as e:
            st.error(f"Cannot preview: {e}")


# ─────────────────────── Option A ───────────────────────────────────────────

def _scope():
    """(scope, org names to show or None for all) — default: the sidebar org's project."""
    org = st.session_state.get('current_org')
    project = projects.project_for_org(org)
    options = [projects.SCOPE_PROJECT, projects.SCOPE_ORG, projects.SCOPE_ALL]
    default = projects.SCOPE_PROJECT if project else (projects.SCOPE_ORG if org else projects.SCOPE_ALL)
    chosen = st.session_state.get('fl_scope')
    # Keep the user's choice unless it no longer applies (no project / no org for the new sidebar org).
    if chosen not in options or (chosen == projects.SCOPE_PROJECT and not project) or \
            (chosen == projects.SCOPE_ORG and not org) or st.session_state.get('_fl_scope_org') != org:
        st.session_state['fl_scope'] = default
    st.session_state['_fl_scope_org'] = org
    scope = st.radio("Show files of", options, key='fl_scope', horizontal=True, label_visibility="collapsed")
    if scope == projects.SCOPE_PROJECT and project:
        labels = projects.project_labels(project)
        st.caption(f"📁 Project **{project['name']}** — {', '.join(project['orgs'])}"
                   + (f" (also filed as {', '.join(project['aliases'])})" if project['aliases'] else ""))
        return scope, labels
    if scope == projects.SCOPE_ORG and org:
        hint = "" if project else (" — it is not in a project yet: group one customer's orgs in "
                                   "⚙️ Configuration → Projects to see them together.")
        st.caption(f"🏢 Org **{org}**{hint}")
        return scope, [org]
    if scope != projects.SCOPE_ALL:
        st.caption("Select a Salesforce org in the sidebar to see its files.")
    return projects.SCOPE_ALL, None


def _org_filter(files, key):
    """Narrow to one org of the scope; 'Unassigned' = files whose org is not known."""
    orgs = sorted({f['org_name'] for f in files if (f['org_name'] or '').lower() not in projects.UNASSIGNED})
    options = ["All orgs in view"] + orgs + (["Unassigned"] if any(
        (f['org_name'] or '').lower() in projects.UNASSIGNED for f in files) else [])
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]
    choice = st.selectbox("Organisation", options, key=key)
    if choice == "Unassigned":
        return [f for f in files if (f['org_name'] or '').lower() in projects.UNASSIGNED]
    return files if choice == options[0] else [f for f in files if f['org_name'] == choice]


def _existing(files, what):
    """Only files that are on disk; say how many index rows point nowhere."""
    present = [f for f in files if os.path.exists(f['stored_path'])]
    gone = len(files) - len(present)
    if gone:
        st.caption(f"ℹ️ {gone} indexed {what} not found on disk are hidden — 🔄 Re-scan disk re-points the "
                   f"ones whose folder moved.")
    return present


def show_file_library():
    """
    Full File Library tab (Option A).
    Call this from the main page router when page == "📁 File Library".
    Shows the sidebar org's PROJECT by default (Configuration > Projects); "This org" and
    "All files" are one click away.
    """
    st.subheader("📁 File Library")
    st.caption("Every source file uploaded and every output file generated (validation, data loads, ETL) — "
               "kept across restarts.")

    # Index existing files on first visit this session
    if not st.session_state.get('_file_library_scanned'):
        with st.spinner("🔍 Indexing existing files on disk…"):
            n = scan_and_register_existing()
        st.session_state['_file_library_scanned'] = True
        if n > 0:
            st.toast(f"Indexed {n} existing file(s) found on disk.", icon="📂")

    col_scope, col_rescan = st.columns([8, 2], vertical_alignment="center")
    with col_scope:
        scope, scope_orgs = _scope()
    with col_rescan:
        if st.button("🔄 Re-scan disk", use_container_width=True,
                     help="Index new files, re-point entries whose folder moved, and file each one under its org"):
            with st.spinner("🔍 Re-scanning and repairing the index…"):
                found = scan_and_register_existing()
                fixed = repair_index()
            st.session_state['_file_library_scanned'] = True
            parts = [f"{found} new" if found else "", f"{fixed['relocated']} re-pointed" if fixed['relocated'] else "",
                     f"{fixed['duplicates_removed']} duplicates removed" if fixed['duplicates_removed'] else "",
                     f"{fixed['orgs_tagged']} filed under their org" if fixed['orgs_tagged'] else ""]
            summary = ", ".join(p for p in parts if p) or "nothing to change"
            st.session_state['_fl_rescan_note'] = summary + (
                f" (index backed up to {os.path.basename(fixed['backup'])})" if fixed['backup'] else "")
            st.rerun()
    note = st.session_state.pop('_fl_rescan_note', None)
    if note:
        st.success(f"🔄 Re-scan: {note}")

    sources = list_source_files(limit=100000, org_names=scope_orgs)
    outputs = list_output_files(limit=100000, org_names=scope_orgs)
    present_src = [f for f in sources if os.path.exists(f['stored_path'])]
    present_out = [f for f in outputs if os.path.exists(f['stored_path'])]
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Source Files", len(present_src))
    c2.metric("Output Files", len(present_out))
    c3.metric("Source Storage", f"{sum(f['file_size'] or 0 for f in present_src) / 1048576:.2f} MB")
    c4.metric("Output Storage", f"{sum(f['file_size'] or 0 for f in present_out) / 1048576:.2f} MB")
    c5.metric("Organisations", len({f['org_name'] for f in present_src + present_out
                                    if (f['org_name'] or '').lower() not in projects.UNASSIGNED}))

    tab_src, tab_out = st.tabs(["📂 Source Files", "📄 Output Files"])

    with tab_src:
        _show_source_files_tab(sources)

    with tab_out:
        _show_output_files_tab(outputs)


UPLOAD_TYPES = ['csv', 'xlsx', 'xls', 'psv', 'txt', 'json']


def upload_files(files, org_name: str, object_name: str = '') -> list:
    """Copy uploaded files into the File Library store under org_name (an org, or a project's
    own name for the whole project): file_store/source/<org_name>/<object or general>/.
    Returns the new (or existing, for the same bytes) file ids."""
    saved = []
    for f in files or []:
        file_id = register_source_file(f, f.name, org_name=org_name, object_name=(object_name or '').strip())
        if file_id is not None:
            saved.append(file_id)
    return saved


def _upload_box():
    """⬆️ Upload to the sidebar org's project (its own folder by default, or one of its orgs)."""
    org = st.session_state.get('current_org')
    project = projects.project_for_org(org)
    with st.container(border=True, key='fl_upload'):
        if project:
            st.markdown(f"**⬆️ Upload to project {project['name']}**")
            names = {projects.WHOLE_PROJECT: f"📁 Whole project ({project['name']})"}
            targets = [projects.WHOLE_PROJECT] + list(project['orgs'])
            if st.session_state.get('fl_up_target') not in targets:
                st.session_state['fl_up_target'] = projects.WHOLE_PROJECT
        elif org:
            st.markdown(f"**⬆️ Upload to {org}**")
            st.caption("This org is not in a project — group it in ⚙️ Configuration → Projects to share files "
                       "across the project's orgs.")
        else:
            st.caption("⬆️ Select a Salesforce org in the sidebar to upload files into its project.")
            return
        col_target, col_object = st.columns(2)
        with col_target:
            if project:
                target = st.selectbox("File for", targets, key='fl_up_target', format_func=lambda t: names.get(t, t),
                                      help="The whole project (seen from every org of the project) or one org")
                org_name = project['name'] if target == projects.WHOLE_PROJECT else target
            else:
                org_name = org
        with col_object:
            object_name = st.text_input("Object (optional)", key='fl_up_object', placeholder="e.g. Account")
        round_key = f"fl_up_files_{st.session_state.get('_fl_up_round', 0)}"
        files = st.file_uploader("Files", type=UPLOAD_TYPES, accept_multiple_files=True, key=round_key,
                                 label_visibility="collapsed")
        label = f"⬆️ Upload {len(files)} file{'s' if len(files) != 1 else ''}" if files else "⬆️ Upload"
        if st.button(label, key='fl_up_go', type='primary', disabled=not files):
            with st.spinner("Saving to the File Library…"):
                saved = upload_files(files, org_name, object_name)
            where = f"{org_name}/{object_name.strip() or 'general'}"
            st.session_state['_fl_up_note'] = f"⬆️ {len(saved)} file(s) saved to {where}."
            st.session_state['_fl_up_round'] = st.session_state.get('_fl_up_round', 0) + 1   # empty the uploader
            st.rerun()
    note = st.session_state.pop('_fl_up_note', None)
    if note:
        st.success(note)


def _show_source_files_tab(all_files):
    st.markdown("### 📂 Source Files")
    st.caption("Files you have uploaded for Data Loading, Validation, or any other operation. "
               "Use the filters to narrow the list, then preview, download, or delete individual files.")
    _upload_box()

    col1, col2 = st.columns(2)
    with col1:
        files = _org_filter(all_files, "fl_src_org")
    with col2:
        filter_obj = st.text_input("Filter by Object", key="src_filter_obj", placeholder="e.g. Account")
    if filter_obj.strip():
        files = [f for f in files if filter_obj.strip().lower() in (f['object_name'] or '').lower()]
    files = _existing(files, "source files")

    if not files:
        st.info(
            "No source files here yet. "
            "Upload a file in **Data Operations** or **Validation** and it will "
            "appear here automatically."
        )
        return

    files = _paginate(files, "src")

    for f in files:
        status_badge = "✅"
        org_obj = f"{f['org_name']} / {f['object_name'] or 'general'}"

        with st.expander(f['original_name'] + f"  [{org_obj}]  {status_badge}",
                         expanded=False):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Uploaded",  _fmt_date(f['uploaded_at']))
            m2.metric("Size",      _fmt_size(f['file_size']))
            m3.metric("Rows",      f['row_count'] if f['row_count'] else "—")
            m4.metric("Type",      f['file_type'].upper() if f['file_type'] else "—")

            st.caption(f"📍 `{f['stored_path']}`")

            btn1, btn2, btn3 = st.columns(3)

            with btn1:
                _load_and_preview(f['stored_path'], f"src_{f['id']}")

            with btn2:
                # The file is read only when the button is clicked.
                st.download_button(
                    label="📥 Download",
                    data=lambda path=f['stored_path']: _read_bytes(path),
                    file_name=f['original_name'],
                    key=f"dl_src_{f['id']}",
                    on_click='ignore',
                )

            with btn3:
                if st.button("🗑️ Delete", key=f"del_src_{f['id']}", type="secondary"):
                    delete_source_file(f['id'])
                    st.toast("File deleted.", icon="🗑️")
                    st.rerun()


def _show_output_files_tab(all_files):
    st.markdown("### 📄 Output Files")
    st.caption("Files generated by the application — validation reports, invalid-record exports, "
               "data-load results, ETL outputs, and more.")

    _OP_TYPES = [
        "All", "GenAI Validation", "Schema Validation",
        "Enhanced Validation", "Validation", "Data Load",
        "ETL", "Mapping", "Object Extraction", "unit_test",
    ]

    col1, col2, col3 = st.columns(3)
    with col1:
        files = _org_filter(all_files, "fl_out_org")
    with col2:
        filter_obj = st.text_input("Filter by Object", key="out_filter_obj", placeholder="e.g. Account")
    with col3:
        filter_op = st.selectbox("Filter by Operation", _OP_TYPES, key="out_filter_op")
    if filter_obj.strip():
        files = [f for f in files if filter_obj.strip().lower() in (f['object_name'] or '').lower()]
    if filter_op != "All":
        files = [f for f in files if f['operation_type'] == filter_op]
    files = _existing(files, "output files")

    if not files:
        st.info(
            "No output files here yet. "
            "Run a Validation or Data Load operation to generate output files."
        )
        return

    files = _paginate(files, "out")

    _OP_EMOJI = {
        "GenAI Validation":    "🤖",
        "Schema Validation":   "🔍",
        "Enhanced Validation": "⚡",
        "Validation":          "✅",
        "Data Load":           "📥",
        "ETL":                 "🔄",
        "Mapping":             "🗺️",
        "Object Extraction":   "📤",
        "unit_test":           "🧪",
    }

    for f in files:
        status_badge = "✅"
        org_obj = f"{f['org_name']} / {f['object_name'] or '—'}"
        op_emoji = _OP_EMOJI.get(f['operation_type'], "📄")
        op_label = f['operation_type'] or "Output"

        with st.expander(
            f"{op_emoji} {f['original_name']}  [{org_obj}]  {status_badge}",
            expanded=False,
        ):
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Generated",  _fmt_date(f['generated_at']))
            m2.metric("Size",       _fmt_size(f['file_size']))
            m3.metric("Rows",       f['row_count'] if f['row_count'] else "—")
            m4.metric("Operation",  op_label)

            if f.get('status'):
                st.caption(f"Status: {f['status']}")
            st.caption(f"📍 `{f['stored_path']}`")

            btn1, btn2, btn3 = st.columns(3)

            with btn1:
                _load_and_preview(f['stored_path'], f"out_{f['id']}")

            with btn2:
                # The file is read only when the button is clicked.
                st.download_button(
                    label="📥 Download",
                    data=lambda path=f['stored_path']: _read_bytes(path),
                    file_name=f['original_name'],
                    key=f"dl_out_{f['id']}",
                    on_click='ignore',
                )

            with btn3:
                if st.button("🗑️ Delete", key=f"del_out_{f['id']}", type="secondary"):
                    delete_output_file(f['id'])
                    st.toast("File deleted.", icon="🗑️")
                    st.rerun()


# ─────────────────────── Option B ───────────────────────────────────────────

def show_file_picker_inline(picker_key: str,
                             org_name: str = None,
                             object_name: str = None):
    """
    Option B — inline stored-file picker.

    Renders a selectbox listing previously stored source files,
    filtered first by (org_name + object_name), then by object_name only,
    then all files if nothing else matches.

    Returns
    -------
    (DataFrame, str)   if the user selects a valid file
    (None, None)       if nothing is selected yet
    """
    # Priority: org + object → object only → all
    files = list_source_files(org_name=org_name, object_name=object_name)
    if not files and object_name:
        files = list_source_files(object_name=object_name)
    if not files:
        files = list_source_files()

    # Filter to files that still exist on disk
    files = [f for f in files if os.path.exists(f['stored_path'])]

    if not files:
        st.info(
            "No stored source files found. "
            "Upload a file first to populate the library."
        )
        return None, None

    options_display = []
    options_map = {}
    for f in files:
        org_obj = f"{f['org_name']} / {f['object_name'] or 'general'}"
        label = (
            f"{f['original_name']}  "
            f"[{org_obj}]  "
            f"— {_fmt_date(f['uploaded_at'])}"
        )
        options_display.append(label)
        options_map[label] = f

    selected_label = st.selectbox(
        "Choose a stored file:",
        options=["— Select a file —"] + options_display,
        key=f"filepicker_{picker_key}",
    )

    if selected_label == "— Select a file —":
        return None, None

    selected = options_map[selected_label]

    try:
        df = load_data_file(selected['stored_path'])
        if df is not None:
            st.success(
                f"✅ Loaded **{selected['original_name']}** "
                f"({len(df):,} rows, {len(df.columns)} columns)"
            )
            return df, selected['original_name']
    except Exception as e:
        st.error(f"Error loading file: {e}")

    return None, None
