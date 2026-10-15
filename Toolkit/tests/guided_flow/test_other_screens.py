"""
Every other screen uses the sidebar connections; Data Hub loader; File Library dedupe.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_other_screens.py -v
"""
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from streamlit.testing.v1 import AppTest  # noqa: E402

from helpers import ORG, OTHER_ORG, SQL_KEY, no_exceptions  # noqa: E402
import fake_salesforce  # noqa: E402
from ui_components import navigation  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP4_PAGE  # noqa: E402

# Own entry script: app_under_test.py fakes + File Library DB redirected to a
# temp folder + 'Execute Tests' result saving disabled.
APP = os.path.join(HERE, 'app_other_screens.py')

DATA_HUB_PAGE = "📊 Data Hub"
MAPPING_PAGE = "🗺️ Mapping"
CONFIG_PAGE = "⚙️ Configuration"
COMPARISON_PAGE = "🔍 Object Comparison"
ORG_MIGRATION_PAGE = "🔄 Org Migration"


def tearDownModule():
    """Undo the File Library redirect done by app_other_screens.py."""
    from ui_components import file_store_manager as fsm
    tmp = getattr(fsm, '_apptest_tmp', None)
    if tmp:
        fsm.DB_PATH, fsm.SOURCE_STORE, fsm.OUTPUT_STORE = fsm._apptest_saved_paths
        fsm._apptest_tmp = None
        shutil.rmtree(tmp, ignore_errors=True)


def new_app(timeout: int = 180) -> AppTest:
    at = AppTest.from_file(APP, default_timeout=timeout)
    at.run()
    return at


def _app_with_org():
    at = new_app()
    at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
    return at


def _go(at, page):
    at.sidebar.radio(key='nav_page').set_value(page).run()
    return at


class EveryScreenUsesSidebarConnectionTests(unittest.TestCase):

    def test_every_page_renders_without_new_logins(self):
        at = _app_with_org()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['connected_org'], ORG)
        logins = len(fake_salesforce.LOGINS)
        for page in navigation.PAGE_LIST:
            with self.subTest(page=page):
                _go(at, page)
                no_exceptions(self, at)
                self.assertEqual(at.session_state['nav_page'], page)
                self.assertEqual(len(fake_salesforce.LOGINS), logins,
                                 f"{page} logged in again instead of reusing the sidebar connection")
                self.assertEqual(at.session_state['current_org'], ORG)

    def test_mapping_and_configuration_keep_sidebar_org_connected(self):
        at = _app_with_org()
        for page in (MAPPING_PAGE, CONFIG_PAGE):
            _go(at, page)
            no_exceptions(self, at)
            self.assertEqual(at.session_state['connected_org'], ORG, page)
            self.assertIsNotNone(at.session_state['sf_connection'], page)

    def test_picklist_and_config_org_lists_only_contain_salesforce_orgs(self):
        at = _app_with_org()
        _go(at, CONFIG_PAGE)
        options = at.selectbox(key='test_org_selector').options
        self.assertIn(ORG, options)
        self.assertNotIn(SQL_KEY, options)
        self.assertNotIn('openai_config', options)
        _go(at, "🔍 Object Comparison")
        no_exceptions(self, at)
        source = at.selectbox(key='comparison_source_org_select')
        self.assertEqual(source.value, ORG, "source org defaults to the sidebar org")
        self.assertNotIn(SQL_KEY, source.options)
        self.assertNotIn('openai_config', source.options)
        _go(at, "🔄 Org Migration")
        no_exceptions(self, at)
        mig_source = at.selectbox(key='migration_source_selector')
        self.assertEqual(mig_source.value, ORG)
        self.assertNotIn(SQL_KEY, mig_source.options)

    def test_picklist_selector_defaults_to_sidebar_org(self):
        at = _app_with_org()
        _go(at, MAPPING_PAGE)
        no_exceptions(self, at)
        keys = [w.key for w in at.selectbox]
        for key in ('picklist_org_select', 'view_org_select', 'delete_org_select'):
            if key in keys:
                box = at.selectbox(key=key)
                self.assertEqual(box.value, ORG, key)
                self.assertNotIn(SQL_KEY, box.options, key)
                self.assertNotIn('openai_config', box.options, key)


    def test_page_visits_do_not_touch_the_real_file_library_db(self):
        from ui_components import file_store_manager as fsm
        at = _app_with_org()
        _go(at, "📁 File Library")
        no_exceptions(self, at)
        self.assertTrue(getattr(fsm, '_apptest_tmp', None))
        self.assertTrue(os.path.abspath(fsm.DB_PATH).startswith(os.path.abspath(fsm._apptest_tmp)))

    def test_source_pickers_follow_the_sidebar_org(self):
        for page, key in ((COMPARISON_PAGE, 'comparison_source_org_select'),
                          (ORG_MIGRATION_PAGE, 'migration_source_selector'),
                          (DATA_HUB_PAGE, 'history_org_filter')):
            with self.subTest(page=page):
                at = _app_with_org()
                _go(at, page)
                no_exceptions(self, at)
                self.assertEqual(at.selectbox(key=key).value, ORG)
                # Switch the sidebar org while on the page ...
                at.sidebar.selectbox(key='global_org_selector').set_value(OTHER_ORG).run()
                no_exceptions(self, at)
                self.assertEqual(at.selectbox(key=key).value, OTHER_ORG)
                # ... and after leaving and coming back.
                _go(at, navigation.DASHBOARD)
                _go(at, page)
                no_exceptions(self, at)
                self.assertEqual(at.selectbox(key=key).value, OTHER_ORG)

    def test_manual_source_choice_is_kept_while_sidebar_org_is_unchanged(self):
        at = _app_with_org()
        _go(at, COMPARISON_PAGE)
        at.selectbox(key='comparison_source_org_select').set_value(OTHER_ORG).run()
        no_exceptions(self, at)
        _go(at, navigation.DASHBOARD)
        _go(at, COMPARISON_PAGE)
        self.assertEqual(at.selectbox(key='comparison_source_org_select').value, OTHER_ORG)


class DataHubLoaderTests(unittest.TestCase):

    def test_data_hub_without_sidebar_org_does_not_log_in(self):
        at = new_app()
        self.assertFalse(at.session_state['current_org'] if 'current_org' in at.session_state else None)
        logins = len(fake_salesforce.LOGINS)
        _go(at, DATA_HUB_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.selectbox(key='history_org_filter').value, "")
        self.assertEqual(fake_salesforce.LOGINS[logins:], [],
                         "Data Hub logged into an org the user never picked")

    def test_load_data_tab_adds_dataset_from_sidebar_sql_connection(self):
        at = _app_with_org()
        at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
        _go(at, DATA_HUB_PAGE)
        no_exceptions(self, at)
        hub = at.session_state['data_hub']
        before = hub.get_dataset_count()

        at.radio(key='hub_loader_source').set_value("🗄️ SQL Server").run()
        no_exceptions(self, at)
        at.selectbox(key='hub_loader_sql_table').set_value('dbo.Accounts').run()
        at.button(key='hub_loader_sql_run').click().run()
        no_exceptions(self, at)
        staged = at.session_state['hub_loader_staged']
        self.assertEqual(staged['details']['sql_connection'], SQL_KEY)
        self.assertEqual(len(staged['df']), 3)

        at.button(key='hub_loader_add').click().run()
        no_exceptions(self, at)
        hub = at.session_state['data_hub']
        self.assertEqual(hub.get_dataset_count(), before + 1)
        info = hub.get_active_dataset_info()
        self.assertEqual(info['metadata']['source_type'], 'sql_server')
        self.assertEqual(info['metadata']['source_details']['org'], ORG)


class DashboardTests(unittest.TestCase):

    def test_start_guided_migration_opens_step1(self):
        at = _app_with_org()
        _go(at, navigation.DASHBOARD)
        no_exceptions(self, at)
        at.button(key='dash_start_flow').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP1_PAGE)

    def test_validation_quick_action_uses_new_page_name(self):
        at = _app_with_org()
        _go(at, navigation.DASHBOARD)
        at.button(key='dash_validation').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], navigation.STEP2_PAGE)


class UnitTestingExecuteTests(unittest.TestCase):

    SUITE_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), 'Unit Testing Generates', ORG, 'Account')

    def test_execute_tests_runs_on_the_sidebar_connection(self):
        if not os.path.isdir(self.SUITE_DIR):
            self.skipTest(f"no generated suite at {self.SUITE_DIR}")
        at = _app_with_org()
        _go(at, STEP4_PAGE)
        no_exceptions(self, at)
        at.session_state['unit_testing_tabs'] = "🏃 Execute Tests"   # only the open tab is drawn
        at.run()
        at.selectbox(key='execute_test_suite').set_value('Account').run()
        no_exceptions(self, at)
        logins = len(fake_salesforce.LOGINS)
        [b for b in at.button if 'Execute Tests' in (b.label or '')][0].click().run()
        no_exceptions(self, at)
        errors = [e.value for e in at.error]
        self.assertFalse([e for e in errors if 'Test execution failed' in e], errors)
        self.assertEqual(len(fake_salesforce.LOGINS), logins, "Execute Tests logged in again")
        self.assertGreaterEqual(at.session_state['_test_saved_results'], 1, "results reached the save step")


class RegisterSourceFileTests(unittest.TestCase):

    def setUp(self):
        from ui_components import file_store_manager as fsm
        self.fsm = fsm
        self.tmp = tempfile.mkdtemp(prefix="fsm_test_")
        self._saved = (fsm.DB_PATH, fsm.SOURCE_STORE, fsm.OUTPUT_STORE)
        fsm.DB_PATH = os.path.join(self.tmp, 'files.db')
        fsm.SOURCE_STORE = os.path.join(self.tmp, 'source')
        fsm.OUTPUT_STORE = os.path.join(self.tmp, 'output')

    def tearDown(self):
        self.fsm.DB_PATH, self.fsm.SOURCE_STORE, self.fsm.OUTPUT_STORE = self._saved
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _stored_files(self):
        found = []
        for root, _dirs, files in os.walk(self.fsm.SOURCE_STORE):
            found.extend(os.path.join(root, f) for f in files)
        return found

    def test_same_bytes_registered_twice_is_stored_once(self):
        data = b"Name,Phone\nAcme,555\n"
        first = self.fsm.register_source_file(data, 'accounts.csv', org_name=ORG, object_name='Account')
        second = self.fsm.register_source_file(data, 'accounts.csv', org_name=ORG, object_name='Account',
                                               row_count=1, col_count=2)
        self.assertIsNotNone(first)
        self.assertEqual(first, second)
        self.assertEqual(len(self._stored_files()), 1)
        rows = self.fsm.list_source_files()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['row_count'], 1)

    def test_changed_content_or_metadata_creates_new_entry(self):
        a = self.fsm.register_source_file(b"x\n1\n", 'f.csv', org_name=ORG, object_name='Account')
        b = self.fsm.register_source_file(b"x\n2\n", 'f.csv', org_name=ORG, object_name='Account')
        c = self.fsm.register_source_file(b"x\n1\n", 'f.csv', org_name=ORG, object_name='Contact')
        self.assertEqual(len({a, b, c}), 3)
        self.assertEqual(len(self._stored_files()), 3)

    def test_missing_stored_file_is_copied_again(self):
        data = b"x\n1\n"
        first = self.fsm.register_source_file(data, 'f.csv', org_name=ORG, object_name='Account')
        for path in self._stored_files():
            os.remove(path)
        second = self.fsm.register_source_file(data, 'f.csv', org_name=ORG, object_name='Account')
        self.assertNotEqual(first, second)
        self.assertEqual(len(self._stored_files()), 1)

    def test_existing_database_gets_content_hash_column(self):
        import sqlite3
        os.makedirs(self.tmp, exist_ok=True)
        with sqlite3.connect(self.fsm.DB_PATH) as conn:
            conn.execute("""CREATE TABLE source_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT, original_name TEXT NOT NULL,
                stored_path TEXT NOT NULL UNIQUE, org_name TEXT DEFAULT 'unknown',
                object_name TEXT DEFAULT '', file_size INTEGER DEFAULT 0,
                row_count INTEGER DEFAULT 0, col_count INTEGER DEFAULT 0,
                file_type TEXT DEFAULT '', uploaded_at TEXT NOT NULL)""")
            # A legacy row (no hash) whose file exists on disk.
            legacy_dir = os.path.join(self.fsm.SOURCE_STORE, ORG, 'Account')
            os.makedirs(legacy_dir, exist_ok=True)
            legacy_path = os.path.join(legacy_dir, 'old_f.csv')
            with open(legacy_path, 'wb') as f:
                f.write(b"x\n1\n")
            conn.execute("INSERT INTO source_files (original_name, stored_path, org_name, object_name, "
                         "uploaded_at) VALUES ('f.csv', ?, ?, 'Account', '2026-01-01')", (legacy_path, ORG))
            conn.commit()
        file_id = self.fsm.register_source_file(b"x\n1\n", 'f.csv', org_name=ORG, object_name='Account')
        self.assertEqual(file_id, 1, "legacy copy with the same content is reused")
        self.assertEqual(len(self._stored_files()), 1)
        with sqlite3.connect(self.fsm.DB_PATH) as conn:
            cols = {row[1] for row in conn.execute("PRAGMA table_info(source_files)")}
        self.assertIn('content_hash', cols)


if __name__ == '__main__':
    unittest.main()
