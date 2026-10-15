"""AppTest entry for test_other_screens: app_under_test.py plus test-only isolation.

In addition to the fakes of app_under_test.py (fake Salesforce, fake SQL Server):
  * the File Library (file_store_manager) DB and stores point at a temp folder,
    so page visits never touch the real dm_toolkit_files.db / file_store;
  * unit_testing_operations.save_real_test_results is a no-op counter, so
    'Execute Tests' does not write result files into the project.
"""
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)
os.chdir(ROOT)

import pandas as pd  # noqa: E402

import fake_salesforce  # noqa: E402
fake_salesforce.install()

from ui_components import file_store_manager as _fsm  # noqa: E402

# Redirect once per process; test_other_screens.tearDownModule restores + cleans up.
if not getattr(_fsm, '_apptest_tmp', None):
    _fsm._apptest_saved_paths = (_fsm.DB_PATH, _fsm.SOURCE_STORE, _fsm.OUTPUT_STORE)
    _fsm._apptest_tmp = tempfile.mkdtemp(prefix="dm_toolkit_apptest_")
    _fsm.DB_PATH = os.path.join(_fsm._apptest_tmp, 'files.db')
    _fsm.SOURCE_STORE = os.path.join(_fsm._apptest_tmp, 'file_store', 'source')
    _fsm.OUTPUT_STORE = os.path.join(_fsm._apptest_tmp, 'file_store', 'output')

import streamlit as st  # noqa: E402
import streamlit_app  # noqa: E402
from ui_components import data_operations, unit_testing_operations  # noqa: E402

SQL_ROWS = pd.DataFrame({
    'AccountName': ['Initech', 'Umbrella', ''],
    'Acct_No': ['B-1', 'B-2', 'B-3'],
    'Phone': ['5550001111', '5550002222', '5550003333'],
    'Industry': ['Energy', 'Banking', 'Energy'],
})


def _fake_sql_query_to_df(db_cfg, query, command_timeout=None, chunk_size=5000, lock_timeout_ms=5000):
    fake_salesforce.QUERIES.append(('sql', query))
    if 'INFORMATION_SCHEMA.TABLES' in query:
        return pd.DataFrame({'TABLE_SCHEMA': ['dbo'], 'TABLE_NAME': ['Accounts']})
    return SQL_ROWS.copy()


data_operations._sql_query_to_df = _fake_sql_query_to_df


def _no_save_real_test_results(*args, **kwargs):
    st.session_state['_test_saved_results'] = st.session_state.get('_test_saved_results', 0) + 1


unit_testing_operations.save_real_test_results = _no_save_real_test_results

streamlit_app.main()
