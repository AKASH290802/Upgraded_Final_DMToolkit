"""AppTest entry point for the Step 2 tests.

Same as app_under_test.py (real app, Salesforce and SQL Server faked) plus: validation
output files go to a temp folder and are not registered in the File Library, so running
the tests does not litter the project's Validation/ and file_store/ folders.
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

import streamlit_app  # noqa: E402
from ui_components import data_operations  # noqa: E402
from ui_components import validation_operations  # noqa: E402

SQL_ROWS = pd.DataFrame({
    'AccountName': ['Initech', 'Umbrella', ''],
    'Acct_No': ['B-1', 'B-2', 'B-3'],
    'Phone': ['5550001111', '5550002222', '5550003333'],
    'Industry': ['Energy', 'Banking', 'Energy'],
})

OUTPUT_ROOT = os.path.join(tempfile.gettempdir(), 'dm_toolkit_step2_tests')


def _fake_sql_query_to_df(db_cfg, query, command_timeout=None, chunk_size=5000, lock_timeout_ms=5000):
    fake_salesforce.QUERIES.append(('sql', query))
    if 'INFORMATION_SCHEMA.TABLES' in query:
        return pd.DataFrame({'TABLE_SCHEMA': ['dbo'], 'TABLE_NAME': ['Accounts']})
    return SQL_ROWS.copy()


def _temp_validation_folder(validation_type, org_name=None, object_name=None):
    folder = os.path.join(OUTPUT_ROOT, validation_type, org_name or '_', object_name or '_')
    os.makedirs(folder, exist_ok=True)
    return folder


data_operations._sql_query_to_df = _fake_sql_query_to_df
validation_operations.get_validation_folder_path = _temp_validation_folder
validation_operations.register_source_file = None
# Result files are not indexed in the File Library unless a test asks for it (the index is
# an isolated temp DB either way, see isolation.isolate_file_library).
import streamlit as _st  # noqa: E402
from ui_components import file_store_manager as _fsm  # noqa: E402
validation_operations.register_output_file = (
    _fsm.register_output_file if _st.session_state.get('_test_keep_file_registration') else None)

import isolation  # noqa: E402
isolation.isolate_file_library()
streamlit_app.main()
