"""
Step 1 - Source/Target Information.

One place to bring source data into the app. Sources: file upload, File Library,
Salesforce (SOQL), SQL Server, Oracle, or a dataset already in the Data Hub.
Salesforce, SQL Server and Oracle always use the sidebar connections.

The loaded data is "staged" first (preview only). When the user picks the target
Salesforce object and clicks "Use this dataset", it is stored in the Data Hub and
becomes the guided-flow dataset that Steps 2-4 use.

render_source_loader() is also used by the Data Hub page's Load Data tab.
"""

import io
import json
import os
import re
from typing import Callable, Dict, Optional

import pandas as pd
import streamlit as st

from ui_components import step_flow
from ui_components.connection_manager import (
    clear_salesforce_metadata_cache, display_name, get_sf_connection, oracle_connection_picker,
    run_oracle_query, run_sql_query, sql_connection_picker,
)
from ui_components.utils import get_object_description, get_salesforce_objects

SOURCES = [
    "📤 Upload File",
    "📁 File Library",
    "☁️ Salesforce (SOQL)",
    "🗄️ SQL Server",
    "🔶 Oracle",
    "📊 Data Hub dataset",
]
NO_TABLE = "-- none (write my own query) --"


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------

def _stage(prefix: str, df: pd.DataFrame, name: str, source_type: str, source_label: str,
           details: Optional[Dict] = None, signature=None, hub_dataset_id: Optional[str] = None,
           suggested_object: Optional[str] = None) -> None:
    st.session_state[f"{prefix}_staged"] = {
        'df': df, 'name': name, 'source_type': source_type, 'source_label': source_label,
        'details': details or {}, 'signature': signature, 'hub_dataset_id': hub_dataset_id,
        'suggested_object': suggested_object,
    }
    # Reset the name box to the new data's name (runs before that widget is drawn).
    st.session_state[f"{prefix}_ds_name"] = name


def get_staged(prefix: str) -> Optional[Dict]:
    return st.session_state.get(f"{prefix}_staged")


def _ensure_name_default(prefix: str, staged: Dict) -> None:
    """Widget state is dropped while a page is not shown; restore the default name."""
    if not st.session_state.get(f"{prefix}_ds_name"):
        st.session_state[f"{prefix}_ds_name"] = staged['name']


def _restore(key: str, options=None) -> None:
    """Put back a widget value Streamlit dropped while the page was not shown."""
    saved = f"{key}__saved"
    if key not in st.session_state and saved in st.session_state:
        value = st.session_state[saved]
        if options is None or value in options:
            st.session_state[key] = value


def _remember(key: str) -> None:
    if key in st.session_state:
        st.session_state[f"{key}__saved"] = st.session_state[key]


def _clean_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df.dropna(how='all')


def _cell_text(value):
    """Cell as text, the way the CSV/Excel readers produce it (None when missing, 10.0 -> '10')."""
    if value is None:
        return None
    if isinstance(value, (list, dict)):
        return json.dumps(value, default=str)
    if isinstance(value, str):
        return value
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def _to_text_frame(df: pd.DataFrame) -> pd.DataFrame:
    # Built column by column with dtype=object: DataFrame.map would let pandas
    # re-infer a string dtype and turn None back into NaN.
    return pd.DataFrame({column: pd.Series([_cell_text(v) for v in df[column]], index=df.index, dtype=object)
                         for column in df.columns}, index=df.index)


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def _parse_upload(uploaded, sheet: Optional[str]) -> pd.DataFrame:
    return _parse_bytes(uploaded.getvalue(), uploaded.name, sheet)


def _parse_bytes(data: bytes, file_name: str, sheet: Optional[str]) -> pd.DataFrame:
    """A data file's bytes as a text table (the same rules for uploads and File Library files)."""
    name = file_name.lower()
    if name.endswith(('.xlsx', '.xls')):
        return pd.read_excel(io.BytesIO(data), sheet_name=sheet or 0, dtype=str)
    if name.endswith('.json'):
        payload = json.load(io.BytesIO(data))
        if isinstance(payload, dict):
            payload = payload.get('records') or payload.get('data') or [payload]
        return _to_text_frame(pd.json_normalize(payload))
    sep = '|' if name.endswith('.psv') else (None if name.endswith('.txt') else ',')
    for encoding in ('utf-8-sig', 'latin-1'):
        try:
            return pd.read_csv(io.BytesIO(data), sep=sep, dtype=str, encoding=encoding,
                               engine='python' if sep is None else 'c')
        except UnicodeDecodeError:
            continue
    raise ValueError("Could not decode the file as UTF-8 or Latin-1")


def _big_file_ok(prefix: str, size_bytes: int, file_name: str, signature) -> bool:
    """False (with a warning and a 'read anyway' button) when the file may not fit in free memory."""
    from ui_components import large_data
    warning = large_data.memory_warning(size_bytes, file_name)
    accepted_key = f"_{prefix}_big_file_accepted"
    if not warning or st.session_state.get(accepted_key) == signature:
        notice = large_data.cycle_notice(size_bytes, file_name)
        if notice:
            st.info(notice)
        return True
    st.warning(warning)
    if st.button("📖 Read the file anyway", key=f"{prefix}_big_file_read"):
        st.session_state[accepted_key] = signature
        return True
    return False


def _source_upload(prefix: str) -> None:
    from ui_components import large_data
    limit = large_data.upload_limit_mb()
    uploaded = st.file_uploader(
        "Upload a data file", type=['csv', 'xlsx', 'xls', 'psv', 'txt', 'json'],
        key=f"{prefix}_upload",
        help=f"CSV, Excel, PSV (pipe-separated), TXT (delimiter auto-detected) or JSON, up to "
             f"{limit:,} MB. For bigger files, copy them into the DataFiles folder and choose 📁 File Library "
             f"(read from disk, no upload). CSV needs far less memory than Excel.",
    )
    if not uploaded:
        return
    sheet = None
    if uploaded.name.lower().endswith(('.xlsx', '.xls')):
        # Opening a big workbook takes seconds: read the sheet names once per upload.
        sheet = _excel_sheet(prefix, uploaded.file_id, uploaded.getvalue)
        if sheet is None:
            return

    signature = ('upload', uploaded.file_id, sheet)
    staged = get_staged(prefix)
    if staged and staged.get('signature') == signature:
        return  # already parsed - do not re-read the file on every rerun
    if not _big_file_ok(prefix, uploaded.size, uploaded.name, signature):
        return
    try:
        with st.spinner(f"Reading {uploaded.name}..."):
            df = _clean_frame(_parse_upload(uploaded, sheet))
    except ImportError:
        st.error("❌ Reading .xls files needs the `xlrd` package (pip install xlrd). "
                 "Or save the workbook as .xlsx and upload it again.")
        return
    except Exception as exc:
        st.error(f"❌ Could not read the file: {exc}")
        return
    base = os.path.splitext(uploaded.name)[0]
    _stage(prefix, df, f"{base} - {sheet}" if sheet and sheet != 0 else base,
           'file_upload', f"file {uploaded.name}", {'file_name': uploaded.name, 'sheet': sheet},
           signature=signature)
    try:
        from ui_components.file_store_manager import register_source_file
        register_source_file(uploaded, uploaded.name, org_name=st.session_state.get('current_org') or 'unknown',
                             object_name='', row_count=len(df), col_count=len(df.columns))
    except Exception:
        pass


READABLE_FILE_TYPES = ('.csv', '.xlsx', '.xls', '.psv', '.txt', '.json')


def _excel_sheet(prefix: str, data_id, read_bytes) -> Optional[str]:
    """Sheet picker for a workbook (sheet names read once per file); None if it could not be opened."""
    sheets_key = f"{prefix}_sheet_names"
    cached = st.session_state.get(sheets_key)
    if not cached or cached[0] != data_id:
        try:
            sheets = pd.ExcelFile(io.BytesIO(read_bytes())).sheet_names
        except ImportError:
            st.error("❌ Reading .xls files needs the `xlrd` package (pip install xlrd). "
                     "Or save the workbook as .xlsx and use it again.")
            return None
        except Exception as exc:
            st.error(f"❌ Could not read the Excel workbook: {exc}")
            return None
        st.session_state[sheets_key] = (data_id, sheets)
    sheets = st.session_state[sheets_key][1]
    return st.selectbox("Sheet", sheets, key=f"{prefix}_sheet") if len(sheets) > 1 else sheets[0]


def _library_scope(prefix: str, org: Optional[str]):
    """Which stored files to offer, like the 📁 File Library page: org names to list, or None for all.

    Default: the sidebar org's project (its orgs and alias folders), else the org, else all files.
    """
    try:
        from ui_components import projects
    except ImportError:
        return None
    project = projects.project_for_org(org)
    options = [projects.SCOPE_PROJECT, projects.SCOPE_ORG, projects.SCOPE_ALL]
    scope_key, org_key = f"{prefix}_library_scope", f"_{prefix}_library_scope_org"
    chosen = st.session_state.get(scope_key)
    # Keep the user's choice unless it no longer applies (no project / no org for a new sidebar org).
    if chosen not in options or (chosen == projects.SCOPE_PROJECT and not project) or \
            (chosen == projects.SCOPE_ORG and not org) or st.session_state.get(org_key) != org:
        st.session_state[scope_key] = (projects.SCOPE_PROJECT if project else
                                       projects.SCOPE_ORG if org else projects.SCOPE_ALL)
    st.session_state[org_key] = org
    scope = st.radio("Show files of", options, key=scope_key, horizontal=True,
                     help="The project groups one customer's orgs (⚙️ Configuration → Projects).")
    if scope == projects.SCOPE_PROJECT and project:
        st.caption(f"📁 Project **{project['name']}** — {', '.join(project['orgs'])}")
        return projects.project_labels(project)
    if scope == projects.SCOPE_ORG and org:
        return [org]
    return None


def _source_file_library(prefix: str) -> None:
    try:
        from ui_components.file_store_manager import list_source_files
    except ImportError:
        st.error("❌ File Library is not available.")
        return
    from ui_components import large_data
    # Files copied into the DataFiles folder (any size, no upload) are indexed once per session.
    rescan = st.button("🔄 Re-scan disk", key=f"{prefix}_library_rescan",
                       help="Find files copied into the DataFiles folder since the last scan.")
    if rescan or not st.session_state.get('_file_library_scanned'):
        try:
            from ui_components.file_store_manager import scan_and_register_existing
            found = scan_and_register_existing()
            if rescan:
                st.toast(f"Found {found} new file(s) on disk.", icon="📂")
        except Exception:
            pass
        st.session_state['_file_library_scanned'] = True
    st.caption(f"💡 Files too big to upload: copy them into `{large_data.DATAFILES_DIR}"
               f"{os.sep}<org>{os.sep}<object>` and pick them here — they are read from disk, with no size "
               f"limit other than this machine's memory.")
    org = st.session_state.get('current_org')
    labels_in_scope = _library_scope(prefix, org)
    # The sidebar org's files first, newest first.
    found_files = (list_source_files(org_names=labels_in_scope, limit=1000) if labels_in_scope
                   else list_source_files(limit=1000))
    files = [f for f in found_files
             if os.path.exists(f['stored_path']) and f['stored_path'].lower().endswith(READABLE_FILE_TYPES)]
    files.sort(key=lambda f: str(f.get('uploaded_at') or ''), reverse=True)
    files.sort(key=lambda f: f.get('org_name') != org)
    if not files:
        st.info("No stored source files found here. Upload a file first, or choose 🌐 All files above.")
        return
    labels = {f"{f['original_name']}  [{f['org_name']} / {f['object_name'] or 'general'}]  — "
              f"{str(f['uploaded_at'])[:16].replace('T', ' ')}": f for f in files}
    options = ["— Select a file —"] + list(labels)
    pick_key = f"{prefix}_library_pick"
    _restore(pick_key, options)
    label = st.selectbox("Stored file", options, key=pick_key)
    _remember(pick_key)
    if label == options[0]:
        return
    record = labels[label]
    path = record['stored_path']

    def read_bytes():
        with open(path, 'rb') as handle:
            return handle.read()

    sheet = None
    if path.lower().endswith(('.xlsx', '.xls')):
        sheet = _excel_sheet(prefix, (path, os.path.getmtime(path)), read_bytes)
        if sheet is None:
            return
    signature = ('library', path, os.path.getmtime(path), sheet)
    staged = get_staged(prefix)
    if staged and staged.get('signature') == signature:
        return  # already loaded - do not re-read the file on every rerun
    if not _big_file_ok(prefix, os.path.getsize(path), record['original_name'], signature):
        return
    try:
        with st.spinner(f"Reading {record['original_name']}..."):
            df = _clean_frame(_parse_bytes(read_bytes(), record['original_name'], sheet))
    except ImportError:
        st.error("❌ Reading .xls files needs the `xlrd` package (pip install xlrd). "
                 "Or save the workbook as .xlsx and use it again.")
        return
    except Exception as exc:
        st.error(f"❌ Could not read the file: {exc}")
        return
    base = os.path.splitext(record['original_name'])[0]
    _stage(prefix, df, f"{base} - {sheet}" if sheet and sheet != 0 else base, 'file_library',
           f"File Library file {record['original_name']}", {'file_name': record['original_name'],
                                                            'stored_path': path, 'sheet': sheet},
           signature=signature)


def _flatten_record(record: Dict, prefix: str, out: Dict, child_relationships: set) -> None:
    for key, value in record.items():
        if key == 'attributes':
            continue
        name = f"{prefix}{key}"
        if isinstance(value, dict) and 'records' in value and 'totalSize' in value:
            child_relationships.add(name)  # child subquery, e.g. (SELECT Id FROM Contacts)
        elif isinstance(value, dict):
            _flatten_record(value, f"{name}.", out, child_relationships)
        else:
            out[name] = value


def _flatten_records(records):
    """Salesforce records -> DataFrame of text cells.

    Parent relationships become dotted columns ('Owner.Name'); an empty
    relationship leaves those cells empty. Child subqueries are left out (they
    are lists of records, not fields of this object). Returns (df, dropped).
    """
    if not records:
        return pd.DataFrame(), []
    child_relationships = set()
    rows = []
    for record in records:
        flat = {}
        _flatten_record(record, '', flat, child_relationships)
        rows.append(flat)
    df = pd.DataFrame(rows)
    # 'Parent' is None where the lookup is empty and 'Parent.Name' holds the value elsewhere.
    parents = [c for c in df.columns if any(other.startswith(f"{c}.") for other in df.columns)]
    df = df.drop(columns=parents + [c for c in child_relationships if c in df.columns])
    return _to_text_frame(df), sorted(child_relationships)


def _source_salesforce(prefix: str, sf_conn) -> None:
    if sf_conn is None:
        st.warning("⚠️ Connect to the sidebar Salesforce org to query it.")
        return
    objects = get_salesforce_objects(sf_conn, filter_custom=False)
    if not objects:
        return
    col1, col2 = st.columns([2, 1])
    _restore(f"{prefix}_soql_object", [""] + objects)
    _restore(f"{prefix}_soql_mode")
    with col1:
        obj = st.selectbox("Object to query", [""] + objects, key=f"{prefix}_soql_object")
    with col2:
        mode = st.radio("Query", ["Pick fields", "Write SOQL"], key=f"{prefix}_soql_mode", horizontal=True)
    _remember(f"{prefix}_soql_object")
    _remember(f"{prefix}_soql_mode")
    if not obj:
        return

    if mode == "Pick fields":
        describe = get_object_description(sf_conn, obj) or {}
        fields = [f['name'] for f in describe.get('fields', []) if f.get('type') not in ('address', 'location')]
        defaults = [f for f in ('Id', 'Name') if f in fields]
        chosen = st.multiselect("Fields", fields, default=defaults, key=f"{prefix}_soql_fields_{obj}")
        c1, c2 = st.columns([3, 1])
        with c1:
            where = st.text_input("WHERE (optional)", key=f"{prefix}_soql_where",
                                  placeholder="e.g. CreatedDate = LAST_N_DAYS:30")
        with c2:
            limit = st.number_input("LIMIT (0 = all)", min_value=0, value=1000, step=500, key=f"{prefix}_soql_limit")
        soql = ""
        if chosen:
            soql = f"SELECT {', '.join(chosen)} FROM {obj}"
            if where.strip():
                soql += f" WHERE {where.strip()}"
            if limit:
                soql += f" LIMIT {int(limit)}"
            st.code(soql, language="sql")
    else:
        soql = st.text_area("SOQL", value=f"SELECT Id, Name FROM {obj} LIMIT 1000", height=110,
                            key=f"{prefix}_soql_text_{obj}")

    if st.button("🔍 Run query", key=f"{prefix}_soql_run", disabled=not soql.strip()):
        try:
            with st.spinner("Querying Salesforce..."):
                result = sf_conn.query_all(soql.strip())
            df, dropped = _flatten_records(result.get('records', []))
        except Exception as exc:
            st.error(f"❌ SOQL query failed: {exc}")
            return
        if df.empty:
            st.warning("⚠️ The query returned no records.")
            return
        if dropped:
            st.caption(f"ℹ️ Child-relationship subqueries are not loaded as columns: {', '.join(dropped)}")
        _stage(prefix, df, f"{obj} (Salesforce)", 'salesforce_soql',
               f"Salesforce org {st.session_state.get('current_org')}", {'soql': soql.strip(), 'object': obj},
               signature=('soql', soql.strip()), suggested_object=obj)


ALL_ROWS = "All rows"
FIRST_ROWS = "First rows only"

# Oracle-maintained schemas (used when the database is older than 12c and has no ORACLE_MAINTAINED flag).
_ORACLE_SYSTEM_SCHEMAS = (
    'SYS', 'SYSTEM', 'XDB', 'MDSYS', 'CTXSYS', 'ORDSYS', 'ORDDATA', 'ORDPLUGINS', 'OUTLN', 'DBSNMP', 'WMSYS',
    'OLAPSYS', 'EXFSYS', 'LBACSYS', 'DVSYS', 'DVF', 'GSMADMIN_INTERNAL', 'OJVMSYS', 'AUDSYS', 'APPQOSSYS',
    'DBSFWUSER', 'REMOTE_SCHEDULER_AGENT', 'GGSYS', 'ANONYMOUS', 'XS$NULL', 'SI_INFORMTN_SCHEMA', 'ORACLE_OCM',
    'DIP', 'MDDATA', 'SPATIAL_CSW_ADMIN_USR', 'SPATIAL_WFS_ADMIN_USR', 'SYSBACKUP', 'SYSDG', 'SYSKM', 'SYSRAC',
    'GSMCATUSER', 'GSMUSER', 'SYSMAN', 'MGMT_VIEW', 'FLOWS_FILES',
)


def _table_picker(prefix: str, kind: str, conn_name: str, tables, views, error: Optional[str],
                  hint: Callable[[str], str]) -> Optional[str]:
    """Table/view selectbox with a refresh button; the error (and a Retry button) when the list failed.

    Returns (chosen table 'schema.name' or None, whether the picker was shown). The
    button's value is read by the caller (st.session_state[f"{prefix}_{kind}_tables_refresh"]).
    """
    table_key = f"{prefix}_{kind}_table"
    col_pick, col_refresh = st.columns([5, 1], vertical_alignment="bottom")
    with col_refresh:
        st.button("🔄 Retry" if error else "🔄 Tables", key=f"{prefix}_{kind}_tables_refresh",
                  use_container_width=True,
                  help="Load the list of tables and views again (e.g. after connecting the VPN).")
    with col_pick:
        if error:
            st.warning(f"⚠️ Could not list the tables of **{conn_name}**: {hint(error)}")
            return None, False
        if not tables:
            st.caption("ℹ️ This login sees no tables or views — write the query below.")
            return None, False
        options = [NO_TABLE] + list(tables)
        _restore(table_key, options)
        table = st.selectbox(f"Table or view ({len(tables):,})", options, key=table_key,
                             format_func=lambda t: f"{t}   (view)" if t in views else t,
                             help="Type to search. Picking one builds the query below; you can still edit it.")
        _remember(table_key)
    return (None if table == NO_TABLE else table), True


def _rows_to_load(prefix: str, kind: str) -> Optional[int]:
    """None for 'All rows', else the number of first rows to load (the query is built from it)."""
    mode_key, top_key = f"{prefix}_{kind}_rows", f"{prefix}_{kind}_top"
    _restore(mode_key, [ALL_ROWS, FIRST_ROWS])
    _restore(top_key)
    col_mode, col_top = st.columns([3, 2], vertical_alignment="bottom")
    with col_mode:
        mode = st.radio("Rows to load", [ALL_ROWS, FIRST_ROWS], key=mode_key, horizontal=True,
                        help="A migration normally loads all rows; use the first rows to try the flow quickly.")
    top = None
    if mode == FIRST_ROWS:
        if top_key not in st.session_state:
            st.session_state[top_key] = 1000
        with col_top:
            top = int(st.number_input("Number of rows", min_value=1, max_value=10_000_000, step=1000,
                                      key=top_key))
    _remember(mode_key)
    _remember(top_key)
    return top


def _prefill_query(query_key: str, last_key: str, table: Optional[str], build, shown: bool = True) -> None:
    """Write the built query into the query box when the table or the row choice changes.

    Only while the picker is shown: when the list failed (or is empty) the user's own
    query stays, also after a Retry brings the list back.
    """
    if not shown:
        return
    choice = (table, build(table) if table else None)
    if table and st.session_state.get(last_key) != choice:
        st.session_state[query_key] = choice[1]
    st.session_state[last_key] = choice


def _source_sql(prefix: str) -> None:
    key, cfg = sql_connection_picker(f"{prefix}_sql")
    if not cfg:
        return
    from ui_components.data_operations import _get_sql_tables, sql_error_hint
    refresh = bool(st.session_state.get(f"{prefix}_sql_tables_refresh"))
    try:
        tables = _get_sql_tables(cfg, key, force_refresh=refresh, include_views=True)
    except Exception:
        tables = []
    table, shown = _table_picker(prefix, 'sql', display_name(key), tables,
                                 st.session_state.get(f"sql_views_{key}") or set(),
                                 st.session_state.get(f"sql_tables_error_{key}_with_views"), sql_error_hint)
    parts = st.session_state.get(f"sql_table_parts_{key}") or {}
    query_key = f"{prefix}_sql_query"
    _restore(query_key)
    _restore(f"{prefix}_sql_timeout")
    top = _rows_to_load(prefix, 'sql') if table else None
    _prefill_query(query_key, f"{prefix}_sql_table_last", table,
                   lambda t: f"SELECT {'TOP ' + str(top) + ' ' if top else ''}* FROM "
                             f"{_bracket_parts(parts.get(t) or t.split('.', 1))}", shown)
    if query_key not in st.session_state:
        st.session_state[query_key] = ""
    if f"{prefix}_sql_timeout" not in st.session_state:
        st.session_state[f"{prefix}_sql_timeout"] = 300
    query = st.text_area("SQL query", key=query_key, height=110,
                         placeholder="Pick a table above, or write a query: SELECT * FROM [dbo].[Customers]")
    timeout = st.number_input("Query timeout (seconds)", min_value=10, max_value=3600,
                              key=f"{prefix}_sql_timeout")
    _remember(query_key)
    _remember(f"{prefix}_sql_timeout")
    is_select = _is_select_query(query)
    if query.strip() and not is_select:
        st.error("❌ Only SELECT (or WITH ... SELECT) queries can be used to load data.")
    if st.button("🔍 Run query", key=f"{prefix}_sql_run", disabled=not (query.strip() and is_select)):
        try:
            with st.spinner(f"Running query on {display_name(key)}..."):
                df = run_sql_query(query.strip(), command_timeout=int(timeout))
        except Exception as exc:
            st.error(f"❌ SQL query failed: {sql_error_hint(str(exc))}")
            return
        if df.empty:
            st.warning("⚠️ The query returned no rows.")
            return
        _stage(prefix, _clean_frame(df.astype(object).where(pd.notnull(df), None)),
               f"{display_name(key)} query", 'sql_server', f"SQL Server {display_name(key)}",
               {'sql_connection': key, 'query': query.strip(), 'table': table},
               signature=('sql', key, query.strip()))


def _oracle_tables(cfg: Dict, key: str, force_refresh: bool = False):
    """(['OWNER.NAME', ...], {views}, error, {name: (owner, object)}) of the user schemas.

    Cached per connection and its settings (failures too, so an unreachable database does
    not stall every rerun). The pre-12c fallback query runs only when the first one failed
    because ORACLE_MAINTAINED does not exist (ORA-00904) - any other error (wrong password,
    no answer) stops at once, so an attempt never costs two logins.
    """
    settings = '|'.join(str(cfg.get(k, '')) for k in ('host', 'port', 'service_name', 'sid', 'username'))
    cache_key = f"oracle_tables_{key}_{settings}"
    if force_refresh:
        st.session_state.pop(cache_key, None)
    if cache_key in st.session_state:
        return st.session_state[cache_key]
    base = ("SELECT o.owner, o.object_name, o.object_type FROM all_objects o "
            "WHERE o.object_type IN ('TABLE', 'VIEW') AND o.object_name NOT LIKE 'BIN$%' ")
    system = ", ".join(f"'{name}'" for name in _ORACLE_SYSTEM_SCHEMAS)
    queries = [
        base + "AND o.owner IN (SELECT username FROM all_users WHERE oracle_maintained = 'N') "
               "ORDER BY o.owner, o.object_name",
        base + f"AND o.owner NOT IN ({system}) AND o.owner NOT LIKE 'APEX%' "
               "ORDER BY o.owner, o.object_name",
    ]
    result, error = None, None
    try:
        from ui_components.data_operations import _oracle_query_to_df
        for query in queries:
            try:
                df = _oracle_query_to_df(cfg, query)
            except ImportError:
                raise
            except Exception as exc:
                error = str(exc)[:500]
                if 'ORA-00904' in str(exc):   # ORACLE_MAINTAINED does not exist before 12c
                    continue
                break
            parts = [(str(o), str(n)) for o, n in zip(df.iloc[:, 0], df.iloc[:, 1])]
            names = [f"{o}.{n}" for o, n in parts]
            views = {name for name, kind in zip(names, df.iloc[:, 2]) if str(kind).upper() == 'VIEW'}
            result, error = (names, views, None, dict(zip(names, parts))), None
            break
    except ImportError:
        error = "The `oracledb` package is not installed in this Python environment."
    result = result or ([], set(), error, {})
    st.session_state[cache_key] = result
    return result


def _oracle_error_hint(message: str) -> str:
    text = str(message or '').strip().split('\n')[0][:220]
    lower = text.lower()
    if 'dpy-6005' in lower or 'timed out' in lower or 'ora-12170' in lower:
        return text + " — the database did not answer; check the VPN / network and the host and port."
    if 'ora-01017' in lower:
        return text + " — the user name or password was rejected."
    return text


def _quote_oracle(parts) -> str:
    """("HR", "Order Lines") -> "HR"."Order Lines" (exact case; embedded quotes doubled)."""
    return '.'.join('"' + str(part).replace('"', '""') + '"' for part in parts if part)


def _bracket_parts(parts) -> str:
    """("dbo", "a.b]c") -> [dbo].[a.b]]c] (exact names; ']' doubled)."""
    return '.'.join('[' + str(part).replace(']', ']]') + ']' for part in parts if part)


# Comments, semicolons and brackets a pasted query may start with (e.g. SSMS "Select Top 1000 Rows").
_LEADING_SQL_NOISE = re.compile(r'^(?:\s+|--[^\n]*(?:\n|$)|/\*.*?\*/|;|\()*', re.S)


def _is_select_query(query: str) -> bool:
    return _LEADING_SQL_NOISE.sub('', query or '', count=1).lower().startswith(('select', 'with'))


def _source_oracle(prefix: str) -> None:
    key, cfg = oracle_connection_picker(f"{prefix}_oracle")
    if not cfg:
        return
    refresh = bool(st.session_state.get(f"{prefix}_oracle_tables_refresh"))
    tables, views, error, parts = _oracle_tables(cfg, key, force_refresh=refresh)
    table, shown = _table_picker(prefix, 'oracle', display_name(key), tables, views, error, _oracle_error_hint)
    query_key = f"{prefix}_oracle_query"
    _restore(query_key)
    top = _rows_to_load(prefix, 'oracle') if table else None
    _prefill_query(query_key, f"{prefix}_oracle_table_last", table,
                   lambda t: f"SELECT * FROM {_quote_oracle(parts.get(t) or t.split('.', 1))}"
                             + (f" WHERE ROWNUM <= {top}" if top else ""), shown)
    query = st.text_area("Oracle SQL query", key=query_key, height=110,
                         placeholder='Pick a table above, or write a query: SELECT * FROM "HR"."EMPLOYEES"')
    _remember(query_key)
    is_select = _is_select_query(query)
    if query.strip() and not is_select:
        st.error("❌ Only SELECT (or WITH ... SELECT) queries can be used to load data.")
    if st.button("🔍 Run query", key=f"{prefix}_oracle_run", disabled=not (query.strip() and is_select)):
        try:
            with st.spinner(f"Running query on {display_name(key)}..."):
                df = run_oracle_query(query.strip().rstrip(';'))
        except ImportError:
            st.error("❌ The `oracledb` package is not installed in this Python environment.")
            return
        except Exception as exc:
            st.error(f"❌ Oracle query failed: {_oracle_error_hint(str(exc))}")
            return
        if df.empty:
            st.warning("⚠️ The query returned no rows.")
            return
        _stage(prefix, _clean_frame(df), f"{display_name(key)} query", 'oracle', f"Oracle {display_name(key)}",
               {'oracle_connection': key, 'query': query.strip(), 'table': table},
               signature=('oracle', key, query.strip()))


def _source_data_hub(prefix: str) -> None:
    hub = st.session_state.get('data_hub')
    datasets = hub.list_datasets() if hub else []
    if not datasets:
        st.info("💡 The Data Hub is empty. Load data with one of the other sources.")
        return
    labels = {f"{d['name']}  ({d['metadata']['row_count']:,} rows, {d['metadata']['column_count']} cols)"
              + ("  ★ active" if d['is_active'] else ""): d['id'] for d in datasets}
    label = st.selectbox("Dataset", list(labels), key=f"{prefix}_hub_pick")
    dataset_id = labels[label]
    staged = get_staged(prefix)
    if not staged or staged.get('signature') != ('hub', dataset_id):
        record = hub.get_dataset_with_metadata(dataset_id)
        details = record['metadata'].get('source_details') or {}
        _stage(prefix, record['df'], record['name'], record['metadata'].get('source_type', 'manual'),
               f"Data Hub dataset {record['name']}", details, signature=('hub', dataset_id),
               hub_dataset_id=dataset_id, suggested_object=details.get('target_object'))


def render_source_loader(prefix: str, sf_conn) -> Optional[Dict]:
    """Source picker + staging. Returns the staged dataset dict, or None."""
    _restore(f"{prefix}_source", SOURCES)
    source = st.radio("Data source", SOURCES, key=f"{prefix}_source", horizontal=True)
    _remember(f"{prefix}_source")
    with st.container(border=True):
        if source == SOURCES[0]:
            _source_upload(prefix)
        elif source == SOURCES[1]:
            _source_file_library(prefix)
        elif source == SOURCES[2]:
            _source_salesforce(prefix, sf_conn)
        elif source == SOURCES[3]:
            _source_sql(prefix)
        elif source == SOURCES[4]:
            _source_oracle(prefix)
        else:
            _source_data_hub(prefix)

    staged = get_staged(prefix)
    if staged is not None:
        df = staged['df']
        st.markdown(f"**Staged data:** {len(df):,} rows × {len(df.columns)} columns from {staged['source_label']}")
        with st.expander("👁️ Preview (first 20 rows)", expanded=False):
            st.dataframe(df.head(20), use_container_width=True)
    return staged


# ---------------------------------------------------------------------------
# Step 1 page
# ---------------------------------------------------------------------------

def _confirm_dataset(prefix: str) -> None:
    staged = get_staged(prefix)
    target = st.session_state.get(f"{prefix}_target_object")
    if not staged or not target:
        return
    name = (st.session_state.get(f"{prefix}_ds_name") or staged['name']).strip() or staged['name']
    dataset_id = step_flow.set_flow_dataset(
        staged['df'], name, target, staged['source_type'], staged['source_label'],
        details=staged['details'], dataset_id=staged.get('hub_dataset_id'),
    )
    # Confirming the same staged data again reuses this Data Hub entry, and the
    # staged record shares the Hub's DataFrame instead of keeping its own copy.
    staged['hub_dataset_id'] = dataset_id
    staged['df'] = st.session_state.data_hub.cached_datasets[dataset_id]['df']
    st.session_state[f"{prefix}_just_confirmed"] = True


def _object_for_table(table: Optional[str], objects) -> Optional[str]:
    """'dbo.Accounts' -> 'Account' when the org has such an object (case-insensitive, plural 's' ignored)."""
    if not table or table == NO_TABLE:
        return None
    name = str(table).split('.')[-1].strip('[]').lower()
    by_lower = {o.lower(): o for o in objects}
    for candidate in (name, name[:-1] if name.endswith('s') else None, name.replace('_', '')):
        if candidate and candidate in by_lower:
            return by_lower[candidate]
    return None


def _loadable_objects(sf_conn):
    """Objects that can be queried AND created (the list Step 2 validates against)."""
    try:
        from ui_components.validation_operations import get_salesforce_objects as validation_objects
        return validation_objects(sf_conn, filter_custom=False)
    except ImportError:
        return get_salesforce_objects(sf_conn, filter_custom=False)


def show_data_loading_step(credentials: Dict) -> None:
    prefix = "step1"
    step_flow.render_step_header(
        1, "Load your source data **once** here. Step 2 (Mapping & Validation), Step 3 (Data Operations) "
           "and Step 4 (Unit Testing) use this dataset automatically — no re-uploading. "
           "Progress is kept for this browser session; uploaded files also stay in 📁 File Library.")

    if not st.session_state.get('current_org'):
        st.warning("⚠️ Select a Salesforce org in the sidebar (🔌 Connection). "
                   "The target object and validation rules come from that org.")
        step_flow.render_step_footer(1)
        return

    sf_conn = get_sf_connection(credentials=credentials)

    dataset = step_flow.get_flow_dataset()
    if dataset:
        st.success(f"✅ **Dataset ready:** {dataset['name']} — {dataset['rows']:,} rows × {dataset['cols']} "
                   f"columns from {dataset['source_label']} → target object **{dataset['object']}**. "
                   "Load different data below to replace it.")
    if st.session_state.pop(f"{prefix}_just_confirmed", False):
        st.toast("Dataset confirmed for the guided flow", icon="✅")

    st.subheader("A · Source information")
    st.caption("Where the data comes from: a file, the File Library, Salesforce, SQL Server, Oracle or the Data Hub.")
    staged = render_source_loader(prefix, sf_conn)

    st.subheader("B · Target information")
    st.caption("The Salesforce object the rows will be validated against and loaded into.")
    objects = _loadable_objects(sf_conn) if sf_conn else []
    target_key = f"{prefix}_target_object"
    if staged and not staged.get('suggested_object'):
        staged['suggested_object'] = _object_for_table((staged.get('details') or {}).get('table'), objects)
    preferred = ((staged or {}).get('suggested_object') or step_flow.get_flow_object()
                 or st.session_state.get('current_object'))
    if st.session_state.get(target_key) not in objects:
        st.session_state[target_key] = preferred if preferred in objects else ""
    elif staged and staged.get('suggested_object') in objects and \
            st.session_state.get(f"{prefix}_suggested_applied") != staged.get('signature'):
        st.session_state[target_key] = staged['suggested_object']
    if staged:
        st.session_state[f"{prefix}_suggested_applied"] = staged.get('signature')
    col_target, col_refresh = st.columns([6, 1])
    with col_target:
        st.selectbox("Target object", [""] + objects, key=target_key,
                     help="The Salesforce object these rows will be validated against and loaded into "
                          "(objects you can query and create).",
                     disabled=not objects)
    with col_refresh:
        st.write("")
        if st.button("🔄", key=f"{prefix}_refresh_objects", help="Reload objects and fields from Salesforce",
                     use_container_width=True, disabled=sf_conn is None):
            clear_salesforce_metadata_cache()
            st.rerun()
    if not objects:
        st.caption("The object list appears once the sidebar org is connected.")

    st.subheader("C · Confirm")
    if staged:
        _ensure_name_default(prefix, staged)
        st.text_input("Dataset name", key=f"{prefix}_ds_name")
    ready = bool(staged is not None and len(staged['df']) > 0 and st.session_state.get(target_key))
    if ready and dataset and step_flow.get_flow_validation(any_source=True) and (
            staged.get('hub_dataset_id') != dataset['id'] or st.session_state.get(target_key) != dataset['object']):
        st.caption("⚠️ Using different data or a different target object resets Steps 2-4.")
    st.button("✅ Use this dataset", type="primary", disabled=not ready, key=f"{prefix}_confirm",
              on_click=_confirm_dataset, args=(prefix,), use_container_width=True)
    if not ready:
        missing = []
        if staged is None:
            missing.append("load data in section A")
        elif len(staged['df']) == 0:
            missing.append("the staged data has no rows")
        if not st.session_state.get(target_key):
            missing.append("choose the target object in section B")
        st.caption("To continue: " + "; ".join(missing) + ".")

    step_flow.render_step_footer(1)


def render_hub_loader(sf_conn) -> None:
    """Load Data tab of the Data Hub page: same sources, adds to the Hub without the flow."""
    prefix = "hub_loader"
    staged = render_source_loader(prefix, sf_conn)
    if staged is None:
        return
    if staged.get('hub_dataset_id'):
        st.caption("This dataset is already in the Data Hub.")
        return
    _ensure_name_default(prefix, staged)
    st.text_input("Dataset name", key=f"{prefix}_ds_name")
    if st.button("➕ Add to Data Hub", type="primary", key=f"{prefix}_add", use_container_width=True):
        from ui_components.data_hub import initialize_data_hub
        hub = initialize_data_hub()
        name = (st.session_state.get(f"{prefix}_ds_name") or staged['name']).strip() or staged['name']
        details = dict(staged['details'])
        details['org'] = st.session_state.get('current_org')
        dataset_id = hub.add_dataset(staged['df'], name, staged['source_type'], details, set_active=True)
        # Update the staged record in place (the name box is already drawn this run).
        staged.update({'name': name, 'details': details, 'signature': ('hub', dataset_id),
                       'hub_dataset_id': dataset_id})
        st.success(f"✅ Added **{name}** to the Data Hub. To use it in the guided flow, open "
                   "1️⃣ Source/Target Information and pick it under “📊 Data Hub dataset”.")
