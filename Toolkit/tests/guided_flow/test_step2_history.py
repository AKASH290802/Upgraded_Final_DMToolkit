"""
Step 2: the current result comes first; earlier runs are an ordered history.

* "📋 Latest validation result" is drawn ABOVE the tabs (it used to be below all of
  them, so after a run the user had to scroll to the end of the page).
* Every validation run is recorded (file_store_manager.validation_runs) and the
  📋 Validation Summary tab lists the runs newest first, for the sidebar org and the
  current object, the newest tagged Latest.
* Download buttons do not rerun the page (a rerun cleared the result on screen).

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_step2_history.py -v
"""
import glob
import os
import re
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG  # noqa: E402
from test_step2_validation import SUMMARY_TAB, Step2TestCase, app_on_step2, assert_clean_page, open_tab  # noqa: E402
from ui_components import file_store_manager as fsm  # noqa: E402


def walk(node):
    yield node
    for child in getattr(node, 'children', {}).values():
        yield from walk(child)


def first_index(at, predicate):
    for i, node in enumerate(walk(at.main)):
        if predicate(node):
            return i
    return None


def run_schema(case, at):
    at.button(key='schema_run_validation').click().run()
    assert_clean_page(case, at)


def history_table(at):
    tables = [d for d in at.dataframe if 'Pass rate' in list(d.value.columns)]
    return tables[0].value if tables else None


class LatestResultFirstTests(Step2TestCase):

    def test_latest_result_card_is_above_the_tabs(self):
        at = app_on_step2(self, with_step1=True)
        run_schema(self, at)
        card = first_index(at, lambda n: getattr(n, 'type', '') == 'markdown'
                           and 'Latest validation result' in str(getattr(n, 'value', '')))
        tabs = first_index(at, lambda n: getattr(n, 'type', '') == 'tab_container')
        self.assertIsNotNone(card, "the latest-result card is shown")
        self.assertLess(card, tabs, "the latest result comes before the tabs")

    def test_card_shows_the_run_made_in_this_very_rerun(self):
        at = app_on_step2(self, with_step1=True)
        run_schema(self, at)
        cards = [m.value for m in at.markdown if 'Latest validation result' in str(m.value)]
        self.assertEqual(len(cards), 1)
        self.assertIn('Schema Validation', cards[0])


class RunHistoryTests(Step2TestCase):

    def test_every_run_is_recorded(self):
        at = app_on_step2(self, with_step1=True)
        run_schema(self, at)
        run_schema(self, at)
        runs = fsm.list_validation_runs(org_name=ORG, object_name='Account')
        self.assertGreaterEqual(len(runs), 2)
        latest = runs[0]
        self.assertEqual(latest['method'], 'Schema Validation')
        self.assertEqual(latest['total'], latest['valid'] + latest['invalid'])
        self.assertGreater(latest['total'], 0)

    def test_summary_lists_runs_newest_first_with_latest_tag(self):
        at = app_on_step2(self, with_step1=True)
        fsm.save_validation_run(org_name=ORG, object_name='Account', method='Enhanced Validation',
                                total=10, valid=7, invalid=3, mapped_fields=4, source='old run',
                                created_at='2020-01-01T09:00:00')
        run_schema(self, at)
        open_tab(at, SUMMARY_TAB)
        assert_clean_page(self, at)
        table = history_table(at)
        self.assertIsNotNone(table, "run history table is shown")
        when = list(table['When'])
        self.assertEqual(when, sorted(when, reverse=True), "newest first")
        self.assertIn('Latest', str(table.iloc[0, 0]))
        self.assertEqual(table.iloc[0]['Type'], 'Schema Validation')
        self.assertEqual(table.iloc[-1]['Type'], 'Enhanced Validation')
        self.assertEqual(table.iloc[-1]['Pass rate'], '70.0%')

    def test_summary_shows_the_current_object_by_default(self):
        at = app_on_step2(self, with_step1=True)
        fsm.save_validation_run(org_name=ORG, object_name='Contact', method='Schema Validation',
                                total=5, valid=5, invalid=0, mapped_fields=2, source='other object')
        run_schema(self, at)
        open_tab(at, SUMMARY_TAB)
        self.assertEqual(set(history_table(at)['Object']), {'Account'})
        at.selectbox(key='val_hist_object').set_value('All objects').run()
        self.assertEqual(set(history_table(at)['Object']), {'Account', 'Contact'})

    def test_other_orgs_never_appear(self):
        at = app_on_step2(self, with_step1=True)
        fsm.save_validation_run(org_name='SomeOtherOrg', object_name='Account', method='Schema Validation',
                                total=1, valid=1, invalid=0, mapped_fields=1, source='x')
        run_schema(self, at)
        open_tab(at, SUMMARY_TAB)
        at.selectbox(key='val_hist_object').set_value('All objects').run()
        self.assertNotIn('x', set(history_table(at)['Source']))

    def test_selecting_a_run_shows_its_details(self):
        at = app_on_step2(self, with_step1=True)
        run_schema(self, at)
        open_tab(at, SUMMARY_TAB)
        assert_clean_page(self, at)
        picker = at.selectbox(key='val_hist_run')
        self.assertEqual(picker.index, 0, "the latest run is selected first")
        labels = [m.label for m in at.metric]
        self.assertIn('✅ Valid', labels)
        self.assertIn('Pass rate', labels)

    def test_empty_history_explains_itself(self):
        at = app_on_step2(self, with_step1=False)
        # Other tests share the isolated DB; this one needs an empty one (still inside the
        # isolated temp folder, so isolation.isolate_file_library leaves it in place).
        saved_db = fsm.DB_PATH
        fsm.DB_PATH = os.path.join(fsm._apptest_tmp, 'empty_history.db')
        try:
            open_tab(at, SUMMARY_TAB)
            assert_clean_page(self, at)
            self.assertIsNone(history_table(at))
            self.assertTrue(any('No validation runs' in str(i.value) for i in at.info))
        finally:
            fsm.DB_PATH = saved_db


class SfRulesResultFirstTests(unittest.TestCase):
    """The SF Validation Rules result needs a generated AI bundle to reach in AppTest, so the
    order is checked in the source: the slot is created before Step 1 and the result fills it."""

    def test_result_slot_is_above_the_steps_and_receives_the_result(self):
        import inspect
        from ui_components import validation_operations as vo
        src = inspect.getsource(vo.show_genai_validation)
        slot = src.index('genai_results_slot = st.empty()')
        self.assertLess(slot, src.index('Step 1: Extract Validation Rule Formulas'))
        fill = src.index('with genai_results_slot.container():')
        self.assertLess(fill, src.index('display_genai_validation_results(', fill))
        self.assertEqual(src.count('display_genai_validation_results('), 1)


class DownloadButtonTests(unittest.TestCase):

    def test_download_buttons_do_not_rerun_the_page(self):
        import ast
        offenders = []
        for name in ('validation_operations.py', 'unit_testing_operations.py', 'step4_verification.py'):
            with open(os.path.join(ROOT, 'ui_components', name), encoding='utf-8') as f:
                tree = ast.parse(f.read())
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr == 'download_button'
                        and not any(k.arg == 'on_click' for k in node.keywords)):
                    offenders.append(f"{name}:{node.lineno}")
        self.assertEqual(offenders, [])


class ResultFilesRegisteredTests(Step2TestCase):

    def test_schema_complete_results_file_is_in_the_file_library(self):
        at = app_on_step2(self, with_step1=True)
        at.session_state['_test_keep_file_registration'] = True   # app_step2.py turns indexing off otherwise
        run_schema(self, at)
        names = [f['original_name'] for f in fsm.list_output_files(org_name=ORG)]
        self.assertTrue(any('schema_validation_complete_results' in n for n in names), names)


if __name__ == '__main__':
    unittest.main()
