"""
Step 4: the current result comes first; earlier test runs are an ordered history.

* The Step 3 load card and the Step 4 test card are drawn ABOVE the tabs (they used to
  be below them).
* 📊 Test Reports > 📁 Test Files & Results lists every test run newest first (Execute
  Tests runs and ✅ Test Loaded Records reports), for the current object by default, the
  newest tagged Latest; one run is opened at a time with its per-test results (the old
  view stacked identical "<suite> - Detailed Results" expanders with no date).
* Generated test files are listed for the chosen object, newest first.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_step4_history.py -v
"""
import json
import os
import shutil
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG, no_exceptions  # noqa: E402
from test_step2_history import first_index  # noqa: E402
from test_step4_and_tab_nav import app_with_org, app_with_step3_loaded, run_step4_tests  # noqa: E402
from ui_components import file_store_manager as fsm  # noqa: E402
from ui_components import unit_testing_operations as uto  # noqa: E402
from ui_components.navigation import STEP4_PAGE  # noqa: E402

REPORTS_TAB = "📊 Test Reports"


def write_run(root, obj, start, passed, failed, tests=None):
    folder = os.path.join(root, ORG, obj)
    os.makedirs(folder, exist_ok=True)
    stamp = start.replace('-', '').replace(':', '').replace('T', '_')
    path = os.path.join(folder, f"real_test_execution_{obj}_{stamp}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'execution_summary': {'object_name': obj, 'start_time': start, 'total_tests': passed + failed,
                                         'passed': passed, 'failed': failed, 'execution_time_seconds': 75},
                   'detailed_results': tests or [
                       {'test_name': f'{obj} test {i}', 'test_category': 'Field', 'status': 'PASS' if i < passed else 'FAIL',
                        'error_message': '' if i < passed else 'value mismatch'} for i in range(passed + failed)]}, f)
    return path


def history_table(at):
    tables = [d for d in at.dataframe if 'Pass rate' in list(d.value.columns) and 'Kind' in list(d.value.columns)]
    return tables[0].value if tables else None


class ResultCardsFirstTests(unittest.TestCase):

    def test_load_and_test_cards_are_above_the_tabs(self):
        at = app_with_step3_loaded(self)
        run_step4_tests(self, at)
        tabs = first_index(at, lambda n: getattr(n, 'type', '') == 'tab_container')
        load = first_index(at, lambda n: 'Step 3 load finished' in str(getattr(n, 'value', '')))
        test = first_index(at, lambda n: 'Step 4 tests finished' in str(getattr(n, 'value', '')))
        self.assertIsNotNone(load)
        self.assertIsNotNone(test)
        self.assertLess(load, tabs)
        self.assertLess(test, tabs)


class TestRunHistoryTests(unittest.TestCase):

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix='dm_unit_tests_')
        self._saved_root = uto.UNIT_TEST_ROOT
        uto.UNIT_TEST_ROOT = self.root
        # A File Library index of its own (other tests save Step 4 reports into the shared one),
        # inside the isolated temp folder so isolation.isolate_file_library() keeps it.
        import isolation
        isolation.isolate_file_library()
        self._saved_db = fsm.DB_PATH
        fsm.DB_PATH = os.path.join(fsm._apptest_tmp, f'step4_history_{self._testMethodName}.db')
        write_run(self.root, 'Account', '2026-09-01T10:00:00', passed=4, failed=1)
        write_run(self.root, 'Account', '2026-09-30T16:45:00', passed=5, failed=0)
        write_run(self.root, 'Contact', '2026-09-15T08:00:00', passed=2, failed=2)

    def tearDown(self):
        uto.UNIT_TEST_ROOT = self._saved_root
        fsm.DB_PATH = self._saved_db
        shutil.rmtree(self.root, ignore_errors=True)

    def reports(self, current_object='Account'):
        at = app_with_org()
        at.session_state['current_object'] = current_object
        at.sidebar.radio(key='nav_page').set_value(STEP4_PAGE).run()
        at.session_state['unit_testing_tabs'] = REPORTS_TAB   # only the open tab is drawn
        at.run()
        no_exceptions(self, at)
        return at

    def test_runs_are_listed_newest_first_with_latest_tag(self):
        at = self.reports()
        table = history_table(at)
        self.assertIsNotNone(table, "the run history table is shown")
        self.assertEqual(list(table['When']), ['2026-09-30 16:45:00', '2026-09-01 10:00:00'])
        self.assertIn('Latest', str(table.iloc[0, 0]))
        self.assertEqual(list(table['Pass rate']), ['100.0%', '80.0%'])

    def test_current_object_by_default_and_all_objects_on_request(self):
        at = self.reports()
        self.assertEqual(set(history_table(at)['Object']), {'Account'})
        at.selectbox(key='ut_hist_object').set_value('All objects').run()
        no_exceptions(self, at)
        self.assertEqual(set(history_table(at)['Object']), {'Account', 'Contact'})

    def test_one_run_is_opened_at_a_time_with_its_tests(self):
        at = self.reports()
        self.assertEqual(at.selectbox(key='ut_hist_run').index, 0, "the latest run is open first")
        detail = [d.value for d in at.dataframe if 'test_name' in list(d.value.columns)]
        self.assertEqual(len(detail), 1)
        self.assertEqual(len(detail[0]), 5)
        self.assertFalse([e.label for e in at.expander if 'Detailed Results' in e.label],
                         "no stack of identical per-run expanders")
        at.selectbox(key='ut_hist_run').set_value(at.selectbox(key='ut_hist_run').options[1]).run()
        detail = [d.value for d in at.dataframe if 'test_name' in list(d.value.columns)]
        self.assertIn('FAIL', set(detail[0]['status']))

    def test_loaded_records_reports_are_in_the_history(self):
        report = os.path.join(self.root, 'Account_step4_tests.xlsx')
        with open(report, 'wb') as f:
            f.write(b'xlsx')
        at = self.reports()
        fsm.register_output_file(report, org_name=ORG, object_name='Account', operation_type='unit_test',
                                 row_count=2, status='pass')
        at.run()
        table = history_table(at)
        self.assertIn('✅ Test Loaded Records', set(table['Kind']))
        self.assertIn('Latest', str(table.iloc[0, 0]), "the report just saved is the latest run")
        self.assertEqual(table.iloc[0]['Kind'], '✅ Test Loaded Records')

    def test_generated_files_are_for_the_chosen_object_newest_first(self):
        folder = os.path.join(self.root, ORG, 'Account')
        old = os.path.join(folder, 'unitTest_Account.xlsx')
        with open(old, 'wb') as f:
            f.write(b'old')
        past = time.time() - 3600
        os.utime(old, (past, past))
        at = self.reports()
        labels = [e.label for e in at.expander if 'Test Files' in e.label]
        self.assertEqual(len(labels), 1)
        self.assertIn('Account', labels[0])
        names = [str(m.value) for m in at.markdown if 'unitTest_Account.xlsx' in str(m.value)
                 or 'real_test_execution_Account' in str(m.value)]
        self.assertTrue(names and 'unitTest_Account.xlsx' in names[-1], "the oldest file is listed last")

    def test_no_runs_explains_itself(self):
        shutil.rmtree(os.path.join(self.root, ORG))
        at = self.reports(current_object='Lead')
        self.assertIsNone(history_table(at))
        self.assertTrue(any('No test runs' in str(i.value) for i in at.info))


if __name__ == '__main__':
    unittest.main()
