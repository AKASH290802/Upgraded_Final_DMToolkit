"""AppTest entry point: the real streamlit_app with Salesforce / SQL Server faked."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
os.chdir(ROOT)

import pandas as pd  # noqa: E402

import fake_salesforce  # noqa: E402
fake_salesforce.install()

import streamlit_app  # noqa: E402
from ui_components import data_operations  # noqa: E402

SQL_ROWS = pd.DataFrame({
    'AccountName': ['Initech', 'Umbrella', ''],
    'Acct_No': ['B-1', 'B-2', 'B-3'],
    'Phone': ['5550001111', '5550002222', '5550003333'],
    'Industry': ['Energy', 'Banking', 'Energy'],
})


def _fake_sql_query_to_df(db_cfg, query, command_timeout=None, chunk_size=5000, lock_timeout_ms=5000):
    """Hook: st.session_state['_test_sql_tables'] = 'fail' (unreachable server) or 'views' (a table + a view)."""
    import streamlit as st
    fake_salesforce.QUERIES.append(('sql', query))
    if 'INFORMATION_SCHEMA.TABLES' in query:
        mode = st.session_state.get('_test_sql_tables')
        if mode == 'fail':
            raise RuntimeError("(pyodbc.OperationalError) ('08001', '[08001] [Microsoft][ODBC Driver 17 for SQL "
                               "Server]TCP Provider: The wait operation timed out.\r\n (258) (SQLDriverConnect)')")
        if mode == 'views':
            return pd.DataFrame({'TABLE_SCHEMA': ['dbo', 'dbo'], 'TABLE_NAME': ['Accounts', 'vActiveAccounts'],
                                 'TABLE_TYPE': ['BASE TABLE', 'VIEW']})
        return pd.DataFrame({'TABLE_SCHEMA': ['dbo'], 'TABLE_NAME': ['Accounts']})
    return SQL_ROWS.copy()


data_operations._sql_query_to_df = _fake_sql_query_to_df

import isolation  # noqa: E402
isolation.isolate_file_library()
streamlit_app.main()

# Test hook: connect to a second org the way SQL Migration / Object Comparison do.
import streamlit as st  # noqa: E402
from ui_components.utils import establish_sf_connection  # noqa: E402
_other_org = st.session_state.pop('_pending_test_other_org', None)
if _other_org:
    establish_sf_connection(st.session_state.credentials, _other_org)
