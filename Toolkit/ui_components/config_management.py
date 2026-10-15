import streamlit as st
import json
import os
import pandas as pd
from typing import Dict
from .utils import establish_sf_connection, show_processing_status
from . import sql_connection

def show_configuration(credentials: Dict):
    """Display configuration management interface"""

    st.title("⚙️ Configuration Management")
    st.markdown("Manage your Salesforce organizations, database connections, and system settings")

    _render_undo_delete_banner()
    pending = st.session_state.get(PENDING_DELETE_KEY)
    if pending:
        _confirm_delete_dialog(pending)

    tab1, tab2, tab_projects, tab3, tab4 = st.tabs([
        "🏢 Organizations", 
        "🔌 Source Connections", 
        "📁 Projects",
        "📁 Directory Structure",
        "🔧 System Settings"
    ])
    
    with tab1:
        show_org_management(credentials)
    
    with tab2:
        show_source_connections(credentials)

    with tab_projects:
        show_projects(credentials)
    
    with tab3:
        show_directory_structure()
    
    with tab4:
        show_system_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Delete one saved connection: row button → confirmation dialog → undo banner
# ─────────────────────────────────────────────────────────────────────────────

PENDING_DELETE_KEY = '_pending_delete_connection'
UNDO_DELETE_KEY = '_undo_delete_connection'


def _request_delete(key: str) -> None:
    st.session_state[PENDING_DELETE_KEY] = key


def _clear_pending_delete() -> None:
    st.session_state.pop(PENDING_DELETE_KEY, None)


def _connection_label(key: str) -> str:
    from ui_components.connection_manager import display_name
    return key if not key.lower().startswith(('sql_', 'oracle_', 'snowflake_', 'pg_')) else display_name(key)


def _delete_button(key: str) -> None:
    st.button("🗑️ Delete", key=f"delete_conn_{key}", on_click=_request_delete, args=(key,),
              help=f"Delete the saved connection '{_connection_label(key)}'", use_container_width=True)


@st.dialog("Delete connection?", on_dismiss=_clear_pending_delete)
def _confirm_delete_dialog(key: str) -> None:
    from ui_components import connection_manager as cm
    entry = cm.get_credentials().get(key)
    kind = cm.connection_kind(key)
    if entry is None or kind is None:
        _clear_pending_delete()
        st.rerun()
    label = _connection_label(key)
    where = entry.get('username') or entry.get('server') or entry.get('host') or entry.get('account') or ''
    st.markdown(f"**{cm.CONNECTION_KINDS[kind]}:** {label}" + (f"  \n`{where}`" if where else ""))
    st.warning("This removes its saved username, password and token from Services/linkedservices.json. "
               "You can undo it until you close this browser tab.")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("🗑️ Delete", type="primary", key="confirm_delete_connection", use_container_width=True):
            deleted = cm.delete_connection(key)
            _clear_pending_delete()
            if deleted:
                st.session_state[UNDO_DELETE_KEY] = deleted
            st.rerun()
    with col_no:
        if st.button("Cancel", key="cancel_delete_connection", use_container_width=True):
            _clear_pending_delete()
            st.rerun()


def _render_undo_delete_banner() -> None:
    deleted = st.session_state.get(UNDO_DELETE_KEY)
    if not deleted:
        return
    from ui_components import connection_manager as cm
    label = _connection_label(deleted['key'])
    col_msg, col_undo, col_ok = st.columns([6, 1.3, 1])
    with col_msg:
        st.success(f"🗑️ Deleted {cm.CONNECTION_KINDS.get(deleted['kind'], 'connection')} **{label}**.")
    with col_undo:
        if st.button("↩️ Undo", key="undo_delete_connection", use_container_width=True):
            if cm.restore_connection(deleted):
                st.session_state.pop(UNDO_DELETE_KEY, None)
                st.rerun()
            st.session_state.pop(UNDO_DELETE_KEY, None)
            st.error(f"❌ Not restored: a connection named '{label}' was saved since. Nothing was overwritten.")
    with col_ok:
        if st.button("✖ Dismiss", key="dismiss_undo_delete", use_container_width=True):
            st.session_state.pop(UNDO_DELETE_KEY, None)
            st.rerun()


def _esc(value) -> str:
    """Show value literally: HTML-escaped, so a user name is neither markdown nor an auto-linked e-mail."""
    import html
    return html.escape(str(value if value not in (None, '') else '—'))


def _connection_rows(headers, rows, widths) -> None:
    """A table whose last column is each row's 🗑️ Delete button. rows: [(key, [cell, ...]), ...]."""
    head = st.columns(widths, vertical_alignment="center")
    for col, title in zip(head, headers + [""]):
        col.caption(f"**{title}**")
    for key, cells in rows:
        cols = st.columns(widths, vertical_alignment="center")
        for col, value in zip(cols, cells):
            # A <div> makes the cell an HTML block: markdown leaves its text alone (no mailto: links)
            col.markdown(f'<div class="dm-conn-cell">{value}</div>', unsafe_allow_html=True)
        with cols[-1]:
            _delete_button(key)


# ─────────────────────────────────────────────────────────────────────────────
# Projects: one customer's org connections grouped (File Library shows a project's files)
# ─────────────────────────────────────────────────────────────────────────────

def _add_project_from_form() -> None:
    from ui_components import projects
    name = (st.session_state.get('proj_new_name') or '').strip()
    orgs = list(st.session_state.get('proj_new_orgs') or [])
    aliases = list(st.session_state.get('proj_new_aliases') or [])
    items = projects.load_projects()
    if not name or not orgs:
        st.session_state['_proj_message'] = ('error', "Give the project a name and at least one org connection.")
        return
    if any(p['name'].lower() == name.lower() for p in items):
        st.session_state['_proj_message'] = ('error', f"A project named '{name}' already exists.")
        return
    projects.save_projects(items + [{'name': name, 'orgs': orgs, 'aliases': aliases}])
    for key in ('proj_new_name', 'proj_new_orgs', 'proj_new_aliases'):
        st.session_state.pop(key, None)
    st.session_state['_proj_message'] = ('success', f"Project '{name}' created.")


def _create_suggested_project(name: str, orgs) -> None:
    from ui_components import projects
    items = projects.load_projects()
    if not any(p['name'].lower() == name.lower() for p in items):
        projects.save_projects(items + [{'name': name, 'orgs': list(orgs), 'aliases': []}])
        st.session_state['_proj_message'] = ('success', f"Project '{name}' created.")


def _delete_project(name: str) -> None:
    from ui_components import projects
    projects.save_projects([p for p in projects.load_projects() if p['name'] != name])
    st.session_state['_proj_message'] = ('success', f"Project '{name}' deleted (its files and orgs are kept).")


def show_projects(credentials: Dict):
    """Group one customer's org connections into a project (e.g. Valmont = Dev + QA + UAT)."""
    from ui_components import projects
    from ui_components.connection_manager import classify_credentials
    st.subheader("📁 Projects")
    st.caption("A project groups one customer's org connections — e.g. Valmont = ValmontDev, ValmontQA, "
               "ValmontUAT. The sidebar org decides the project, and 📁 File Library shows that project's files.")
    message = st.session_state.pop('_proj_message', None)
    if message:
        (st.success if message[0] == 'success' else st.error)(message[1])

    items = projects.load_projects()
    sf_orgs = list(classify_credentials(credentials)['salesforce'])
    assigned = {o for p in items for o in projects.project_labels(p)}

    if items:
        _connection_rows_plain(["Project", "Org connections", "Also filed as"], [
            (p['name'], [f"<b>{_esc(p['name'])}</b>", _esc(', '.join(p['orgs'])), _esc(', '.join(p['aliases']) or '—')])
            for p in items], [1.6, 4, 2.4, 1.2])
    else:
        st.info("No projects yet. Create one from a suggestion below, or add your own.")

    suggestions = projects.suggest_projects(sf_orgs)
    if suggestions:
        st.markdown("#### 💡 Suggested from your org names")
        st.caption("Only a suggestion — nothing is grouped until you click Create.")
        for name, orgs in suggestions.items():
            col_text, col_btn = st.columns([5, 1.3], vertical_alignment="center")
            col_text.markdown(f'<div class="dm-conn-cell"><b>{_esc(name)}</b> — {_esc(", ".join(orgs))}</div>',
                              unsafe_allow_html=True)
            col_btn.button("➕ Create", key=f"proj_suggest_{name}", on_click=_create_suggested_project,
                           args=(name, orgs), use_container_width=True)

    st.markdown("#### ➕ Add a project")
    try:
        from ui_components.file_store_manager import list_output_files, list_source_files
        filed_as = {f['org_name'] for f in list_source_files(limit=100000) + list_output_files(limit=100000)}
    except Exception:
        filed_as = set()
    alias_options = sorted(o for o in filed_as
                           if o and o.lower() not in projects.UNASSIGNED and o not in sf_orgs and o not in assigned)
    st.text_input("Project name", key="proj_new_name", placeholder="e.g. Valmont")
    st.multiselect("Org connections", [o for o in sf_orgs if o not in assigned], key="proj_new_orgs",
                   help="Each org can be in one project only")
    st.multiselect("Also file under (folder names)", alias_options, key="proj_new_aliases",
                   help="Folder / org names files were saved under that belong to this project — e.g. "
                        "Valmont_Industries, the name Salesforce reports for the org")
    st.button("➕ Add project", key="proj_add", type="primary", on_click=_add_project_from_form)


def _connection_rows_plain(headers, rows, widths) -> None:
    """Like _connection_rows, but the last column deletes a PROJECT (not a connection)."""
    head = st.columns(widths, vertical_alignment="center")
    for col, title in zip(head, headers + [""]):
        col.caption(f"**{title}**")
    for name, cells in rows:
        cols = st.columns(widths, vertical_alignment="center")
        for col, value in zip(cols, cells):
            col.markdown(f'<div class="dm-conn-cell">{value}</div>', unsafe_allow_html=True)
        cols[-1].button("🗑️ Delete", key=f"proj_delete_{name}", on_click=_delete_project, args=(name,),
                        help=f"Delete the project '{name}' (its org connections and files are kept)",
                        use_container_width=True)


def show_org_management(credentials: Dict):
    """Manage Salesforce organizations"""
    st.subheader("🏢 Salesforce Organizations")
    
    if not credentials:
        st.warning("No credentials found. Please add organization credentials.")
        return
    
    # Display existing organizations
    st.write("### Configured Organizations")
    
    from ui_components.connection_manager import classify_credentials
    sf_org_creds = classify_credentials(credentials)['salesforce']
    org_rows = [
        (org_name, [f"<b>{_esc(org_name)}</b>", _esc(creds.get('username', 'N/A')),
                    _esc(creds.get('domain', 'login')), "✅ Yes" if creds.get('security_token') else "— No"])
        for org_name, creds in sf_org_creds.items() if 'username' in creds
    ]
    if org_rows:
        _connection_rows(["Organization", "Username", "Domain", "Security token"], org_rows, [2, 4, 1.2, 1.4, 1.3])
    else:
        st.info("No Salesforce organizations saved yet. Add one below.")

    st.divider()
    
    # Test connection section
    st.write("### Test Connections")
    
    col1, col2 = st.columns([3, 1])
    with col1:
        test_org = st.selectbox(
            "Select organization to test",
            options=[""] + list(sf_org_creds.keys()),
            key="test_org_selector"
        )
    
    with col2:
        test_button = st.button("🔍 Test Connection", disabled=not test_org)
    
    if test_button and test_org:
        with st.spinner(f"Testing connection to {test_org}..."):
            # Pooled per org: testing another org never replaces the sidebar
            # connection. An explicit test retries a previously failed login.
            from ui_components.connection_manager import get_sf_connection_error, retry_sf_connection
            if get_sf_connection_error(test_org):
                retry_sf_connection(test_org)
            sf_conn = establish_sf_connection(credentials, test_org)
            
            if sf_conn:
                try:
                    # Get basic org info
                    org_info = sf_conn.query("SELECT Id, Name FROM Organization LIMIT 1")
                    if org_info['records']:
                        org_record = org_info['records'][0]
                        st.success(f"✅ Connection successful!")
                        st.info(f"**Organization ID:** {org_record['Id']}")
                        st.info(f"**Organization Name:** {org_record['Name']}")
                        show_processing_status("connection_test", f"Successfully connected to {test_org}", "success")
                    else:
                        st.warning("Connected but unable to retrieve organization details")
                except Exception as e:
                    st.error(f"Connected but error retrieving org details: {str(e)}")
    
    st.divider()
    
    # Add new organization
    st.write("### Add New Organization")
    
    with st.expander("➕ Add New Salesforce Organization", expanded=False):
        with st.form("add_org_form"):
            new_org_name = st.text_input("Organization Name", help="Unique identifier for this org")
            new_username = st.text_input("Username", help="Salesforce username")
            new_password = st.text_input("Password", type="password", help="Salesforce password")
            new_security_token = st.text_input("Security Token", help="Optional security token")
            new_domain = st.selectbox("Domain", ["login", "test"], help="login for production, test for sandbox")
            
            submit_button = st.form_submit_button("Add Organization")
            
            if submit_button:
                if new_org_name and new_username and new_password:
                    # Add to credentials
                    new_creds = {
                        "username": new_username,
                        "password": new_password,
                        "security_token": new_security_token,
                        "domain": new_domain
                    }
                    
                    # Check if org name already exists
                    if new_org_name in credentials:
                        st.error(f"❌ Organization '{new_org_name}' already exists! Please choose a different name.")
                    else:
                        # Save to file and update session state
                        if save_credentials(credentials, new_org_name, new_creds):
                            # Show prominent success message with balloons effect
                            st.balloons()
                            st.success(f"🎉 **Organization '{new_org_name}' created successfully!**")
                            
                            # Show detailed success information
                            st.markdown("""
                            **✅ What happened:**
                            - New organization credentials saved securely
                            - Organization added to your available orgs list
                            - You can now select it from the sidebar dropdown
                            
                            **🚀 Next steps:**
                            1. Select the new organization from the sidebar dropdown
                            2. Go to any module (Data Operations, Validation, etc.)
                            3. Test the connection to ensure everything works
                            """)
                            
                            # Auto-refresh after showing success
                            import time
                            time.sleep(2)  # Give user time to read the success message
                            st.rerun()
                        else:
                            st.error("❌ Failed to save organization credentials")
                else:
                    st.error("Please fill in all required fields (Name, Username, Password)")

def show_source_connections(credentials: Dict):
    """Manage all source database connections: SQL Server, Oracle, Snowflake, PostgreSQL"""
    st.subheader("🔌 Source Connections")
    st.markdown("Configure source database connections. Salesforce target orgs are managed in the **Organizations** tab.")

    # ── Source type labels and key prefixes ──────────────────────────────────
    SOURCE_TYPES = {
        "SQL Server":   {"prefix": "sql_",        "icon": "🗄️",  "pkg": "pyodbc"},
        "Oracle":       {"prefix": "oracle_",     "icon": "🔶",  "pkg": "oracledb"},
        "Snowflake":    {"prefix": "snowflake_",  "icon": "❄️",  "pkg": "snowflake-connector-python"},
        "PostgreSQL":   {"prefix": "pg_",         "icon": "🐘",  "pkg": "psycopg2"},
    }

    # ── Collect all existing source connections ───────────────────────────────
    all_source_conns = {}
    for k, v in credentials.items():
        for stype, meta in SOURCE_TYPES.items():
            if k.lower().startswith(meta["prefix"]):
                all_source_conns[k] = {**v, "_source_type": stype, "_display_name": k[len(meta["prefix"]):].upper()}

    # ── Overview table ────────────────────────────────────────────────────────
    if all_source_conns:
        st.write("### Configured Source Connections")
        rows = []
        for k, v in all_source_conns.items():
            stype = v["_source_type"]
            host = (v.get("server") or v.get("host") or v.get("account") or "N/A")
            db   = (v.get("database") or v.get("service_name") or v.get("sid") or "N/A")
            rows.append((k, [f"<b>{_esc(v['_display_name'])}</b>", f"{SOURCE_TYPES[stype]['icon']} {stype}",
                             _esc(host), _esc(db), _esc(v.get("username", "Windows Auth"))]))
        _connection_rows(["Name", "Type", "Host/Account", "Database", "Username"], rows, [2, 1.6, 3.2, 2, 1.6, 1.3])

        st.write("### Connection Details & Testing")
        for conn_key, conn_val in all_source_conns.items():
            stype = conn_val["_source_type"]
            display = conn_val["_display_name"]
            with st.expander(f"{SOURCE_TYPES[stype]['icon']} {display} ({stype})", expanded=False):
                _show_connection_detail(conn_key, conn_val, stype, credentials)
    else:
        st.info("No source connections configured yet. Add one below.")

    st.divider()

    # ── Add new connection ────────────────────────────────────────────────────
    st.write("### Add New Source Connection")

    source_type = st.selectbox(
        "Select Source Type",
        list(SOURCE_TYPES.keys()),
        key="new_source_type_selector",
        help="Choose the database technology you want to connect to"
    )

    # Check package availability and warn immediately
    pkg = SOURCE_TYPES[source_type]["pkg"]
    pkg_available = _check_package(pkg)
    if not pkg_available:
        install_cmd = f"pip install {pkg}"
        st.warning(f"⚠️ **Required package `{pkg}` is not installed.**  \nRun in your terminal:  \n```\n{install_cmd}\n```\nYou can still configure the connection now and test it after installing the package.")

    with st.expander(f"➕ Add New {source_type} Connection", expanded=True):
        if source_type == "SQL Server":
            _form_sqlserver(credentials)
        elif source_type == "Oracle":
            _form_oracle(credentials)
        elif source_type == "Snowflake":
            _form_snowflake(credentials)
        elif source_type == "PostgreSQL":
            _form_postgresql(credentials)


# ─────────────────────────────────────────────────────────────────────────────
# Package availability check
# ─────────────────────────────────────────────────────────────────────────────

def _check_package(pkg_name: str) -> bool:
    """Return True if the package is importable."""
    import importlib
    import_name = {
        "pyodbc": "pyodbc",
        "oracledb": "oracledb",
        "snowflake-connector-python": "snowflake.connector",
        "psycopg2": "psycopg2",
    }.get(pkg_name, pkg_name)
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Connection detail panel (test + remove)
# ─────────────────────────────────────────────────────────────────────────────

def _show_connection_detail(conn_key: str, conn_val: dict, stype: str, credentials: Dict):
    col1, col2 = st.columns(2)
    with col1:
        if stype == "SQL Server":
            st.write("**Server:**",   conn_val.get("server",   "N/A"))
            st.write("**Database:**", conn_val.get("database", "N/A"))
            st.write("**Port:**",     conn_val.get("port",     "1433"))
        elif stype == "Oracle":
            st.write("**Host:**",         conn_val.get("host",         "N/A"))
            st.write("**Port:**",         conn_val.get("port",         "1521"))
            st.write("**Service/SID:**",  conn_val.get("service_name") or conn_val.get("sid", "N/A"))
        elif stype == "Snowflake":
            st.write("**Account:**",   conn_val.get("account",   "N/A"))
            st.write("**Warehouse:**", conn_val.get("warehouse", "N/A"))
            st.write("**Database:**",  conn_val.get("database",  "N/A"))
            st.write("**Schema:**",    conn_val.get("schema",    "N/A"))
        elif stype == "PostgreSQL":
            st.write("**Host:**",     conn_val.get("host",     "N/A"))
            st.write("**Port:**",     conn_val.get("port",     "5432"))
            st.write("**Database:**", conn_val.get("database", "N/A"))
    with col2:
        st.write("**Username:**", conn_val.get("username", "Windows Auth"))
        st.write("**Password:**", "***" if conn_val.get("password") else "Not set")
        if stype == "Snowflake":
            st.write("**Role:**", conn_val.get("role", "default"))
        if stype == "SQL Server":
            st.write("**Auth:**", "Windows" if conn_val.get("Trusted_Connection") == "yes" else "SQL")

    # Deleting is the 🗑️ Delete button on this connection's row in the table above.
    if st.button(f"🔍 Test Connection", key=f"test_{conn_key}"):
        _dispatch_test(conn_val, stype, conn_key)


# ─────────────────────────────────────────────────────────────────────────────
# Test dispatcher
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch_test(config: dict, stype: str, display_name: str = ""):
    if stype == "SQL Server":
        test_database_connection(config, display_name)
    elif stype == "Oracle":
        _test_oracle_connection(config)
    elif stype == "Snowflake":
        _test_snowflake_connection(config)
    elif stype == "PostgreSQL":
        _test_postgresql_connection(config)


# ─────────────────────────────────────────────────────────────────────────────
# Oracle
# ─────────────────────────────────────────────────────────────────────────────

def _form_oracle(credentials: Dict):
    st.markdown("**Configure Oracle Database connection**")
    with st.form("add_oracle_form"):
        st.markdown("#### 🔧 Connection Details")
        col1, col2 = st.columns(2)
        with col1:
            conn_name  = st.text_input("Connection Name*", help="Unique name e.g. 'OracleProd'")
            host       = st.text_input("Host*", help="Oracle server hostname or IP")
            port       = st.text_input("Port", value="1521", help="Default: 1521")
        with col2:
            connect_by = st.radio("Connect by", ["Service Name", "SID"], horizontal=True)
            service_or_sid = st.text_input(
                "Service Name*" if connect_by == "Service Name" else "SID*",
                help="Oracle service name (preferred) or SID"
            )
            encoding   = st.selectbox("Encoding", ["UTF-8", "AL32UTF8", "US7ASCII"], index=0)

        st.markdown("#### 🔐 Authentication")
        col3, col4 = st.columns(2)
        with col3:
            ora_user = st.text_input("Username*")
        with col4:
            ora_pass = st.text_input("Password*", type="password")
        connect_mode = st.selectbox("Connection Mode", ["Default", "SYSDBA", "SYSOPER"], index=0)

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            test_btn = st.form_submit_button("🔍 Test Connection")
        with col_s2:
            save_btn = st.form_submit_button("✅ Save Connection", type="primary")

        if test_btn or save_btn:
            if not (conn_name and host and service_or_sid and ora_user and ora_pass):
                st.error("❌ Please fill in all required fields")
            else:
                cfg = {
                    "db_type": "oracle",
                    "host": host,
                    "port": port or "1521",
                    "service_name": service_or_sid if connect_by == "Service Name" else "",
                    "sid": service_or_sid if connect_by == "SID" else "",
                    "username": ora_user,
                    "password": ora_pass,
                    "encoding": encoding,
                    "connect_mode": connect_mode,
                }
                if test_btn:
                    _test_oracle_connection(cfg)
                if save_btn:
                    key = f"oracle_{conn_name}"
                    if key in credentials:
                        st.error(f"❌ Connection '{conn_name}' already exists")
                    elif save_credentials(credentials, key, cfg):
                        st.balloons()
                        st.success(f"🎉 Oracle connection '{conn_name}' saved!")
                        import time; time.sleep(1); st.rerun()
                    else:
                        st.error("❌ Failed to save connection")


def _test_oracle_connection(cfg: dict):
    with st.spinner("Testing Oracle connection..."):
        try:
            import oracledb
            dsn = cfg.get("service_name") or cfg.get("sid", "")
            host = cfg.get("host", "")
            port = int(cfg.get("port", 1521))
            if cfg.get("service_name"):
                dsn_str = oracledb.makedsn(host, port, service_name=cfg["service_name"])
            else:
                dsn_str = oracledb.makedsn(host, port, sid=cfg.get("sid", ""))
            mode = 0
            if cfg.get("connect_mode") == "SYSDBA":
                mode = oracledb.AUTH_MODE_SYSDBA
            elif cfg.get("connect_mode") == "SYSOPER":
                mode = oracledb.AUTH_MODE_SYSOPER
            conn = oracledb.connect(user=cfg["username"], password=cfg["password"], dsn=dsn_str, mode=mode)
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM DUAL")
            cursor.execute("SELECT SYS_CONTEXT('USERENV','DB_NAME') FROM DUAL")
            db_name = cursor.fetchone()[0]
            cursor.execute("SELECT USER FROM DUAL")
            db_user = cursor.fetchone()[0]
            conn.close()
            st.success("✅ **Oracle connection successful!**")
            st.info(f"**Database:** {db_name}")
            st.info(f"**Connected as:** {db_user}")
        except ImportError:
            st.error("❌ `oracledb` package not installed. Run: `pip install oracledb`")
        except Exception as e:
            err = str(e)
            st.error("❌ **Oracle connection failed**")
            st.code(err, language="text")
            if "ORA-01017" in err:
                st.warning("🔐 Invalid username or password")
            elif "ORA-12541" in err or "TNS:no listener" in err:
                st.warning("🌐 Cannot reach Oracle listener — check host, port, and firewall")
            elif "ORA-12154" in err:
                st.warning("🔧 TNS could not resolve service name / SID")
            elif "DPY-6000" in err or "DPY-4011" in err:
                st.warning("📦 Oracle Client libraries may be required for thick mode — try thin mode (default with oracledb)")


# ─────────────────────────────────────────────────────────────────────────────
# Snowflake
# ─────────────────────────────────────────────────────────────────────────────

def _form_snowflake(credentials: Dict):
    st.markdown("**Configure Snowflake connection**")
    with st.form("add_snowflake_form"):
        st.markdown("#### 🔧 Connection Details")
        col1, col2 = st.columns(2)
        with col1:
            conn_name  = st.text_input("Connection Name*", help="Unique name e.g. 'SnowflakeDW'")
            account    = st.text_input("Account Identifier*", help="e.g. xyz12345.us-east-1  (from your Snowflake URL)")
            warehouse  = st.text_input("Warehouse*", help="Compute warehouse name e.g. COMPUTE_WH")
        with col2:
            sf_database = st.text_input("Database*",  help="Snowflake database name")
            sf_schema   = st.text_input("Schema",     value="PUBLIC", help="Schema name (default: PUBLIC)")
            sf_role     = st.text_input("Role",       help="Optional: Snowflake role e.g. SYSADMIN")

        st.markdown("#### 🔐 Authentication")
        col3, col4 = st.columns(2)
        with col3:
            sf_user = st.text_input("Username*")
        with col4:
            sf_pass = st.text_input("Password*", type="password")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            test_btn = st.form_submit_button("🔍 Test Connection")
        with col_s2:
            save_btn = st.form_submit_button("✅ Save Connection", type="primary")

        if test_btn or save_btn:
            if not (conn_name and account and warehouse and sf_database and sf_user and sf_pass):
                st.error("❌ Please fill in all required fields")
            else:
                cfg = {
                    "db_type": "snowflake",
                    "account": account,
                    "warehouse": warehouse,
                    "database": sf_database,
                    "schema": sf_schema or "PUBLIC",
                    "role": sf_role or "",
                    "username": sf_user,
                    "password": sf_pass,
                }
                if test_btn:
                    _test_snowflake_connection(cfg)
                if save_btn:
                    key = f"snowflake_{conn_name}"
                    if key in credentials:
                        st.error(f"❌ Connection '{conn_name}' already exists")
                    elif save_credentials(credentials, key, cfg):
                        st.balloons()
                        st.success(f"🎉 Snowflake connection '{conn_name}' saved!")
                        import time; time.sleep(1); st.rerun()
                    else:
                        st.error("❌ Failed to save connection")


def _test_snowflake_connection(cfg: dict):
    with st.spinner("Testing Snowflake connection..."):
        try:
            import snowflake.connector
            kwargs = {
                "user":      cfg["username"],
                "password":  cfg["password"],
                "account":   cfg["account"],
                "warehouse": cfg["warehouse"],
                "database":  cfg["database"],
                "schema":    cfg.get("schema", "PUBLIC"),
            }
            if cfg.get("role"):
                kwargs["role"] = cfg["role"]
            conn = snowflake.connector.connect(**kwargs)
            cur = conn.cursor()
            cur.execute("SELECT CURRENT_VERSION(), CURRENT_DATABASE(), CURRENT_USER(), CURRENT_WAREHOUSE()")
            row = cur.fetchone()
            conn.close()
            st.success("✅ **Snowflake connection successful!**")
            st.info(f"**Snowflake Version:** {row[0]}")
            st.info(f"**Database:** {row[1]}")
            st.info(f"**User:** {row[2]}")
            st.info(f"**Warehouse:** {row[3]}")
        except ImportError:
            st.error("❌ `snowflake-connector-python` not installed. Run: `pip install snowflake-connector-python`")
        except Exception as e:
            err = str(e)
            st.error("❌ **Snowflake connection failed**")
            st.code(err, language="text")
            if "250001" in err or "Incorrect username or password" in err:
                st.warning("🔐 Incorrect username or password")
            elif "404" in err or "account" in err.lower():
                st.warning("🌐 Account identifier not found — check your Snowflake account URL format")
            elif "250006" in err:
                st.warning("🏭 Warehouse not found or suspended — check warehouse name")


# ─────────────────────────────────────────────────────────────────────────────
# PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────

def _form_postgresql(credentials: Dict):
    st.markdown("**Configure PostgreSQL connection**")
    with st.form("add_pg_form"):
        st.markdown("#### 🔧 Connection Details")
        col1, col2 = st.columns(2)
        with col1:
            conn_name = st.text_input("Connection Name*", help="Unique name e.g. 'PostgresProd'")
            host      = st.text_input("Host*", help="PostgreSQL server hostname or IP")
            port      = st.text_input("Port", value="5432", help="Default: 5432")
        with col2:
            pg_db     = st.text_input("Database*", help="Database name")
            ssl_mode  = st.selectbox("SSL Mode", ["prefer", "require", "disable", "verify-full"], index=0,
                                     help="SSL/TLS mode for the connection")

        st.markdown("#### 🔐 Authentication")
        col3, col4 = st.columns(2)
        with col3:
            pg_user = st.text_input("Username*")
        with col4:
            pg_pass = st.text_input("Password*", type="password")

        col_s1, col_s2 = st.columns(2)
        with col_s1:
            test_btn = st.form_submit_button("🔍 Test Connection")
        with col_s2:
            save_btn = st.form_submit_button("✅ Save Connection", type="primary")

        if test_btn or save_btn:
            if not (conn_name and host and pg_db and pg_user and pg_pass):
                st.error("❌ Please fill in all required fields")
            else:
                cfg = {
                    "db_type": "postgresql",
                    "host":     host,
                    "port":     port or "5432",
                    "database": pg_db,
                    "username": pg_user,
                    "password": pg_pass,
                    "ssl_mode": ssl_mode,
                }
                if test_btn:
                    _test_postgresql_connection(cfg)
                if save_btn:
                    key = f"pg_{conn_name}"
                    if key in credentials:
                        st.error(f"❌ Connection '{conn_name}' already exists")
                    elif save_credentials(credentials, key, cfg):
                        st.balloons()
                        st.success(f"🎉 PostgreSQL connection '{conn_name}' saved!")
                        import time; time.sleep(1); st.rerun()
                    else:
                        st.error("❌ Failed to save connection")


def _test_postgresql_connection(cfg: dict):
    with st.spinner("Testing PostgreSQL connection..."):
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=cfg["host"],
                port=int(cfg.get("port", 5432)),
                dbname=cfg["database"],
                user=cfg["username"],
                password=cfg["password"],
                sslmode=cfg.get("ssl_mode", "prefer"),
                connect_timeout=15,
            )
            cur = conn.cursor()
            cur.execute("SELECT version(), current_database(), current_user")
            row = cur.fetchone()
            conn.close()
            st.success("✅ **PostgreSQL connection successful!**")
            st.info(f"**Database:** {row[1]}")
            st.info(f"**User:** {row[2]}")
            with st.expander("📊 Server Details"):
                st.text(row[0])
        except ImportError:
            st.error("❌ `psycopg2` not installed. Run: `pip install psycopg2-binary`")
        except Exception as e:
            err = str(e)
            st.error("❌ **PostgreSQL connection failed**")
            st.code(err, language="text")
            if "password authentication failed" in err:
                st.warning("🔐 Incorrect username or password")
            elif "could not connect to server" in err or "Connection refused" in err:
                st.warning("🌐 Cannot reach PostgreSQL server — check host, port, and firewall")
            elif "database" in err and "does not exist" in err:
                st.warning("🗄️ Database not found — check database name")


# ─────────────────────────────────────────────────────────────────────────────
# SQL Server form (kept from original show_database_settings)
# ─────────────────────────────────────────────────────────────────────────────

def _form_sqlserver(credentials: Dict):
    """SQL Server add-connection form — original logic, now called from show_source_connections"""
    # Display existing SQL connections (kept inside for consistency)
    sql_connections = {k: v for k, v in credentials.items() if k.lower().startswith("sql_")}
    if not sql_connections:
        st.info("No SQL Server connections configured yet.")

    st.markdown("**Configure a new SQL Server database connection**")

    with st.form("add_db_form"):
        st.markdown("#### 🔧 **Connection Details**")
        col1, col2 = st.columns(2)
        with col1:
            db_name = st.text_input("Connection Name*", help="e.g. 'Production', 'Staging'")
            server  = st.text_input("Server Address*", help="e.g. 'localhost' or '192.168.1.100\\SQLEXPRESS'")
            database = st.text_input("Database Name*")
            port    = st.text_input("Port", value="1433")
        with col2:
            try:
                import pyodbc as _pyodbc
                installed_sql_drivers = [d for d in _pyodbc.drivers()
                                         if 'sql server' in d.lower() or 'sql native' in d.lower()]
            except Exception:
                installed_sql_drivers = []
            driver_options = ["Auto-detect (recommended)"] + installed_sql_drivers + [
                "{ODBC Driver 18 for SQL Server}", "{ODBC Driver 17 for SQL Server}",
                "{ODBC Driver 13 for SQL Server}", "{SQL Server}", "{SQL Server Native Client 11.0}"]
            seen = set()
            driver_options = [x for x in driver_options if not (x in seen or seen.add(x))]
            driver = st.selectbox("ODBC Driver (optional)", driver_options, index=0)
            encrypt = st.selectbox("Encryption", ["no", "yes", "strict"], index=0)
            trust_server_cert = st.checkbox("Trust Server Certificate", value=False)
            connection_timeout = st.number_input("Connection Timeout (s)", min_value=5, max_value=300, value=30)

        st.divider()
        st.markdown("#### 🔐 **Authentication**")
        auth_type = st.radio("Authentication Type", ["Windows Authentication", "SQL Server Authentication"])
        if auth_type == "SQL Server Authentication":
            col_a1, col_a2 = st.columns(2)
            with col_a1:
                username = st.text_input("Username*")
            with col_a2:
                password = st.text_input("Password*", type="password")
        else:
            username = password = ""
            st.info("ℹ️ Windows Authentication will use your current Windows credentials")

        with st.expander("⚙️ Advanced Settings", expanded=False):
            col_adv1, col_adv2 = st.columns(2)
            with col_adv1:
                application_name = st.text_input("Application Name", value="DM_Toolkit")
                mars_connection  = st.checkbox("Enable MARS", value=False)
            with col_adv2:
                command_timeout = st.number_input("Command Timeout (s)", min_value=30, max_value=3600, value=300)
                auto_commit     = st.checkbox("Auto Commit", value=True)

        col_s1, col_s2 = st.columns([1, 2])
        with col_s1:
            test_before_save = st.form_submit_button("🔍 Test Connection")
        with col_s2:
            submit_db = st.form_submit_button("✅ Save Database Connection", type="primary")

        if test_before_save or submit_db:
            if not (db_name and server and database):
                st.error("❌ Please fill in required fields (Connection Name, Server, Database)")
            else:
                if auth_type == "SQL Server Authentication" and (not username or not password):
                    st.error("❌ Username and password required for SQL Server Authentication")
                else:
                    cfg = create_db_config(server, database, username, password, driver, port,
                                           auth_type == "Windows Authentication", encrypt,
                                           trust_server_cert, connection_timeout,
                                           application_name, mars_connection, command_timeout, auto_commit)
                    if test_before_save:
                        test_database_connection(cfg, f"Test_{db_name}")
                    if submit_db:
                        key = f"sql_{db_name}"
                        if key in credentials:
                            st.error(f"❌ Connection '{db_name}' already exists")
                        elif save_credentials(credentials, key, cfg):
                            st.balloons()
                            st.success(f"🎉 SQL Server connection '{db_name}' saved!")
                            import time; time.sleep(2); st.rerun()
                        else:
                            st.error("❌ Failed to save connection")


def show_database_settings(credentials: Dict):
    """Kept for backward compatibility — delegates to show_source_connections"""
    show_source_connections(credentials)


def show_directory_structure():
    """Show and manage directory structure"""
    st.subheader("📁 Directory Structure")
    
    project_root = os.path.dirname(os.path.dirname(__file__))
    
    # Display current directory structure
    st.write("### Current Project Structure")
    
    required_directories = [
        "DataFiles",
        "DataLoader_Logs", 
        "mapping_logs",
        "Validation",
        "Unit Testing Generates",
        "Services"
    ]
    
    dir_status = []
    for dir_name in required_directories:
        dir_path = os.path.join(project_root, dir_name)
        if os.path.exists(dir_path):
            # Count files in directory
            file_count = _count_files(dir_path)
            dir_status.append({
                "Directory": dir_name,
                "Status": "✅ Exists",
                "Files": file_count,
                "Path": dir_path
            })
        else:
            dir_status.append({
                "Directory": dir_name,
                "Status": "❌ Missing",
                "Files": 0,
                "Path": dir_path
            })
    
    df_dirs = pd.DataFrame(dir_status)
    st.dataframe(df_dirs, use_container_width=True)
    
    st.divider()
    
    # Create missing directories
    st.write("### Directory Management")
    
    missing_dirs = [d for d in dir_status if "Missing" in d["Status"]]
    
    if missing_dirs:
        st.warning(f"Found {len(missing_dirs)} missing directories")
        
        if st.button("🔨 Create Missing Directories"):
            created_count = 0
            for dir_info in missing_dirs:
                try:
                    os.makedirs(dir_info["Path"], exist_ok=True)
                    created_count += 1
                    st.success(f"✅ Created: {dir_info['Directory']}")
                except Exception as e:
                    st.error(f"❌ Failed to create {dir_info['Directory']}: {str(e)}")
            
            if created_count > 0:
                st.success(f"Successfully created {created_count} directories!")
                st.rerun()
    else:
        st.success("✅ All required directories exist")
    
    # Cleanup options
    st.write("### Cleanup Options")
    
    with st.expander("🧹 Cleanup Tools", expanded=False):
        st.warning("⚠️ These operations will permanently delete files. Use with caution!")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🗑️ Clear Log Files", key="clear_logs"):
                if clear_log_files():
                    st.success("Log files cleared successfully")
                else:
                    st.error("Error clearing log files")
        
        with col2:
            if st.button("🗑️ Clear Temp Files", key="clear_temp"):
                if clear_temp_files():
                    st.success("Temporary files cleared successfully")
                else:
                    st.error("Error clearing temporary files")

def show_system_settings():
    """Show system-wide settings"""
    st.subheader("🔧 System Settings")
    
    # Batch processing settings
    st.write("### Default Batch Processing Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        default_batch_size = st.number_input(
            "Default Batch Size",
            min_value=1,
            max_value=10000,
            value=2000,
            help="Default number of records per batch"
        )
        
        max_parallel_batches = st.number_input(
            "Max Parallel Batches",
            min_value=1,
            max_value=10,
            value=3,
            help="Maximum number of batches to process in parallel"
        )
    
    with col2:
        log_level = st.selectbox(
            "Log Level",
            ["DEBUG", "INFO", "WARNING", "ERROR"],
            index=1,
            help="Minimum log level to record"
        )
        
        auto_cleanup = st.checkbox(
            "Auto Cleanup",
            value=False,
            help="Automatically clean up old log files"
        )
    
    # File handling settings
    st.write("### File Handling Settings")
    
    col3, col4 = st.columns(2)
    
    with col3:
        max_file_size_mb = st.number_input(
            "Max File Size (MB)",
            min_value=1,
            max_value=1000,
            value=100,
            help="Maximum file size for uploads"
        )
    
    with col4:
        backup_enabled = st.checkbox(
            "Enable Backups",
            value=True,
            help="Create backups before processing"
        )
    
    # Save settings
    if st.button("💾 Save Settings", use_container_width=True):
        settings = {
            "batch_size": default_batch_size,
            "max_parallel_batches": max_parallel_batches,
            "log_level": log_level,
            "auto_cleanup": auto_cleanup,
            "max_file_size_mb": max_file_size_mb,
            "backup_enabled": backup_enabled
        }
        
        if save_system_settings(settings):
            st.success("✅ Settings saved successfully!")
            show_processing_status("settings_save", "System settings updated", "success")
        else:
            st.error("❌ Failed to save settings")

_resolve_driver = sql_connection.resolve_driver  # older callers import it from here


@st.cache_data(ttl=60, show_spinner=False)  # folder scan: at most once a minute
def _count_files(dir_path: str) -> int:
    return sum(len(files) for _, _, files in os.walk(dir_path))


def test_database_connection(db_config: Dict, db_name: str):
    """Test database connection with enhanced feedback"""
    try:
        import pyodbc
        
        with st.spinner(f"Testing connection to {db_name.replace('sql_', '')}..."):
            connection_string = sql_connection.build_connection_string(db_config)

            # Test connection
            with pyodbc.connect(connection_string, timeout=sql_connection.login_timeout(db_config)) as conn:
                cursor = conn.cursor()
                
                # Test basic query
                cursor.execute("SELECT @@VERSION as sql_version, DB_NAME() as current_db, SYSTEM_USER as connected_user")
                result = cursor.fetchone()
                
                if result:
                    st.success("✅ **Database connection successful!**")
                    
                    # Show detailed connection info
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.info(f"**Database:** {result.current_db}")
                        st.info(f"**Connected User:** {result.connected_user}")
                    
                    with col2:
                        # Get table count
                        cursor.execute("SELECT COUNT(*) as table_count FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                        table_result = cursor.fetchone()
                        st.info(f"**Tables Available:** {table_result.table_count}")
                        
                        # Test permissions
                        try:
                            cursor.execute("SELECT 1")
                            st.info("**Permissions:** ✅ Read Access")
                        except:
                            st.warning("**Permissions:** ⚠️ Limited Access")
                    
                    # Show SQL Server version info
                    with st.expander("📊 SQL Server Details", expanded=False):
                        st.text(result.sql_version)
                    
                    show_processing_status("db_connection_test", f"Successfully connected to {db_name.replace('sql_', '')}", "success")
                else:
                    st.error("❌ Database connection failed - no response from server")
                    
    except ImportError:
        st.error("❌ **pyodbc module not installed**")
        st.markdown("""
        **To fix this issue:**
        ```bash
        pip install pyodbc
        ```
        """)
    except pyodbc.Error as e:
        st.error(f"❌ **Database connection failed**")

        # Parse error for better user guidance
        # NOTE: checks must come BEFORE the driver check because pyodbc always
        # embeds the driver name in the error text, e.g. "[ODBC Driver 18 for SQL Server]"
        # which would make "driver" in error_msg match every single error.
        error_msg = str(e)
        st.code(error_msg, language="text")  # Always show full error for diagnosis

        if "40615" in error_msg or "IP address" in error_msg:
            st.warning("🔥 **Firewall Issue:** Your IP is not whitelisted on the Azure SQL Server. Add it in Azure Portal → SQL Server → Networking → Firewall rules.")
        elif "SSL" in error_msg or "certificate" in error_msg.lower() or "TLS" in error_msg:
            st.warning("🔒 **SSL Issue:** Enable 'Trust Server Certificate' in Advanced Settings and retry.")
        elif "Login failed" in error_msg:
            st.warning("🔐 **Authentication Issue:** Check username and password")
        elif sql_connection.is_network_error(error_msg):
            with st.spinner("Checking whether this machine can reach the server..."):
                diagnosis = sql_connection.network_diagnosis(db_config)
            st.warning("🌐 **Server Issue:** " + (diagnosis or "Check server address and network connectivity"))
        elif "database" in error_msg.lower() and "does not exist" in error_msg.lower():
            st.warning("🗄️ **Database Issue:** Check database name")
        elif "IM002" in error_msg or "data source name not found" in error_msg.lower():
            st.warning("🔧 **Driver Issue:** The selected ODBC driver is not installed on this machine.")
        else:
            st.warning(f"**Error Details:** {error_msg}")
            
        # Show troubleshooting tips
        with st.expander("🔧 Troubleshooting Tips", expanded=False):
            st.markdown("""
            **Common Solutions:**
            
            1. **Authentication Issues:**
               - Verify username and password
               - Try Windows Authentication if available
               - Check if account is locked or expired
            
            2. **Connection Issues:**
               - Verify server name and port
               - Check if SQL Server is running
               - Verify network connectivity
               - Check firewall settings
            
            3. **Driver Issues:**
               - Install Microsoft ODBC Driver for SQL Server
               - Try different driver version
               - Restart application after driver installation
            
            4. **Database Issues:**
               - Verify database exists
               - Check database permissions
               - Ensure database is online
            """)
            
    except Exception as e:
        st.error(f"❌ **Unexpected error:** {str(e)}")

def create_db_config(server: str, database: str, username: str, password: str, driver: str, 
                    port: str, use_windows_auth: bool, encrypt: str, trust_server_cert: bool,
                    connection_timeout: int, application_name: str, mars_connection: bool,
                    command_timeout: int, auto_commit: bool) -> Dict:
    """Create database configuration dictionary"""
    config = {
        "server": server,
        "database": database,
        "driver": driver,
        "port": port if port != "1433" else "",
        "encrypt": encrypt,
        "trust_server_cert": trust_server_cert,
        "connection_timeout": connection_timeout,
        "application_name": application_name,
        "mars_connection": mars_connection,
        "command_timeout": command_timeout,
        "auto_commit": auto_commit
    }
    
    if use_windows_auth:
        config["Trusted_Connection"] = "yes"
        config["username"] = ""
        config["password"] = ""
    else:
        config["username"] = username
        config["password"] = password
        config["Trusted_Connection"] = "no"
    
    return config

def save_credentials(credentials: Dict, org_name: str, new_creds: Dict) -> bool:
    """Save updated credentials to file and refresh session state"""
    try:
        from ui_components.connection_manager import credentials_path, write_credentials_file
        credentials[org_name] = new_creds
        creds_path = credentials_path()

        # Save to file
        write_credentials_file(credentials)
        
        # CRITICAL FIX: Update session state with the new org
        if 'available_orgs' not in st.session_state:
            st.session_state.available_orgs = []
        
        # Add new org to available orgs if it's not already there
        # (Salesforce orgs only - SQL Server / Oracle / ... keys are not orgs)
        from ui_components.connection_manager import classify_credentials, retry_sf_connection
        is_sf_org = org_name in classify_credentials({org_name: new_creds})['salesforce']
        if is_sf_org and org_name not in st.session_state.available_orgs:
            st.session_state.available_orgs.append(org_name)
        if is_sf_org:
            # Forget the cached connection / failed login so the new credentials are used
            retry_sf_connection(org_name)
        
        # Also refresh the complete credentials in session state if it exists
        if 'credentials' in st.session_state:
            st.session_state.credentials = credentials
            
        # Success feedback
        st.info(f"📁 Credentials saved to: {creds_path}")
        st.info(f"🔄 Session state updated with {len(st.session_state.available_orgs)} organizations")
        
        return True
    except Exception as e:
        st.error(f"❌ Error saving credentials: {str(e)}")
        return False

def save_system_settings(settings: Dict) -> bool:
    """Save system settings to file"""
    try:
        settings_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), 
            'system_settings.json'
        )
        
        with open(settings_path, 'w') as f:
            json.dump(settings, f, indent=2)
        
        return True
    except Exception as e:
        st.error(f"Error saving settings: {str(e)}")
        return False

def clear_log_files() -> bool:
    """Clear log files"""
    try:
        logs_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'DataLoader_Logs')
        if os.path.exists(logs_path):
            for root, dirs, files in os.walk(logs_path):
                for file in files:
                    if file.endswith('.log') or 'log' in file.lower():
                        os.remove(os.path.join(root, file))
        return True
    except Exception:
        return False

def clear_temp_files() -> bool:
    """Clear temporary files"""
    try:
        temp_extensions = ['.tmp', '.temp', '.bak']
        project_root = os.path.dirname(os.path.dirname(__file__))
        
        for root, dirs, files in os.walk(project_root):
            for file in files:
                if any(file.lower().endswith(ext) for ext in temp_extensions):
                    os.remove(os.path.join(root, file))
        return True
    except Exception:
        return False