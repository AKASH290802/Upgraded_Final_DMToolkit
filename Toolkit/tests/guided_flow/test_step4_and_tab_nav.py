"""
Step 4 (Unit Testing) as the last step of the migration cycle, and the
Previous / Next buttons between the (optional) tabs of a page.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p test_step4_and_tab_nav.py -v
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from helpers import ORG, no_exceptions  # noqa: E402
from test_step3_data_operations import (  # noqa: E402
    STEP2_RESULT, app_with_step2_done, button_keys, configure_insert, goto, new_app,
)
from ui_components import step1_data_loading, step4_verification as sv  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE, STEP4_PAGE  # noqa: E402

ENHANCED_TAB = "⚡ Enhanced Validation"
GENERATE_TAB = "🔧 Generate Tests"


def texts(elements):
    return ' | '.join(str(e.value) for e in elements)


def raw(at, kind):
    """Text of elements AppTest has no class for (progress bars, st.html)."""
    return ' | '.join(str(getattr(e, 'proto', '')) for e in at.get(kind))


def app_with_org():
    at = new_app()
    at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
    return at


def app_with_step3_loaded(case):
    """Steps 1-2 as in the Step 3 tests, then an Insert of the 2 valid rows; opens Step 4 with Next."""
    at = app_with_step2_done(case, _test_persist_sf=True)
    configure_insert(at)
    at.button(key='sf_load_start').click().run()
    no_exceptions(case, at)
    load = at.session_state['flow_load_result']
    case.assertEqual(load['success'], 2)
    at.button(key='flow_next_3').click().run()
    no_exceptions(case, at)
    case.assertEqual(at.session_state['nav_page'], STEP4_PAGE)
    return at


def run_step4_tests(case, at):
    at.button(key='step4_run_tests').click().run()
    no_exceptions(case, at)
    return at.session_state['flow_test_result']


def checks_by_name(result):
    return {c['check']: c for c in result['checks']}


def overlay(at):
    return at.session_state['_test_sf_overlay']['Account']


class TabNavigationTests(unittest.TestCase):

    def test_step2_tabs_have_previous_and_next_buttons(self):
        at = app_with_org()
        goto(at, STEP2_PAGE)
        no_exceptions(self, at)
        keys = button_keys(at)
        self.assertIn('step2_tabnav_next', keys)
        self.assertNotIn('step2_tabnav_prev', keys, "the first tab has no Previous")
        self.assertEqual(at.button(key='step2_tabnav_next').label, f"Next: {ENHANCED_TAB} ➡️")
        self.assertFalse(at.button(key='step2_tabnav_next').disabled, "the tabs are optional")
        at.button(key='step2_tabnav_next').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['step2_tabs'], ENHANCED_TAB)
        self.assertIn('dm-tab-scroll', raw(at, 'html'), "the page scrolls back up to the tabs")
        at.button(key='step2_tabnav_prev').click().run()
        self.assertEqual(at.session_state['step2_tabs'], "🔍 Schema Validation")
        # The step Next stays next to them (disabled until a validation is done).
        self.assertTrue(at.button(key='flow_next_2').disabled)

    def test_last_step2_tab_has_no_next_tab(self):
        at = app_with_org()
        goto(at, STEP2_PAGE)
        at.session_state['step2_tabs'] = "💾 Saved Mappings"
        at.run()
        no_exceptions(self, at)
        self.assertNotIn('step2_tabnav_next', button_keys(at))
        self.assertIn('step2_tabnav_prev', button_keys(at))

    def test_step2_next_step_is_enabled_from_any_tab_once_validated(self):
        at = app_with_step2_done(self)
        goto(at, STEP2_PAGE)
        at.session_state['step2_tabs'] = ENHANCED_TAB
        at.run()
        no_exceptions(self, at)
        self.assertFalse(at.button(key='flow_next_2').disabled)
        self.assertIn('step2_tabnav_next', button_keys(at))

    def test_step3_and_step4_tabs(self):
        at = app_with_org()
        goto(at, STEP3_PAGE)
        at.button(key='step3_tabnav_next').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['data_ops_active_tab'], 1)
        at.button(key='step3_tabnav_prev').click().run()
        self.assertEqual(at.session_state['data_ops_active_tab'], 0)
        goto(at, STEP4_PAGE)
        at.button(key='step4_tabnav_next').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['unit_testing_tabs'], GENERATE_TAB)
        self.assertIsNotNone(at.selectbox(key='unit_test_object'), "the Generate tab is drawn")

    def test_mapping_page_tabs(self):
        at = app_with_org()
        goto(at, "🗺️ Mapping")
        no_exceptions(self, at)
        at.button(key='mapping_tabnav_next').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['mapping_tabs'], "📋 Picklist Mappings")


class Step4GateTests(unittest.TestCase):

    def test_four_steps_and_step4_is_locked_until_step3(self):
        at = app_with_org()
        goto(at, STEP4_PAGE)
        no_exceptions(self, at)
        self.assertEqual(at.title[0].value, "🧪 Step 4 · Unit Testing")
        self.assertIn('0 of 4 steps', raw(at, 'progress'))
        keys = button_keys(at)
        self.assertTrue(any(k and k.startswith('flow_gate_4_') for k in keys), keys)
        self.assertNotIn('step4_run_tests', keys)
        self.assertIn('flow_back_4', keys)
        self.assertTrue(at.button(key='flow_next_4').disabled)
        # The standalone tools still work.
        at.session_state['unit_testing_tabs'] = GENERATE_TAB
        at.run()
        no_exceptions(self, at)
        self.assertIsNotNone(at.selectbox(key='unit_test_object'))


class Step4SalesforceTests(unittest.TestCase):

    def test_step3_hands_the_loaded_records_to_step4(self):
        at = app_with_step3_loaded(self)
        details = at.session_state['flow_load_result']['details']
        self.assertEqual(len(details['record_ids']), 2)
        self.assertEqual(details['created'], [True, True])
        self.assertEqual(sorted(details['row_positions']), [0, 1])
        self.assertEqual(set(details['expected']['Name']), {'Initech', 'Umbrella'})
        self.assertEqual(details['match']['fields'], ['External_Key__c'])
        self.assertEqual(at.session_state['flow_load_result']['total'], 2)
        # Step 4 opens with its first tab and the object Step 3 loaded pre-selected in Generate.
        self.assertIn('step4_run_tests', button_keys(at))
        at.session_state['unit_testing_tabs'] = GENERATE_TAB
        at.run()
        self.assertEqual(at.selectbox(key='unit_test_object').value, 'Account')

    def test_all_checks_pass_and_the_cycle_completes(self):
        at = app_with_step3_loaded(self)
        self.assertTrue(at.button(key='flow_next_4').disabled)
        result = run_step4_tests(self, at)
        checks = checks_by_name(result)
        self.assertEqual(result['failed'], 0, result['checks'])
        self.assertEqual(result['verified'], 2)
        for name in ("Step 3 counts add up", "Loaded records exist in Account", "Field values match what was loaded",
                     "Records were written by this load", "One record per match key (no duplicates)"):
            self.assertEqual(checks[name]['status'], 'PASS', checks[name])
        self.assertFalse(at.button(key='flow_next_4').disabled)
        self.assertEqual(at.button(key='flow_next_4').label, "🔁 Start a new migration")
        self.assertIn('Migration cycle complete', texts(at.success))
        self.assertIn('4 of 4 steps', raw(at, 'progress'))
        self.assertTrue(os.path.exists(result['details']['report_path']), "the report is saved")
        self.assertIn('step4_dl_report', {d.key for d in at.get('download_button')})

    def test_a_changed_value_fails_and_is_listed(self):
        at = app_with_step3_loaded(self)
        records = overlay(at)
        first = next(iter(records))
        records[first]['Phone'] = 'CHANGED'
        result = run_step4_tests(self, at)
        checks = checks_by_name(result)
        self.assertEqual(checks["Field values match what was loaded"]['status'], 'FAIL')
        self.assertIn('Phone', checks["Field values match what was loaded"]['detail'])
        diffs = result['details']['mismatches']
        self.assertEqual(list(diffs['Field']), ['Phone'])
        self.assertEqual(list(diffs['In Salesforce']), ['CHANGED'])
        self.assertEqual(result['verified'], 1)
        # Step 4 is finished, with issues: the stepper and the footer say so.
        self.assertIn('some checks failed', texts(at.markdown))
        self.assertIn('finished with 1 failed check', texts(at.warning))

    def test_a_missing_record_fails(self):
        at = app_with_step3_loaded(self)
        records = overlay(at)
        del records[next(iter(records))]
        result = run_step4_tests(self, at)
        self.assertEqual(checks_by_name(result)["Loaded records exist in Account"]['status'], 'FAIL')
        self.assertEqual(len(result['details']['missing_ids']), 1)

    def test_a_duplicate_match_key_fails(self):
        at = app_with_step3_loaded(self)
        overlay(at)['001DUPLICATE00001'] = {'Id': '001DUPLICATE00001', 'Name': 'Initech copy',
                                            'External_Key__c': 'Initech'}
        result = run_step4_tests(self, at)
        dup = checks_by_name(result)["One record per match key (no duplicates)"]
        self.assertEqual(dup['status'], 'FAIL', dup)
        self.assertEqual(int(result['details']['duplicates']['Records'].iloc[0]), 2)

    def test_a_new_validation_relocks_step4(self):
        at = app_with_step3_loaded(self)
        run_step4_tests(self, at)
        at.session_state['_test_publish_validation'] = dict(STEP2_RESULT)
        at.run()
        no_exceptions(self, at)
        self.assertFalse('flow_test_result' in at.session_state, 'flow_test_result')
        self.assertFalse('flow_load_result' in at.session_state, 'flow_load_result')

    def test_start_a_new_migration(self):
        at = app_with_step3_loaded(self)
        run_step4_tests(self, at)
        at.button(key='flow_next_4').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP1_PAGE)
        for key in ('flow_dataset', 'flow_validation', 'flow_load_result', 'flow_test_result', 'step1_staged'):
            self.assertFalse(key in at.session_state, key)
        self.assertIn('New migration started', texts(at.info))
        self.assertEqual(at.session_state['current_org'], ORG, "the connections stay")
        # Step 1 starts empty (the old table/query would load the previous data again); the source kind stays.
        # (assertFalse with the key only: a failing assertIn would print the whole session, credentials too.)
        self.assertEqual(at.radio(key='step1_source').value, "🗄️ SQL Server")
        self.assertEqual(at.selectbox(key='step1_sql_table').value, step1_data_loading.NO_TABLE)
        self.assertEqual(at.text_area(key='step1_sql_query').value, "")
        self.assertFalse('step1_staged' in at.session_state and at.session_state['step1_staged'], 'step1_staged')

    def test_footer_next_to_reports_scrolls_to_the_step4_tabs(self):
        at = app_with_org()
        goto(at, STEP4_PAGE)
        at.session_state['unit_testing_tabs'] = "🏃 Execute Tests"
        at.run()
        at.button(key='step4_tabnav_next').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['unit_testing_tabs'], "📊 Test Reports")
        scripts = raw(at, 'html')
        self.assertIn('dm-tab-scroll', scripts)
        self.assertNotIn('[data-testid=\\"stTabs\\"] [data-testid=\\"stTabs\\"]', scripts,
                         "the inner Reports tabs must not take the Step 4 scroll")


class Step3AccountingTests(unittest.TestCase):
    """Every row sent to a Salesforce load ends up loaded, failed or skipped (Step 4 reconciles them)."""

    def setUp(self):
        import isolation
        import pandas as pd
        import streamlit as st
        import fake_salesforce
        from ui_components import data_operations
        isolation.isolate_file_library()
        self.st, self.pd, self.fake, self.ops = st, pd, fake_salesforce, data_operations
        self.saved_records = list(fake_salesforce.RECORDS['Account'])
        for key in ('flow_load_result', 'flow_validation'):
            st.session_state.pop(key, None)
        st.session_state.setdefault('processing_status', {})

    def tearDown(self):
        self.fake.RECORDS['Account'] = self.saved_records
        for key in ('insert_matching_strategy', 'insert_match_fields', 'insert_target_field', 'flow_load_result'):
            self.st.session_state.pop(key, None)

    def test_insert_batch_with_a_duplicate_counts_every_row(self):
        # A record created after the pre-check: the batch's uniqueness check finds it.
        self.fake.RECORDS['Account'] = self.saved_records + [
            {'Id': '001EXISTING000001', 'Name': 'Old', 'External_Key__c': 'Initech'}]
        state = self.st.session_state
        state.insert_matching_strategy = 'external_id'
        state.insert_match_fields = ['External_Key__c']
        state.insert_target_field = 'External_Key__c'
        df = self.pd.DataFrame({'Name': ['Initech', 'Umbrella'], 'External_Key__c': ['Initech', 'Umbrella']})
        sf = self.fake.FakeSalesforce(username='u')
        self.ops.load_data_to_salesforce(sf, df, 'Account', 'Insert', 200, 1, field_mappings={},
                                         skip_lookup_resolution=True)
        load = state.flow_load_result
        self.assertEqual(load['success'], 0)
        self.assertEqual(load['skipped'], 2, "the duplicate AND the unique row of the stopped batch")
        self.assertEqual(load['success'] + load['failed'] + load['skipped'], load['total'])


class Step4SqlServerTests(unittest.TestCase):

    def _loaded(self):
        at = app_with_step2_done(self)
        at.selectbox(key='load_destination').set_value('SQL Server').run()
        at.selectbox(key='sql_load_mode').set_value('Replace Existing').run()
        at.button(key='sql_load_start').click().run()
        no_exceptions(self, at)
        self.assertEqual(at.session_state['flow_load_result']['details']['table'], 'Account')
        goto(at, STEP4_PAGE)
        return at

    def test_sql_load_is_tested_against_the_table(self):
        at = self._loaded()
        result = run_step4_tests(self, at)
        checks = checks_by_name(result)
        self.assertEqual(result['failed'], 0, result['checks'])
        self.assertEqual(checks["Table holds the loaded rows"]['status'], 'PASS')
        self.assertEqual(checks["Row count"]['status'], 'PASS')
        self.assertEqual(result['verified'], 2)

    def test_a_changed_row_in_the_table_fails(self):
        at = self._loaded()
        tables = at.session_state['_test_sql_tables']
        tables['dbo.Account'].loc[0, 'Phone'] = 'CHANGED'
        result = run_step4_tests(self, at)
        self.assertEqual(checks_by_name(result)["Table holds the loaded rows"]['status'], 'FAIL')
        self.assertFalse(result['details']['mismatches'].empty)


class ValueComparisonTests(unittest.TestCase):

    def test_types(self):
        self.assertTrue(sv.values_match(None, False, 'boolean'), "a blank checkbox is stored unchecked")
        self.assertTrue(sv.values_match('yes', True, 'boolean'))
        self.assertTrue(sv.values_match('10.004', 10.0, 'currency', 2))
        self.assertFalse(sv.values_match('10.01', 10.0, 'currency', 2))
        self.assertTrue(sv.values_match('7', 7.0, 'int'))
        self.assertTrue(sv.values_match('2024-01-15', '2024-01-15', 'date'))
        self.assertTrue(sv.values_match('2024-01-15T10:00:00', '2024-01-15T10:00:00.000+0000', 'datetime'))
        self.assertFalse(sv.values_match('2024-01-15T10:00:00', '2024-01-15T11:00:00.000+0000', 'datetime'))
        self.assertTrue(sv.values_match('001000000000001', '001000000000001AAA', 'reference'))
        self.assertTrue(sv.values_match('B;A', 'A;B', 'multipicklist'))
        self.assertTrue(sv.values_match(' Acme\r\nLtd ', 'Acme\nLtd', 'string'))
        self.assertTrue(sv.values_match('', None, 'string'))
        self.assertFalse(sv.values_match('Acme', 'acme', 'string'))

    def test_sample_is_evenly_spread(self):
        positions = sv._sample_positions(10000, 'sample')
        self.assertEqual(len(positions), sv.SAMPLE_SIZE)
        self.assertEqual(positions[0], 0)
        self.assertGreater(positions[-1], 9900)
        self.assertEqual(sv._sample_positions(10000, 'all'), list(range(10000)))


if __name__ == '__main__':
    unittest.main()
