"""
Step 2 (Mapping & Validation) of the guided flow.

Run from the app folder:
    .venv\\Scripts\\python.exe -m unittest discover -s tests\\guided_flow -p "test_step2_validation.py" -v
"""
import logging
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from streamlit.testing.v1 import AppTest  # noqa: E402

from helpers import ORG, SQL_KEY, no_exceptions  # noqa: E402
from ui_components.navigation import STEP1_PAGE, STEP2_PAGE, STEP3_PAGE  # noqa: E402

APP = os.path.join(HERE, 'app_step2.py')
APP_PICKLIST = os.path.join(HERE, 'app_step2_picklist.py')   # + picklist mapping Banking -> Agriculture
FLOW_OPTION = "📦 Step 1 dataset"
# Source pickers the validation tabs used to draw; with a Step 1 dataset none may appear.
SOURCE_RADIO_KEYS = ('schema_validation_source', 'custom_validation_source', 'genai_data_source', 'enhanced_validation_source_choice')
VALIDATION_TABS = ('schema', 'enhanced', 'custom', 'sf_rules')


def new_app(timeout: int = 180, app: str = APP) -> AppTest:
    at = AppTest.from_file(app, default_timeout=timeout)
    at.run()
    return at


def app_on_step2(case, with_step1: bool, app: str = APP) -> AppTest:
    """Sidebar org + SQL selected; optionally Step 1 done (SQL source -> Account); on Step 2."""
    at = new_app(app=app)
    at.sidebar.selectbox(key='global_org_selector').set_value(ORG).run()
    at.sidebar.selectbox(key='global_source_selector').set_value(SQL_KEY).run()
    if not with_step1:
        at.sidebar.radio(key='nav_page').set_value(STEP2_PAGE).run()
        no_exceptions(case, at)
        return at
    at.sidebar.radio(key='nav_page').set_value(STEP1_PAGE).run()
    at.radio(key='step1_source').set_value("🗄️ SQL Server").run()
    at.selectbox(key='step1_sql_table').set_value('dbo.Accounts').run()
    at.button(key='step1_sql_run').click().run()
    at.selectbox(key='step1_target_object').set_value('Account').run()
    at.button(key='step1_confirm').click().run()
    no_exceptions(case, at)
    at.button(key='flow_next_1').click().run()
    no_exceptions(case, at)
    case.assertEqual(at.session_state['nav_page'], STEP2_PAGE)
    return at


SUMMARY_TAB = "📋 Validation Summary"


def open_tab(at, label):
    """Select a Step 2 tab (the browser does this when the user clicks a tab)."""
    at.session_state['step2_tabs'] = label
    at.run()


def keys_of(elements):
    return {getattr(e, 'key', None) for e in elements}


def assert_clean_page(case, at):
    """No exception (StreamlitAPIException, DuplicateWidgetID, ...) and no error text about them."""
    no_exceptions(case, at)
    texts = [str(w.value) for w in at.warning] + [str(e.value) for e in at.error]
    bad = [t for t in texts if 'DuplicateWidgetID' in t or 'StreamlitAPIException' in t
           or 'UnboundLocalError' in t or 'Traceback' in t]
    case.assertEqual(bad, [], f"Problems shown on the page: {bad}")


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__(level=logging.WARNING)
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage())


class Step2TestCase(unittest.TestCase):
    """Fails a test if Streamlit logged 'widget created with a default value but also had its
    value set via the Session State API' (it is only logged, never drawn on the page)."""

    def setUp(self):
        from streamlit.elements.lib import policies
        policies._shown_default_value_warning = False
        self._policy_log = _ListHandler()
        logging.getLogger('streamlit.elements.lib.policies').addHandler(self._policy_log)

    def tearDown(self):
        logging.getLogger('streamlit.elements.lib.policies').removeHandler(self._policy_log)
        misuse = [m for m in self._policy_log.messages if 'Session State API' in m]
        self.assertEqual(misuse, [], f"Session-state misuse: {misuse}")


class Step2GateTests(Step2TestCase):

    def test_step2_locked_without_step1(self):
        at = app_on_step2(self, with_step1=False)
        assert_clean_page(self, at)
        button_keys = keys_of(at.button)
        for suffix in VALIDATION_TABS:
            self.assertIn(f"flow_gate_2_1_{suffix}", button_keys, f"gate missing in the {suffix} tab")
        self.assertTrue(at.button(key='flow_next_2').disabled)
        # Tab bodies are skipped while locked.
        self.assertNotIn('schema_validation_source', keys_of(at.radio))
        # Summary / Saved Mappings still work (they only need the org); they run when opened.
        self.assertFalse(any('Validation History' in str(s.value) for s in at.subheader),
                         "hidden read-only tabs must not run")
        open_tab(at, SUMMARY_TAB)
        assert_clean_page(self, at)
        self.assertTrue(any('Validation History' in str(s.value) for s in at.subheader))

    def test_gate_button_goes_to_step1(self):
        at = app_on_step2(self, with_step1=False)
        at.button(key='flow_gate_2_1_schema').click().run()
        assert_clean_page(self, at)
        self.assertEqual(at.session_state['nav_page'], STEP1_PAGE)


class Step2SchemaTests(Step2TestCase):

    def test_schema_defaults_to_step1_dataset_and_publishes(self):
        at = app_on_step2(self, with_step1=True)
        assert_clean_page(self, at)
        dataset = at.session_state['flow_dataset']
        self.assertTrue(at.button(key='flow_next_2').disabled)

        self.assertNotIn('schema_validation_source', keys_of(at.radio))   # data comes from Step 1
        self.assertEqual(at.selectbox(key='schema_validation_object').value, 'Account')
        self.assertTrue(at.selectbox(key='schema_validation_object').disabled)
        self.assertEqual(len(at.session_state['schema_validation_data']), 3)
        self.assertEqual(at.selectbox(key='schema_mapping_0_AccountName').value.split(' (')[0], 'Name')
        self.assertEqual(at.selectbox(key='schema_mapping_2_Phone').value.split(' (')[0], 'Phone')
        self.assertEqual(at.selectbox(key='schema_mapping_3_Industry').value.split(' (')[0], 'Industry')

        at.button(key='schema_run_validation').click().run()
        assert_clean_page(self, at)
        result = at.session_state['flow_validation']
        self.assertEqual(result['method'], 'Schema Validation')
        self.assertEqual(result['object'], 'Account')
        self.assertEqual(result['dataset_id'], dataset['id'])
        self.assertGreater(result['summary']['valid'], 0)
        self.assertGreaterEqual(result['summary']['invalid'], 1)   # empty AccountName -> required Name
        self.assertEqual(result['field_mappings'].get('AccountName'), 'Name')
        # Contract: valid_df keeps SOURCE columns; apply_field_mappings gives Salesforce names.
        self.assertIn('AccountName', result['valid_df'].columns)
        self.assertNotIn('', list(result['valid_df']['AccountName']))
        from ui_components.data_operations import apply_field_mappings
        mapped = apply_field_mappings(result['valid_df'], result['field_mappings'])
        self.assertIn('Name', mapped.columns)
        self.assertIn('Validation_Errors', result['invalid_df'].columns)

        self.assertFalse(at.button(key='flow_next_2').disabled)
        at.button(key='flow_next_2').click().run()
        self.assertEqual(at.session_state['nav_page'], STEP3_PAGE)
        no_exceptions(self, at)

    def test_reset_mappings_overrides_widget_state(self):
        at = app_on_step2(self, with_step1=True)
        at.selectbox(key='schema_mapping_0_AccountName').set_value("⚠️ No mapping").run()
        self.assertEqual(at.selectbox(key='schema_mapping_0_AccountName').value, "⚠️ No mapping")
        at.button(key='schema_reset_mappings').click().run()
        assert_clean_page(self, at)
        self.assertEqual(at.selectbox(key='schema_mapping_0_AccountName').value.split(' (')[0], 'Name')

    def test_step2_uses_step1_data_without_asking_again(self):
        """No source picker, no query box, no new SQL query: Step 2 validates the Step 1 rows."""
        import fake_salesforce
        at = app_on_step2(self, with_step1=True)
        sql_queries = [q for q in fake_salesforce.QUERIES if isinstance(q, tuple) and q[0] == 'sql']
        radios = keys_of(at.radio)
        for key in SOURCE_RADIO_KEYS:
            self.assertNotIn(key, radios, key)
        self.assertNotIn('schema_validation_sql_query', keys_of(at.text_area))
        for key in ('schema_validation_object', 'custom_validation_object', 'enhanced_validation_object_selectbox'):
            box = at.selectbox(key=key)
            self.assertEqual(box.value, 'Account', key)
            self.assertTrue(box.disabled, f"{key} must be locked to the Step 1 target")
        self.assertEqual(len(at.session_state['schema_validation_data']), 3)
        self.assertEqual(len(at.session_state['enhanced_validation_data']), 3)
        self.assertTrue(any('Validating the Step 1 dataset' in str(m.value) for m in at.success))
        at.button(key='schema_run_validation').click().run()
        assert_clean_page(self, at)
        self.assertEqual([q for q in fake_salesforce.QUERIES if isinstance(q, tuple) and q[0] == 'sql'],
                         sql_queries, "Step 2 must not run the SQL query again")
        self.assertEqual(at.session_state['flow_validation']['dataset_id'], at.session_state['flow_dataset']['id'])


class Step2OtherMethodsTests(Step2TestCase):

    def test_enhanced_validation_checks_mapped_required_fields(self):
        """AccountName is mapped to the required Name field: the row with no name is invalid."""
        at = app_on_step2(self, with_step1=True)
        at.button(key='enhanced_start_validation').click().run()
        assert_clean_page(self, at)
        result = at.session_state['flow_validation']
        self.assertEqual(result['summary']['valid'], 2)
        self.assertEqual(result['summary']['invalid'], 1)
        self.assertEqual(result['summary']['required_failures'], 1)
        self.assertEqual(set(result['valid_df']['AccountName']), {'Initech', 'Umbrella'})
        self.assertIn('Required field Name is empty', result['invalid_df']['Data_Issue_Details'].iloc[0])

    def test_enhanced_validation_publishes(self):
        at = app_on_step2(self, with_step1=True)
        self.assertNotIn('enhanced_validation_source_choice', keys_of(at.radio))
        self.assertEqual(at.selectbox(key='enhanced_validation_object_selectbox').value, 'Account')
        at.button(key='enhanced_start_validation').click().run()
        assert_clean_page(self, at)
        result = at.session_state['flow_validation']
        self.assertEqual(result['method'], 'Enhanced Validation')
        self.assertEqual(result['dataset_id'], at.session_state['flow_dataset']['id'])
        self.assertEqual(result['summary']['total'], 3)
        self.assertGreater(result['summary']['valid'], 0)
        self.assertTrue(result['lookups_resolved'])   # Account in the fake has no mapped lookups
        self.assertEqual(result['field_mappings'].get('AccountName'), 'Name')
        self.assertNotIn('Transform_Status', result['valid_df'].columns)
        self.assertFalse(at.button(key='flow_next_2').disabled)
        # The nested quick actions work through their on_click callbacks.
        mapping_key = 'enhanced_field_mappings_Account'
        at.selectbox(key='mapping_Account_0_AccountName').set_value('AccountNumber').run()
        self.assertEqual(at.session_state[mapping_key].get('AccountName'), 'AccountNumber')
        at.button(key='enhanced_start_validation').click().run()
        at.button(key='restart_transformation').click().run()
        assert_clean_page(self, at)
        # State was reset: the grid is back on the auto-suggestion.
        self.assertEqual(at.selectbox(key='mapping_Account_0_AccountName').value, 'Name')
        self.assertEqual(at.session_state[mapping_key].get('AccountName'), 'Name')
        self.assertEqual(len(at.session_state['enhanced_validation_data']), 3)
        at.button(key='enhanced_start_validation').click().run()
        at.button(key='goto_data_loading').click().run()
        self.assertEqual(at.session_state['nav_page'], STEP3_PAGE)

    def test_step1_data_is_still_used_after_a_page_switch(self):
        at = app_on_step2(self, with_step1=True)
        at.sidebar.radio(key='nav_page').set_value("📊 Data Hub").run()
        at.sidebar.radio(key='nav_page').set_value(STEP2_PAGE).run()
        assert_clean_page(self, at)
        self.assertNotIn('schema_validation_source', keys_of(at.radio))
        self.assertEqual(len(at.session_state['schema_validation_data']), 3)
        self.assertEqual(at.selectbox(key='schema_validation_object').value, 'Account')

    def test_custom_validation_shows_results_and_publishes(self):
        at = app_on_step2(self, with_step1=True)
        self.assertEqual(at.selectbox(key='custom_validation_object').value, 'Account')
        at.text_input(key='custom_rule_name').input('Phone prefix')
        at.selectbox(key='custom_rule_field').set_value('Phone')
        at.radio(key='custom_rule_type').set_value('Pattern Match').run()
        at.text_input(key='custom_rule_pattern').input('^555000[12]').run()
        at.button(key='custom_add_rule').click().run()
        assert_clean_page(self, at)
        self.assertNotIn('custom_validation_source', keys_of(at.radio))
        at.button(key='custom_run_validation').click().run()
        assert_clean_page(self, at)
        self.assertFalse(any('Error in custom validation' in str(e.value) for e in at.error))
        result = at.session_state['flow_validation']
        self.assertEqual(result['method'], 'Custom Validation')
        self.assertEqual(result['dataset_id'], at.session_state['flow_dataset']['id'])
        self.assertEqual((result['summary']['valid'], result['summary']['invalid']), (2, 1))
        # The shared Step 2 mapping is published (AccountName -> Name from the Schema grid).
        self.assertEqual(result['field_mappings'], {'AccountName': 'Name', 'Phone': 'Phone', 'Industry': 'Industry'})



def stepper_texts(at):
    return [str(m.value) for m in at.markdown if 'STEP 2 ·' in str(m.value)]


class Step2ReviewFixTests(Step2TestCase):

    def test_schema_publishes_mapped_picklist_values(self):
        at = app_on_step2(self, with_step1=True, app=APP_PICKLIST)
        at.button(key='schema_run_validation').click().run()
        assert_clean_page(self, at)
        result = at.session_state['flow_validation']
        by_name = dict(zip(result['valid_df']['AccountName'], result['valid_df']['Industry']))
        # 'Banking' passed validation as 'Agriculture' (saved picklist mapping): publish that value.
        self.assertEqual(by_name.get('Umbrella'), 'Agriculture')
        self.assertEqual(by_name.get('Initech'), 'Energy')

    def test_stepper_updates_in_the_publishing_run(self):
        at = app_on_step2(self, with_step1=True)
        self.assertTrue(any('STEP 2 · 🟠 Current' in t for t in stepper_texts(at)))
        at.button(key='schema_run_validation').click().run()
        assert_clean_page(self, at)
        self.assertFalse(at.button(key='flow_next_2').disabled)
        texts = stepper_texts(at)
        self.assertEqual(len(texts), 1, texts)
        self.assertIn('STEP 2 · ✅ Done', texts[0])

    def test_enhanced_publishes_only_current_columns(self):
        at = app_on_step2(self, with_step1=True)
        mapping_key = 'enhanced_field_mappings_Account'
        stale = dict(at.session_state[mapping_key])
        stale['Old_Column'] = 'Description'
        at.session_state[mapping_key] = stale
        at.run()
        at.button(key='enhanced_start_validation').click().run()
        assert_clean_page(self, at)
        mappings = at.session_state['flow_validation']['field_mappings']
        self.assertNotIn('Old_Column', mappings)
        self.assertEqual(mappings.get('AccountName'), 'Name')


class Step2SharedMappingAndSpeedTests(Step2TestCase):

    def test_mapping_made_in_one_tab_is_used_by_the_others(self):
        at = app_on_step2(self, with_step1=True)
        phone_schema = at.selectbox(key='schema_mapping_2_Phone')
        phone_schema.set_value(next(o for o in phone_schema.options if o.startswith('AccountNumber'))).run()
        assert_clean_page(self, at)
        self.assertEqual(at.session_state['flow_field_mappings']['map'].get('Phone'), 'AccountNumber')
        at.run()   # the Enhanced grid follows on the next run
        self.assertEqual(at.selectbox(key='mapping_Account_2_Phone').value, 'AccountNumber')
        self.assertEqual(at.session_state['enhanced_field_mappings_Account'].get('Phone'), 'AccountNumber')
        at.button(key='enhanced_start_validation').click().run()
        assert_clean_page(self, at)
        self.assertEqual(at.session_state['flow_validation']['field_mappings'].get('Phone'), 'AccountNumber')
        # and back: a change in Enhanced reaches the Schema grid
        at.selectbox(key='mapping_Account_2_Phone').set_value('Phone').run()
        at.run()
        self.assertTrue(at.selectbox(key='schema_mapping_2_Phone').value.startswith('Phone'))

    def test_custom_rule_on_a_salesforce_field_uses_the_mapping(self):
        at = app_on_step2(self, with_step1=True)
        at.text_input(key='custom_rule_name').input('Name required')
        at.selectbox(key='custom_rule_field').set_value('Name')
        at.radio(key='custom_rule_type').set_value('Required Field').run()
        at.button(key='custom_add_rule').click().run()
        at.button(key='custom_run_validation').click().run()
        assert_clean_page(self, at)
        result = at.session_state['flow_validation']
        self.assertEqual((result['summary']['valid'], result['summary']['invalid']), (2, 1))
        self.assertIn('AccountName', result['valid_df'].columns)       # rows keep source names
        self.assertEqual(result['field_mappings'].get('AccountName'), 'Name')

    def test_enhanced_publishes_match_settings(self):
        at = app_on_step2(self, with_step1=True)
        at.button(key='enhanced_start_validation').click().run()
        assert_clean_page(self, at)
        match = at.session_state['flow_validation']['match']
        self.assertIn('strategy', match)
        self.assertIsInstance(match['fields'], list)

    def test_summary_reads_the_run_log_not_every_result_file(self):
        # The summary used to os.walk() every file under Validation/ (all orgs) and parse it;
        # it now reads one indexed table (test_step2_history.py covers what it shows).
        from unittest import mock
        from ui_components import validation_operations as vo
        at = app_on_step2(self, with_step1=True)
        with mock.patch.object(vo, 'get_validation_results', side_effect=AssertionError("file scan")), \
                mock.patch.object(vo, 'get_comprehensive_validation_summary', side_effect=AssertionError("file scan")):
            open_tab(at, SUMMARY_TAB)
        assert_clean_page(self, at)
        self.assertEqual(at.session_state['step2_tabs'], SUMMARY_TAB)

    def test_open_tab_is_remembered_across_page_switches(self):
        at = app_on_step2(self, with_step1=True)
        open_tab(at, SUMMARY_TAB)
        at.sidebar.radio(key='nav_page').set_value("📊 Data Hub").run()
        at.sidebar.radio(key='nav_page').set_value(STEP2_PAGE).run()
        assert_clean_page(self, at)
        self.assertEqual(at.session_state['step2_tabs'], SUMMARY_TAB)


class SalesforceIdCheckTests(unittest.TestCase):

    def test_structural_id_check(self):
        from ui_components.validation_operations import _is_salesforce_id
        self.assertTrue(_is_salesforce_id('001A0000006Vm9rIAC'))          # correct checksum
        self.assertTrue(_is_salesforce_id('001A0000006Vm9r'))
        self.assertFalse(_is_salesforce_id('001A0000006Vm9rAAA'))         # wrong checksum
        self.assertFalse(_is_salesforce_id('ACMECORPORATION'))            # 15 letters
        self.assertFalse(_is_salesforce_id('ACMECORPORATIONXYZ'))         # 18 letters
        self.assertFalse(_is_salesforce_id('CUST00000012345', {'001'}))   # wrong key prefix
        self.assertTrue(_is_salesforce_id('001A0000006Vm9rIAC', {'001'}))


if __name__ == '__main__':
    unittest.main()
