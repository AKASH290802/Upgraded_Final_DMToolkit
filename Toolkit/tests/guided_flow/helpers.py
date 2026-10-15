"""Shared helpers for the guided-flow AppTest tests."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for path in (ROOT, HERE):
    if path not in sys.path:
        sys.path.insert(0, path)

from streamlit.testing.v1 import AppTest  # noqa: E402

import fake_salesforce  # noqa: E402
fake_salesforce.install()

import isolation  # noqa: E402
isolation.use_test_credentials()   # fake connections, never the real Services/linkedservices.json
isolation.use_test_projects()      # no projects, never the real Services/projects.json

APP = os.path.join(HERE, 'app_under_test.py')
ORG = 'AkashDev'
OTHER_ORG = 'FCS'
SQL_KEY = 'sql_SQL Server'


def new_app(timeout: int = 120) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.run()
    return at


def no_exceptions(case, at) -> None:
    errors = [e.value for e in at.exception]
    case.assertEqual(errors, [], f"Streamlit raised: {errors}")
