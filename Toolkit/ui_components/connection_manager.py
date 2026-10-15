"""
Connection Manager - the single source of truth for every connection in the app.

Every screen uses the connections chosen in the sidebar:

    Salesforce org  -> st.session_state.current_org
    SQL Server      -> st.session_state.current_sql_connection
    Oracle          -> st.session_state.current_oracle_connection

Salesforce connections are kept in a per-org pool, so a screen that needs a
second org (SQL Migration, Object Comparison, Config "Test Connection") gets its
own cached connection and can no longer overwrite the sidebar org's connection.
The legacy keys st.session_state.sf_connection / connected_org are kept as a
mirror of the SIDEBAR org only, for the modules that still read them directly.

Screens must not change the sidebar selection by assigning current_* keys.
Use request_connection_change() instead: it is applied before the sidebar
widgets are drawn on the next run, so the sidebar and the screen stay in sync.
"""

import hashlib
import json
import os
import time
from typing import Dict, Optional, Tuple

import pandas as pd
import streamlit as st

# Credential key prefixes written by Configuration (config_management.py).
DB_PREFIXES = {
    'sql_': 'sqlserver',
    'oracle_': 'oracle',
    'snowflake_': 'snowflake',
    'pg_': 'postgres',
}
NON_ORG_KEYS = {'openai_config'}

# A live Salesforce connection is re-checked with a cheap query at most this often.
SF_HEALTH_CHECK_SECONDS = 300
# After a network error (not a credentials error) the login is tried again after this long.
SF_NETWORK_RETRY_SECONDS = 20

# Session keys that hold data belonging to one org. They are cleared when the
# sidebar org changes so no screen mixes data from two orgs.
ORG_SCOPED_PREFIXES = (
    'flow_',
    'step1_soql_', 'step1_target_object', 'step1_suggested_applied',
    'schema_validation_', 'schema_field_mappings', 'custom_validation_',
    'genai_validation_', 'genai_field_mappings', 'current_field_mappings',
    'ai_bundle_', 'genai_bundle_', 'current_genai_object', 'extracted_validation_rules',
    'validator_file_path', 'bundle_file_path', 'formula_',
    'enhanced_validation_', 'enhanced_field_mappings_', 'enhanced_lookup_configs_',
    'enhanced_unresolved_lookup_indices',
    'sf_load_', 'load_field_mappings', 'dataload_lookup_configs',
    'mig_preview_', 'mig_field_mapping',
    '_sf_objects_cache', '_sf_describe_cache',
    'step4_', 'unit_test_', '_unit_test_', 'execute_test_suite', '_execute_test_suite', 'correlation_object',
)
# Step 1 data staged from Salesforce belongs to the old org; data from a file,
# SQL Server or Oracle does not, so it stays staged across an org change.
STAGED_KEY = 'step1_staged'

# Session keys that hold data read from one SQL Server / Oracle connection.
SQL_SCOPED_PREFIXES = ('sql_tables_', 'sql_query_text', 'mig_preview_')
SQL_SCOPED_SUFFIXES = ('_sql_df',)
ORACLE_SCOPED_SUFFIXES = ('_oracle_df',)

ORG_PLACEHOLDER = "Select an organization..."
SQL_PLACEHOLDER = "Select a SQL connection..."
ORACLE_PLACEHOLDER = "Select an Oracle connection..."
SOURCE_PLACEHOLDER = "Select a source connection..."
# The one sidebar "Source connection" picker lists every saved source of these kinds.
SOURCE_KINDS = {'sqlserver': ('🗄️', 'SQL Server'), 'oracle': ('🔶', 'Oracle'),
                'snowflake': ('❄️', 'Snowflake'), 'postgres': ('🐘', 'PostgreSQL')}


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------

def get_credentials() -> Dict:
    """Credentials loaded by streamlit_app.load_credentials()."""
    return st.session_state.get('credentials') or {}


# Set to another file to run the app (or a test) on a copy of the credentials.
CREDENTIALS_ENV = 'DM_TOOLKIT_CREDENTIALS'
_APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def credentials_path() -> str:
    """The linkedservices.json every screen reads and writes."""
    return os.environ.get(CREDENTIALS_ENV) or os.path.join(_APP_ROOT, 'Services', 'linkedservices.json')


def read_credentials_file() -> Dict:
    with open(credentials_path(), 'r', encoding='utf-8') as f:
        return json.load(f)


def write_credentials_file(creds: Dict) -> None:
    with open(credentials_path(), 'w', encoding='utf-8') as f:
        json.dump(creds, f, indent=2)


def _publish_credentials(creds: Dict) -> None:
    """Make every screen and the sidebar see creds (the file was just written)."""
    groups = classify_credentials(creds)
    st.session_state.credentials = creds
    st.session_state.available_orgs = list(groups['salesforce'].keys())
    st.session_state.available_sql_connections = list(groups['sqlserver'].keys())
    st.session_state.available_oracle_connections = list(groups['oracle'].keys())


CONNECTION_KINDS = {
    'salesforce': 'Salesforce org', 'sqlserver': 'SQL Server', 'oracle': 'Oracle',
    'snowflake': 'Snowflake', 'postgres': 'PostgreSQL',
}


def connection_kind(key: str, creds: Optional[Dict] = None) -> Optional[str]:
    """'salesforce', 'sqlserver', ... for a saved connection; None for other settings (e.g. openai_config)."""
    creds = get_credentials() if creds is None else creds
    if key not in creds:
        return None
    kind = next((k for k, entries in classify_credentials({key: creds[key]}).items() if key in entries), None)
    return kind if kind in CONNECTION_KINDS else None


def delete_connection(key: str) -> Optional[Dict]:
    """Remove ONE saved connection from linkedservices.json.

    Returns what is needed to undo it ({'key', 'value', 'index', 'kind'}), or None when
    key is not a saved connection. The sidebar drops the connection on the next run
    (and resets its selection if it was the one in use); a Salesforce org's cached
    login and metadata are forgotten now.
    """
    creds = read_credentials_file()
    kind = connection_kind(key, creds)
    if kind is None:
        return None
    index = list(creds).index(key)
    value = creds.pop(key)
    write_credentials_file(creds)
    _publish_credentials(creds)
    if kind == 'salesforce':
        retry_sf_connection(key)
    return {'key': key, 'value': value, 'index': index, 'kind': kind}


def restore_connection(deleted: Dict) -> bool:
    """Undo delete_connection(): put the entry back where it was.

    Refuses (returns False) if a connection with that name was saved since, so an
    undo never overwrites newer credentials.
    """
    creds = read_credentials_file()
    if deleted['key'] in creds:
        return False
    items = list(creds.items())
    items.insert(min(deleted['index'], len(items)), (deleted['key'], deleted['value']))
    creds = dict(items)
    write_credentials_file(creds)
    _publish_credentials(creds)
    return True


def classify_credentials(creds: Dict) -> Dict[str, Dict]:
    """Split linkedservices.json entries by connection type.

    DB entries are identified by the prefix Configuration writes (sql_, oracle_,
    snowflake_, pg_). Legacy SQL Server entries without the prefix are detected
    by their server/database fields. Anything with a username that is not a
    database and not a known non-org key is a Salesforce org.
    """
    groups = {'salesforce': {}, 'sqlserver': {}, 'oracle': {},
              'snowflake': {}, 'postgres': {}, 'other': {}}
    for key, value in (creds or {}).items():
        if not isinstance(value, dict):
            groups['other'][key] = value
            continue
        key_lower = key.lower()
        kind = next((k for prefix, k in DB_PREFIXES.items() if key_lower.startswith(prefix)), None)
        if kind:
            groups[kind][key] = value
        elif key_lower in NON_ORG_KEYS or not value.get('username'):
            groups['other'][key] = value
        elif 'server' in value and 'database' in value:
            groups['sqlserver'][key] = value
        else:
            groups['salesforce'][key] = value
    return groups


def salesforce_orgs() -> Dict[str, Dict]:
    return classify_credentials(get_credentials())['salesforce']


def sql_connections() -> Dict[str, Dict]:
    return classify_credentials(get_credentials())['sqlserver']


def oracle_connections() -> Dict[str, Dict]:
    return classify_credentials(get_credentials())['oracle']


def display_name(key: Optional[str]) -> str:
    """'sql_SQL Server' -> 'SQL Server', 'oracle_HR' -> 'HR'."""
    if not key:
        return ''
    for prefix in DB_PREFIXES:
        if key.lower().startswith(prefix):
            return key[len(prefix):]
    return key


# ---------------------------------------------------------------------------
# Salesforce
# ---------------------------------------------------------------------------

def _creds_fingerprint(creds: Dict) -> str:
    raw = f"{creds.get('username', '')}|{creds.get('domain', '')}|{creds.get('password', '')}|{creds.get('security_token', '')}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _pool() -> Dict[str, Dict]:
    if '_sf_conn_pool' not in st.session_state:
        st.session_state._sf_conn_pool = {}
    return st.session_state._sf_conn_pool


def _mirror_if_current(org_name: str, conn) -> None:
    if org_name == st.session_state.get('current_org'):
        st.session_state.sf_connection = conn
        st.session_state.connected_org = org_name if conn is not None else None


def normalize_domain(domain: Optional[str]) -> str:
    """Salesforce login domain as simple_salesforce expects it ('login', 'test', 'mycompany.my').

    Accepts the forms people paste: 'https://mycompany.my.salesforce.com/',
    'mycompany.my.salesforce.com', 'test.salesforce.com', '' / None (-> 'login').
    """
    value = (domain or '').strip()
    for scheme in ('https://', 'http://'):
        if value.lower().startswith(scheme):
            value = value[len(scheme):]
    value = value.strip('/')
    if value.lower().endswith('.salesforce.com'):
        value = value[:-len('.salesforce.com')]
    return value or 'login'


def _is_auth_failure(exc: Exception) -> bool:
    """True for errors caused by the credentials (retrying them can lock the user)."""
    try:
        from simple_salesforce.exceptions import SalesforceAuthenticationFailed
        if isinstance(exc, SalesforceAuthenticationFailed):
            return True
    except ImportError:
        pass
    return isinstance(exc, TypeError)  # missing username/password/token


def _connection_help(org_name: str, auth_failure: bool) -> str:
    if auth_failure:
        return (f"Check the credentials of **{org_name}** (Services/linkedservices.json or Configuration → "
                "Organizations), then click **🔁 Retry connection** in the sidebar.")
    return "This looks like a network problem (VPN, proxy or Salesforce unavailable). It is retried automatically."


def get_sf_connection(org_name: Optional[str] = None, credentials: Optional[Dict] = None,
                      quiet: bool = False):
    """Return a live Salesforce connection for org_name (default: the sidebar org).

    Connections are cached per org for the session and health-checked at most
    every SF_HEALTH_CHECK_SECONDS (simple_salesforce renews an expired session
    by itself, so the check only drops a connection on an auth/session error).
    Returns None (and shows an error unless quiet) when the org is unknown or
    the login fails. A login rejected for bad credentials is not retried until
    the credentials change or retry_sf_connection() is called; a network error
    is retried after SF_NETWORK_RETRY_SECONDS.
    """
    org_name = org_name or st.session_state.get('current_org')
    if not org_name:
        return None

    creds_all = credentials if credentials is not None else get_credentials()
    creds = creds_all.get(org_name)
    if not isinstance(creds, dict) or not creds.get('username'):
        if not quiet:
            st.error(f"❌ Organization '{org_name}' not found in credentials")
        _mirror_if_current(org_name, None)
        return None

    pool = _pool()
    fingerprint = _creds_fingerprint(creds)

    failure = _failures().get(org_name)
    if failure and failure.get('fingerprint') == fingerprint and (
            failure.get('auth') or time.time() - failure.get('at', 0) < SF_NETWORK_RETRY_SECONDS):
        _mirror_if_current(org_name, None)
        if not quiet:
            st.error(f"❌ Could not connect to {org_name}: {failure['error']}")
            st.caption(_connection_help(org_name, failure.get('auth', False)))
        return None

    entry = pool.get(org_name)
    if entry and entry.get('fingerprint') == fingerprint:
        if time.time() - entry.get('checked_at', 0) >= SF_HEALTH_CHECK_SECONDS:
            try:
                entry['conn'].query("SELECT Id FROM Organization LIMIT 1")
            except Exception as exc:
                try:
                    from simple_salesforce.exceptions import SalesforceExpiredSession
                    expired = isinstance(exc, SalesforceExpiredSession) or _is_auth_failure(exc)
                except ImportError:
                    expired = _is_auth_failure(exc)
                if expired:
                    pool.pop(org_name, None)
                    entry = None
            if entry:
                entry['checked_at'] = time.time()
        if entry:
            _mirror_if_current(org_name, entry['conn'])
            return entry['conn']

    try:
        from simple_salesforce import Salesforce
        with st.spinner(f"Connecting to {org_name}..."):
            conn = Salesforce(
                username=creds['username'],
                password=creds.get('password') or '',
                security_token=creds.get('security_token') or '',
                domain=normalize_domain(creds.get('domain')),
            )
    except Exception as exc:
        pool.pop(org_name, None)
        auth = _is_auth_failure(exc)
        _failures()[org_name] = {'fingerprint': fingerprint, 'error': str(exc).rstrip('. '),
                                 'auth': auth, 'at': time.time()}
        _mirror_if_current(org_name, None)
        if not quiet:
            st.error(f"❌ Failed to connect to {org_name}: {str(exc).rstrip('. ')}")
            st.caption(_connection_help(org_name, auth))
        return None

    _failures().pop(org_name, None)
    pool[org_name] = {'conn': conn, 'fingerprint': fingerprint, 'checked_at': time.time()}
    _mirror_if_current(org_name, conn)
    if not quiet:
        st.toast(f"Connected to {org_name}", icon="🔗")
    return conn


def _failures() -> Dict[str, Dict]:
    if '_sf_conn_failures' not in st.session_state:
        st.session_state._sf_conn_failures = {}
    return st.session_state._sf_conn_failures


def get_sf_connection_error(org_name: Optional[str] = None) -> Optional[str]:
    """The recorded login error for org_name (default: sidebar org), if any."""
    org_name = org_name or st.session_state.get('current_org')
    failure = _failures().get(org_name) if org_name else None
    return failure['error'] if failure else None


def retry_sf_connection(org_name: Optional[str] = None) -> None:
    """Forget a recorded login failure, the cached connection and cached metadata for org_name.

    Called by the sidebar Retry button and after the org's credentials are saved.
    """
    org_name = org_name or st.session_state.get('current_org')
    if not org_name:
        return
    _failures().pop(org_name, None)
    _pool().pop(org_name, None)
    for cache_name in ('_sf_objects_cache', '_sf_describe_cache'):
        cache = st.session_state.get(cache_name) or {}
        for key in [k for k in cache if isinstance(k, tuple) and org_name in k]:
            cache.pop(key, None)


def org_for_connection(sf_conn) -> Optional[str]:
    """Return the org name a pooled connection belongs to, or None."""
    for org_name, entry in _pool().items():
        if entry.get('conn') is sf_conn:
            return org_name
    return None


def is_sidebar_org_connected() -> bool:
    org = st.session_state.get('current_org')
    entry = _pool().get(org) if org else None
    return bool(entry and entry.get('conn') is not None)


def clear_salesforce_metadata_cache() -> None:
    """Forget cached object lists and describes (sidebar 'Refresh metadata')."""
    st.session_state.pop('_sf_objects_cache', None)
    st.session_state.pop('_sf_describe_cache', None)


# ---------------------------------------------------------------------------
# SQL Server / Oracle
# ---------------------------------------------------------------------------

def get_active_sql_config() -> Tuple[Optional[str], Optional[Dict]]:
    """(key, config) of the sidebar SQL Server connection, or (None, None)."""
    key = st.session_state.get('current_sql_connection')
    conns = sql_connections()
    if key and key in conns:
        return key, conns[key]
    return None, None


def get_active_oracle_config() -> Tuple[Optional[str], Optional[Dict]]:
    """(key, config) of the sidebar Oracle connection, or (None, None)."""
    key = st.session_state.get('current_oracle_connection')
    conns = oracle_connections()
    if key and key in conns:
        return key, conns[key]
    return None, None


def run_sql_query(query: str, command_timeout: Optional[int] = None,
                  chunk_size: int = 5000) -> pd.DataFrame:
    """Run a query on the sidebar SQL Server connection (raises on error)."""
    key, cfg = get_active_sql_config()
    if not cfg:
        raise RuntimeError("No SQL Server connection selected in the sidebar")
    from ui_components.data_operations import _sql_query_to_df
    return _sql_query_to_df(cfg, query, command_timeout=command_timeout, chunk_size=chunk_size)


def run_oracle_query(query: str, chunk_size: int = 5000) -> pd.DataFrame:
    """Run a query on the sidebar Oracle connection (raises on error)."""
    key, cfg = get_active_oracle_config()
    if not cfg:
        raise RuntimeError("No Oracle connection selected in the sidebar")
    from ui_components.data_operations import _oracle_query_to_df
    return _oracle_query_to_df(cfg, query, chunk_size=chunk_size)


# ---------------------------------------------------------------------------
# Changing the sidebar selection
# ---------------------------------------------------------------------------

def _clear_keys(prefixes=(), suffixes=()) -> None:
    for key in list(st.session_state.keys()):
        if not isinstance(key, str):
            continue
        if (prefixes and key.startswith(prefixes)) or (suffixes and key.endswith(suffixes)):
            del st.session_state[key]


def set_current_org(org_name: Optional[str]) -> bool:
    """Make org_name the sidebar org. Returns True if it changed.

    Clears everything that belonged to the previous org (connection mirror,
    current object, guided-flow progress, per-screen data and mappings). Data
    staged in Step 1 from a file, SQL Server or Oracle is kept (it does not
    depend on the org); the Step 1 page tells the user to re-confirm it.
    Safe to call from a widget callback.
    """
    org_name = org_name or None
    previous = st.session_state.get('current_org')
    if org_name == previous:
        return False
    had_flow = bool(st.session_state.get('flow_dataset'))
    st.session_state.current_org = org_name
    st.session_state.sf_connection = None
    st.session_state.connected_org = None
    st.session_state.current_object = None
    _clear_keys(prefixes=ORG_SCOPED_PREFIXES)
    staged = st.session_state.get(STAGED_KEY)
    if staged and staged.get('source_type') == 'salesforce_soql':
        st.session_state.pop(STAGED_KEY, None)
    if previous and (had_flow or st.session_state.get(STAGED_KEY)):
        st.session_state._org_change_notice = {'from': previous, 'to': org_name,
                                               'kept_staged': bool(st.session_state.get(STAGED_KEY))}
    if org_name:
        entry = _pool().get(org_name)
        if entry:
            _mirror_if_current(org_name, entry['conn'])
    return True


def set_current_sql_connection(key: Optional[str]) -> bool:
    """Make key the sidebar SQL Server connection. Returns True if it changed."""
    key = key or None
    if key == st.session_state.get('current_sql_connection'):
        return False
    st.session_state.current_sql_connection = key
    st.session_state.sql_connection = None
    st.session_state.connected_sql = None
    # The guided-flow dataset is a snapshot in the Data Hub, so it stays valid:
    # Step 3 may load it into a different SQL Server than the one it came from.
    _clear_keys(prefixes=SQL_SCOPED_PREFIXES, suffixes=SQL_SCOPED_SUFFIXES)
    return True


def set_current_oracle_connection(key: Optional[str]) -> bool:
    """Make key the sidebar Oracle connection. Returns True if it changed."""
    key = key or None
    if key == st.session_state.get('current_oracle_connection'):
        return False
    st.session_state.current_oracle_connection = key
    _clear_keys(suffixes=ORACLE_SCOPED_SUFFIXES)
    return True


def source_connections() -> Dict[str, str]:
    """{key: kind} of every saved source connection (SQL Server, Oracle, Snowflake, PostgreSQL), in order."""
    groups = classify_credentials(get_credentials())
    return {key: kind for kind in SOURCE_KINDS for key in groups[kind]}


def source_label(key: Optional[str]) -> str:
    """'🗄️ SQL Server · Staging' for a source key (the placeholder for None)."""
    if not key or key == SOURCE_PLACEHOLDER:
        return SOURCE_PLACEHOLDER
    # From the key's prefix first (works without session state, e.g. as a widget format_func);
    # legacy SQL Server entries without a prefix are looked up in the credentials.
    kind = next((k for prefix, k in DB_PREFIXES.items() if key.lower().startswith(prefix)), None) \
        or source_connections().get(key)
    icon, label = SOURCE_KINDS.get(kind, ('🔌', 'Source'))
    return f"{icon} {label} · {display_name(key)}"


def current_source_key() -> Optional[str]:
    """The source chosen in the sidebar (also when it was set through the SQL / Oracle setters)."""
    ss = st.session_state
    return ss.get('current_source_connection') or ss.get('current_sql_connection') or ss.get('current_oracle_connection')


def set_current_source_connection(key: Optional[str]) -> bool:
    """Make key THE sidebar source connection; returns True if it changed.

    One source at a time: choosing an Oracle connection clears the SQL Server one and the
    other way round. Screens keep reading current_sql_connection / current_oracle_connection
    (get_active_sql_config / get_active_oracle_config).
    """
    key = key or None
    kind = source_connections().get(key) if key else None
    changed = key != current_source_key()
    st.session_state.current_source_connection = key
    set_current_sql_connection(key if kind == 'sqlserver' else None)
    set_current_oracle_connection(key if kind == 'oracle' else None)
    return changed


def request_connection_change(kind: str, key: Optional[str]) -> None:
    """Ask the sidebar to switch connection and rerun.

    kind is 'org', 'sql' or 'oracle'. The change is applied by
    apply_pending_connection_changes() before the sidebar widgets are drawn,
    so the sidebar shows the new selection too.
    """
    pending = st.session_state.get('_pending_connection_changes') or {}
    pending[kind] = key
    st.session_state._pending_connection_changes = pending
    st.rerun()


def apply_pending_connection_changes() -> None:
    """Called by the sidebar before its widgets are drawn."""
    pending = st.session_state.pop('_pending_connection_changes', None) or {}
    if 'org' in pending:
        set_current_org(pending['org'])
        st.session_state.global_org_selector = pending['org'] or ORG_PLACEHOLDER
    # 'sql' / 'oracle' (from sql_connection_picker / oracle_connection_picker) and 'source' all set
    # the ONE sidebar source; clearing a kind only clears the source if it is of that kind.
    for kind in ('sql', 'oracle', 'source'):
        if kind not in pending:
            continue
        key = pending[kind]
        if key is None and kind != 'source':
            current = current_source_key()
            wanted = {'sql': 'sqlserver', 'oracle': 'oracle'}[kind]
            if current and source_connections().get(current) != wanted:
                continue
        set_current_source_connection(key)
        st.session_state.global_source_selector = key or SOURCE_PLACEHOLDER


# ---------------------------------------------------------------------------
# Small UI helpers shared by the screens
# ---------------------------------------------------------------------------

def render_connection_banner(show_sql: bool = True, show_oracle: bool = True) -> None:
    """One line telling the user which sidebar connections this screen uses."""
    org = st.session_state.get('current_org')
    if not org:
        parts = ["🏢 _no org selected_"]
    elif is_sidebar_org_connected():
        parts = [f"🏢 **{org}**"]
    elif get_sf_connection_error(org):
        parts = [f"🏢 **{org}** (❌ not connected — login failed)"]
    else:
        parts = [f"🏢 **{org}** (not connected yet)"]
    if show_sql or show_oracle:   # the ONE sidebar source connection
        source = current_source_key()
        if source and source in source_connections():
            icon, label = SOURCE_KINDS[source_connections()[source]]
            parts.append(f"{icon} {label} **{display_name(source)}**")
        else:
            parts.append("🔌 _no source connection_")
    st.caption("🔌 Connections (from the sidebar): " + "  ·  ".join(parts))


def sql_connection_picker(state_prefix: str) -> Tuple[Optional[str], Optional[Dict]]:
    """Return the sidebar SQL Server connection.

    When none is selected, show a picker that SETS THE SIDEBAR connection (so
    every screen uses the same one) instead of a private, screen-only choice.
    """
    key, cfg = get_active_sql_config()
    if cfg:
        st.caption(f"🗄️ Using sidebar SQL Server connection **{display_name(key)}** "
                   f"({cfg.get('server', '?')} / {cfg.get('database', '?')}). Change it in the sidebar.")
        return key, cfg
    conns = sql_connections()
    if not conns:
        st.warning("⚠️ No SQL Server connections configured.")
        st.info("💡 Add one in Configuration → Source Connections, then come back.")
        return None, None
    st.info("🗄️ No SQL Server connection is selected in the sidebar.")
    col1, col2 = st.columns([3, 1])
    with col1:
        choice = st.selectbox("SQL Server connection", list(conns), format_func=display_name,
                              key=f"{state_prefix}_pick_sql")
    with col2:
        st.write("")
        if st.button("Use for all screens", key=f"{state_prefix}_pick_sql_btn", use_container_width=True):
            request_connection_change('sql', choice)
    return None, None


def oracle_connection_picker(state_prefix: str) -> Tuple[Optional[str], Optional[Dict]]:
    """Oracle counterpart of sql_connection_picker()."""
    key, cfg = get_active_oracle_config()
    if cfg:
        st.caption(f"🔶 Using sidebar Oracle connection **{display_name(key)}** "
                   f"({cfg.get('host', '?')}). Change it in the sidebar.")
        return key, cfg
    conns = oracle_connections()
    if not conns:
        st.warning("⚠️ No Oracle connections configured.")
        st.info("💡 Add one in Configuration → Source Connections, then come back.")
        return None, None
    st.info("🔶 No Oracle connection is selected in the sidebar.")
    col1, col2 = st.columns([3, 1])
    with col1:
        choice = st.selectbox("Oracle connection", list(conns), format_func=display_name,
                              key=f"{state_prefix}_pick_oracle")
    with col2:
        st.write("")
        if st.button("Use for all screens", key=f"{state_prefix}_pick_oracle_btn", use_container_width=True):
            request_connection_change('oracle', choice)
    return None, None
